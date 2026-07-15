import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from threading import Barrier

import pytest

from .audit import AuditStage, CommandAuditRecord
from .command import CommandProvenance, CommandSource
from .game_event import GameEvent
from .journals import (
    CommandAuditJournal,
    CommandAuditJournalEntry,
    GameEventJournal,
    GameEventJournalEntry,
)


FIXED_UTC = datetime(2026, 7, 15, 10, 11, 12, tzinfo=timezone.utc)


def provenance():
    return CommandProvenance(
        source=CommandSource.SYSTEM,
        initiator_id="journal-test",
    )


def event(number, **overrides):
    values = {
        "event_id": f"event-journal-{number}",
        "event_type": "world.location_revealed",
        "occurred_at": FIXED_UTC,
        "provenance": provenance(),
    }
    values.update(overrides)
    return GameEvent(**values)


def audit(number, **overrides):
    values = {
        "audit_record_id": f"audit-journal-{number}",
        "command_id": f"command-journal-{number}",
        "command_type": "world.inspect",
        "stage": AuditStage.POLICY_EVALUATED,
        "outcome": "automatic",
        "recorded_at": FIXED_UTC,
        "provenance": provenance(),
    }
    values.update(overrides)
    return CommandAuditRecord(**values)


def test_event_journal_assigns_sequences_and_preserves_insertion_order():
    journal = GameEventJournal()
    second_event = event(2)
    first_entry = journal.append(event(1))
    second_entry = journal.append(second_event)

    assert first_entry.sequence == 1
    assert second_entry.sequence == 2
    assert journal.entries == (first_entry, second_entry)
    assert journal.entries[1].event is second_event


def test_event_journal_batch_appends_one_event_atomically():
    journal = GameEventJournal()
    produced_event = event(1)

    entries = journal.append_batch((produced_event,))

    assert isinstance(entries, tuple)
    assert entries == journal.entries
    assert entries[0].sequence == 1
    assert entries[0].event is produced_event


def test_event_journal_batch_preserves_multiple_event_order_and_sequences():
    journal = GameEventJournal()
    events = tuple(event(number) for number in (3, 1, 2))

    entries = journal.append_batch(events)

    assert tuple(entry.sequence for entry in entries) == (1, 2, 3)
    assert tuple(entry.event for entry in entries) == events
    assert journal.entries == entries


def test_event_journal_materializes_ordered_iterable_before_mutation():
    journal = GameEventJournal()
    events = (event(1), event(2))

    entries = journal.append_batch(item for item in events)

    assert tuple(entry.event for entry in entries) == events
    assert journal.entries == entries


def test_event_journal_iterable_failure_cannot_partially_append():
    journal = GameEventJournal()

    def failing_events():
        yield event(1)
        raise RuntimeError("test iterable failure")

    with pytest.raises(RuntimeError, match="test iterable failure"):
        journal.append_batch(failing_events())

    assert journal.entries == ()
    assert journal.append(event(2)).sequence == 1


def test_empty_event_batch_is_a_successful_no_op_without_sequence_gap():
    journal = GameEventJournal()
    first = journal.append(event(1))
    before = journal.entries

    assert journal.append_batch(()) == ()
    assert journal.entries is before
    assert journal.entries == (first,)
    assert journal.append(event(2)).sequence == 2


@pytest.mark.parametrize(
    "invalid_batch",
    [None, "events", b"events", {"event": "value"}, {"event"}],
)
def test_event_batch_rejects_values_that_are_not_ordered_collections(
    invalid_batch,
):
    journal = GameEventJournal()

    with pytest.raises(TypeError, match="ordered collection"):
        journal.append_batch(invalid_batch)

    assert journal.entries == ()


def test_event_batch_validates_every_value_before_any_mutation():
    journal = GameEventJournal()
    existing = journal.append(event("existing"))
    corrupted = event("corrupted")
    object.__setattr__(corrupted, "event_type", " ")

    with pytest.raises(ValueError, match="Game event type"):
        journal.append_batch((event(1), corrupted, event(2)))

    assert journal.entries == (existing,)
    assert journal.append(event(3)).sequence == 2


def test_event_batch_rejects_non_event_values_without_partial_append():
    journal = GameEventJournal()

    with pytest.raises(TypeError, match="only GameEvent"):
        journal.append_batch((event(1), audit(1), event(2)))

    assert journal.entries == ()
    assert journal.append(event(3)).sequence == 1


def test_event_batch_rejects_duplicate_ids_within_batch_atomically():
    journal = GameEventJournal()
    first = event(1)
    duplicate = event(2, event_id=first.event_id)

    with pytest.raises(ValueError, match="Duplicate game event ID in batch"):
        journal.append_batch((first, duplicate))

    assert journal.entries == ()
    assert journal.append(event(3)).sequence == 1


def test_event_batch_rejects_existing_id_without_partial_append_or_gap():
    journal = GameEventJournal()
    existing_event = event("existing")
    existing_entry = journal.append(existing_event)
    duplicate = event(2, event_id=existing_event.event_id)

    with pytest.raises(ValueError, match="Duplicate game event ID"):
        journal.append_batch((event(1), duplicate, event(3)))

    assert journal.entries == (existing_entry,)
    assert journal.append(event(4)).sequence == 2


def test_concurrent_event_batches_never_interleave():
    journal = GameEventJournal()
    ready = Barrier(2)
    batches = (
        (event("a1"), event("a2"), event("a3")),
        (event("b1"), event("b2"), event("b3")),
    )

    def append_after_barrier(batch):
        ready.wait()
        return journal.append_batch(batch)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = tuple(
            executor.submit(append_after_barrier, batch) for batch in batches
        )
        returned_batches = tuple(future.result() for future in futures)

    journal_event_ids = tuple(
        entry.event.event_id for entry in journal.entries
    )
    expected_orders = {
        tuple(item.event_id for batch in batches for item in batch),
        tuple(
            item.event_id
            for batch in reversed(batches)
            for item in batch
        ),
    }
    assert journal_event_ids in expected_orders
    assert tuple(entry.sequence for entry in journal.entries) == tuple(
        range(1, 7)
    )
    assert all(
        tuple(entry.sequence for entry in returned)
        in ((1, 2, 3), (4, 5, 6))
        for returned in returned_batches
    )


def test_audit_journal_assigns_sequences_and_preserves_insertion_order():
    journal = CommandAuditJournal()
    first_entry = journal.append(audit(1))
    second_entry = journal.append(audit(2))

    assert first_entry.sequence == 1
    assert second_entry.sequence == 2
    assert journal.entries == (first_entry, second_entry)


def test_duplicate_event_id_is_rejected_without_sequence_gap():
    journal = GameEventJournal()
    first = event(1)
    journal.append(first)

    with pytest.raises(ValueError, match="Duplicate game event ID"):
        journal.append(event("duplicate", event_id=first.event_id))

    next_entry = journal.append(event(2))
    assert next_entry.sequence == 2
    assert tuple(entry.event for entry in journal.entries) == (
        first,
        next_entry.event,
    )


def test_duplicate_audit_id_is_rejected_without_sequence_gap():
    journal = CommandAuditJournal()
    first = audit(1)
    journal.append(first)

    with pytest.raises(ValueError, match="Duplicate audit record ID"):
        journal.append(audit("duplicate", audit_record_id=first.audit_record_id))

    next_entry = journal.append(audit(2))
    assert next_entry.sequence == 2
    assert tuple(entry.record for entry in journal.entries) == (
        first,
        next_entry.record,
    )


def test_failed_structural_append_leaves_journal_and_sequence_unchanged():
    journal = GameEventJournal()
    corrupted = event("corrupted")
    object.__setattr__(corrupted, "event_type", " ")

    with pytest.raises(ValueError, match="Game event type"):
        journal.append(corrupted)

    assert journal.entries == ()
    assert journal.append(event(1)).sequence == 1


def test_journal_snapshots_and_entries_are_immutable():
    event_journal = GameEventJournal()
    audit_journal = CommandAuditJournal()
    event_entry = event_journal.append(event(1))
    audit_entry = audit_journal.append(audit(1))
    event_snapshot = event_journal.entries
    audit_snapshot = audit_journal.entries

    with pytest.raises(AttributeError):
        event_snapshot.append(event_entry)
    with pytest.raises(AttributeError):
        audit_snapshot.append(audit_entry)
    with pytest.raises(FrozenInstanceError):
        event_entry.sequence = 2
    with pytest.raises(FrozenInstanceError):
        audit_entry.sequence = 2

    event_snapshot += (GameEventJournalEntry(2, event(2)),)
    audit_snapshot += (CommandAuditJournalEntry(2, audit(2)),)
    assert event_journal.entries == (event_entry,)
    assert audit_journal.entries == (audit_entry,)


def test_event_journal_filters_exact_type_and_command_id_in_order():
    journal = GameEventJournal()
    matching_first = journal.append(
        event(1, originating_command_id="command-shared")
    )
    journal.append(
        event(
            2,
            event_type="World.Location_Revealed",
            originating_command_id="command-shared",
        )
    )
    matching_second = journal.append(
        event(3, originating_command_id="command-shared")
    )
    journal.append(event(4, originating_command_id="command-other"))

    assert journal.filter(
        event_type="world.location_revealed",
        command_id="command-shared",
    ) == (matching_first, matching_second)
    assert journal.filter(event_type="WORLD.LOCATION_REVEALED") == ()


def test_audit_journal_filters_command_id_and_typed_stage_in_order():
    journal = CommandAuditJournal()
    matching_first = journal.append(
        audit(1, command_id="command-shared")
    )
    journal.append(
        audit(
            2,
            command_id="command-shared",
            stage=AuditStage.GATE_RESOLVED,
        )
    )
    matching_second = journal.append(
        audit(3, command_id="command-shared")
    )

    assert journal.filter(
        command_id="command-shared",
        stage=AuditStage.POLICY_EVALUATED,
    ) == (matching_first, matching_second)
    with pytest.raises(ValueError, match="Audit stage filter"):
        journal.filter(stage="policy_evaluated")


def test_each_journal_rejects_the_other_record_type():
    event_journal = GameEventJournal()
    audit_journal = CommandAuditJournal()

    with pytest.raises(TypeError, match="requires a GameEvent"):
        event_journal.append(audit(1))
    with pytest.raises(TypeError, match="requires a CommandAuditRecord"):
        audit_journal.append(event(1))

    assert event_journal.entries == ()
    assert audit_journal.entries == ()


def test_event_and_audit_journals_remain_distinct_even_with_same_id_text():
    event_journal = GameEventJournal()
    audit_journal = CommandAuditJournal()
    event_entry = event_journal.append(event(1, event_id="shared-id"))
    audit_entry = audit_journal.append(
        audit(1, audit_record_id="shared-id")
    )

    assert isinstance(event_entry, GameEventJournalEntry)
    assert isinstance(event_entry.event, GameEvent)
    assert isinstance(audit_entry, CommandAuditJournalEntry)
    assert isinstance(audit_entry.record, CommandAuditRecord)
    assert event_entry.sequence == audit_entry.sequence == 1


def test_serialized_journal_data_is_json_compatible_and_defensive():
    event_journal = GameEventJournal()
    audit_journal = CommandAuditJournal()
    event_journal.append(event(1, payload={"nested": [{"value": 1}]}))
    audit_journal.append(audit(1, details={"nested": [{"value": 1}]}))

    serialized_events = event_journal.to_list()
    serialized_audits = audit_journal.to_list()
    serialized_events[0]["event"]["payload"]["nested"][0]["value"] = 2
    serialized_audits[0]["record"]["details"]["nested"][0]["value"] = 2

    fresh_events = event_journal.to_list()
    fresh_audits = audit_journal.to_list()
    assert fresh_events[0]["event"]["payload"]["nested"][0]["value"] == 1
    assert fresh_audits[0]["record"]["details"]["nested"][0]["value"] == 1
    assert json.loads(json.dumps(fresh_events, allow_nan=False)) == fresh_events
    assert json.loads(json.dumps(fresh_audits, allow_nan=False)) == fresh_audits


@pytest.mark.parametrize("sequence", [0, -1, True, "1"])
def test_journal_entries_require_positive_integer_sequences(sequence):
    with pytest.raises(ValueError, match="positive integer"):
        GameEventJournalEntry(sequence, event(1))
    with pytest.raises(ValueError, match="positive integer"):
        CommandAuditJournalEntry(sequence, audit(1))


def test_journals_offer_no_update_delete_or_reorder_pathway():
    for journal in (GameEventJournal(), CommandAuditJournal()):
        assert not hasattr(journal, "update")
        assert not hasattr(journal, "delete")
        assert not hasattr(journal, "remove")
        assert not hasattr(journal, "reorder")
        assert not hasattr(journal, "replace")
