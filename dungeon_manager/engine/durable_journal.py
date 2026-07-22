"""Typed durable-journal capabilities, publication metadata, and health."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from ._json import validate_trimmed_identifier
from .journals import GameEventJournalEntry


def _validate_sequence(value: Any, label: str) -> None:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise ValueError(f"{label} must be a non-negative integer.")


class EventJournalStoreStatus(str, Enum):
    """Safe outcomes for durable event-journal operations."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    INVALID_INPUT = "invalid_input"
    STALE_TAIL = "stale_tail"
    JOURNAL_ID_MISMATCH = "journal_id_mismatch"
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
            if value is not None:
                _validate_sequence(value, label)
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


@runtime_checkable
class DurableEventJournalAppender(Protocol):
    """Smallest storage capability required by durable publication."""

    def append(
        self,
        entries: tuple[GameEventJournalEntry, ...],
        *,
        expected_tail_sequence: int,
        expected_journal_id: str,
    ) -> EventJournalStoreResult:
        ...


@dataclass(frozen=True)
class DurableJournalBinding:
    """Validated store identity and tail supplied to a durable pipeline."""

    store: DurableEventJournalAppender
    journal_id: str
    tail_sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.store, DurableEventJournalAppender):
            raise ValueError("Durable journal binding requires an append store.")
        validate_trimmed_identifier(self.journal_id, "Journal ID")
        _validate_sequence(self.tail_sequence, "Durable binding tail")


class DurablePublicationStatus(str, Enum):
    """Durable outcome for one command submission."""

    NOT_CONFIGURED = "not_configured"
    NOT_APPLICABLE = "not_applicable"
    NO_EVENTS = "no_events"
    NOT_COMMITTED = "not_committed"
    COMMITTED_SYNCHRONIZED = "committed_synchronized"
    COMMITTED_LOCAL_SYNC_FAILED = "committed_local_sync_failed"
    COMMITTED_PROJECTION_FAILED = "committed_projection_failed"
    DIVERGED = "diverged"
    STORAGE_UNAVAILABLE = "storage_unavailable"


@dataclass(frozen=True)
class DurablePublicationResult:
    """Payload-free metadata for one durable publication attempt."""

    status: DurablePublicationStatus
    journal_id: Optional[str] = None
    previous_tail: Optional[int] = None
    resulting_tail: Optional[int] = None
    appended_count: int = 0
    durable_commit_confirmed: bool = False
    reason_code: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, DurablePublicationStatus):
            raise ValueError("Durable publication status must be typed.")
        if self.journal_id is not None:
            validate_trimmed_identifier(self.journal_id, "Journal ID")
        for value, label in (
            (self.previous_tail, "Durable previous tail"),
            (self.resulting_tail, "Durable resulting tail"),
            (self.appended_count, "Durable appended count"),
        ):
            if value is not None:
                _validate_sequence(value, label)
        if not isinstance(self.durable_commit_confirmed, bool):
            raise ValueError("Durable commitment confirmation must be boolean.")
        if self.reason_code is not None:
            validate_trimmed_identifier(self.reason_code, "Durable reason code")
        if self.error is not None:
            validate_trimmed_identifier(self.error, "Durable publication error")

        committed_statuses = {
            DurablePublicationStatus.COMMITTED_SYNCHRONIZED,
            DurablePublicationStatus.COMMITTED_LOCAL_SYNC_FAILED,
            DurablePublicationStatus.COMMITTED_PROJECTION_FAILED,
        }
        if self.durable_commit_confirmed != (self.status in committed_statuses):
            raise ValueError(
                "Durable commitment confirmation must match publication status."
            )
        if self.status in committed_statuses:
            if (
                self.journal_id is None
                or self.previous_tail is None
                or self.resulting_tail is None
                or self.appended_count < 1
                or self.resulting_tail
                != self.previous_tail + self.appended_count
            ):
                raise ValueError(
                    "Committed durable publication requires exact tail metadata."
                )
        if self.status is DurablePublicationStatus.COMMITTED_SYNCHRONIZED:
            if self.reason_code is not None or self.error is not None:
                raise ValueError(
                    "Synchronized durable publication cannot contain failure metadata."
                )
        elif self.status in {
            DurablePublicationStatus.NOT_CONFIGURED,
            DurablePublicationStatus.NOT_APPLICABLE,
            DurablePublicationStatus.NO_EVENTS,
        }:
            if self.reason_code is not None or self.error is not None:
                raise ValueError(
                    "Non-failing durable publication cannot contain failure metadata."
                )
        else:
            validate_trimmed_identifier(self.reason_code, "Durable reason code")
            validate_trimmed_identifier(self.error, "Durable publication error")

    def to_dict(self) -> dict[str, Any]:
        return {
            "appended_count": self.appended_count,
            "durable_commit_confirmed": self.durable_commit_confirmed,
            "error": self.error,
            "journal_id": self.journal_id,
            "previous_tail": self.previous_tail,
            "reason_code": self.reason_code,
            "resulting_tail": self.resulting_tail,
            "status": self.status.value,
        }


class DurableJournalHealthStatus(str, Enum):
    """Whether a durable store and its process-local journal may dispatch."""

    NOT_CONFIGURED = "not_configured"
    SYNCHRONIZED = "synchronized"
    UNAVAILABLE = "unavailable"


class DurableJournalHealthReason(str, Enum):
    """Stable reasons a durable runtime must be rehydrated."""

    INITIAL_TAIL_MISMATCH = "initial_tail_mismatch"
    STALE_DURABLE_TAIL = "stale_durable_tail"
    JOURNAL_ID_MISMATCH = "journal_id_mismatch"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    STORE_RESULT_MISMATCH = "store_result_mismatch"
    LOCAL_SYNCHRONIZATION_FAILED = "local_synchronization_failed"


@dataclass(frozen=True)
class DurableJournalHealth:
    """Safe durable/local agreement metadata without event or state data."""

    status: DurableJournalHealthStatus
    journal_id: Optional[str]
    durable_tail: int
    local_tail: int
    reason_code: Optional[DurableJournalHealthReason] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, DurableJournalHealthStatus):
            raise ValueError("Durable journal health status must be typed.")
        if self.journal_id is not None:
            validate_trimmed_identifier(self.journal_id, "Journal ID")
        _validate_sequence(self.durable_tail, "Durable health durable tail")
        _validate_sequence(self.local_tail, "Durable health local tail")
        if self.reason_code is not None and not isinstance(
            self.reason_code, DurableJournalHealthReason
        ):
            raise ValueError("Durable journal health reason must be typed.")
        if self.status is DurableJournalHealthStatus.NOT_CONFIGURED:
            if self.journal_id is not None or self.reason_code is not None:
                raise ValueError("Non-durable health cannot contain durable metadata.")
        elif self.status is DurableJournalHealthStatus.SYNCHRONIZED:
            if (
                self.journal_id is None
                or self.durable_tail != self.local_tail
                or self.reason_code is not None
            ):
                raise ValueError("Synchronized durable health requires matching tails.")
        elif self.reason_code is None or self.journal_id is None:
            raise ValueError("Unavailable durable health requires a typed reason.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "durable_tail": self.durable_tail,
            "journal_id": self.journal_id,
            "local_tail": self.local_tail,
            "reason_code": (
                None if self.reason_code is None else self.reason_code.value
            ),
            "status": self.status.value,
        }
