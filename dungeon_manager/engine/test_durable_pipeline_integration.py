import json
import threading
from datetime import datetime, timezone

from .audited_pipeline import (
    AuditIntegrationStatus,
    AuditedCommandPipeline,
    EventPublicationDisposition,
    ProjectionDisposition,
)
from .automation import (
    AutomationMode,
    AutomationPolicy,
    CapabilityAutomationRule,
)
from .command import CommandProvenance, CommandSource, GameCommand
from .durable_journal import (
    DurableJournalBinding,
    DurableJournalHealthReason,
    DurableJournalHealthStatus,
    DurablePublicationStatus,
    EventJournalStoreResult,
    EventJournalStoreStatus,
)
from .event_journal_store import EventJournalStore
from .game_engine import GameEngine
from .game_event import GameEvent
from .journals import CommandAuditJournal, GameEventJournal, GameEventJournalEntry
from .policy_gated_dispatcher import PolicyGatedCommandDispatcher
from .result import GameResult
from .startup_hydration import StartupHydrationStatus, hydrate_durable_runtime
from .world_state import WorldState, WorldStateProjector
from .world_state_holder import WorldStateHolder, WorldStateSynchronizationStatus
from .world_state_recovery import WorldStateRecoveryStatus, WorldStateRecoveryStrategy


COMMAND_TYPE = "test.durable_publication"
EVENT_TYPE = "test.durable_value"
JOURNAL_ID = "durable-pipeline-journal"
FIXED_UTC = datetime(2026, 7, 22, 13, 45, 12, 654321, timezone.utc)
PROVENANCE = CommandProvenance(CommandSource.SYSTEM, "durable-pipeline-test")


def command(number=1, *, command_id=None):
    return GameCommand(
        command_id=command_id or f"durable-command-{number}",
        command_type=COMMAND_TYPE,
        payload={"value": number},
        provenance=PROVENANCE,
    )


def event_for(item, number=None, *, event_id=None):
    value = item.payload["value"] if number is None else number
    return GameEvent(
        event_id=event_id or f"durable-event-{item.command_id}-{value}",
        event_type=EVENT_TYPE,
        schema_version=1,
        payload={"value": value, "private": f"payload-secret-{value}"},
        provenance=item.provenance,
        originating_command_id=item.command_id,
        occurred_at=FIXED_UTC,
    )


def reducer(state_data, item):
    return {"values": [*state_data.get("values", ()), item.payload["value"]]}


def projector_with(selected_reducer=reducer):
    projector = WorldStateProjector()
    projector.register_reducer(EVENT_TYPE, 1, selected_reducer)
    return projector


def initialize_and_hydrate(tmp_path, *, projector=None, count=0):
    store = EventJournalStore(tmp_path / "durable.sqlite")
    assert store.initialize(journal_id=JOURNAL_ID).status is EventJournalStoreStatus.SUCCESS
    if count:
        seed_entries = tuple(
            GameEventJournalEntry(
                index,
                event_for(
                    command(index, command_id=f"seed-command-{index}"),
                    event_id=f"seed-event-{index}",
                ),
            )
            for index in range(1, count + 1)
        )
        assert store.append(seed_entries, expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS
    selected_projector = projector_with() if projector is None else projector
    hydrated = hydrate_durable_runtime(
        store,
        expected_journal_id=JOURNAL_ID,
        base_state=WorldState({"values": []}),
        projector=selected_projector,
    )
    assert hydrated.status is StartupHydrationStatus.SUCCESS
    return store, hydrated.runtime, selected_projector


def build_pipeline(runtime, projector, handler, *, binding=None):
    calls = []
    engine = GameEngine()

    def tracked(item):
        calls.append(item.command_id)
        return handler(item)

    engine.register_handler(COMMAND_TYPE, tracked)
    dispatcher = PolicyGatedCommandDispatcher(
        AutomationPolicy(
            capabilities={
                COMMAND_TYPE: CapabilityAutomationRule(
                    default_mode=AutomationMode.AUTOMATIC
                )
            }
        ),
        engine,
    )
    pipeline = AuditedCommandPipeline(
        dispatcher,
        CommandAuditJournal(),
        runtime.event_journal,
        projector,
        runtime.state_holder,
        durable_journal_binding=(
            runtime.durable_binding if binding is None else binding
        ),
    )
    return pipeline, calls


class RecordingAppender:
    def __init__(self, store, journal):
        self.store = store
        self.journal = journal
        self.calls = []
        self.visible_snapshots = []

    def append(self, entries, *, expected_tail_sequence, expected_journal_id):
        self.calls.append((entries, expected_tail_sequence, expected_journal_id))
        self.visible_snapshots.append(self.journal.entries)
        return self.store.append(
            entries,
            expected_tail_sequence=expected_tail_sequence,
            expected_journal_id=expected_journal_id,
        )


class RejectingAppender:
    def __init__(self, status=EventJournalStoreStatus.INVALID_INPUT):
        self.status = status
        self.calls = 0

    def append(self, entries, *, expected_tail_sequence, expected_journal_id):
        self.calls += 1
        return EventJournalStoreResult(
            status=self.status,
            journal_id=expected_journal_id,
            previous_tail=expected_tail_sequence,
            tail_sequence=expected_tail_sequence,
            reason_code="controlled_rejection",
            error="The durable append was rejected.",
        )


class RaisingAppender:
    def __init__(self):
        self.calls = 0

    def append(self, entries, *, expected_tail_sequence, expected_journal_id):
        self.calls += 1
        raise RuntimeError("raw sqlite path credential secret")


class MismatchedSuccessAppender:
    def __init__(self):
        self.calls = 0

    def append(self, entries, *, expected_tail_sequence, expected_journal_id):
        self.calls += 1
        return EventJournalStoreResult(
            status=EventJournalStoreStatus.SUCCESS,
            journal_id=expected_journal_id,
            previous_tail=expected_tail_sequence,
            tail_sequence=expected_tail_sequence,
            appended_count=0,
        )


class FailingPreparedAppendJournal(GameEventJournal):
    def append_prepared_batch(self, entries, *, expected_tail_sequence):
        raise RuntimeError("raw local journal secret")


class InvalidLaterPreparationJournal(GameEventJournal):
    def prepare_batch(self, events, *, expected_tail_sequence):
        prepared = super().prepare_batch(
            events,
            expected_tail_sequence=expected_tail_sequence,
        )
        return (
            prepared[0],
            GameEventJournalEntry(prepared[1].sequence + 1, prepared[1].event),
        )


def test_durable_multi_event_publication_commits_exact_batch_before_visibility(tmp_path):
    store, runtime, projector = initialize_and_hydrate(tmp_path)
    recording = RecordingAppender(store, runtime.event_journal)
    binding = DurableJournalBinding(recording, JOURNAL_ID, 0)
    item = command(7)
    produced = (event_for(item, 7), event_for(item, 8))
    pipeline, calls = build_pipeline(
        runtime,
        projector,
        lambda received: GameResult.success(received.command_id, events=produced),
        binding=binding,
    )

    result = pipeline.dispatch(item)

    assert result.audit_status is AuditIntegrationStatus.COMPLETED
    assert result.publication_disposition is EventPublicationDisposition.PUBLISHED
    assert result.projection_disposition is ProjectionDisposition.PROJECTED
    assert result.durable_publication.status is DurablePublicationStatus.COMMITTED_SYNCHRONIZED
    assert result.durable_publication.durable_commit_confirmed
    assert result.durable_publication.previous_tail == 0
    assert result.durable_publication.resulting_tail == 2
    assert result.durable_publication.appended_count == 2
    assert recording.visible_snapshots == [()]
    assert len(recording.calls) == 1
    prepared = recording.calls[0][0]
    assert all(actual is exact for actual, exact in zip(runtime.event_journal.entries, prepared))
    assert tuple(entry.event for entry in runtime.event_journal.entries) == produced
    assert [entry.to_dict() for entry in store.load().entries] == [
        entry.to_dict() for entry in runtime.event_journal.entries
    ]
    assert runtime.state_holder.snapshot.to_dict() == {
        "data": {"values": [7, 8]},
        "last_sequence": 2,
    }
    assert calls == [item.command_id]
    serialized = json.dumps(result.to_dict(), sort_keys=True)
    assert "payload-secret" not in serialized
    assert '"payload"' not in serialized
    assert '"data"' not in serialized
    assert "durable.sqlite" not in serialized
    assert "payload-secret" not in json.dumps(
        pipeline._audit_journal.to_list(),
        sort_keys=True,
    )


def test_eventless_success_performs_no_durable_write(tmp_path):
    store, runtime, projector = initialize_and_hydrate(tmp_path)
    recording = RecordingAppender(store, runtime.event_journal)
    binding = DurableJournalBinding(recording, JOURNAL_ID, 0)
    pipeline, _ = build_pipeline(
        runtime,
        projector,
        lambda received: GameResult.success(received.command_id),
        binding=binding,
    )

    result = pipeline.dispatch(command())

    assert result.durable_publication.status is DurablePublicationStatus.NO_EVENTS
    assert recording.calls == []
    assert store.load().tail_sequence == 0
    assert runtime.event_journal.entries == ()
    assert runtime.state_holder.snapshot.last_sequence == 0


def test_controlled_store_rejection_leaves_runtime_unchanged_without_retry(tmp_path):
    _, runtime, projector = initialize_and_hydrate(tmp_path)
    rejecting = RejectingAppender()
    binding = DurableJournalBinding(rejecting, JOURNAL_ID, 0)
    pipeline, calls = build_pipeline(
        runtime,
        projector,
        lambda item: GameResult.success(item.command_id, events=(event_for(item),)),
        binding=binding,
    )

    result = pipeline.dispatch(command())

    assert result.durable_publication.status is DurablePublicationStatus.NOT_COMMITTED
    assert not result.durable_publication.durable_commit_confirmed
    assert runtime.event_journal.entries == ()
    assert runtime.state_holder.snapshot.last_sequence == 0
    assert pipeline.durable_journal_health.status is DurableJournalHealthStatus.SYNCHRONIZED
    assert rejecting.calls == 1
    assert calls == ["durable-command-1"]


def test_storage_failure_marks_runtime_unavailable_and_blocks_later_dispatch(tmp_path):
    _, runtime, projector = initialize_and_hydrate(tmp_path)
    failing = RaisingAppender()
    binding = DurableJournalBinding(failing, JOURNAL_ID, 0)
    pipeline, calls = build_pipeline(
        runtime,
        projector,
        lambda item: GameResult.success(item.command_id, events=(event_for(item),)),
        binding=binding,
    )

    failed = pipeline.dispatch(command(1))
    blocked = pipeline.dispatch(command(2))

    assert failed.durable_publication.status is DurablePublicationStatus.STORAGE_UNAVAILABLE
    assert failed.publication_disposition is EventPublicationDisposition.FAILED
    assert pipeline.durable_journal_health.status is DurableJournalHealthStatus.UNAVAILABLE
    assert pipeline.durable_journal_health.reason_code is DurableJournalHealthReason.STORAGE_UNAVAILABLE
    assert blocked.projection_disposition is ProjectionDisposition.UNAVAILABLE
    assert blocked.policy_gated_result is None
    assert failing.calls == 1
    assert calls == ["durable-command-1"]
    serialized = json.dumps(failed.to_dict())
    assert "raw sqlite" not in serialized
    assert str(tmp_path) not in serialized


def test_successful_store_result_metadata_is_verified_before_local_visibility(tmp_path):
    _, runtime, projector = initialize_and_hydrate(tmp_path)
    mismatched = MismatchedSuccessAppender()
    binding = DurableJournalBinding(mismatched, JOURNAL_ID, 0)
    pipeline, calls = build_pipeline(
        runtime,
        projector,
        lambda item: GameResult.success(item.command_id, events=(event_for(item),)),
        binding=binding,
    )

    result = pipeline.dispatch(command())

    assert result.durable_publication.status is DurablePublicationStatus.STORAGE_UNAVAILABLE
    assert result.durable_publication.reason_code == "store_result_mismatch"
    assert runtime.event_journal.entries == ()
    assert runtime.state_holder.snapshot.last_sequence == 0
    assert pipeline.durable_journal_health.reason_code is DurableJournalHealthReason.STORE_RESULT_MISMATCH
    assert mismatched.calls == 1
    assert calls == ["durable-command-1"]


def test_competing_store_stale_tail_fails_closed_until_fresh_hydration(tmp_path):
    store, runtime, projector = initialize_and_hydrate(tmp_path)
    competing_item = command(99, command_id="competing-command")
    competing_entry = GameEventJournalEntry(1, event_for(competing_item))
    assert store.append((competing_entry,), expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS
    pipeline, calls = build_pipeline(
        runtime,
        projector,
        lambda item: GameResult.success(item.command_id, events=(event_for(item),)),
    )

    stale = pipeline.dispatch(command(1))
    blocked = pipeline.dispatch(command(2))
    recovery = pipeline.recover_world_state(WorldStateRecoveryStrategy.CATCH_UP)

    assert stale.durable_publication.status is DurablePublicationStatus.DIVERGED
    assert stale.durable_publication.reason_code == "stale_tail"
    assert pipeline.durable_journal_health.reason_code is DurableJournalHealthReason.STALE_DURABLE_TAIL
    assert runtime.event_journal.entries == ()
    assert runtime.state_holder.snapshot.last_sequence == 0
    assert blocked.policy_gated_result is None
    assert recovery.status is WorldStateRecoveryStatus.UNAVAILABLE
    assert calls == ["durable-command-1"]


def test_journal_id_mismatch_rejects_before_durable_or_local_append(tmp_path):
    store, runtime, projector = initialize_and_hydrate(tmp_path)
    mismatched = DurableJournalBinding(store, "wrong-journal", 0)
    pipeline, _ = build_pipeline(
        runtime,
        projector,
        lambda item: GameResult.success(item.command_id, events=(event_for(item),)),
        binding=mismatched,
    )

    result = pipeline.dispatch(command())

    assert result.durable_publication.status is DurablePublicationStatus.DIVERGED
    assert result.durable_publication.reason_code == "journal_id_mismatch"
    assert pipeline.durable_journal_health.reason_code is DurableJournalHealthReason.JOURNAL_ID_MISMATCH
    assert store.load().entries == ()
    assert runtime.event_journal.entries == ()


def test_duplicate_existing_event_is_rejected_before_durable_append(tmp_path):
    store, runtime, projector = initialize_and_hydrate(tmp_path, count=1)
    recording = RecordingAppender(store, runtime.event_journal)
    binding = DurableJournalBinding(recording, JOURNAL_ID, 1)
    item = command(2)
    duplicate = event_for(item, event_id="seed-event-1")
    pipeline, _ = build_pipeline(
        runtime,
        projector,
        lambda received: GameResult.success(received.command_id, events=(duplicate,)),
        binding=binding,
    )

    result = pipeline.dispatch(item)

    assert result.durable_publication.status is DurablePublicationStatus.NOT_COMMITTED
    assert recording.calls == []
    assert store.load().tail_sequence == 1
    assert runtime.event_journal.tail_sequence == 1
    assert runtime.state_holder.snapshot.last_sequence == 1


def test_invalid_later_prepared_entry_is_atomically_rejected(tmp_path):
    store = EventJournalStore(tmp_path / "invalid-later.sqlite")
    assert store.initialize(journal_id=JOURNAL_ID).status is EventJournalStoreStatus.SUCCESS
    journal = InvalidLaterPreparationJournal()
    runtime = type("Runtime", (), {})()
    runtime.event_journal = journal
    runtime.state_holder = WorldStateHolder(WorldState({"values": []}))
    recording = RecordingAppender(store, journal)
    runtime.durable_binding = DurableJournalBinding(recording, JOURNAL_ID, 0)
    item = command(3)
    produced = (event_for(item, 3), event_for(item, 4))
    pipeline, _ = build_pipeline(
        runtime,
        projector_with(),
        lambda received: GameResult.success(received.command_id, events=produced),
    )

    result = pipeline.dispatch(item)

    assert result.durable_publication.status is DurablePublicationStatus.NOT_COMMITTED
    assert len(recording.calls) == 1
    assert store.load().entries == ()
    assert journal.entries == ()
    assert runtime.state_holder.snapshot.last_sequence == 0


def test_confirmed_commit_survives_injected_local_append_failure_and_blocks(tmp_path):
    store = EventJournalStore(tmp_path / "local-failure.sqlite")
    assert store.initialize(journal_id=JOURNAL_ID).status is EventJournalStoreStatus.SUCCESS
    journal = FailingPreparedAppendJournal()
    runtime = type("Runtime", (), {})()
    runtime.event_journal = journal
    runtime.state_holder = WorldStateHolder(WorldState({"values": []}))
    recording = RecordingAppender(store, journal)
    runtime.durable_binding = DurableJournalBinding(recording, JOURNAL_ID, 0)
    pipeline, calls = build_pipeline(
        runtime,
        projector_with(),
        lambda item: GameResult.success(item.command_id, events=(event_for(item),)),
    )

    failed = pipeline.dispatch(command(1))
    blocked = pipeline.dispatch(command(2))

    assert failed.durable_publication.status is DurablePublicationStatus.COMMITTED_LOCAL_SYNC_FAILED
    assert failed.durable_publication.durable_commit_confirmed
    assert failed.published_event_entries == ()
    assert store.load().tail_sequence == 1
    assert journal.entries == ()
    assert runtime.state_holder.snapshot.last_sequence == 0
    assert pipeline.durable_journal_health.status is DurableJournalHealthStatus.UNAVAILABLE
    assert blocked.policy_gated_result is None
    assert len(recording.calls) == 1
    assert calls == ["durable-command-1"]

    restarted = hydrate_durable_runtime(
        EventJournalStore(store.path),
        expected_journal_id=JOURNAL_ID,
        base_state=WorldState({"values": []}),
        projector=projector_with(),
    )
    assert restarted.status is StartupHydrationStatus.SUCCESS
    assert restarted.runtime.event_journal.tail_sequence == 1
    assert restarted.runtime.state_holder.snapshot.last_sequence == 1


def test_projection_failure_preserves_durable_and_local_events_then_recovers_without_append(tmp_path):
    fail = {"active": True}

    def conditional_reducer(state_data, item):
        if fail["active"]:
            raise RuntimeError("private projection failure")
        return reducer(state_data, item)

    projector = projector_with(conditional_reducer)
    store, runtime, _ = initialize_and_hydrate(tmp_path, projector=projector)
    recording = RecordingAppender(store, runtime.event_journal)
    binding = DurableJournalBinding(recording, JOURNAL_ID, 0)
    pipeline, _ = build_pipeline(
        runtime,
        projector,
        lambda item: GameResult.success(item.command_id, events=(event_for(item),)),
        binding=binding,
    )

    failed = pipeline.dispatch(command())

    assert failed.durable_publication.status is DurablePublicationStatus.COMMITTED_PROJECTION_FAILED
    assert failed.durable_publication.durable_commit_confirmed
    assert store.load().tail_sequence == runtime.event_journal.tail_sequence == 1
    assert runtime.state_holder.snapshot.last_sequence == 0
    assert runtime.state_holder.health.status is WorldStateSynchronizationStatus.OUT_OF_SYNC
    assert pipeline.durable_journal_health.status is DurableJournalHealthStatus.SYNCHRONIZED

    fail["active"] = False
    recovered = pipeline.recover_world_state(WorldStateRecoveryStrategy.CATCH_UP)

    assert recovered.status is WorldStateRecoveryStatus.RECOVERED
    assert runtime.state_holder.snapshot.last_sequence == 1
    assert len(recording.calls) == 1


def test_same_thread_reentry_still_fails_without_extra_handler_or_store_call(tmp_path):
    store, runtime, projector = initialize_and_hydrate(tmp_path)
    recording = RecordingAppender(store, runtime.event_journal)
    binding = DurableJournalBinding(recording, JOURNAL_ID, 0)
    inner_results = []
    pipeline = None

    def handler(item):
        inner_results.append(pipeline.dispatch(command(2)))
        return GameResult.success(item.command_id, events=(event_for(item),))

    pipeline, calls = build_pipeline(runtime, projector, handler, binding=binding)
    outer = pipeline.dispatch(command(1))

    assert outer.durable_publication.status is DurablePublicationStatus.COMMITTED_SYNCHRONIZED
    assert inner_results[0].projection_disposition is ProjectionDisposition.UNAVAILABLE
    assert inner_results[0].policy_gated_result is None
    assert calls == ["durable-command-1"]
    assert len(recording.calls) == 1


def test_concurrent_durable_dispatch_is_serialized_in_exact_sequence(tmp_path):
    store, runtime, projector = initialize_and_hydrate(tmp_path)
    entered = threading.Event()
    release = threading.Event()

    def handler(item):
        if item.command_id == "durable-command-1":
            entered.set()
            assert release.wait(timeout=5)
        return GameResult.success(item.command_id, events=(event_for(item),))

    pipeline, calls = build_pipeline(runtime, projector, handler)
    results = []
    first = threading.Thread(target=lambda: results.append(pipeline.dispatch(command(1))))
    second = threading.Thread(target=lambda: results.append(pipeline.dispatch(command(2))))

    first.start()
    assert entered.wait(timeout=5)
    second.start()
    release.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert calls == ["durable-command-1", "durable-command-2"]
    assert all(
        item.durable_publication.status is DurablePublicationStatus.COMMITTED_SYNCHRONIZED
        for item in results
    )
    assert tuple(entry.sequence for entry in runtime.event_journal.entries) == (1, 2)
    assert store.load().tail_sequence == runtime.state_holder.snapshot.last_sequence == 2


def test_restart_hydration_reproduces_runtime_and_appends_next_exact_sequence(tmp_path):
    store, runtime, projector = initialize_and_hydrate(tmp_path)
    first_pipeline, _ = build_pipeline(
        runtime,
        projector,
        lambda item: GameResult.success(item.command_id, events=(event_for(item),)),
    )
    first = first_pipeline.dispatch(command(1))
    assert first.durable_publication.status is DurablePublicationStatus.COMMITTED_SYNCHRONIZED
    original_entries = [entry.to_dict() for entry in runtime.event_journal.entries]
    original_state = runtime.state_holder.snapshot.to_dict()

    reopened = EventJournalStore(store.path)
    hydrated = hydrate_durable_runtime(
        reopened,
        expected_journal_id=JOURNAL_ID,
        base_state=WorldState({"values": []}),
        projector=projector,
    )
    assert hydrated.status is StartupHydrationStatus.SUCCESS
    fresh = hydrated.runtime
    assert [entry.to_dict() for entry in fresh.event_journal.entries] == original_entries
    assert fresh.state_holder.snapshot.to_dict() == original_state

    second_pipeline, _ = build_pipeline(
        fresh,
        projector,
        lambda item: GameResult.success(item.command_id, events=(event_for(item),)),
    )
    second = second_pipeline.dispatch(command(2))

    assert second.durable_publication.previous_tail == 1
    assert second.durable_publication.resulting_tail == 2
    assert fresh.event_journal.entries[-1].sequence == 2
    assert reopened.load().tail_sequence == fresh.state_holder.snapshot.last_sequence == 2
