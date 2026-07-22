import json
import sqlite3
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from .command import CommandProvenance, CommandSource
from .event_journal_store import EventJournalStore, EventJournalStoreStatus
from .game_event import GameEvent
from .journals import GameEventJournal, GameEventJournalEntry
from .startup_hydration import (
    StartupHydrationStatus,
    hydrate_durable_runtime,
)
from .world_state import WorldState, WorldStateProjector


JOURNAL_ID = "hydration-journal-001"
OCCURRED_AT = datetime(2026, 7, 22, 12, 30, 45, 123456, timezone.utc)
PROVENANCE = CommandProvenance(CommandSource.SYSTEM, "hydration-test")


def event(number):
    return GameEvent(
        event_id=f"hydration-event-{number}",
        event_type="test.hydration_value",
        schema_version=1,
        payload={"value": number, "private": f"secret-{number}"},
        provenance=PROVENANCE,
        originating_command_id=f"hydration-command-{number}",
        occurred_at=OCCURRED_AT,
    )


def entries(count):
    return tuple(GameEventJournalEntry(index, event(index)) for index in range(1, count + 1))


def projector_with_calls(calls=None, *, fail=False):
    projector = WorldStateProjector()

    def reducer(state_data, item):
        if calls is not None:
            calls.append(item.event_id)
        if fail:
            raise RuntimeError("private reducer details")
        return {
            "base": state_data["base"],
            "values": [*state_data.get("values", ()), item.payload["value"]],
        }

    projector.register_reducer("test.hydration_value", 1, reducer)
    return projector


def initialized_store(tmp_path, count=0):
    store = EventJournalStore(tmp_path / "journal.sqlite")
    assert store.initialize(journal_id=JOURNAL_ID).status is EventJournalStoreStatus.SUCCESS
    if count:
        assert store.append(entries(count), expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS
    return store


class TrackingStore(EventJournalStore):
    def __init__(self, path):
        super().__init__(path)
        self.append_calls = 0
        self.loaded_result = None

    def append(self, entries, *, expected_tail_sequence, expected_journal_id=None):
        self.append_calls += 1
        return super().append(
            entries,
            expected_tail_sequence=expected_tail_sequence,
            expected_journal_id=expected_journal_id,
        )

    def load(self):
        self.loaded_result = super().load()
        return self.loaded_result


class FailingLoadStore(EventJournalStore):
    def load(self):
        raise RuntimeError("raw filesystem or sqlite secret")


def hydrate(store, projector=None, base_state=None, expected_id=JOURNAL_ID):
    return hydrate_durable_runtime(
        store,
        expected_journal_id=expected_id,
        base_state=(
            WorldState({"base": "explicit", "values": []})
            if base_state is None
            else base_state
        ),
        projector=projector_with_calls() if projector is None else projector,
    )


def test_missing_database_is_not_initialized_or_exposed(tmp_path):
    path = tmp_path / "missing.sqlite"

    result = hydrate(EventJournalStore(path))

    assert result.status is StartupHydrationStatus.NOT_FOUND
    assert result.runtime is None
    assert not path.exists()


def test_initialized_empty_database_hydrates_explicit_base_without_reducer(tmp_path):
    store = initialized_store(tmp_path)
    calls = []
    base = WorldState({"base": "caller-owned", "values": []})

    result = hydrate(store, projector_with_calls(calls), base)

    assert result.status is StartupHydrationStatus.SUCCESS
    assert result.tail_sequence == 0
    assert calls == []
    assert result.runtime.event_journal.entries == ()
    assert result.runtime.state_holder.snapshot is base
    assert result.runtime.state_holder.health.to_dict() == {
        "committed_sequence": 0,
        "journal_sequence": 0,
        "projector_status": None,
        "reason_code": None,
        "status": "synchronized",
    }


@pytest.mark.parametrize("count", [1, 3], ids=["one-event", "multi-event"])
def test_hydration_reconstructs_exact_ordered_entries_and_state(tmp_path, count):
    original_store = initialized_store(tmp_path, count)
    before = original_store.load().entries
    calls = []
    reopened = EventJournalStore(original_store.path)

    result = hydrate(reopened, projector_with_calls(calls))

    assert result.status is StartupHydrationStatus.SUCCESS
    runtime = result.runtime
    assert runtime.event_journal.entries == before
    assert runtime.event_journal.tail_sequence == count
    assert runtime.state_holder.snapshot.last_sequence == count
    assert runtime.state_holder.snapshot.to_dict()["data"] == {
        "base": "explicit",
        "values": list(range(1, count + 1)),
    }
    assert calls == [f"hydration-event-{index}" for index in range(1, count + 1)]
    assert runtime.durable_binding.journal_id == JOURNAL_ID
    assert runtime.durable_binding.tail_sequence == count


def test_hydration_preserves_loaded_entry_objects_ids_times_and_payloads(tmp_path):
    path = tmp_path / "tracked.sqlite"
    initial = EventJournalStore(path)
    assert initial.initialize(journal_id=JOURNAL_ID).status is EventJournalStoreStatus.SUCCESS
    assert initial.append(entries(2), expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS
    store = TrackingStore(path)

    result = hydrate(store)

    assert result.status is StartupHydrationStatus.SUCCESS
    loaded_entries = store.loaded_result.entries
    hydrated_entries = result.runtime.event_journal.entries
    assert all(actual is loaded for actual, loaded in zip(hydrated_entries, loaded_entries))
    assert [item.to_dict() for item in hydrated_entries] == [
        item.to_dict() for item in entries(2)
    ]
    assert store.append_calls == 0


def test_hydration_rejects_exact_journal_id_mismatch_without_runtime(tmp_path):
    store = initialized_store(tmp_path, 1)

    result = hydrate(store, expected_id="different-journal")

    assert result.status is StartupHydrationStatus.JOURNAL_ID_MISMATCH
    assert result.journal_id == JOURNAL_ID
    assert result.runtime is None


@pytest.mark.parametrize(
    ("mutation", "expected_status"),
    [
        (
            "UPDATE metadata SET value = 99 WHERE key = 'schema_version'",
            StartupHydrationStatus.UNSUPPORTED_VERSION,
        ),
        (
            "UPDATE metadata SET value = 'bad' WHERE key = 'schema_version'",
            StartupHydrationStatus.CORRUPT,
        ),
        (
            "UPDATE entries SET integrity_digest = 'bad' WHERE sequence = 1",
            StartupHydrationStatus.CORRUPT,
        ),
    ],
)
def test_corrupt_or_unsupported_storage_fails_closed(tmp_path, mutation, expected_status):
    store = initialized_store(tmp_path, 1)
    with sqlite3.connect(store.path) as connection:
        connection.execute(mutation)
        connection.commit()

    result = hydrate(store)

    assert result.status is expected_status
    assert result.runtime is None


def test_storage_contract_failure_is_sanitized_and_exposes_no_runtime(tmp_path):
    result = hydrate(FailingLoadStore(tmp_path / "failure.sqlite"))

    assert result.status is StartupHydrationStatus.STORAGE_FAILURE
    assert result.runtime is None
    serialized = json.dumps(result.to_dict())
    assert "filesystem" not in serialized
    assert "sqlite" not in serialized.lower()
    assert str(tmp_path) not in serialized


@pytest.mark.parametrize(
    ("base_state", "reason"),
    [
        (None, "missing_base_state"),
        (object(), "missing_base_state"),
        (WorldState({"base": "bad"}, last_sequence=1), "nonzero_base_state"),
    ],
)
def test_hydration_requires_explicit_valid_sequence_zero_base(tmp_path, base_state, reason):
    store = initialized_store(tmp_path)

    result = hydrate_durable_runtime(
        store,
        expected_journal_id=JOURNAL_ID,
        base_state=base_state,
        projector=projector_with_calls(),
    )

    assert result.status is StartupHydrationStatus.INVALID_INPUT
    assert result.reason_code == reason
    assert result.runtime is None


def test_projection_failure_exposes_no_partial_runtime_or_state(tmp_path):
    store = initialized_store(tmp_path, 2)

    result = hydrate(store, projector_with_calls(fail=True))

    assert result.status is StartupHydrationStatus.PROJECTION_FAILURE
    assert result.tail_sequence == 2
    assert result.runtime is None
    serialized = json.dumps(result.to_dict())
    assert "private reducer details" not in serialized
    assert "secret-1" not in serialized


def test_unknown_event_projection_failure_is_controlled(tmp_path):
    store = initialized_store(tmp_path, 1)

    result = hydrate(store, WorldStateProjector())

    assert result.status is StartupHydrationStatus.PROJECTION_FAILURE
    assert result.reason_code == "unknown_event_type"
    assert result.runtime is None


def test_runtime_initialization_failure_is_controlled_and_all_or_nothing(
    tmp_path,
    monkeypatch,
):
    store = initialized_store(tmp_path, 1)

    def fail_reconstruction(cls, snapshot):
        raise RuntimeError("private reconstruction failure")

    monkeypatch.setattr(
        GameEventJournal,
        "from_snapshot",
        classmethod(fail_reconstruction),
    )

    result = hydrate(store)

    assert result.status is StartupHydrationStatus.INITIALIZATION_FAILURE
    assert result.runtime is None
    assert "private reconstruction" not in json.dumps(result.to_dict())


def test_hydration_does_not_append_or_rewrite_durable_rows(tmp_path):
    store = initialized_store(tmp_path, 2)
    with sqlite3.connect(store.path) as connection:
        before = connection.execute(
            "SELECT sequence, event_id, event_json, integrity_digest "
            "FROM entries ORDER BY sequence"
        ).fetchall()

    result = hydrate(EventJournalStore(store.path))

    with sqlite3.connect(store.path) as connection:
        after = connection.execute(
            "SELECT sequence, event_id, event_json, integrity_digest "
            "FROM entries ORDER BY sequence"
        ).fetchall()
    assert result.status is StartupHydrationStatus.SUCCESS
    assert after == before


def test_hydration_result_is_immutable_defensive_and_payload_free(tmp_path):
    store = initialized_store(tmp_path, 1)
    result = hydrate(store)

    with pytest.raises(FrozenInstanceError):
        result.tail_sequence = 99
    serialized = result.to_dict()
    serialized["tail_sequence"] = 99
    fresh = result.to_dict()

    assert fresh["tail_sequence"] == 1
    assert "runtime" not in fresh
    assert "entries" not in fresh
    assert "state" not in fresh
    assert "secret-1" not in json.dumps(fresh)
    assert json.loads(json.dumps(fresh, allow_nan=False)) == fresh
