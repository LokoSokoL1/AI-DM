"""Explicit all-or-nothing hydration of one durable event-journal runtime."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ._json import validate_trimmed_identifier
from .durable_journal import (
    DurableJournalBinding,
    EventJournalStoreResult,
    EventJournalStoreStatus,
)
from .event_journal_store import EventJournalStore
from .journals import GameEventJournal
from .world_state import (
    WorldState,
    WorldStateProjectionResult,
    WorldStateProjectionStatus,
    WorldStateProjector,
)
from .world_state_holder import WorldStateHolder


logger = logging.getLogger("DungeonManager")

_INVALID_INPUT_ERROR = "Startup hydration input is invalid."
_NOT_FOUND_ERROR = "The durable event journal does not exist."
_JOURNAL_ID_MISMATCH_ERROR = (
    "The durable journal identity does not match the expected journal."
)
_CORRUPT_ERROR = "The durable event journal is corrupt."
_UNSUPPORTED_VERSION_ERROR = "The durable event-journal version is unsupported."
_STORAGE_FAILURE_ERROR = "The durable event journal could not be loaded."
_PROJECTION_FAILURE_ERROR = (
    "Durable startup projection failed; no runtime was initialized."
)
_INITIALIZATION_FAILURE_ERROR = "Durable startup hydration failed safely."


class StartupHydrationStatus(str, Enum):
    """Controlled outcomes of one explicit durable startup hydration."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"
    JOURNAL_ID_MISMATCH = "journal_id_mismatch"
    CORRUPT = "corrupt"
    UNSUPPORTED_VERSION = "unsupported_version"
    STORAGE_FAILURE = "storage_failure"
    PROJECTION_FAILURE = "projection_failure"
    INITIALIZATION_FAILURE = "initialization_failure"


@dataclass(frozen=True)
class HydratedDurableRuntime:
    """Fresh synchronized in-process views and their validated store binding."""

    event_journal: GameEventJournal
    state_holder: WorldStateHolder
    durable_binding: DurableJournalBinding

    def __post_init__(self) -> None:
        if not isinstance(self.event_journal, GameEventJournal):
            raise ValueError("Hydrated runtime requires a fresh game-event journal.")
        if not isinstance(self.state_holder, WorldStateHolder):
            raise ValueError("Hydrated runtime requires a world-state holder.")
        if not isinstance(self.durable_binding, DurableJournalBinding):
            raise ValueError("Hydrated runtime requires a durable journal binding.")
        journal_tail = self.event_journal.tail_sequence
        if (
            journal_tail != self.state_holder.snapshot.last_sequence
            or journal_tail != self.durable_binding.tail_sequence
        ):
            raise ValueError("Hydrated runtime tails must agree exactly.")


@dataclass(frozen=True)
class StartupHydrationResult:
    """Safe hydration metadata; only success may carry the runtime internally."""

    status: StartupHydrationStatus
    journal_id: Optional[str] = None
    tail_sequence: Optional[int] = None
    reason_code: Optional[str] = None
    error: Optional[str] = None
    runtime: Optional[HydratedDurableRuntime] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, StartupHydrationStatus):
            raise ValueError("Startup hydration status must be typed.")
        if self.journal_id is not None:
            validate_trimmed_identifier(self.journal_id, "Journal ID")
        if self.tail_sequence is not None and (
            not isinstance(self.tail_sequence, int)
            or isinstance(self.tail_sequence, bool)
            or self.tail_sequence < 0
        ):
            raise ValueError("Hydration tail sequence must be non-negative.")
        if self.reason_code is not None:
            validate_trimmed_identifier(self.reason_code, "Hydration reason code")

        if self.status is StartupHydrationStatus.SUCCESS:
            if (
                not isinstance(self.runtime, HydratedDurableRuntime)
                or self.journal_id is None
                or self.tail_sequence is None
                or self.reason_code is not None
                or self.error is not None
            ):
                raise ValueError("Successful hydration requires only a complete runtime.")
            if (
                self.runtime.durable_binding.journal_id != self.journal_id
                or self.runtime.durable_binding.tail_sequence != self.tail_sequence
            ):
                raise ValueError("Hydration result metadata must match its runtime.")
            return

        if self.runtime is not None:
            raise ValueError("Failed hydration cannot expose a partial runtime.")
        validate_trimmed_identifier(self.reason_code, "Hydration reason code")
        validate_trimmed_identifier(self.error, "Hydration error")

    def to_dict(self) -> dict[str, Any]:
        """Serialize only safe metadata, never entries, state, or store details."""

        return {
            "error": self.error,
            "journal_id": self.journal_id,
            "reason_code": self.reason_code,
            "status": self.status.value,
            "tail_sequence": self.tail_sequence,
        }


def _failure(
    status: StartupHydrationStatus,
    reason_code: str,
    error: str,
    *,
    journal_id: Optional[str] = None,
    tail_sequence: Optional[int] = None,
) -> StartupHydrationResult:
    return StartupHydrationResult(
        status=status,
        journal_id=journal_id,
        tail_sequence=tail_sequence,
        reason_code=reason_code,
        error=error,
    )


def hydrate_durable_runtime(
    store: EventJournalStore,
    *,
    expected_journal_id: str,
    base_state: WorldState,
    projector: WorldStateProjector,
) -> StartupHydrationResult:
    """Load, validate, reconstruct, and expose one fresh durable runtime."""

    if not isinstance(store, EventJournalStore):
        return _failure(
            StartupHydrationStatus.INVALID_INPUT,
            "invalid_store",
            _INVALID_INPUT_ERROR,
        )
    try:
        validate_trimmed_identifier(expected_journal_id, "Expected journal ID")
    except (TypeError, ValueError):
        return _failure(
            StartupHydrationStatus.INVALID_INPUT,
            "invalid_expected_journal_id",
            _INVALID_INPUT_ERROR,
        )
    if not isinstance(base_state, WorldState):
        return _failure(
            StartupHydrationStatus.INVALID_INPUT,
            "missing_base_state",
            _INVALID_INPUT_ERROR,
            journal_id=expected_journal_id,
        )
    try:
        base_state.validate()
    except (TypeError, ValueError):
        return _failure(
            StartupHydrationStatus.INVALID_INPUT,
            "invalid_base_state",
            _INVALID_INPUT_ERROR,
            journal_id=expected_journal_id,
        )
    if base_state.last_sequence != 0:
        return _failure(
            StartupHydrationStatus.INVALID_INPUT,
            "nonzero_base_state",
            _INVALID_INPUT_ERROR,
            journal_id=expected_journal_id,
        )
    if not isinstance(projector, WorldStateProjector):
        return _failure(
            StartupHydrationStatus.INVALID_INPUT,
            "invalid_projector",
            _INVALID_INPUT_ERROR,
            journal_id=expected_journal_id,
        )

    try:
        loaded = store.load()
    except Exception:
        logger.error("Durable startup store contract failed safely")
        return _failure(
            StartupHydrationStatus.STORAGE_FAILURE,
            "store_load_failed",
            _STORAGE_FAILURE_ERROR,
            journal_id=expected_journal_id,
        )
    if not isinstance(loaded, EventJournalStoreResult):
        return _failure(
            StartupHydrationStatus.INITIALIZATION_FAILURE,
            "invalid_store_result",
            _INITIALIZATION_FAILURE_ERROR,
            journal_id=expected_journal_id,
        )
    if loaded.status is not EventJournalStoreStatus.SUCCESS:
        mapped_status, error = {
            EventJournalStoreStatus.NOT_FOUND: (
                StartupHydrationStatus.NOT_FOUND,
                _NOT_FOUND_ERROR,
            ),
            EventJournalStoreStatus.INVALID_INPUT: (
                StartupHydrationStatus.INVALID_INPUT,
                _INVALID_INPUT_ERROR,
            ),
            EventJournalStoreStatus.JOURNAL_ID_MISMATCH: (
                StartupHydrationStatus.JOURNAL_ID_MISMATCH,
                _JOURNAL_ID_MISMATCH_ERROR,
            ),
            EventJournalStoreStatus.CORRUPT: (
                StartupHydrationStatus.CORRUPT,
                _CORRUPT_ERROR,
            ),
            EventJournalStoreStatus.UNSUPPORTED_VERSION: (
                StartupHydrationStatus.UNSUPPORTED_VERSION,
                _UNSUPPORTED_VERSION_ERROR,
            ),
            EventJournalStoreStatus.STORAGE_FAILURE: (
                StartupHydrationStatus.STORAGE_FAILURE,
                _STORAGE_FAILURE_ERROR,
            ),
        }.get(
            loaded.status,
            (
                StartupHydrationStatus.INITIALIZATION_FAILURE,
                _INITIALIZATION_FAILURE_ERROR,
            ),
        )
        return _failure(
            mapped_status,
            loaded.reason_code or "store_load_rejected",
            error,
            journal_id=loaded.journal_id or expected_journal_id,
            tail_sequence=loaded.tail_sequence,
        )

    if loaded.journal_id != expected_journal_id:
        return _failure(
            StartupHydrationStatus.JOURNAL_ID_MISMATCH,
            "journal_id_mismatch",
            _JOURNAL_ID_MISMATCH_ERROR,
            journal_id=loaded.journal_id,
            tail_sequence=loaded.tail_sequence,
        )
    entries = loaded.entries
    tail = loaded.tail_sequence
    if (
        not isinstance(entries, tuple)
        or not isinstance(tail, int)
        or isinstance(tail, bool)
        or tail < 0
        or len(entries) != tail
        or loaded.previous_tail != tail
        or loaded.appended_count != 0
    ):
        return _failure(
            StartupHydrationStatus.INITIALIZATION_FAILURE,
            "invalid_store_snapshot",
            _INITIALIZATION_FAILURE_ERROR,
            journal_id=expected_journal_id,
        )

    try:
        event_journal = GameEventJournal.from_snapshot(entries)
    except Exception:
        logger.error("Durable startup journal reconstruction failed safely")
        return _failure(
            StartupHydrationStatus.INITIALIZATION_FAILURE,
            "journal_initialization_failed",
            _INITIALIZATION_FAILURE_ERROR,
            journal_id=expected_journal_id,
            tail_sequence=tail,
        )

    try:
        projection = projector.project(entries, base_state)
    except Exception:
        logger.error("Durable startup projection contract failed safely")
        return _failure(
            StartupHydrationStatus.PROJECTION_FAILURE,
            "projector_contract_failure",
            _PROJECTION_FAILURE_ERROR,
            journal_id=expected_journal_id,
            tail_sequence=tail,
        )
    if not isinstance(projection, WorldStateProjectionResult):
        return _failure(
            StartupHydrationStatus.PROJECTION_FAILURE,
            "invalid_projection_result",
            _PROJECTION_FAILURE_ERROR,
            journal_id=expected_journal_id,
            tail_sequence=tail,
        )
    if projection.status is not WorldStateProjectionStatus.SUCCESS:
        return _failure(
            StartupHydrationStatus.PROJECTION_FAILURE,
            projection.status.value,
            _PROJECTION_FAILURE_ERROR,
            journal_id=expected_journal_id,
            tail_sequence=tail,
        )

    try:
        projected_state = projection.state
        if not isinstance(projected_state, WorldState):
            raise ValueError("Projection returned no world state.")
        projected_state.validate()
        if (
            projected_state.last_sequence != tail
            or event_journal.tail_sequence != tail
        ):
            raise ValueError("Hydrated tails do not agree.")
        holder = WorldStateHolder(projected_state)
        binding = DurableJournalBinding(
            store=store,
            journal_id=expected_journal_id,
            tail_sequence=tail,
        )
        runtime = HydratedDurableRuntime(event_journal, holder, binding)
    except Exception:
        logger.error("Durable startup runtime initialization failed safely")
        return _failure(
            StartupHydrationStatus.INITIALIZATION_FAILURE,
            "runtime_initialization_failed",
            _INITIALIZATION_FAILURE_ERROR,
            journal_id=expected_journal_id,
            tail_sequence=tail,
        )

    return StartupHydrationResult(
        status=StartupHydrationStatus.SUCCESS,
        journal_id=expected_journal_id,
        tail_sequence=tail,
        runtime=runtime,
    )
