"""Durable SQLite storage for immutable sequenced game-event journals.

Integrity digests detect accidental corruption; they are not cryptographic
authentication and do not protect against a malicious database writer.
"""

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterable, Mapping, Set as AbstractSet
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from ._json import validate_trimmed_identifier
from .game_event import GameEvent
from .journals import GameEventJournalEntry


EVENT_JOURNAL_STORAGE_FORMAT = "dungeon_manager.game_event_journal.sqlite"
EVENT_JOURNAL_STORAGE_SCHEMA_VERSION = 1
_METADATA_KEYS = frozenset({"format", "journal_id", "schema_version"})


class EventJournalStoreStatus(str, Enum):
    """Safe outcomes for durable event-journal operations."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    INVALID_INPUT = "invalid_input"
    STALE_TAIL = "stale_tail"
    CORRUPT = "corrupt"
    UNSUPPORTED_VERSION = "unsupported_version"
    STORAGE_FAILURE = "storage_failure"


@dataclass(frozen=True)
class EventJournalStoreResult:
    """Immutable controlled result with entries only for successful loads."""

    status: EventJournalStoreStatus
    journal_id: Optional[str] = None
    previous_tail: Optional[int] = None
    tail_sequence: Optional[int] = None
    appended_count: int = 0
    reason_code: Optional[str] = None
    error: Optional[str] = None
    entries: Optional[tuple[GameEventJournalEntry, ...]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, EventJournalStoreStatus):
            raise ValueError("Event-journal store status must be valid.")
        if self.journal_id is not None:
            validate_trimmed_identifier(self.journal_id, "Journal ID")
        for value, label in (
            (self.previous_tail, "Previous tail"),
            (self.tail_sequence, "Tail sequence"),
            (self.appended_count, "Appended count"),
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{label} must be a non-negative integer.")
        if self.reason_code is not None:
            validate_trimmed_identifier(self.reason_code, "Reason code")
        if self.error is not None:
            validate_trimmed_identifier(self.error, "Store error")
        if self.status is EventJournalStoreStatus.SUCCESS:
            if self.error is not None or self.reason_code is not None:
                raise ValueError("Successful store results cannot carry errors.")
        elif self.entries is not None:
            raise ValueError("Only successful loads may expose journal entries.")
        if self.entries is not None:
            if not isinstance(self.entries, tuple):
                raise ValueError("Loaded journal entries must be an immutable tuple.")
            for entry in self.entries:
                if not isinstance(entry, GameEventJournalEntry):
                    raise ValueError("Loaded journal entries must be valid entries.")

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible transport representation."""

        return {
            "appended_count": self.appended_count,
            "entries": (
                None
                if self.entries is None
                else [entry.to_dict() for entry in self.entries]
            ),
            "error": self.error,
            "journal_id": self.journal_id,
            "previous_tail": self.previous_tail,
            "reason_code": self.reason_code,
            "status": self.status.value,
            "tail_sequence": self.tail_sequence,
        }


def _canonical_event_json(event: GameEvent) -> str:
    return json.dumps(
        event.to_dict(),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _entry_digest(sequence: int, event_json: str) -> str:
    content = f"event-journal-entry-v1\0{sequence}\0{event_json}".encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def _safe_failure(
    status: EventJournalStoreStatus,
    reason_code: str,
    error: str,
    *,
    journal_id: Optional[str] = None,
    previous_tail: Optional[int] = None,
    tail_sequence: Optional[int] = None,
) -> EventJournalStoreResult:
    return EventJournalStoreResult(
        status=status,
        journal_id=journal_id,
        previous_tail=previous_tail,
        tail_sequence=tail_sequence,
        reason_code=reason_code,
        error=error,
    )


class EventJournalStore:
    """A path-bound, explicit SQLite store for one immutable event journal."""

    def __init__(self, path: str | Path) -> None:
        if not isinstance(path, (str, Path)):
            raise ValueError("Event-journal database path must be a filesystem path.")
        self.__path = Path(path)
        if not str(self.__path):
            raise ValueError("Event-journal database path must not be empty.")

    @property
    def path(self) -> Path:
        """Return the caller-supplied database path without opening it."""

        return self.__path

    def initialize(self, *, journal_id: Optional[str] = None) -> EventJournalStoreResult:
        """Explicitly create one new empty durable journal database."""

        if journal_id is None:
            journal_id = str(uuid.uuid4())
        try:
            validate_trimmed_identifier(journal_id, "Journal ID")
        except ValueError:
            return _safe_failure(
                EventJournalStoreStatus.INVALID_INPUT,
                "invalid_journal_id",
                "The journal ID is invalid.",
            )
        if self.__path.exists():
            return _safe_failure(
                EventJournalStoreStatus.ALREADY_EXISTS,
                "storage_exists",
                "The event-journal database already exists.",
                journal_id=journal_id,
            )
        try:
            self.__path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.__path, timeout=0)
            try:
                self._configure(connection)
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "CREATE TABLE metadata (key TEXT PRIMARY KEY, value NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE entries ("
                    "sequence INTEGER PRIMARY KEY CHECK(sequence > 0), "
                    "event_id TEXT NOT NULL UNIQUE, "
                    "event_json TEXT NOT NULL, "
                    "integrity_digest TEXT NOT NULL)"
                )
                connection.executemany(
                    "INSERT INTO metadata(key, value) VALUES (?, ?)",
                    (
                        ("format", EVENT_JOURNAL_STORAGE_FORMAT),
                        ("journal_id", journal_id),
                        ("schema_version", EVENT_JOURNAL_STORAGE_SCHEMA_VERSION),
                    ),
                )
                connection.commit()
            except (sqlite3.Error, OSError):
                connection.rollback()
                raise
            finally:
                connection.close()
        except (sqlite3.Error, OSError):
            return _safe_failure(
                EventJournalStoreStatus.STORAGE_FAILURE,
                "initialize_failed",
                "The event-journal database could not be initialized.",
            )
        return EventJournalStoreResult(
            status=EventJournalStoreStatus.SUCCESS,
            journal_id=journal_id,
            previous_tail=0,
            tail_sequence=0,
        )

    def append(
        self,
        entries: Iterable[GameEventJournalEntry],
        *,
        expected_tail_sequence: int,
    ) -> EventJournalStoreResult:
        """Atomically append an already-sequenced immutable entry batch."""

        batch_result = self._materialize_batch(entries, expected_tail_sequence)
        if isinstance(batch_result, EventJournalStoreResult):
            return batch_result
        batch = batch_result
        if not self.__path.is_file():
            return _safe_failure(
                EventJournalStoreStatus.NOT_FOUND,
                "storage_missing",
                "The event-journal database does not exist.",
            )
        connection: Optional[sqlite3.Connection] = None
        try:
            connection = sqlite3.connect(self.__path, timeout=0)
            self._configure(connection)
            connection.execute("BEGIN IMMEDIATE")
            metadata = self._read_metadata(connection)
            if isinstance(metadata, EventJournalStoreResult):
                connection.rollback()
                return metadata
            journal_id = metadata
            existing_entries = self._read_entries(connection, journal_id)
            if isinstance(existing_entries, EventJournalStoreResult):
                return existing_entries
            tail = len(existing_entries)
            if tail != expected_tail_sequence:
                connection.rollback()
                return _safe_failure(
                    EventJournalStoreStatus.STALE_TAIL,
                    "stale_tail",
                    "The durable journal tail no longer matches the expected tail.",
                    journal_id=journal_id,
                    previous_tail=tail,
                    tail_sequence=tail,
                )
            if not batch:
                connection.commit()
                return EventJournalStoreResult(
                    status=EventJournalStoreStatus.SUCCESS,
                    journal_id=journal_id,
                    previous_tail=tail,
                    tail_sequence=tail,
                    appended_count=0,
                )
            existing_event_ids = {item.event.event_id for item in existing_entries}
            if any(entry.event.event_id in existing_event_ids for entry in batch):
                connection.rollback()
                return _safe_failure(
                    EventJournalStoreStatus.INVALID_INPUT,
                    "duplicate_event_id",
                    "The event-journal entry batch is invalid.",
                    journal_id=journal_id,
                    previous_tail=tail,
                    tail_sequence=tail,
                )
            for entry in batch:
                event_json = _canonical_event_json(entry.event)
                connection.execute(
                    "INSERT INTO entries(sequence, event_id, event_json, integrity_digest) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        entry.sequence,
                        entry.event.event_id,
                        event_json,
                        _entry_digest(entry.sequence, event_json),
                    ),
                )
            connection.commit()
            return EventJournalStoreResult(
                status=EventJournalStoreStatus.SUCCESS,
                journal_id=journal_id,
                previous_tail=tail,
                tail_sequence=batch[-1].sequence,
                appended_count=len(batch),
            )
        except sqlite3.IntegrityError:
            if connection is not None:
                connection.rollback()
            return _safe_failure(
                EventJournalStoreStatus.STORAGE_FAILURE,
                "append_failed",
                "The event-journal batch could not be persisted.",
            )
        except (sqlite3.Error, OSError):
            if connection is not None:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
            return _safe_failure(
                EventJournalStoreStatus.STORAGE_FAILURE,
                "append_failed",
                "The event-journal batch could not be persisted.",
            )
        finally:
            if connection is not None:
                connection.close()

    def load(self) -> EventJournalStoreResult:
        """Load one complete validated immutable durable journal snapshot."""

        if not self.__path.is_file():
            return _safe_failure(
                EventJournalStoreStatus.NOT_FOUND,
                "storage_missing",
                "The event-journal database does not exist.",
            )
        connection: Optional[sqlite3.Connection] = None
        try:
            connection = sqlite3.connect(self.__path, timeout=0)
            self._configure(connection)
            connection.execute("BEGIN")
            metadata = self._read_metadata(connection)
            if isinstance(metadata, EventJournalStoreResult):
                connection.rollback()
                return metadata
            journal_id = metadata
            entries = self._read_entries(connection, journal_id)
            if isinstance(entries, EventJournalStoreResult):
                return entries
            connection.commit()
            snapshot = entries
            return EventJournalStoreResult(
                status=EventJournalStoreStatus.SUCCESS,
                journal_id=journal_id,
                previous_tail=len(snapshot),
                tail_sequence=len(snapshot),
                entries=snapshot,
            )
        except (sqlite3.Error, OSError):
            if connection is not None:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
            return _safe_failure(
                EventJournalStoreStatus.STORAGE_FAILURE,
                "load_failed",
                "The event-journal database could not be loaded.",
            )
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _configure(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")

    @staticmethod
    def _corrupt(connection: sqlite3.Connection, journal_id: str) -> EventJournalStoreResult:
        connection.rollback()
        return _safe_failure(
            EventJournalStoreStatus.CORRUPT,
            "invalid_durable_record",
            "The event-journal database contains invalid durable records.",
            journal_id=journal_id,
        )

    def _read_entries(
        self,
        connection: sqlite3.Connection,
        journal_id: str,
    ) -> tuple[GameEventJournalEntry, ...] | EventJournalStoreResult:
        try:
            rows = connection.execute(
                "SELECT sequence, event_id, event_json, integrity_digest "
                "FROM entries ORDER BY sequence ASC"
            ).fetchall()
        except sqlite3.Error:
            return self._corrupt(connection, journal_id)
        entries: list[GameEventJournalEntry] = []
        event_ids: set[str] = set()
        for expected_sequence, row in enumerate(rows, start=1):
            sequence, event_id, event_json, digest = row
            if (
                not isinstance(sequence, int)
                or sequence != expected_sequence
                or not isinstance(event_id, str)
                or not isinstance(event_json, str)
                or not isinstance(digest, str)
                or digest != _entry_digest(sequence, event_json)
            ):
                return self._corrupt(connection, journal_id)
            try:
                decoded = json.loads(event_json)
                event = GameEvent.from_dict(decoded)
                if _canonical_event_json(event) != event_json:
                    return self._corrupt(connection, journal_id)
                entry = GameEventJournalEntry(sequence, event)
            except (TypeError, ValueError, json.JSONDecodeError):
                return self._corrupt(connection, journal_id)
            if event.event_id != event_id or event_id in event_ids:
                return self._corrupt(connection, journal_id)
            event_ids.add(event_id)
            entries.append(entry)
        return tuple(entries)

    @staticmethod
    def _read_metadata(connection: sqlite3.Connection) -> str | EventJournalStoreResult:
        try:
            rows = connection.execute("SELECT key, value FROM metadata").fetchall()
        except sqlite3.Error:
            return _safe_failure(
                EventJournalStoreStatus.CORRUPT,
                "invalid_metadata",
                "The event-journal database metadata is invalid.",
            )
        metadata: dict[str, Any] = {}
        for key, value in rows:
            if not isinstance(key, str) or key in metadata:
                return _safe_failure(
                    EventJournalStoreStatus.CORRUPT,
                    "invalid_metadata",
                    "The event-journal database metadata is invalid.",
                )
            metadata[key] = value
        if set(metadata) != _METADATA_KEYS:
            return _safe_failure(
                EventJournalStoreStatus.CORRUPT,
                "invalid_metadata",
                "The event-journal database metadata is invalid.",
            )
        if not isinstance(metadata["format"], str):
            return _safe_failure(
                EventJournalStoreStatus.CORRUPT,
                "invalid_metadata",
                "The event-journal database metadata is invalid.",
            )
        if metadata["format"] != EVENT_JOURNAL_STORAGE_FORMAT:
            return _safe_failure(
                EventJournalStoreStatus.UNSUPPORTED_VERSION,
                "unsupported_format",
                "The event-journal storage format is unsupported.",
            )
        version = metadata["schema_version"]
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version < 1
        ):
            return _safe_failure(
                EventJournalStoreStatus.CORRUPT,
                "invalid_metadata",
                "The event-journal database metadata is invalid.",
            )
        if version != EVENT_JOURNAL_STORAGE_SCHEMA_VERSION:
            return _safe_failure(
                EventJournalStoreStatus.UNSUPPORTED_VERSION,
                "unsupported_schema_version",
                "The event-journal storage schema version is unsupported.",
            )
        try:
            validate_trimmed_identifier(metadata["journal_id"], "Journal ID")
        except ValueError:
            return _safe_failure(
                EventJournalStoreStatus.CORRUPT,
                "invalid_metadata",
                "The event-journal database metadata is invalid.",
            )
        return metadata["journal_id"]

    @staticmethod
    def _materialize_batch(
        entries: Iterable[GameEventJournalEntry], expected_tail_sequence: int
    ) -> tuple[GameEventJournalEntry, ...] | EventJournalStoreResult:
        if (
            not isinstance(expected_tail_sequence, int)
            or isinstance(expected_tail_sequence, bool)
            or expected_tail_sequence < 0
        ):
            return _safe_failure(
                EventJournalStoreStatus.INVALID_INPUT,
                "invalid_expected_tail",
                "The expected journal tail is invalid.",
            )
        if (
            isinstance(entries, (str, bytes, bytearray, Mapping, AbstractSet))
            or not isinstance(entries, Iterable)
        ):
            return _safe_failure(
                EventJournalStoreStatus.INVALID_INPUT,
                "invalid_entry_batch",
                "The event-journal entry batch is invalid.",
            )
        try:
            batch = tuple(entries)
        except Exception:
            return _safe_failure(
                EventJournalStoreStatus.INVALID_INPUT,
                "invalid_entry_batch",
                "The event-journal entry batch is invalid.",
            )
        event_ids: set[str] = set()
        for offset, entry in enumerate(batch):
            if not isinstance(entry, GameEventJournalEntry):
                return _safe_failure(
                    EventJournalStoreStatus.INVALID_INPUT,
                    "invalid_entry",
                    "The event-journal entry batch is invalid.",
                )
            try:
                entry.event.validate()
            except (TypeError, ValueError):
                return _safe_failure(
                    EventJournalStoreStatus.INVALID_INPUT,
                    "invalid_entry",
                    "The event-journal entry batch is invalid.",
                )
            if entry.sequence != expected_tail_sequence + offset + 1:
                return _safe_failure(
                    EventJournalStoreStatus.INVALID_INPUT,
                    "invalid_sequence_range",
                    "The event-journal entry sequence range is invalid.",
                )
            if entry.event.event_id in event_ids:
                return _safe_failure(
                    EventJournalStoreStatus.INVALID_INPUT,
                    "duplicate_event_id",
                    "The event-journal entry batch is invalid.",
                )
            event_ids.add(entry.event.event_id)
        return batch
