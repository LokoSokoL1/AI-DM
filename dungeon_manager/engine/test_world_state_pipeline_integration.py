import itertools
import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from threading import Event, Thread

import pytest

from .audit import AuditStage
from .audited_pipeline import (
    AuditedCommandPipeline,
    AuditIntegrationStatus,
    EventPublicationDisposition,
    ProjectionDisposition,
)
from .automation import (
    AutomationMode,
    AutomationPolicy,
    CapabilityAutomationRule,
)
from .command import CommandProvenance, CommandSource, GameCommand
from .game_engine import GameEngine
from .game_event import GameEvent
from .journals import CommandAuditJournal, GameEventJournal
from .policy_gated_dispatcher import (
    PolicyGatedCommandDispatcher,
    PolicyGatedDispatchStatus,
)
from .result import GameResult
from .world_state import (
    WorldState,
    WorldStateProjectionStatus,
    WorldStateProjector,
)
from .world_state_holder import (
    ProjectionReasonCode,
    WorldStateHolder,
    WorldStateSynchronizationStatus,
)


COMMAND_TYPE = "test.project_world_state"
EVENT_TYPE = "test.synthetic_state_changed"
FIXED_UTC = datetime(2026, 7, 15, 22, 0, tzinfo=timezone.utc)


def make_command(command_id="command-projection-001", value=1):
    return GameCommand(
        command_id=command_id,
        command_type=COMMAND_TYPE,
        provenance=CommandProvenance(
            source=CommandSource.SYSTEM,
            initiator_id="projection-test",
        ),
        payload={"value": value, "hidden_input": "never-audit-input"},
    )


def make_event(command, *, number=1, event_type=EVENT_TYPE, schema_version=1):
    return GameEvent(
        event_id=f"event-{command.command_id}-{number:03d}",
        event_type=event_type,
        schema_version=schema_version,
        payload={
            "value": command.payload["value"] + number - 1,
            "hidden_event": "never-audit-event-payload",
        },
        provenance=CommandProvenance(
            source=CommandSource.SYSTEM,
            initiator_id="synthetic-test-handler",
        ),
        originating_command_id=command.command_id,
        occurred_at=FIXED_UTC,
    )


def ordered_reducer(state_data, event):
    applied = list(state_data.get("applied", ()))
    applied.append(event.payload["value"])
    return {
        "applied": applied,
        "hidden_reducer_output": "never-audit-reducer-output",
    }


class CountingProjector(WorldStateProjector):
    def __init__(self):
        super().__init__()
        self.calls = []

    def project(self, entries, state):
        snapshot = tuple(entries)
        self.calls.append((snapshot, state))
        return super().project(snapshot, state)


class FailingEventJournal(GameEventJournal):
    def __init__(self):
        super().__init__()
        self.append_batch_attempts = 0

    def append_batch(self, events):
        self.append_batch_attempts += 1
        raise RuntimeError("raw publication backend secret")


class FailingAuditJournal(CommandAuditJournal):
    def __init__(self, fail_on_append):
        super().__init__()
        self.fail_on_append = fail_on_append
        self.append_attempts = 0

    def append(self, record):
        self.append_attempts += 1
        if self.append_attempts == self.fail_on_append:
            raise RuntimeError("raw audit backend secret")
        return super().append(record)


def projector_with(reducer=ordered_reducer, *, schema_version=1):
    projector = CountingProjector()
    projector.register_reducer(EVENT_TYPE, schema_version, reducer)
    return projector


def build_pipeline(
    handler,
    *,
    mode=AutomationMode.AUTOMATIC,
    projector=None,
    state_holder=None,
    event_journal=None,
    audit_journal=None,
):
    calls = []
    engine = GameEngine()

    def tracked_handler(command):
        calls.append(command.command_id)
        return handler(command)

    engine.register_handler(COMMAND_TYPE, tracked_handler)
    dispatcher = PolicyGatedCommandDispatcher(
        AutomationPolicy(
            capabilities={
                COMMAND_TYPE: CapabilityAutomationRule(default_mode=mode)
            }
        ),
        engine,
    )
    selected_event_journal = (
        GameEventJournal() if event_journal is None else event_journal
    )
    selected_audit_journal = (
        CommandAuditJournal() if audit_journal is None else audit_journal
    )
    selected_projector = (
        projector_with() if projector is None else projector
    )
    selected_state_holder = state_holder
    if selected_state_holder is None:
        tail = (
            0
            if not selected_event_journal.entries
            else selected_event_journal.entries[-1].sequence
        )
        selected_state_holder = WorldStateHolder(
            WorldState(last_sequence=tail)
        )
    audit_ids = itertools.count(1)
    pipeline = AuditedCommandPipeline(
        dispatcher,
        selected_audit_journal,
        selected_event_journal,
        selected_projector,
        selected_state_holder,
        audit_record_id_factory=(
            lambda: f"audit-projection-{next(audit_ids):04d}"
        ),
        clock=lambda: FIXED_UTC,
    )
    return (
        pipeline,
        dispatcher,
        selected_audit_journal,
        selected_event_journal,
        selected_projector,
        selected_state_holder,
        calls,
    )


def one_event_handler(command):
    return GameResult.success(
        command.command_id,
        {"hidden_handler_output": "never-audit-handler-output"},
        events=(make_event(command),),
    )


def test_explicit_synchronized_initial_state_matches_existing_journal_tail():
    existing_command = make_command("command-existing", 4)
    journal = GameEventJournal()
    journal.append(make_event(existing_command))
    holder = WorldStateHolder(
        WorldState(data={"applied": [4]}, last_sequence=1)
    )
    pipeline, _, _, _, projector, _, calls = build_pipeline(
        lambda command: GameResult.success(command.command_id),
        event_journal=journal,
        state_holder=holder,
    )

    assert holder.health.status is (
        WorldStateSynchronizationStatus.SYNCHRONIZED
    )
    result = pipeline.dispatch(make_command("command-next", 5))

    assert result.projection_disposition is ProjectionDisposition.UNCHANGED
    assert result.projection_sequence == 1
    assert holder.snapshot.to_dict() == {
        "data": {"applied": [4]},
        "last_sequence": 1,
    }
    assert projector.calls == []
    assert calls == ["command-next"]


def test_initial_state_and_journal_mismatch_is_explicitly_unavailable():
    existing_command = make_command("command-existing", 3)
    journal = GameEventJournal()
    journal.append(make_event(existing_command))
    holder = WorldStateHolder(WorldState.initial())
    pipeline, dispatcher, audit, _, projector, _, calls = build_pipeline(
        one_event_handler,
        event_journal=journal,
        state_holder=holder,
    )

    assert holder.health.to_dict() == {
        "committed_sequence": 0,
        "journal_sequence": 1,
        "projector_status": None,
        "reason_code": "initial_sequence_mismatch",
        "status": "out_of_sync",
    }
    result = pipeline.dispatch(make_command("command-blocked-mismatch", 8))

    assert result.projection_disposition is ProjectionDisposition.UNAVAILABLE
    assert result.projection_reason_code is (
        ProjectionReasonCode.INITIAL_SEQUENCE_MISMATCH
    )
    assert result.policy_gated_result is None
    assert dispatcher.dispatch_attempted_command_ids == ()
    assert calls == []
    assert projector.calls == []
    assert len(journal.entries) == 1
    assert [entry.record.stage for entry in audit.entries] == [
        AuditStage.COMMAND_PROPOSED,
        AuditStage.COORDINATOR_FAILURE,
    ]


def test_dispatched_result_without_events_leaves_projection_unchanged():
    pipeline, _, _, journal, projector, holder, _ = build_pipeline(
        lambda command: GameResult.success(command.command_id, {"ok": True})
    )

    result = pipeline.dispatch(make_command())

    assert result.audit_status is AuditIntegrationStatus.COMPLETED
    assert result.publication_disposition is (
        EventPublicationDisposition.NO_EVENTS
    )
    assert result.projection_disposition is ProjectionDisposition.UNCHANGED
    assert result.projection_sequence == 0
    assert journal.entries == ()
    assert projector.calls == []
    assert holder.snapshot is holder.snapshot


def test_one_published_entry_updates_state_from_authoritative_entry_snapshot():
    pipeline, _, _, journal, projector, holder, _ = build_pipeline(
        one_event_handler
    )

    result = pipeline.dispatch(make_command(value=7))

    assert result.projection_disposition is ProjectionDisposition.PROJECTED
    assert result.projector_status is WorldStateProjectionStatus.SUCCESS
    assert result.projection_previous_sequence == 0
    assert result.projection_target_sequence == 1
    assert result.projection_sequence == 1
    assert projector.calls[0][0] == result.published_event_entries
    assert projector.calls[0][0][0] is journal.entries[0]
    assert holder.snapshot.to_dict() == {
        "data": {
            "applied": [7],
            "hidden_reducer_output": "never-audit-reducer-output",
        },
        "last_sequence": 1,
    }


def test_multiple_published_entries_update_state_in_journal_order():
    def handler(command):
        events = tuple(
            make_event(command, number=number) for number in (1, 2, 3)
        )
        return GameResult.success(command.command_id, events=events)

    pipeline, _, _, journal, projector, holder, _ = build_pipeline(handler)

    result = pipeline.dispatch(make_command(value=10))

    assert [entry.sequence for entry in journal.entries] == [1, 2, 3]
    assert projector.calls[0][0] == journal.entries
    assert holder.snapshot.data["applied"] == (10, 11, 12)
    assert holder.snapshot.last_sequence == 3
    assert result.projection_target_sequence == 3


def test_multiple_commands_project_incrementally_without_replaying_entries():
    pipeline, _, _, journal, projector, holder, _ = build_pipeline(
        one_event_handler
    )

    first = pipeline.dispatch(make_command("command-incremental-1", 2))
    second = pipeline.dispatch(make_command("command-incremental-2", 9))

    assert first.projection_sequence == 1
    assert second.projection_previous_sequence == 1
    assert second.projection_sequence == 2
    assert [call[0][0].sequence for call in projector.calls] == [1, 2]
    assert all(len(call[0]) == 1 for call in projector.calls)
    assert journal.entries == (
        first.published_event_entries[0],
        second.published_event_entries[0],
    )
    assert holder.snapshot.data["applied"] == (2, 9)


def test_blocked_command_does_not_invoke_handler_or_reducer():
    reducer_calls = []

    def reducer(state_data, event):
        reducer_calls.append(event.event_id)
        return state_data

    pipeline, dispatcher, _, journal, projector, holder, calls = build_pipeline(
        one_event_handler,
        mode=AutomationMode.DENY,
        projector=projector_with(reducer),
    )

    result = pipeline.dispatch(make_command())

    assert result.policy_gated_result.status is PolicyGatedDispatchStatus.DENIED
    assert result.projection_disposition is (
        ProjectionDisposition.NOT_APPLICABLE
    )
    assert dispatcher.dispatch_attempted_command_ids == ()
    assert calls == []
    assert reducer_calls == []
    assert projector.calls == []
    assert journal.entries == ()
    assert holder.snapshot.last_sequence == 0


def test_duplicate_command_does_not_publish_or_project_again():
    pipeline, _, _, journal, projector, holder, calls = build_pipeline(
        one_event_handler
    )
    command = make_command()

    first = pipeline.dispatch(command)
    duplicate = pipeline.dispatch(command)

    assert first.projection_disposition is ProjectionDisposition.PROJECTED
    assert duplicate.policy_gated_result.status is (
        PolicyGatedDispatchStatus.DUPLICATE
    )
    assert duplicate.projection_disposition is (
        ProjectionDisposition.NOT_APPLICABLE
    )
    assert len(journal.entries) == 1
    assert len(projector.calls) == 1
    assert holder.snapshot.last_sequence == 1
    assert calls == [command.command_id]


def test_publication_failure_does_not_invoke_projection():
    journal = FailingEventJournal()
    pipeline, dispatcher, _, _, projector, holder, calls = build_pipeline(
        one_event_handler,
        event_journal=journal,
    )

    result = pipeline.dispatch(make_command())

    assert result.audit_status is (
        AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE
    )
    assert result.publication_disposition is EventPublicationDisposition.FAILED
    assert result.projection_disposition is (
        ProjectionDisposition.NOT_APPLICABLE
    )
    assert projector.calls == []
    assert journal.append_batch_attempts == 1
    assert holder.snapshot.last_sequence == 0
    assert dispatcher.dispatch_attempted_command_ids == (
        "command-projection-001",
    )
    assert calls == ["command-projection-001"]


def test_reducer_exception_after_publication_fails_once_and_poison_sync():
    reducer_calls = []

    def failing_reducer(state_data, event):
        reducer_calls.append(event.event_id)
        raise RuntimeError("raw reducer exception secret")

    projector = projector_with(failing_reducer)
    pipeline, dispatcher, audit, journal, _, holder, calls = build_pipeline(
        one_event_handler,
        projector=projector,
    )

    failed = pipeline.dispatch(make_command("command-failing-reducer", 6))

    assert failed.projection_disposition is ProjectionDisposition.FAILED
    assert failed.projector_status is WorldStateProjectionStatus.REDUCER_FAILURE
    assert failed.projection_reason_code is ProjectionReasonCode.PROJECTION_FAILED
    assert holder.snapshot.to_dict() == {"data": {}, "last_sequence": 0}
    assert len(journal.entries) == 1
    assert reducer_calls == ["event-command-failing-reducer-001"]
    assert dispatcher.dispatch_attempted_command_ids == (
        "command-failing-reducer",
    )
    assert holder.health.status is WorldStateSynchronizationStatus.OUT_OF_SYNC
    assert holder.health.journal_sequence == 1

    later = pipeline.dispatch(make_command("command-after-failure", 12))

    assert later.projection_disposition is ProjectionDisposition.UNAVAILABLE
    assert later.policy_gated_result is None
    assert calls == ["command-failing-reducer"]
    assert reducer_calls == ["event-command-failing-reducer-001"]
    assert len(projector.calls) == 1
    assert len(journal.entries) == 1
    assert "raw reducer exception secret" not in json.dumps(
        [entry.record.to_dict() for entry in audit.entries]
    )


def test_invalid_reducer_output_after_publication_preserves_previous_state():
    def invalid_reducer(state_data, event):
        return [event.payload["value"]]

    pipeline, _, _, journal, _, holder, _ = build_pipeline(
        one_event_handler,
        projector=projector_with(invalid_reducer),
    )

    result = pipeline.dispatch(make_command())

    assert result.projection_disposition is ProjectionDisposition.FAILED
    assert result.projector_status is (
        WorldStateProjectionStatus.INVALID_REDUCER_RESULT
    )
    assert holder.snapshot.to_dict() == {"data": {}, "last_sequence": 0}
    assert len(journal.entries) == 1


@pytest.mark.parametrize(
    ("projector", "event_type", "schema_version", "expected_status"),
    [
        (
            CountingProjector(),
            "test.unknown_synthetic_event",
            1,
            WorldStateProjectionStatus.UNKNOWN_EVENT_TYPE,
        ),
        (
            projector_with(),
            EVENT_TYPE,
            2,
            WorldStateProjectionStatus.UNSUPPORTED_SCHEMA_VERSION,
        ),
    ],
)
def test_unknown_event_or_schema_fails_only_after_publication(
    projector,
    event_type,
    schema_version,
    expected_status,
):
    def handler(command):
        event = make_event(
            command,
            event_type=event_type,
            schema_version=schema_version,
        )
        return GameResult.success(command.command_id, events=(event,))

    pipeline, dispatcher, _, journal, _, holder, calls = build_pipeline(
        handler,
        projector=projector,
    )

    result = pipeline.dispatch(make_command())

    assert result.projection_disposition is ProjectionDisposition.FAILED
    assert result.projector_status is expected_status
    assert len(journal.entries) == 1
    assert holder.snapshot.last_sequence == 0
    assert dispatcher.dispatch_attempted_command_ids == (
        "command-projection-001",
    )
    assert calls == ["command-projection-001"]


def test_successful_projection_survives_later_completion_audit_failure():
    audit = FailingAuditJournal(fail_on_append=5)
    pipeline, dispatcher, _, journal, projector, holder, _ = build_pipeline(
        one_event_handler,
        audit_journal=audit,
    )

    result = pipeline.dispatch(make_command(value=13))

    assert result.audit_status is (
        AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE
    )
    assert result.projection_disposition is ProjectionDisposition.PROJECTED
    assert result.projection_sequence == 1
    assert holder.snapshot.data["applied"] == (13,)
    assert holder.health.status is (
        WorldStateSynchronizationStatus.SYNCHRONIZED
    )
    assert len(journal.entries) == 1
    assert len(projector.calls) == 1
    assert dispatcher.dispatch_attempted_command_ids == (
        "command-projection-001",
    )


def test_state_holder_snapshots_are_immutable_and_defensive():
    holder = WorldStateHolder(
        WorldState(data={"nested": {"values": [1]}}, last_sequence=0)
    )
    snapshot = holder.snapshot

    with pytest.raises(TypeError):
        snapshot.data["nested"] = {}
    with pytest.raises(TypeError):
        snapshot.data["nested"]["values"][0] = 9
    with pytest.raises(FrozenInstanceError):
        snapshot.last_sequence = 4

    serialized = snapshot.to_dict()
    serialized["data"]["nested"]["values"][0] = 99
    assert holder.snapshot.data["nested"]["values"] == (1,)
    assert "data" not in holder.health.to_dict()


def test_result_projection_serialization_is_safe_json_and_defensive():
    pipeline, _, _, _, _, holder, _ = build_pipeline(one_event_handler)
    result = pipeline.dispatch(make_command(value=5))

    serialized = result.to_dict()
    assert serialized["projection_disposition"] == "projected"
    assert serialized["projection_sequence"] == 1
    assert serialized["projector_status"] == "success"
    assert "world_state" not in serialized
    assert "state" not in {
        key for key in serialized if key.startswith("projection")
    }
    assert json.loads(json.dumps(serialized, allow_nan=False)) == serialized

    serialized["projection_sequence"] = 999
    serialized["published_event_entries"][0]["event"]["payload"][
        "value"
    ] = 999
    fresh = result.to_dict()
    assert fresh["projection_sequence"] == 1
    assert fresh["published_event_entries"][0]["event"]["payload"][
        "value"
    ] == 5
    assert holder.snapshot.data["applied"] == (5,)


def test_audit_data_excludes_state_event_payload_and_execution_output():
    holder = WorldStateHolder(
        WorldState(
            data={"hidden_world_state": "never-audit-world-state"},
            last_sequence=0,
        )
    )
    pipeline, _, audit, _, _, _, _ = build_pipeline(
        one_event_handler,
        state_holder=holder,
    )

    result = pipeline.dispatch(make_command(value=21))
    audit_json = json.dumps(
        [entry.record.to_dict() for entry in audit.entries],
        sort_keys=True,
    )

    for secret in (
        "never-audit-input",
        "never-audit-event-payload",
        "never-audit-handler-output",
        "never-audit-reducer-output",
        "never-audit-world-state",
    ):
        assert secret not in audit_json
    assert result.audit_status is AuditIntegrationStatus.COMPLETED


def test_concurrent_commands_preserve_journal_and_projection_order():
    first_reducer_entered = Event()
    release_first_reducer = Event()
    reducer_values = []

    def coordinated_reducer(state_data, event):
        value = event.payload["value"]
        reducer_values.append(value)
        if value == 1:
            first_reducer_entered.set()
            assert release_first_reducer.wait(2)
        return ordered_reducer(state_data, event)

    pipeline, _, _, journal, _, holder, calls = build_pipeline(
        one_event_handler,
        projector=projector_with(coordinated_reducer),
    )
    results = {}
    errors = []

    def submit(command):
        try:
            results[command.command_id] = pipeline.dispatch(command)
        except Exception as error:
            errors.append(error)

    first = Thread(target=submit, args=(make_command("command-thread-1", 1),))
    second = Thread(target=submit, args=(make_command("command-thread-2", 2),))
    first.start()
    assert first_reducer_entered.wait(2)
    second.start()
    assert calls == ["command-thread-1"]
    release_first_reducer.set()
    first.join(2)
    second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert calls == ["command-thread-1", "command-thread-2"]
    assert reducer_values == [1, 2]
    assert [entry.sequence for entry in journal.entries] == [1, 2]
    assert [entry.event.payload["value"] for entry in journal.entries] == [1, 2]
    assert holder.snapshot.data["applied"] == (1, 2)
    assert holder.snapshot.last_sequence == 2
    assert results["command-thread-1"].projection_sequence == 1
    assert results["command-thread-2"].projection_previous_sequence == 1


def test_reentrant_pipeline_invocation_fails_without_deadlock_or_replay_use():
    captured = {}
    pipeline_reference = {}
    inner = make_command("command-reentrant-inner", 2)

    def handler(command):
        captured["inner_result"] = pipeline_reference["pipeline"].dispatch(inner)
        return GameResult.success(command.command_id)

    pipeline, dispatcher, audit, journal, projector, holder, calls = build_pipeline(
        handler
    )
    pipeline_reference["pipeline"] = pipeline

    outer = pipeline.dispatch(make_command("command-reentrant-outer", 1))
    inner_result = captured["inner_result"]

    assert outer.audit_status is AuditIntegrationStatus.COMPLETED
    assert outer.projection_disposition is ProjectionDisposition.UNCHANGED
    assert inner_result.projection_disposition is (
        ProjectionDisposition.UNAVAILABLE
    )
    assert inner_result.projection_reason_code is (
        ProjectionReasonCode.REENTRANT_INVOCATION
    )
    assert inner_result.policy_gated_result is None
    assert inner_result.audit_entries == ()
    assert dispatcher.dispatch_attempted_command_ids == (
        "command-reentrant-outer",
    )
    assert calls == ["command-reentrant-outer"]
    assert journal.entries == ()
    assert projector.calls == []
    assert holder.snapshot.last_sequence == 0
    assert all(
        entry.record.command_id == "command-reentrant-outer"
        for entry in audit.entries
    )


def test_failed_projection_is_not_automatically_rebuilt_or_replayed():
    projector = CountingProjector()
    pipeline, _, _, journal, _, holder, calls = build_pipeline(
        one_event_handler,
        projector=projector,
    )

    failed = pipeline.dispatch(make_command("command-no-reducer", 1))
    projector.register_reducer(EVENT_TYPE, 1, ordered_reducer)
    later = pipeline.dispatch(make_command("command-after-registration", 2))

    assert failed.projector_status is (
        WorldStateProjectionStatus.UNKNOWN_EVENT_TYPE
    )
    assert later.projection_disposition is ProjectionDisposition.UNAVAILABLE
    assert len(projector.calls) == 1
    assert len(journal.entries) == 1
    assert holder.snapshot.last_sequence == 0
    assert calls == ["command-no-reducer"]
    for forbidden_api in (
        "clear",
        "delete",
        "patch",
        "rebuild",
        "recover",
        "rollback",
        "set",
        "update",
    ):
        assert not hasattr(holder, forbidden_api)


def test_pipeline_requires_explicit_projector_and_state_holder_dependencies():
    engine = GameEngine()
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
    audit = CommandAuditJournal()
    events = GameEventJournal()

    with pytest.raises(ValueError, match="world-state projector"):
        AuditedCommandPipeline(
            dispatcher,
            audit,
            events,
            None,
            WorldStateHolder(WorldState.initial()),
        )
    with pytest.raises(ValueError, match="world-state holder"):
        AuditedCommandPipeline(
            dispatcher,
            audit,
            events,
            WorldStateProjector(),
            None,
        )


def test_state_holder_requires_explicit_world_state():
    with pytest.raises(ValueError, match="explicit initial WorldState"):
        WorldStateHolder(None)
