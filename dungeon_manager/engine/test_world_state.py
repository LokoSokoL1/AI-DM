from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from .command import CommandProvenance, CommandSource
from .game_event import GameEvent
from .journals import GameEventJournal, GameEventJournalEntry
from .world_state import (
    ReducerRegistration,
    WorldState,
    WorldStateProjectionResult,
    WorldStateProjectionStatus,
    WorldStateProjector,
)


PROVENANCE = CommandProvenance(CommandSource.SYSTEM, "projection-test")
OCCURRED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def game_event(
    number: int,
    *,
    event_type: str = "counter.changed",
    schema_version: int = 1,
    event_id: str | None = None,
    payload: dict | None = None,
) -> GameEvent:
    return GameEvent(
        event_type=event_type,
        schema_version=schema_version,
        provenance=PROVENANCE,
        payload={"amount": number} if payload is None else payload,
        occurred_at=OCCURRED_AT,
        event_id=f"event-{number}" if event_id is None else event_id,
    )


def journal_entry(
    sequence: int,
    *,
    event_type: str = "counter.changed",
    schema_version: int = 1,
    event_id: str | None = None,
    amount: int | None = None,
) -> GameEventJournalEntry:
    value = sequence if amount is None else amount
    return GameEventJournalEntry(
        sequence,
        game_event(
            value,
            event_type=event_type,
            schema_version=schema_version,
            event_id=(
                f"event-{sequence}" if event_id is None else event_id
            ),
        ),
    )


def counter_reducer(state, event):
    return {
        "count": state.get("count", 0) + event.payload["amount"],
        "applied": [*state.get("applied", ()), event.event_id],
    }


def counter_projector() -> WorldStateProjector:
    projector = WorldStateProjector()
    projector.register_reducer("counter.changed", 1, counter_reducer)
    return projector


def assert_success(result: WorldStateProjectionResult) -> WorldState:
    assert result.status is WorldStateProjectionStatus.SUCCESS
    assert result.error is None
    assert result.state is not None
    return result.state


def test_world_state_deeply_freezes_a_defensive_copy():
    source = {"region": {"names": ["north", {"active": True}]}}

    state = WorldState(source, last_sequence=4)
    source["region"]["names"][0] = "changed"
    source["region"]["names"][1]["active"] = False

    assert isinstance(state.data, MappingProxyType)
    assert isinstance(state.data["region"], MappingProxyType)
    assert state.data["region"]["names"] == (
        "north",
        MappingProxyType({"active": True}),
    )
    with pytest.raises(TypeError):
        state.data["new"] = "value"
    with pytest.raises(TypeError):
        state.data["region"]["names"][1]["active"] = False


def test_world_state_serialization_is_defensive_and_json_compatible():
    state = WorldState(
        {"region": {"names": ["north"]}},
        last_sequence=3,
    )

    serialized = state.to_dict()
    serialized["data"]["region"]["names"].append("south")
    serialized["last_sequence"] = 99

    assert state.to_dict() == {
        "data": {"region": {"names": ["north"]}},
        "last_sequence": 3,
    }


@pytest.mark.parametrize("sequence", [-1, True, 1.5, "1"])
def test_world_state_rejects_invalid_sequences(sequence):
    with pytest.raises(ValueError, match="non-negative integer"):
        WorldState({}, last_sequence=sequence)


@pytest.mark.parametrize("data", [[], "state", {"bad": object()}])
def test_world_state_requires_a_json_object(data):
    with pytest.raises(ValueError, match="JSON object|JSON-compatible"):
        WorldState(data)


def test_initial_state_and_empty_replay_succeed_at_sequence_zero():
    initial = WorldState.initial()
    result = WorldStateProjector().replay(())
    state = assert_success(result)

    assert initial.to_dict() == {"data": {}, "last_sequence": 0}
    assert state.to_dict() == initial.to_dict()


def test_empty_incremental_projection_returns_the_unchanged_state():
    state = WorldState({"count": 7}, last_sequence=11)

    result = WorldStateProjector().project((), state)

    assert assert_success(result) is state


def test_one_event_full_replay():
    state = assert_success(counter_projector().replay((journal_entry(1),)))

    assert state.to_dict() == {
        "data": {"count": 1, "applied": ["event-1"]},
        "last_sequence": 1,
    }


def test_multiple_events_apply_in_journal_order():
    entries = (
        journal_entry(1, amount=3),
        journal_entry(2, amount=-1),
        journal_entry(3, amount=4),
    )

    state = assert_success(counter_projector().replay(entries))

    assert state.to_dict() == {
        "data": {
            "count": 6,
            "applied": ["event-1", "event-2", "event-3"],
        },
        "last_sequence": 3,
    }


def test_incremental_projection_starts_after_existing_state():
    projector = counter_projector()
    first = assert_success(projector.replay((journal_entry(1),)))

    second = assert_success(
        projector.project(
            (journal_entry(2, amount=5), journal_entry(3, amount=2)),
            first,
        )
    )

    assert first.to_dict()["data"]["count"] == 1
    assert second.to_dict() == {
        "data": {
            "count": 8,
            "applied": ["event-1", "event-2", "event-3"],
        },
        "last_sequence": 3,
    }


def test_repeat_projection_is_deterministic():
    entries = (journal_entry(1), journal_entry(2))
    projector = counter_projector()

    first = assert_success(projector.replay(entries))
    second = assert_success(projector.replay(entries))

    assert first is not second
    assert first.to_dict() == second.to_dict()


def test_event_type_matching_is_exact_and_case_sensitive():
    projector = counter_projector()

    result = projector.replay(
        (journal_entry(1, event_type="Counter.changed"),)
    )

    assert result.status is WorldStateProjectionStatus.UNKNOWN_EVENT_TYPE
    assert result.state is None


def test_schema_version_matching_is_exact_and_authoritative():
    projector = WorldStateProjector()
    projector.register_reducer("counter.changed", 2, counter_reducer)

    result = projector.replay((journal_entry(1, schema_version=1),))

    assert (
        result.status
        is WorldStateProjectionStatus.UNSUPPORTED_SCHEMA_VERSION
    )
    assert result.state is None


def test_duplicate_reducer_registration_is_rejected_without_replacement():
    projector = counter_projector()

    with pytest.raises(ValueError, match="Duplicate"):
        projector.register_reducer("counter.changed", 1, lambda state, event: {})

    state = assert_success(projector.replay((journal_entry(1),)))
    assert state.data["count"] == 1


@pytest.mark.parametrize(
    ("event_type", "schema_version"),
    [
        ("", 1),
        (" counter.changed", 1),
        (42, 1),
        ("counter.changed", 0),
        ("counter.changed", True),
        ("counter.changed", "1"),
    ],
)
def test_registration_metadata_must_be_exact_and_well_formed(
    event_type,
    schema_version,
):
    with pytest.raises(ValueError):
        WorldStateProjector().register_reducer(
            event_type,
            schema_version,
            counter_reducer,
        )


def no_parameters():
    return {}


def one_parameter(state):
    return state


def three_parameters(state, event, extra):
    return state


def positional_only(state, event, /):
    return state


def keyword_only(*, state, event):
    return state


def variadic(state, event, *extra):
    return state


def defaulted(state, event=None):
    return state


async def asynchronous(state, event):
    return state


class UninspectableReducer:
    @property
    def __signature__(self):
        raise ValueError("hidden signature")

    def __call__(self, state, event):
        return state


@pytest.mark.parametrize(
    "reducer",
    [
        None,
        no_parameters,
        one_parameter,
        three_parameters,
        positional_only,
        keyword_only,
        variadic,
        defaulted,
        asynchronous,
        UninspectableReducer(),
    ],
)
def test_malformed_reducer_signatures_are_rejected(reducer):
    with pytest.raises(ValueError, match="reducer"):
        WorldStateProjector().register_reducer(
            "counter.changed",
            1,
            reducer,
        )


def test_unknown_event_type_fails_closed_with_safe_diagnostics():
    entry = journal_entry(
        1,
        event_type="secret.event",
        amount=12345,
    )

    result = WorldStateProjector().replay((entry,))

    assert result.status is WorldStateProjectionStatus.UNKNOWN_EVENT_TYPE
    assert result.state is None
    assert result.to_dict() == {
        "status": "unknown_event_type",
        "error": "No world-state reducer is registered for this event type.",
        "sequence": 1,
        "event_id": "event-1",
        "event_type": "secret.event",
        "schema_version": 1,
    }
    assert "12345" not in str(result.to_dict())


def test_invalid_journal_entry_type_is_a_controlled_failure():
    result = counter_projector().replay((game_event(1),))

    assert (
        result.status
        is WorldStateProjectionStatus.INVALID_ENTRY_OR_SEQUENCE
    )
    assert result.state is None


@pytest.mark.parametrize(
    ("state", "entries"),
    [
        (WorldState.initial(), (journal_entry(2),)),
        (WorldState({"count": 4}, last_sequence=4), (journal_entry(4),)),
        (
            WorldState.initial(),
            (journal_entry(1), journal_entry(3)),
        ),
        (
            WorldState.initial(),
            (
                journal_entry(1),
                journal_entry(1, event_id="event-other"),
            ),
        ),
        (
            WorldState.initial(),
            (
                journal_entry(1),
                journal_entry(3),
                journal_entry(2),
            ),
        ),
    ],
)
def test_incorrect_start_gap_duplicate_and_out_of_order_sequences_fail(
    state,
    entries,
):
    result = counter_projector().project(entries, state)

    assert (
        result.status
        is WorldStateProjectionStatus.INVALID_ENTRY_OR_SEQUENCE
    )
    assert result.state is None
    assert state.to_dict()["last_sequence"] in {0, 4}


def test_duplicate_event_ids_within_the_batch_fail_before_reducing():
    calls = 0

    def reducer(state, event):
        nonlocal calls
        calls += 1
        return state

    projector = WorldStateProjector()
    projector.register_reducer("counter.changed", 1, reducer)
    entries = (
        journal_entry(1, event_id="duplicate"),
        journal_entry(2, event_id="duplicate"),
    )

    result = projector.replay(entries)

    assert (
        result.status
        is WorldStateProjectionStatus.INVALID_ENTRY_OR_SEQUENCE
    )
    assert result.state is None
    assert calls == 0


def test_complete_sequence_validation_precedes_every_reducer_invocation():
    calls = 0

    def reducer(state, event):
        nonlocal calls
        calls += 1
        return state

    projector = WorldStateProjector()
    projector.register_reducer("counter.changed", 1, reducer)

    result = projector.replay((journal_entry(1), journal_entry(3)))

    assert (
        result.status
        is WorldStateProjectionStatus.INVALID_ENTRY_OR_SEQUENCE
    )
    assert calls == 0


def test_every_reducer_is_resolved_before_any_event_is_applied():
    calls = 0

    def reducer(state, event):
        nonlocal calls
        calls += 1
        return state

    projector = WorldStateProjector()
    projector.register_reducer("counter.changed", 1, reducer)
    entries = (
        journal_entry(1),
        journal_entry(2, event_type="unknown.event"),
    )

    result = projector.replay(entries)

    assert result.status is WorldStateProjectionStatus.UNKNOWN_EVENT_TYPE
    assert calls == 0


def test_reducers_run_once_each_in_sequence_order():
    calls = []

    def reducer(state, event):
        calls.append(event.event_id)
        return {"calls": [*state.get("calls", ()), event.event_id]}

    projector = WorldStateProjector()
    projector.register_reducer("counter.changed", 1, reducer)
    entries = tuple(journal_entry(sequence) for sequence in range(1, 4))

    state = assert_success(projector.replay(entries))

    assert calls == ["event-1", "event-2", "event-3"]
    assert state.to_dict()["data"]["calls"] == calls


def test_reducer_may_return_unchanged_state_but_sequence_advances():
    state = WorldState({"stable": True}, last_sequence=0)
    projector = WorldStateProjector()
    projector.register_reducer(
        "counter.changed",
        1,
        lambda current, event: current,
    )

    completed = assert_success(projector.project((journal_entry(1),), state))

    assert completed is not state
    assert completed.to_dict() == {
        "data": {"stable": True},
        "last_sequence": 1,
    }


@pytest.mark.parametrize("output", [[], "state", 7, None])
def test_non_object_reducer_output_is_invalid(output):
    projector = WorldStateProjector()
    projector.register_reducer(
        "counter.changed",
        1,
        lambda state, event: output,
    )

    result = projector.replay((journal_entry(1),))

    assert (
        result.status
        is WorldStateProjectionStatus.INVALID_REDUCER_RESULT
    )
    assert result.state is None


def test_non_json_reducer_output_is_invalid_and_not_exposed():
    projector = WorldStateProjector()
    projector.register_reducer(
        "counter.changed",
        1,
        lambda state, event: {"hidden": object()},
    )

    result = projector.replay((journal_entry(1),))

    assert (
        result.status
        is WorldStateProjectionStatus.INVALID_REDUCER_RESULT
    )
    assert result.state is None
    assert "object at" not in str(result.to_dict())
    assert "hidden" not in str(result.to_dict())


def test_reducer_outputs_are_defensively_copied_and_deeply_frozen():
    retained = {"nested": {"values": [1]}}
    projector = WorldStateProjector()
    projector.register_reducer(
        "counter.changed",
        1,
        lambda state, event: retained,
    )

    state = assert_success(projector.replay((journal_entry(1),)))
    retained["nested"]["values"].append(2)

    assert state.to_dict()["data"] == {"nested": {"values": [1]}}
    with pytest.raises(TypeError):
        state.data["nested"]["new"] = True


def test_reducer_exception_is_sanitized_and_never_retried(caplog):
    calls = 0

    def reducer(state, event):
        nonlocal calls
        calls += 1
        raise RuntimeError("credential=secret payload=hidden")

    projector = WorldStateProjector()
    projector.register_reducer("counter.changed", 1, reducer)

    result = projector.replay((journal_entry(1, amount=987654),))

    assert result.status is WorldStateProjectionStatus.REDUCER_FAILURE
    assert result.state is None
    assert result.error == "The world-state reducer failed."
    assert calls == 1
    serialized = str(result.to_dict())
    assert "credential" not in serialized
    assert "secret" not in serialized
    assert "hidden" not in serialized
    assert "987654" not in serialized


def test_later_reducer_failure_exposes_no_partial_state():
    start = WorldState({"untouched": [1]}, last_sequence=0)
    first_output = {"partially": "applied"}
    calls = []

    def first(state, event):
        calls.append("first")
        return first_output

    def second(state, event):
        calls.append("second")
        assert state["partially"] == "applied"
        raise RuntimeError("later failure")

    projector = WorldStateProjector()
    projector.register_reducer("first.event", 1, first)
    projector.register_reducer("second.event", 1, second)
    entries = (
        journal_entry(1, event_type="first.event"),
        journal_entry(2, event_type="second.event"),
    )

    result = projector.project(entries, start)

    assert result.status is WorldStateProjectionStatus.REDUCER_FAILURE
    assert result.state is None
    assert calls == ["first", "second"]
    assert start.to_dict() == {
        "data": {"untouched": [1]},
        "last_sequence": 0,
    }


def test_projection_preserves_starting_state_journal_entries_and_events():
    journal = GameEventJournal()
    event_one = game_event(1, payload={"amount": 2, "nested": ["safe"]})
    event_two = game_event(2, payload={"amount": 3, "nested": ["safe"]})
    appended = journal.append_batch((event_one, event_two))
    start = WorldState({"count": 10}, last_sequence=0)
    start_before = start.to_dict()
    journal_before = journal.to_list()
    entry_ids_before = tuple(id(entry) for entry in journal.entries)

    result = counter_projector().project(journal.entries, start)

    assert assert_success(result).data["count"] == 15
    assert start.to_dict() == start_before
    assert journal.to_list() == journal_before
    assert journal.entries == appended
    assert tuple(id(entry) for entry in journal.entries) == entry_ids_before
    assert appended[0].event is event_one
    assert appended[1].event is event_two


def test_registration_snapshot_is_sorted_immutable_and_independent():
    projector = WorldStateProjector()
    projector.register_reducer("z.event", 2, counter_reducer)
    projector.register_reducer("a.event", 3, counter_reducer)
    projector.register_reducer("a.event", 1, counter_reducer)

    snapshot = projector.registrations
    projector.register_reducer("m.event", 1, counter_reducer)

    assert snapshot == (
        ReducerRegistration("a.event", 1),
        ReducerRegistration("a.event", 3),
        ReducerRegistration("z.event", 2),
    )
    assert projector.registrations == (
        ReducerRegistration("a.event", 1),
        ReducerRegistration("a.event", 3),
        ReducerRegistration("m.event", 1),
        ReducerRegistration("z.event", 2),
    )
    with pytest.raises(TypeError):
        snapshot[0] = ReducerRegistration("changed", 1)
    with pytest.raises(FrozenInstanceError):
        snapshot[0].event_type = "changed"


def test_projection_result_serialization_is_defensive():
    result = counter_projector().replay((journal_entry(1),))
    serialized = result.to_dict()
    serialized["state"]["data"]["applied"].append("changed")
    serialized["state"]["last_sequence"] = 100

    assert result.to_dict()["state"] == {
        "data": {"count": 1, "applied": ["event-1"]},
        "last_sequence": 1,
    }


def test_event_publication_does_not_automatically_run_projection():
    calls = 0

    def reducer(state, event):
        nonlocal calls
        calls += 1
        return state

    projector = WorldStateProjector()
    projector.register_reducer("counter.changed", 1, reducer)
    journal = GameEventJournal()

    journal.append(game_event(1))

    assert calls == 0
    assert journal.entries[0].sequence == 1
    assert_success(projector.replay(journal.entries))
    assert calls == 1
