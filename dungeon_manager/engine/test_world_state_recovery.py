import inspect
import itertools
import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from threading import Event, Thread

import pytest

from .audited_pipeline import AuditedCommandPipeline, ProjectionDisposition
from .automation import (
    AutomationMode,
    AutomationPolicy,
    CapabilityAutomationRule,
)
from .command import CommandProvenance, CommandSource, GameCommand
from .game_engine import GameEngine
from .game_event import GameEvent
from .journals import CommandAuditJournal, GameEventJournal
from .policy_gated_dispatcher import PolicyGatedCommandDispatcher
from .result import GameResult
from .world_state import (
    WorldState,
    WorldStateProjectionStatus,
    WorldStateProjector,
)
from .world_state_holder import (
    WorldStateHolder,
    WorldStateSynchronizationStatus,
)
from .world_state_recovery import (
    WorldStateRecoveryResult,
    WorldStateRecoveryStatus,
    WorldStateRecoveryStrategy,
)


COMMAND_TYPE = "test.recovery_command"
EVENT_TYPE = "test.recovery_event"
FIXED_UTC = datetime(2026, 7, 15, 23, 0, tzinfo=timezone.utc)
PROVENANCE = CommandProvenance(CommandSource.SYSTEM, "recovery-test")


def make_command(command_id="command-recovery-001", value=1):
    return GameCommand(
        command_id=command_id,
        command_type=COMMAND_TYPE,
        payload={"value": value, "hidden_command": "command-secret"},
        provenance=PROVENANCE,
    )


def make_event(
    value,
    event_id,
    *,
    command_id=None,
    event_type=EVENT_TYPE,
    schema_version=1,
):
    return GameEvent(
        event_id=event_id,
        event_type=event_type,
        schema_version=schema_version,
        payload={"value": value, "hidden_event": "event-secret"},
        provenance=PROVENANCE,
        originating_command_id=command_id,
        occurred_at=FIXED_UTC,
    )


def journal_with_values(*values, schema_version=1, event_type=EVENT_TYPE):
    journal = GameEventJournal()
    journal.append_batch(
        tuple(
            make_event(
                value,
                f"event-existing-{index:03d}",
                event_type=event_type,
                schema_version=schema_version,
            )
            for index, value in enumerate(values, 1)
        )
    )
    return journal


def ordered_reducer(state_data, event):
    values = list(state_data.get("values", ()))
    values.append(event.payload["value"])
    return {**state_data, "values": values}


class CountingProjector(WorldStateProjector):
    def __init__(self):
        super().__init__()
        self.calls = []

    def project(self, entries, state):
        snapshot = tuple(entries)
        self.calls.append((snapshot, state))
        return super().project(snapshot, state)


class RaisingProjector(WorldStateProjector):
    def project(self, entries, state):
        raise RuntimeError("raw-projector-secret")


def projector_with(reducer=ordered_reducer, *, schema_version=1):
    projector = CountingProjector()
    projector.register_reducer(EVENT_TYPE, schema_version, reducer)
    return projector


def build_pipeline(
    *,
    journal=None,
    holder=None,
    projector=None,
    handler=None,
):
    selected_journal = GameEventJournal() if journal is None else journal
    selected_holder = (
        WorldStateHolder(WorldState.initial()) if holder is None else holder
    )
    selected_projector = (
        projector_with() if projector is None else projector
    )
    audit = CommandAuditJournal()
    handler_calls = []
    engine = GameEngine()

    def default_handler(command):
        event = make_event(
            command.payload["value"],
            f"event-{command.command_id}",
            command_id=command.command_id,
        )
        return GameResult.success(command.command_id, events=(event,))

    selected_handler = default_handler if handler is None else handler

    def tracked_handler(command):
        handler_calls.append(command.command_id)
        return selected_handler(command)

    engine.register_handler(COMMAND_TYPE, tracked_handler)
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
    audit_ids = itertools.count(1)
    pipeline = AuditedCommandPipeline(
        dispatcher,
        audit,
        selected_journal,
        selected_projector,
        selected_holder,
        audit_record_id_factory=(
            lambda: f"audit-recovery-{next(audit_ids):04d}"
        ),
        clock=lambda: FIXED_UTC,
    )
    return (
        pipeline,
        dispatcher,
        audit,
        selected_journal,
        selected_projector,
        selected_holder,
        handler_calls,
    )


def test_synchronized_catch_up_is_no_action_without_invoking_reducers():
    journal = journal_with_values(4)
    state = WorldState(data={"values": [4]}, last_sequence=1)
    holder = WorldStateHolder(state)
    projector = projector_with()
    pipeline, _, audit, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=projector,
    )

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.CATCH_UP
    )

    assert result.status is WorldStateRecoveryStatus.NO_ACTION
    assert result.previous_sequence == 1
    assert result.resulting_sequence == 1
    assert result.captured_journal_tail_sequence == 1
    assert projector.calls == []
    assert holder.snapshot is state
    assert audit.entries == ()


def test_catch_up_selects_only_entries_after_current_state_and_clears_health():
    reducer_sequences = []

    def reducer(state_data, event):
        reducer_sequences.append(event.payload["value"])
        return ordered_reducer(state_data, event)

    journal = journal_with_values(10, 20, 30)
    holder = WorldStateHolder(
        WorldState(data={"values": [10]}, last_sequence=1)
    )
    projector = projector_with(reducer)
    pipeline, _, _, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=projector,
    )
    assert holder.health.status is WorldStateSynchronizationStatus.OUT_OF_SYNC

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.CATCH_UP
    )

    assert result.status is WorldStateRecoveryStatus.RECOVERED
    assert result.previous_sequence == 1
    assert result.resulting_sequence == 3
    assert [entry.sequence for entry in projector.calls[0][0]] == [2, 3]
    assert reducer_sequences == [20, 30]
    assert holder.snapshot.to_dict() == {
        "data": {"values": [10, 20, 30]},
        "last_sequence": 3,
    }
    assert holder.health.status is WorldStateSynchronizationStatus.SYNCHRONIZED


def test_catch_up_rejects_state_ahead_of_journal_without_changing_it():
    journal = journal_with_values(1)
    state = WorldState(data={"values": [1, 2]}, last_sequence=2)
    holder = WorldStateHolder(state)
    projector = projector_with()
    pipeline, _, _, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=projector,
    )
    health_before = holder.health

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.CATCH_UP
    )

    assert result.status is WorldStateRecoveryStatus.INVALID_REQUEST
    assert result.previous_sequence == 2
    assert result.captured_journal_tail_sequence == 1
    assert holder.snapshot is state
    assert holder.health == health_before
    assert projector.calls == []


def test_full_rebuild_replays_complete_journal_from_explicit_zero_base():
    journal = journal_with_values(3, 5, 8)
    stale = WorldState(data={"values": [999]}, last_sequence=3)
    holder = WorldStateHolder(stale)
    projector = projector_with()
    pipeline, _, _, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=projector,
    )
    base = WorldState(data={"campaign": "synthetic"}, last_sequence=0)

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.FULL_REBUILD,
        base_state=base,
    )

    assert result.status is WorldStateRecoveryStatus.RECOVERED
    assert result.previous_sequence == 3
    assert result.resulting_sequence == 3
    assert [entry.sequence for entry in projector.calls[0][0]] == [1, 2, 3]
    assert projector.calls[0][1] is base
    assert holder.snapshot.to_dict() == {
        "data": {"campaign": "synthetic", "values": [3, 5, 8]},
        "last_sequence": 3,
    }


def test_full_rebuild_of_empty_journal_commits_supplied_base_state():
    journal = GameEventJournal()
    stale = WorldState(data={"stale": True}, last_sequence=0)
    holder = WorldStateHolder(stale)
    projector = projector_with()
    pipeline, _, _, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=projector,
    )
    base = WorldState(data={"explicit_base": [1, 2]}, last_sequence=0)

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.FULL_REBUILD,
        base_state=base,
    )

    assert result.status is WorldStateRecoveryStatus.RECOVERED
    assert result.resulting_sequence == 0
    assert projector.calls == [((), base)]
    assert holder.snapshot is base
    assert holder.health.status is WorldStateSynchronizationStatus.SYNCHRONIZED


@pytest.mark.parametrize(
    ("strategy", "base_state"),
    [
        (WorldStateRecoveryStrategy.FULL_REBUILD, None),
        (
            WorldStateRecoveryStrategy.FULL_REBUILD,
            WorldState(data={"invalid": "base"}, last_sequence=1),
        ),
        (
            WorldStateRecoveryStrategy.CATCH_UP,
            WorldState(data={"unexpected": "base"}, last_sequence=0),
        ),
    ],
)
def test_invalid_rebuild_and_catch_up_base_requests_are_rejected(
    strategy,
    base_state,
):
    state = WorldState.initial()
    holder = WorldStateHolder(state)
    projector = projector_with()
    pipeline, _, _, _, _, _, _ = build_pipeline(
        holder=holder,
        projector=projector,
    )

    result = pipeline.recover_world_state(strategy, base_state=base_state)

    assert result.status is WorldStateRecoveryStatus.INVALID_REQUEST
    assert result.resulting_sequence is None
    assert holder.snapshot is state
    assert projector.calls == []


def test_full_rebuild_does_not_mutate_supplied_immutable_base():
    journal = journal_with_values(7)
    holder = WorldStateHolder(WorldState.initial())
    base = WorldState(
        data={"nested": {"values": [1]}, "values": [2]},
        last_sequence=0,
    )
    before = base.to_dict()
    pipeline, _, _, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
    )

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.FULL_REBUILD,
        base_state=base,
    )

    assert result.status is WorldStateRecoveryStatus.RECOVERED
    assert base.to_dict() == before
    assert holder.snapshot is not base
    assert holder.snapshot.data["values"] == (2, 7)
    assert base.data["values"] == (2,)


@pytest.mark.parametrize(
    ("event_type", "schema_version", "expected_status"),
    [
        (
            "test.unknown_recovery_event",
            1,
            WorldStateProjectionStatus.UNKNOWN_EVENT_TYPE,
        ),
        (
            EVENT_TYPE,
            2,
            WorldStateProjectionStatus.UNSUPPORTED_SCHEMA_VERSION,
        ),
    ],
)
def test_unknown_event_type_or_schema_fails_recovery_atomically(
    event_type,
    schema_version,
    expected_status,
):
    journal = journal_with_values(
        1,
        event_type=event_type,
        schema_version=schema_version,
    )
    state = WorldState.initial()
    holder = WorldStateHolder(state)
    projector = projector_with()
    pipeline, _, _, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=projector,
    )
    health_before = holder.health

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.CATCH_UP
    )

    assert result.status is WorldStateRecoveryStatus.PROJECTION_FAILURE
    assert result.projector_status is expected_status
    assert result.resulting_sequence is None
    assert holder.snapshot is state
    assert holder.health == health_before


@pytest.mark.parametrize("failure_kind", ["invalid_result", "exception"])
def test_reducer_failure_preserves_state_health_and_safe_diagnostics(
    failure_kind,
):
    calls = []

    def failing_reducer(state_data, event):
        calls.append(event.event_id)
        if failure_kind == "invalid_result":
            return ["raw-invalid-output-secret"]
        raise RuntimeError("raw-reducer-secret")

    journal = journal_with_values(1)
    state = WorldState.initial()
    holder = WorldStateHolder(state)
    pipeline, _, _, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=projector_with(failing_reducer),
    )
    health_before = holder.health

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.CATCH_UP
    )
    serialized = json.dumps(result.to_dict(), sort_keys=True)

    expected = (
        WorldStateProjectionStatus.INVALID_REDUCER_RESULT
        if failure_kind == "invalid_result"
        else WorldStateProjectionStatus.REDUCER_FAILURE
    )
    assert result.status is WorldStateRecoveryStatus.PROJECTION_FAILURE
    assert result.projector_status is expected
    assert calls == ["event-existing-001"]
    assert holder.snapshot is state
    assert holder.health == health_before
    assert "raw-invalid-output-secret" not in serialized
    assert "raw-reducer-secret" not in serialized
    assert "event-secret" not in serialized


def test_failed_optional_rebuild_keeps_synchronized_state_and_health():
    journal = journal_with_values(4)
    state = WorldState(data={"values": [4]}, last_sequence=1)
    holder = WorldStateHolder(state)
    pipeline, _, _, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=CountingProjector(),
    )
    health_before = holder.health

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.FULL_REBUILD,
        base_state=WorldState.initial(),
    )

    assert result.status is WorldStateRecoveryStatus.PROJECTION_FAILURE
    assert holder.snapshot is state
    assert holder.health == health_before
    assert holder.health.status is WorldStateSynchronizationStatus.SYNCHRONIZED


def test_recovery_reducers_run_once_in_order_without_retry_or_journal_change():
    calls = []

    def reducer(state_data, event):
        calls.append(event.event_id)
        return ordered_reducer(state_data, event)

    journal = journal_with_values(2, 4, 6)
    journal_before = journal.entries
    holder = WorldStateHolder(WorldState.initial())
    pipeline, dispatcher, audit, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=projector_with(reducer),
    )

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.CATCH_UP
    )

    assert result.status is WorldStateRecoveryStatus.RECOVERED
    assert result.resulting_sequence == journal.tail_sequence == 3
    assert calls == [
        "event-existing-001",
        "event-existing-002",
        "event-existing-003",
    ]
    assert journal.entries == journal_before
    assert all(
        current is previous
        for current, previous in zip(journal.entries, journal_before)
    )
    assert audit.entries == ()
    assert dispatcher.dispatch_attempted_command_ids == ()


def test_failed_dispatch_stays_blocked_until_explicit_recovery_then_continues():
    should_fail = {"value": True}
    reducer_calls = []

    def reducer(state_data, event):
        reducer_calls.append(event.payload["value"])
        if should_fail["value"]:
            raise RuntimeError("raw-first-projection-secret")
        return ordered_reducer(state_data, event)

    pipeline, dispatcher, audit, journal, projector, holder, handler_calls = (
        build_pipeline(projector=projector_with(reducer))
    )

    failed = pipeline.dispatch(make_command("command-failed", 5))
    audit_count = len(audit.entries)
    blocked = pipeline.dispatch(make_command("command-blocked", 6))

    assert failed.projection_disposition is ProjectionDisposition.FAILED
    assert blocked.projection_disposition is ProjectionDisposition.UNAVAILABLE
    assert handler_calls == ["command-failed"]
    assert reducer_calls == [5]
    assert holder.health.status is WorldStateSynchronizationStatus.OUT_OF_SYNC

    should_fail["value"] = False
    recovered = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.CATCH_UP
    )

    assert recovered.status is WorldStateRecoveryStatus.RECOVERED
    assert recovered.resulting_sequence == 1
    assert len(audit.entries) == audit_count + 2
    assert len(journal.entries) == 1
    assert dispatcher.dispatch_attempted_command_ids == ("command-failed",)
    assert holder.health.status is WorldStateSynchronizationStatus.SYNCHRONIZED

    continued = pipeline.dispatch(make_command("command-continued", 7))

    assert continued.projection_disposition is ProjectionDisposition.PROJECTED
    assert continued.projection_previous_sequence == 1
    assert continued.projection_sequence == 2
    assert holder.snapshot.data["values"] == (5, 7)
    assert reducer_calls == [5, 5, 7]
    assert handler_calls == ["command-failed", "command-continued"]
    assert len(projector.calls) == 3


def test_concurrent_dispatch_waits_for_recovery_coordination_boundary():
    reducer_entered = Event()
    release_reducer = Event()
    reducer_values = []

    def blocking_reducer(state_data, event):
        value = event.payload["value"]
        reducer_values.append(value)
        if value == 1:
            reducer_entered.set()
            assert release_reducer.wait(2)
        return ordered_reducer(state_data, event)

    journal = journal_with_values(1)
    holder = WorldStateHolder(WorldState.initial())
    pipeline, _, _, _, _, _, handler_calls = build_pipeline(
        journal=journal,
        holder=holder,
        projector=projector_with(blocking_reducer),
    )
    results = {}

    recovery_thread = Thread(
        target=lambda: results.setdefault(
            "recovery",
            pipeline.recover_world_state(WorldStateRecoveryStrategy.CATCH_UP),
        )
    )
    dispatch_thread = Thread(
        target=lambda: results.setdefault(
            "dispatch",
            pipeline.dispatch(make_command("command-concurrent", 2)),
        )
    )
    recovery_thread.start()
    assert reducer_entered.wait(2)
    dispatch_thread.start()
    assert handler_calls == []
    release_reducer.set()
    recovery_thread.join(2)
    dispatch_thread.join(2)

    assert not recovery_thread.is_alive()
    assert not dispatch_thread.is_alive()
    assert results["recovery"].status is WorldStateRecoveryStatus.RECOVERED
    assert results["dispatch"].projection_previous_sequence == 1
    assert results["dispatch"].projection_sequence == 2
    assert reducer_values == [1, 2]
    assert handler_calls == ["command-concurrent"]
    assert holder.snapshot.data["values"] == (1, 2)


def test_concurrent_recoveries_serialize_and_second_becomes_no_action():
    reducer_entered = Event()
    release_reducer = Event()
    calls = []

    def blocking_reducer(state_data, event):
        calls.append(event.event_id)
        reducer_entered.set()
        assert release_reducer.wait(2)
        return ordered_reducer(state_data, event)

    journal = journal_with_values(1)
    holder = WorldStateHolder(WorldState.initial())
    pipeline, _, _, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=projector_with(blocking_reducer),
    )
    results = []

    def recover():
        results.append(
            pipeline.recover_world_state(
                WorldStateRecoveryStrategy.CATCH_UP
            )
        )

    first = Thread(target=recover)
    second = Thread(target=recover)
    first.start()
    assert reducer_entered.wait(2)
    second.start()
    release_reducer.set()
    first.join(2)
    second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert [result.status for result in results] == [
        WorldStateRecoveryStatus.RECOVERED,
        WorldStateRecoveryStatus.NO_ACTION,
    ]
    assert calls == ["event-existing-001"]
    assert holder.snapshot.last_sequence == 1


def test_same_thread_recovery_from_active_reducer_fails_without_deadlock():
    captured = {}
    pipeline_reference = {}

    def reentrant_reducer(state_data, event):
        captured["result"] = pipeline_reference[
            "pipeline"
        ].recover_world_state(WorldStateRecoveryStrategy.CATCH_UP)
        return ordered_reducer(state_data, event)

    pipeline, dispatcher, audit, journal, _, holder, _ = build_pipeline(
        projector=projector_with(reentrant_reducer)
    )
    pipeline_reference["pipeline"] = pipeline

    outer = pipeline.dispatch(make_command("command-reentrant-recovery", 3))
    inner = captured["result"]

    assert outer.projection_disposition is ProjectionDisposition.PROJECTED
    assert inner.status is WorldStateRecoveryStatus.UNAVAILABLE
    assert inner.resulting_sequence is None
    assert holder.snapshot.last_sequence == 1
    assert len(journal.entries) == 1
    assert len(audit.entries) == 5
    assert dispatcher.dispatch_attempted_command_ids == (
        "command-reentrant-recovery",
    )


def test_recovery_detects_changed_journal_tail_before_commit():
    journal = journal_with_values(1)

    class JournalChangingProjector(WorldStateProjector):
        def __init__(self):
            super().__init__()
            self.register_reducer(EVENT_TYPE, 1, ordered_reducer)

        def project(self, entries, state):
            result = super().project(entries, state)
            journal.append(make_event(2, "event-concurrent-change"))
            return result

    state = WorldState.initial()
    holder = WorldStateHolder(state)
    pipeline, _, audit, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=JournalChangingProjector(),
    )

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.CATCH_UP
    )

    assert result.status is WorldStateRecoveryStatus.JOURNAL_CHANGED
    assert result.captured_journal_tail_sequence == 1
    assert result.projector_status is WorldStateProjectionStatus.SUCCESS
    assert holder.snapshot is state
    assert holder.health.status is WorldStateSynchronizationStatus.OUT_OF_SYNC
    assert holder.health.journal_sequence == 2
    assert journal.tail_sequence == 2
    assert audit.entries == ()


def test_coordinator_exception_is_sanitized_and_does_not_change_state():
    journal = journal_with_values(1)
    state = WorldState.initial()
    holder = WorldStateHolder(state)
    pipeline, _, audit, _, _, _, _ = build_pipeline(
        journal=journal,
        holder=holder,
        projector=RaisingProjector(),
    )
    health_before = holder.health

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.CATCH_UP
    )
    serialized = json.dumps(result.to_dict(), sort_keys=True)

    assert result.status is WorldStateRecoveryStatus.COORDINATOR_FAILURE
    assert "raw-projector-secret" not in serialized
    assert "command-secret" not in serialized
    assert "event-secret" not in serialized
    assert holder.snapshot is state
    assert holder.health == health_before
    assert audit.entries == ()


def test_recovery_result_is_immutable_json_compatible_and_defensive():
    journal = journal_with_values(9)
    pipeline, _, _, _, _, holder, _ = build_pipeline(
        journal=journal,
        holder=WorldStateHolder(WorldState.initial()),
    )

    result = pipeline.recover_world_state(
        WorldStateRecoveryStrategy.CATCH_UP
    )
    serialized = result.to_dict()

    assert isinstance(result, WorldStateRecoveryResult)
    assert json.loads(json.dumps(serialized)) == serialized
    assert set(serialized) == {
        "captured_journal_tail_sequence",
        "error",
        "previous_sequence",
        "projector_reason",
        "projector_status",
        "resulting_sequence",
        "status",
        "strategy",
    }
    assert "data" not in serialized
    assert "events" not in serialized
    serialized["resulting_sequence"] = 999
    assert result.to_dict()["resulting_sequence"] == 1
    assert holder.snapshot.data["values"] == (9,)
    with pytest.raises(FrozenInstanceError):
        result.status = WorldStateRecoveryStatus.NO_ACTION


def test_recovery_api_accepts_no_caller_supplied_event_snapshot():
    parameters = inspect.signature(
        AuditedCommandPipeline.recover_world_state
    ).parameters
    pipeline, _, _, _, _, _, _ = build_pipeline()

    assert tuple(parameters) == ("self", "strategy", "base_state")
    with pytest.raises(TypeError):
        pipeline.recover_world_state(
            WorldStateRecoveryStrategy.CATCH_UP,
            entries=(),
        )
    with pytest.raises(TypeError):
        pipeline.recover_world_state("catch_up")
