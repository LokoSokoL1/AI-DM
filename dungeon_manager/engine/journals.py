"""Separate process-local append-only game-event and command-audit journals."""

from collections.abc import Iterable, Mapping, Set as AbstractSet
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional

from ._json import validate_trimmed_identifier
from .audit import AuditStage, CommandAuditRecord
from .game_event import GameEvent


def _validate_sequence(sequence: int) -> None:
    if (
        not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or sequence < 1
    ):
        raise ValueError("Journal sequence must be a positive integer.")


@dataclass(frozen=True)
class GameEventJournalEntry:
    """One immutable game event with its journal-order sequence number."""

    sequence: int
    event: GameEvent

    def __post_init__(self) -> None:
        _validate_sequence(self.sequence)
        if not isinstance(self.event, GameEvent):
            raise ValueError("Game-event entries require a GameEvent.")
        self.event.validate()

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event.to_dict(), "sequence": self.sequence}


@dataclass(frozen=True)
class CommandAuditJournalEntry:
    """One immutable command audit record with its journal-order sequence."""

    sequence: int
    record: CommandAuditRecord

    def __post_init__(self) -> None:
        _validate_sequence(self.sequence)
        if not isinstance(self.record, CommandAuditRecord):
            raise ValueError(
                "Command-audit entries require a CommandAuditRecord."
            )
        self.record.validate()

    def to_dict(self) -> dict[str, Any]:
        return {"record": self.record.to_dict(), "sequence": self.sequence}


class GameEventJournal:
    """Thread-safe process-local append-only storage for game events only."""

    def __init__(self) -> None:
        self.__entries: tuple[GameEventJournalEntry, ...] = ()
        self.__event_ids: frozenset[str] = frozenset()
        self.__lock = Lock()

    @property
    def entries(self) -> tuple[GameEventJournalEntry, ...]:
        """Return an immutable insertion-ordered snapshot."""

        with self.__lock:
            return self.__entries

    def append(self, event: GameEvent) -> GameEventJournalEntry:
        """Atomically append one unique event and assign its sequence."""

        if not isinstance(event, GameEvent):
            raise TypeError("GameEventJournal.append requires a GameEvent.")
        return self.append_batch((event,))[0]

    def append_batch(
        self,
        events: Iterable[GameEvent],
    ) -> tuple[GameEventJournalEntry, ...]:
        """Atomically append one complete ordered batch of unique events."""

        if (
            isinstance(
                events,
                (str, bytes, bytearray, Mapping, AbstractSet),
            )
            or not isinstance(events, Iterable)
        ):
            raise TypeError(
                "GameEventJournal.append_batch requires an ordered "
                "collection of GameEvent values."
            )

        batch = tuple(events)
        batch_ids: set[str] = set()
        for event in batch:
            if not isinstance(event, GameEvent):
                raise TypeError(
                    "GameEventJournal.append_batch requires only GameEvent "
                    "values."
                )
            event.validate()
            if event.event_id in batch_ids:
                raise ValueError(
                    f"Duplicate game event ID in batch: {event.event_id}"
                )
            batch_ids.add(event.event_id)

        if not batch:
            return ()

        with self.__lock:
            existing_duplicates = batch_ids & self.__event_ids
            if existing_duplicates:
                duplicate_id = next(
                    event.event_id
                    for event in batch
                    if event.event_id in existing_duplicates
                )
                raise ValueError(f"Duplicate game event ID: {duplicate_id}")

            first_sequence = len(self.__entries) + 1
            entries = tuple(
                GameEventJournalEntry(
                    sequence=first_sequence + offset,
                    event=event,
                )
                for offset, event in enumerate(batch)
            )
            updated_entries = self.__entries + entries
            updated_ids = self.__event_ids | batch_ids
            self.__entries = updated_entries
            self.__event_ids = updated_ids
            return entries

    def filter(
        self,
        *,
        event_type: Optional[str] = None,
        command_id: Optional[str] = None,
    ) -> tuple[GameEventJournalEntry, ...]:
        """Return an immutable insertion-ordered filtered snapshot."""

        if event_type is not None:
            validate_trimmed_identifier(event_type, "Event type filter")
        if command_id is not None:
            validate_trimmed_identifier(command_id, "Command ID filter")

        snapshot = self.entries
        return tuple(
            entry
            for entry in snapshot
            if (event_type is None or entry.event.event_type == event_type)
            and (
                command_id is None
                or entry.event.originating_command_id == command_id
            )
        )

    def to_list(self) -> list[dict[str, Any]]:
        """Return independent JSON-compatible serialized journal data."""

        return [entry.to_dict() for entry in self.entries]


class CommandAuditJournal:
    """Thread-safe process-local append-only storage for audit records only."""

    def __init__(self) -> None:
        self.__entries: tuple[CommandAuditJournalEntry, ...] = ()
        self.__audit_record_ids: frozenset[str] = frozenset()
        self.__lock = Lock()

    @property
    def entries(self) -> tuple[CommandAuditJournalEntry, ...]:
        """Return an immutable insertion-ordered snapshot."""

        with self.__lock:
            return self.__entries

    def append(self, record: CommandAuditRecord) -> CommandAuditJournalEntry:
        """Atomically append one unique record and assign its sequence."""

        if not isinstance(record, CommandAuditRecord):
            raise TypeError(
                "CommandAuditJournal.append requires a CommandAuditRecord."
            )
        record.validate()

        with self.__lock:
            if record.audit_record_id in self.__audit_record_ids:
                raise ValueError(
                    f"Duplicate audit record ID: {record.audit_record_id}"
                )
            entry = CommandAuditJournalEntry(
                sequence=len(self.__entries) + 1,
                record=record,
            )
            updated_entries = self.__entries + (entry,)
            updated_ids = (
                self.__audit_record_ids | {record.audit_record_id}
            )
            self.__entries = updated_entries
            self.__audit_record_ids = updated_ids
            return entry

    def filter(
        self,
        *,
        command_id: Optional[str] = None,
        stage: Optional[AuditStage] = None,
    ) -> tuple[CommandAuditJournalEntry, ...]:
        """Return an immutable insertion-ordered filtered snapshot."""

        if command_id is not None:
            validate_trimmed_identifier(command_id, "Command ID filter")
        if stage is not None and not isinstance(stage, AuditStage):
            raise ValueError("Audit stage filter must be an AuditStage value.")

        snapshot = self.entries
        return tuple(
            entry
            for entry in snapshot
            if (command_id is None or entry.record.command_id == command_id)
            and (stage is None or entry.record.stage is stage)
        )

    def to_list(self) -> list[dict[str, Any]]:
        """Return independent JSON-compatible serialized journal data."""

        return [entry.to_dict() for entry in self.entries]
