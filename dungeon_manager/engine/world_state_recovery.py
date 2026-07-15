"""Typed outcomes for explicit process-local world-state recovery."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ._json import validate_trimmed_identifier
from .world_state import WorldStateProjectionStatus


def _validate_sequence(sequence: Any, label: str) -> None:
    if (
        not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or sequence < 0
    ):
        raise ValueError(f"{label} must be a non-negative integer.")


class WorldStateRecoveryStrategy(str, Enum):
    """Explicit operator-selected recovery behavior."""

    CATCH_UP = "catch_up"
    FULL_REBUILD = "full_rebuild"


class WorldStateRecoveryStatus(str, Enum):
    """Controlled outcome of one explicit recovery attempt."""

    RECOVERED = "recovered"
    NO_ACTION = "no_action"
    INVALID_REQUEST = "invalid_request"
    PROJECTION_FAILURE = "projection_failure"
    JOURNAL_CHANGED = "journal_changed"
    UNAVAILABLE = "unavailable"
    COORDINATOR_FAILURE = "coordinator_failure"


@dataclass(frozen=True)
class WorldStateRecoveryResult:
    """Payload-free recovery metadata with defensive serialization."""

    strategy: WorldStateRecoveryStrategy
    status: WorldStateRecoveryStatus
    previous_sequence: int
    captured_journal_tail_sequence: int
    resulting_sequence: Optional[int] = None
    projector_status: Optional[WorldStateProjectionStatus] = None
    projector_reason: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, WorldStateRecoveryStrategy):
            raise ValueError("Recovery strategy must be typed.")
        if not isinstance(self.status, WorldStateRecoveryStatus):
            raise ValueError("Recovery status must be typed.")
        _validate_sequence(
            self.previous_sequence,
            "Recovery previous sequence",
        )
        _validate_sequence(
            self.captured_journal_tail_sequence,
            "Recovery captured journal-tail sequence",
        )
        if self.resulting_sequence is not None:
            _validate_sequence(
                self.resulting_sequence,
                "Recovery resulting sequence",
            )
        if self.projector_status is not None and not isinstance(
            self.projector_status,
            WorldStateProjectionStatus,
        ):
            raise ValueError("Recovery projector status must be typed.")
        if self.projector_reason is not None:
            validate_trimmed_identifier(
                self.projector_reason,
                "Recovery projector reason",
            )

        if self.status is WorldStateRecoveryStatus.RECOVERED:
            if (
                self.resulting_sequence
                != self.captured_journal_tail_sequence
                or self.projector_status
                is not WorldStateProjectionStatus.SUCCESS
                or self.projector_reason is not None
                or self.error is not None
            ):
                raise ValueError(
                    "Recovered state must reach the captured journal tail."
                )
            return

        if self.status is WorldStateRecoveryStatus.NO_ACTION:
            if (
                self.strategy is not WorldStateRecoveryStrategy.CATCH_UP
                or self.previous_sequence
                != self.captured_journal_tail_sequence
                or self.resulting_sequence != self.previous_sequence
                or self.projector_status is not None
                or self.projector_reason is not None
                or self.error is not None
            ):
                raise ValueError(
                    "No-action recovery requires synchronized catch-up."
                )
            return

        if self.resulting_sequence is not None:
            raise ValueError("Failed recovery cannot report a resulting state.")
        validate_trimmed_identifier(self.error, "Recovery error")

        if self.status is WorldStateRecoveryStatus.PROJECTION_FAILURE:
            if (
                self.projector_status is None
                or self.projector_status
                is WorldStateProjectionStatus.SUCCESS
                or self.projector_reason is None
            ):
                raise ValueError(
                    "Projection failure requires controlled projector metadata."
                )
            return

        if self.projector_reason is not None:
            raise ValueError(
                "Only projection failures can contain a projector reason."
            )
        if (
            self.projector_status is not None
            and self.status is not WorldStateRecoveryStatus.JOURNAL_CHANGED
        ):
            raise ValueError(
                "Only projection or journal-change failures report a "
                "projector status."
            )
        if (
            self.status is WorldStateRecoveryStatus.JOURNAL_CHANGED
            and self.projector_status is not WorldStateProjectionStatus.SUCCESS
        ):
            raise ValueError(
                "Journal-change recovery requires a completed projection."
            )

    def to_dict(self) -> dict[str, Any]:
        """Return independent JSON-compatible safe metadata."""

        return {
            "captured_journal_tail_sequence": (
                self.captured_journal_tail_sequence
            ),
            "error": self.error,
            "previous_sequence": self.previous_sequence,
            "projector_reason": self.projector_reason,
            "projector_status": (
                None
                if self.projector_status is None
                else self.projector_status.value
            ),
            "resulting_sequence": self.resulting_sequence,
            "status": self.status.value,
            "strategy": self.strategy.value,
        }
