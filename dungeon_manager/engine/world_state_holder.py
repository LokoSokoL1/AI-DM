"""Process-local ownership of one committed immutable world-state snapshot."""

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Any, Optional

from .world_state import (
    WorldState,
    WorldStateProjectionResult,
    WorldStateProjectionStatus,
)


def _validate_sequence(sequence: Any, label: str) -> None:
    if (
        not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or sequence < 0
    ):
        raise ValueError(f"{label} must be a non-negative integer.")


class WorldStateSynchronizationStatus(str, Enum):
    """Whether the committed projection agrees with its event journal."""

    SYNCHRONIZED = "synchronized"
    OUT_OF_SYNC = "out_of_sync"


class ProjectionReasonCode(str, Enum):
    """Stable payload-free reasons for failed or unavailable projection."""

    INITIAL_SEQUENCE_MISMATCH = "initial_sequence_mismatch"
    JOURNAL_SEQUENCE_MISMATCH = "journal_sequence_mismatch"
    PROJECTION_FAILED = "projection_failed"
    PROJECTOR_CONTRACT_FAILURE = "projector_contract_failure"
    REENTRANT_INVOCATION = "reentrant_invocation"


@dataclass(frozen=True)
class WorldStateHealth:
    """Safe synchronization metadata that never contains world-state data."""

    status: WorldStateSynchronizationStatus
    committed_sequence: int
    journal_sequence: int
    reason_code: Optional[ProjectionReasonCode] = None
    projector_status: Optional[WorldStateProjectionStatus] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, WorldStateSynchronizationStatus):
            raise ValueError(
                "World-state health status must be a typed status."
            )
        _validate_sequence(
            self.committed_sequence,
            "World-state health committed sequence",
        )
        _validate_sequence(
            self.journal_sequence,
            "World-state health journal sequence",
        )
        if self.reason_code is not None and not isinstance(
            self.reason_code,
            ProjectionReasonCode,
        ):
            raise ValueError(
                "World-state health reason must be a typed reason code."
            )
        if self.projector_status is not None and not isinstance(
            self.projector_status,
            WorldStateProjectionStatus,
        ):
            raise ValueError(
                "World-state health projector status must be typed."
            )

        if self.status is WorldStateSynchronizationStatus.SYNCHRONIZED:
            if self.committed_sequence != self.journal_sequence:
                raise ValueError(
                    "Synchronized world-state health requires matching "
                    "sequences."
                )
            if self.reason_code is not None or self.projector_status is not None:
                raise ValueError(
                    "Synchronized world-state health cannot contain failure "
                    "metadata."
                )
            return

        if self.reason_code is None:
            raise ValueError(
                "Out-of-sync world-state health requires a reason code."
            )
        if self.reason_code is ProjectionReasonCode.REENTRANT_INVOCATION:
            raise ValueError(
                "Re-entrant invocation is not a world-state health reason."
            )
        if self.projector_status is WorldStateProjectionStatus.SUCCESS:
            raise ValueError(
                "Out-of-sync world-state health cannot report successful "
                "projection."
            )

    def to_dict(self) -> dict[str, Any]:
        """Return defensive JSON-compatible payload-free metadata."""

        return {
            "committed_sequence": self.committed_sequence,
            "journal_sequence": self.journal_sequence,
            "projector_status": (
                None
                if self.projector_status is None
                else self.projector_status.value
            ),
            "reason_code": (
                None if self.reason_code is None else self.reason_code.value
            ),
            "status": self.status.value,
        }


class WorldStateHolder:
    """Hold one committed state and expose no arbitrary mutation API."""

    def __init__(self, initial_state: WorldState) -> None:
        if not isinstance(initial_state, WorldState):
            raise ValueError(
                "World-state holder requires an explicit initial WorldState."
            )
        initial_state.validate()

        self.__state = initial_state
        self.__status = WorldStateSynchronizationStatus.SYNCHRONIZED
        self.__journal_sequence = initial_state.last_sequence
        self.__reason_code: Optional[ProjectionReasonCode] = None
        self.__projector_status: Optional[WorldStateProjectionStatus] = None
        self.__lock = Lock()

    @property
    def snapshot(self) -> WorldState:
        """Return the current deeply immutable committed snapshot."""

        with self.__lock:
            return self.__state

    @property
    def health(self) -> WorldStateHealth:
        """Return safe synchronization metadata without state data."""

        with self.__lock:
            return WorldStateHealth(
                status=self.__status,
                committed_sequence=self.__state.last_sequence,
                journal_sequence=self.__journal_sequence,
                reason_code=self.__reason_code,
                projector_status=self.__projector_status,
            )

    def _check_journal_sequence(
        self,
        journal_sequence: int,
        mismatch_reason: ProjectionReasonCode,
    ) -> bool:
        """Fail closed when the current journal tail no longer agrees."""

        _validate_sequence(journal_sequence, "Game-event journal tail sequence")
        if mismatch_reason not in {
            ProjectionReasonCode.INITIAL_SEQUENCE_MISMATCH,
            ProjectionReasonCode.JOURNAL_SEQUENCE_MISMATCH,
        }:
            raise ValueError("Invalid journal-sequence mismatch reason.")

        with self.__lock:
            if self.__status is WorldStateSynchronizationStatus.OUT_OF_SYNC:
                return False
            if self.__state.last_sequence == journal_sequence:
                self.__journal_sequence = journal_sequence
                return True

            self.__status = WorldStateSynchronizationStatus.OUT_OF_SYNC
            self.__journal_sequence = journal_sequence
            self.__reason_code = mismatch_reason
            self.__projector_status = None
            return False

    def _commit_projection(
        self,
        projection_result: WorldStateProjectionResult,
        *,
        expected_previous_sequence: int,
        journal_sequence: int,
    ) -> None:
        """Commit only one complete validated successful projection."""

        _validate_sequence(
            expected_previous_sequence,
            "Expected previous world-state sequence",
        )
        _validate_sequence(journal_sequence, "Game-event journal tail sequence")
        if not isinstance(projection_result, WorldStateProjectionResult):
            raise ValueError(
                "World-state commit requires a typed projection result."
            )
        if (
            projection_result.status is not WorldStateProjectionStatus.SUCCESS
            or not isinstance(projection_result.state, WorldState)
        ):
            raise ValueError(
                "World-state commit requires a successful projection."
            )
        projection_result.state.validate()
        if projection_result.state.last_sequence != journal_sequence:
            raise ValueError(
                "Projected world-state sequence must match the journal tail."
            )

        with self.__lock:
            if self.__status is not WorldStateSynchronizationStatus.SYNCHRONIZED:
                raise ValueError(
                    "Out-of-sync world state cannot accept a projection."
                )
            if self.__state.last_sequence != expected_previous_sequence:
                raise ValueError(
                    "Committed world state changed during projection."
                )
            if self.__journal_sequence != expected_previous_sequence:
                raise ValueError(
                    "World-state journal sequence changed during projection."
                )

            self.__state = projection_result.state
            self.__journal_sequence = journal_sequence

    def _mark_projection_failure(
        self,
        *,
        journal_sequence: int,
        reason_code: ProjectionReasonCode,
        projector_status: Optional[WorldStateProjectionStatus],
    ) -> None:
        """Irreversibly mark this holder unavailable for future dispatch."""

        _validate_sequence(journal_sequence, "Game-event journal tail sequence")
        if reason_code not in {
            ProjectionReasonCode.PROJECTION_FAILED,
            ProjectionReasonCode.PROJECTOR_CONTRACT_FAILURE,
        }:
            raise ValueError("Invalid projection-failure reason code.")
        if projector_status is not None and not isinstance(
            projector_status,
            WorldStateProjectionStatus,
        ):
            raise ValueError("Projection failure status must be typed.")
        if projector_status is WorldStateProjectionStatus.SUCCESS:
            raise ValueError("Projection failure cannot report success.")

        with self.__lock:
            if self.__status is WorldStateSynchronizationStatus.OUT_OF_SYNC:
                return
            self.__status = WorldStateSynchronizationStatus.OUT_OF_SYNC
            self.__journal_sequence = journal_sequence
            self.__reason_code = reason_code
            self.__projector_status = projector_status
