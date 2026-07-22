import json
import sqlite3
import uuid
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from .command import CommandProvenance, CommandSource
from .event_journal_store import (
    EVENT_JOURNAL_STORAGE_FORMAT,
    EVENT_JOURNAL_STORAGE_SCHEMA_VERSION,
    EventJournalStore,
    EventJournalStoreStatus,
    _entry_digest,
)
from .game_event import GameEvent
from .journals import GameEventJournalEntry


OCCURRED_AT = datetime(2026, 7, 22, 11, 12, 13, 456789, timezone.utc)
PROVENANCE = CommandProvenance(CommandSource.SYSTEM, "durable-store-test")


def event(number, **overrides):
    values = {
        "event_id": f"event-{number}",
        "event_type": "world.location_revealed",
        "occurred_at": OCCURRED_AT,
        "payload": {"number": number},
        "provenance": PROVENANCE,
        "schema_version": 1,
    }
    values.update(overrides)
    return GameEvent(**values)


def entry(sequence, **overrides):
    return GameEventJournalEntry(sequence, event(sequence, **overrides))


def store_path(tmp_path):
    return tmp_path / "event-journal.sqlite"


def initialized_store(tmp_path, journal_id="journal-test-001"):
    store = EventJournalStore(store_path(tmp_path))
    result = store.initialize(journal_id=journal_id)
    assert result.status is EventJournalStoreStatus.SUCCESS
    return store


def raw_connection(path: Path):
    return sqlite3.connect(path)


def insert_raw_entry(connection, sequence, event_id, event_json, digest=None):
    connection.execute(
        "INSERT INTO entries(sequence, event_id, event_json, integrity_digest) "
        "VALUES (?, ?, ?, ?)",
        (
            sequence,
            event_id,
            event_json,
            _entry_digest(sequence, event_json) if digest is None else digest,
        ),
    )
    connection.commit()


def test_missing_database_is_not_an_implicit_empty_journal(tmp_path):
    store = EventJournalStore(store_path(tmp_path))

    for result in (store.load(), store.append((), expected_tail_sequence=0)):
        assert result.status is EventJournalStoreStatus.NOT_FOUND
        assert result.entries is None


def test_explicit_initialization_and_deterministic_journal_identity(tmp_path):
    store = initialized_store(tmp_path, "campaign-stream-001")

    loaded = store.load()
    assert loaded.status is EventJournalStoreStatus.SUCCESS
    assert loaded.journal_id == "campaign-stream-001"
    assert loaded.entries == ()
    assert loaded.tail_sequence == 0


def test_generated_journal_identity_is_a_valid_uuid(tmp_path):
    result = EventJournalStore(store_path(tmp_path)).initialize()

    assert result.status is EventJournalStoreStatus.SUCCESS
    assert result.journal_id is not None
    assert str(uuid.UUID(result.journal_id)) == result.journal_id


def test_reinitialization_is_rejected_without_replacing_existing_metadata(tmp_path):
    store = initialized_store(tmp_path, "first-journal")

    result = store.initialize(journal_id="replacement-journal")
    assert result.status is EventJournalStoreStatus.ALREADY_EXISTS
    assert store.load().journal_id == "first-journal"


def test_one_and_multiple_entries_round_trip_in_sequence_order(tmp_path):
    store = initialized_store(tmp_path)
    first = entry(1)
    second = entry(2, payload={"nested": ["safe", {"value": True}]})

    one = store.append((first,), expected_tail_sequence=0)
    many = store.append((second,), expected_tail_sequence=1)
    loaded = store.load()

    assert one.appended_count == 1
    assert many.appended_count == 1
    assert loaded.entries == (first, second)
    assert loaded.tail_sequence == 2


def test_complete_game_event_round_trip_uses_strict_constructor_decoding(tmp_path):
    store = initialized_store(tmp_path)
    complete = GameEventJournalEntry(
        1,
        event(
            "complete",
            actor_id="npc-17",
            event_id="event-complete",
            event_type="world.Location_Revealed",
            originating_command_id="command-17",
            payload={"nested": [{"flag": False}], "none": None},
            provenance=CommandProvenance(CommandSource.AI, "local-model"),
            schema_version=7,
        ),
    )

    assert store.append((complete,), expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS
    loaded = store.load()
    assert loaded.entries == (complete,)
    assert loaded.entries[0].event.to_dict() == complete.event.to_dict()


def test_store_closes_and_reopens_across_instances(tmp_path):
    path = store_path(tmp_path)
    first_store = EventJournalStore(path)
    assert first_store.initialize(journal_id="reopen-journal").status is EventJournalStoreStatus.SUCCESS
    assert first_store.append((entry(1), entry(2)), expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS

    reopened = EventJournalStore(path).load()
    assert reopened.status is EventJournalStoreStatus.SUCCESS
    assert tuple(item.sequence for item in reopened.entries) == (1, 2)


def test_atomic_multi_entry_append_and_matching_empty_no_op(tmp_path):
    store = initialized_store(tmp_path)

    appended = store.append((entry(1), entry(2), entry(3)), expected_tail_sequence=0)
    no_op = store.append((), expected_tail_sequence=3)

    assert appended.tail_sequence == 3
    assert appended.appended_count == 3
    assert no_op.status is EventJournalStoreStatus.SUCCESS
    assert no_op.previous_tail == no_op.tail_sequence == 3
    assert no_op.appended_count == 0


def test_empty_append_and_competing_store_reject_stale_tail(tmp_path):
    path = store_path(tmp_path)
    first = EventJournalStore(path)
    second = EventJournalStore(path)
    assert first.initialize(journal_id="shared-journal").status is EventJournalStoreStatus.SUCCESS
    assert first.append((entry(1),), expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS

    empty = second.append((), expected_tail_sequence=0)
    competing = second.append((entry(1, event_id="event-competition"),), expected_tail_sequence=0)

    assert empty.status is EventJournalStoreStatus.STALE_TAIL
    assert competing.status is EventJournalStoreStatus.STALE_TAIL
    assert first.load().tail_sequence == 1


def test_expected_journal_identity_mismatch_rejects_before_append(tmp_path):
    store = initialized_store(tmp_path, "actual-journal")

    result = store.append(
        (entry(1),),
        expected_tail_sequence=0,
        expected_journal_id="different-journal",
    )

    assert result.status is EventJournalStoreStatus.JOURNAL_ID_MISMATCH
    assert result.journal_id == "actual-journal"
    assert result.appended_count == 0
    assert store.load().entries == ()


@pytest.mark.parametrize(
    "entries",
    [
        (entry(2),),
        (entry(1), entry(3)),
        (entry(1), entry(1, event_id="event-other")),
    ],
    ids=["invalid-start", "gap", "duplicate-sequence"],
)
def test_invalid_sequence_ranges_are_rejected_before_mutation(tmp_path, entries):
    store = initialized_store(tmp_path)

    result = store.append(entries, expected_tail_sequence=0)
    assert result.status is EventJournalStoreStatus.INVALID_INPUT
    assert store.load().entries == ()


def test_duplicate_ids_within_and_against_durable_history_are_atomic(tmp_path):
    store = initialized_store(tmp_path)
    duplicate = entry(2, event_id="event-1")

    within = store.append((entry(1), entry(2, event_id="event-1")), expected_tail_sequence=0)
    assert within.status is EventJournalStoreStatus.INVALID_INPUT
    assert store.append((entry(1),), expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS

    against_history = store.append((duplicate,), expected_tail_sequence=1)
    assert against_history.status is EventJournalStoreStatus.INVALID_INPUT
    assert store.load().entries == (entry(1),)


def test_invalid_entry_values_and_unordered_batches_fail_safely(tmp_path):
    store = initialized_store(tmp_path)

    results = (
        store.append(None, expected_tail_sequence=0),
        store.append({"not-an-entry"}, expected_tail_sequence=0),
        store.append((event(1),), expected_tail_sequence=0),
        store.append((entry(1),), expected_tail_sequence=True),
    )
    assert all(item.status is EventJournalStoreStatus.INVALID_INPUT for item in results)
    assert store.load().entries == ()


def test_later_insert_failure_rolls_back_every_prior_batch_row(tmp_path):
    store = initialized_store(tmp_path)
    with raw_connection(store.path) as connection:
        connection.execute(
            "CREATE TRIGGER fail_second_insert BEFORE INSERT ON entries "
            "WHEN NEW.sequence = 2 BEGIN SELECT RAISE(ABORT, 'secret failure'); END"
        )
        connection.commit()

    result = store.append(
        (entry(1), entry(2)),
        expected_tail_sequence=0,
    )
    assert result.status is EventJournalStoreStatus.STORAGE_FAILURE
    assert store.load().entries == ()


def test_unsupported_version_and_malformed_metadata_fail_closed(tmp_path):
    store = initialized_store(tmp_path)
    with raw_connection(store.path) as connection:
        connection.execute("UPDATE metadata SET value = 99 WHERE key = 'schema_version'")
        connection.commit()

    unsupported = store.load()
    assert unsupported.status is EventJournalStoreStatus.UNSUPPORTED_VERSION
    assert unsupported.entries is None

    with raw_connection(store.path) as connection:
        connection.execute("UPDATE metadata SET value = 'bad' WHERE key = 'schema_version'")
        connection.commit()

    malformed = store.load()
    assert malformed.status is EventJournalStoreStatus.CORRUPT
    assert malformed.entries is None


def test_unsupported_format_is_reported_without_migration(tmp_path):
    store = initialized_store(tmp_path)
    with raw_connection(store.path) as connection:
        connection.execute("UPDATE metadata SET value = 'other.format' WHERE key = 'format'")
        connection.commit()

    result = store.load()
    assert result.status is EventJournalStoreStatus.UNSUPPORTED_VERSION
    assert result.reason_code == "unsupported_format"


@pytest.mark.parametrize(
    "event_json",
    [
        "{not json",
        json.dumps({"event_id": "only-one-field"}, separators=(",", ":")),
    ],
    ids=["malformed-json", "structurally-invalid-event"],
)
def test_malformed_event_rows_fail_closed_without_partial_snapshot(tmp_path, event_json):
    store = initialized_store(tmp_path)
    assert store.append((entry(1),), expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS
    with raw_connection(store.path) as connection:
        insert_raw_entry(connection, 2, "event-broken", event_json)

    result = store.load()
    assert result.status is EventJournalStoreStatus.CORRUPT
    assert result.entries is None


def test_row_identity_digest_and_sequence_corruption_are_detected(tmp_path):
    store = initialized_store(tmp_path)
    assert store.append((entry(1),), expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS

    with raw_connection(store.path) as connection:
        event_json = connection.execute(
            "SELECT event_json FROM entries WHERE sequence = 1"
        ).fetchone()[0]
        connection.execute(
            "UPDATE entries SET event_id = 'wrong-row-id', integrity_digest = ? "
            "WHERE sequence = 1",
            (_entry_digest(1, event_json),),
        )
        connection.commit()
    assert store.load().status is EventJournalStoreStatus.CORRUPT

    with raw_connection(store.path) as connection:
        connection.execute("UPDATE entries SET event_id = 'event-1', integrity_digest = 'wrong' WHERE sequence = 1")
        connection.commit()
    assert store.load().status is EventJournalStoreStatus.CORRUPT

    path = store_path(tmp_path / "gap")
    gap_store = EventJournalStore(path)
    assert gap_store.initialize(journal_id="gap-journal").status is EventJournalStoreStatus.SUCCESS
    raw_event = json.dumps(entry(2).event.to_dict(), sort_keys=True, separators=(",", ":"))
    with raw_connection(path) as connection:
        insert_raw_entry(connection, 2, "event-2", raw_event)
    assert gap_store.load().status is EventJournalStoreStatus.CORRUPT


def test_error_sanitization_never_exposes_raw_event_data_or_database_errors(tmp_path):
    store = initialized_store(tmp_path)
    secret_json = '{"secret":"credential=hidden"}'
    with raw_connection(store.path) as connection:
        insert_raw_entry(connection, 1, "event-secret", secret_json)

    result = store.load()
    serialized = str(result.to_dict())
    assert result.status is EventJournalStoreStatus.CORRUPT
    assert "credential" not in serialized
    assert "hidden" not in serialized
    assert "sqlite" not in serialized.lower()


def test_loaded_snapshot_results_and_serialization_are_immutable_and_defensive(tmp_path):
    store = initialized_store(tmp_path)
    original = entry(1, payload={"nested": ["safe"]})
    assert store.append((original,), expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS

    loaded = store.load()
    assert loaded.entries is not None
    with pytest.raises(AttributeError):
        loaded.entries.append(original)
    with pytest.raises(FrozenInstanceError):
        loaded.tail_sequence = 9

    serialized = loaded.to_dict()
    serialized["entries"][0]["event"]["payload"]["nested"].append("changed")
    assert loaded.to_dict()["entries"][0]["event"]["payload"]["nested"] == ["safe"]


def test_store_has_no_mutating_or_history_replacement_api(tmp_path):
    store = EventJournalStore(store_path(tmp_path))

    for name in ("update", "delete", "remove", "truncate", "reorder", "replace"):
        assert not hasattr(store, name)


def test_append_does_not_mutate_supplied_entries_or_create_project_files(tmp_path):
    store = initialized_store(tmp_path)
    supplied = (entry(1, payload={"nested": [1]}),)
    before = supplied[0].to_dict()

    assert store.append(supplied, expected_tail_sequence=0).status is EventJournalStoreStatus.SUCCESS
    assert supplied[0].to_dict() == before
    assert list(tmp_path.glob("*.sqlite")) == [store.path]


def test_store_constants_are_stable_and_explicit():
    assert EVENT_JOURNAL_STORAGE_FORMAT == "dungeon_manager.game_event_journal.sqlite"
    assert EVENT_JOURNAL_STORAGE_SCHEMA_VERSION == 1
