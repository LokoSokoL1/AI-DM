"""Pure deterministic projection of game-event entries into world state."""

import inspect
import logging
from collections.abc import Callable, Iterable, Mapping, Set as AbstractSet
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Optional

from ._json import (
    freeze_json_value,
    thaw_json_value,
    validate_trimmed_identifier,
)
from .game_event import GameEvent
from .journals import GameEventJournalEntry


logger = logging.getLogger("DungeonManager")

WorldStateReducer = Callable[[Mapping[str, Any], GameEvent], Mapping[str, Any]]

_INVALID_STATE_ERROR = "The starting world state is structurally invalid."
_INVALID_ENTRIES_ERROR = (
    "The game-event entries or their journal sequence are invalid."
)
_UNKNOWN_EVENT_TYPE_ERROR = (
    "No world-state reducer is registered for this event type."
)
_UNSUPPORTED_SCHEMA_VERSION_ERROR = (
    "No world-state reducer supports this event schema version."
)
_INVALID_REDUCER_RESULT_ERROR = (
    "The world-state reducer returned an invalid state object."
)
_REDUCER_FAILURE_ERROR = "The world-state reducer failed."


def _validate_world_sequence(sequence: Any) -> None:
    if (
        not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or sequence < 0
    ):
        raise ValueError(
            "World-state last sequence must be a non-negative integer."
        )


def _validate_schema_version(schema_version: Any) -> None:
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version < 1
    ):
        raise ValueError(
            "Reducer schema version must be a positive integer."
        )


@dataclass(frozen=True)
class WorldState:
    """Immutable derived state data and its last applied journal sequence."""

    data: Any = field(default_factory=dict)
    last_sequence: int = 0

    def __post_init__(self) -> None:
        _validate_world_sequence(self.last_sequence)
        if not isinstance(self.data, Mapping):
            raise ValueError("World-state data must be a JSON object.")
        object.__setattr__(
            self,
            "data",
            freeze_json_value(self.data, "World-state data"),
        )

    @classmethod
    def initial(cls) -> "WorldState":
        """Return the empty initial derived state at journal sequence zero."""

        return cls()

    def validate(self) -> None:
        """Revalidate this state before using it as a projection boundary."""

        _validate_world_sequence(self.last_sequence)
        if not isinstance(self.data, Mapping):
            raise ValueError("World-state data must be a JSON object.")
        freeze_json_value(self.data, "World-state data")

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible representation."""

        return {
            "data": thaw_json_value(self.data),
            "last_sequence": self.last_sequence,
        }


@dataclass(frozen=True, order=True)
class ReducerRegistration:
    """One exact event-type and schema-version reducer registration key."""

    event_type: str
    schema_version: int

    def __post_init__(self) -> None:
        validate_trimmed_identifier(
            self.event_type,
            "Reducer event type",
        )
        _validate_schema_version(self.schema_version)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "schema_version": self.schema_version,
        }


class WorldStateProjectionStatus(str, Enum):
    SUCCESS = "success"
    INVALID_STATE = "invalid_state"
    INVALID_ENTRY_OR_SEQUENCE = "invalid_entry_or_sequence"
    UNKNOWN_EVENT_TYPE = "unknown_event_type"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    INVALID_REDUCER_RESULT = "invalid_reducer_result"
    REDUCER_FAILURE = "reducer_failure"


@dataclass(frozen=True)
class WorldStateProjectionResult:
    """A completed projection or one controlled, sanitized failure."""

    status: WorldStateProjectionStatus
    state: Optional[WorldState] = None
    error: Optional[str] = None
    sequence: Optional[int] = None
    event_id: Optional[str] = None
    event_type: Optional[str] = None
    schema_version: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, WorldStateProjectionStatus):
            raise ValueError(
                "World-state projection status must be a typed status."
            )

        if self.status is WorldStateProjectionStatus.SUCCESS:
            if not isinstance(self.state, WorldState):
                raise ValueError(
                    "Successful world-state projection requires a WorldState."
                )
            self.state.validate()
            if self.error is not None:
                raise ValueError(
                    "Successful world-state projection cannot contain an error."
                )
            if any(
                value is not None
                for value in (
                    self.sequence,
                    self.event_id,
                    self.event_type,
                    self.schema_version,
                )
            ):
                raise ValueError(
                    "Successful world-state projection cannot contain failure "
                    "diagnostics."
                )
            return

        if self.state is not None:
            raise ValueError(
                "Failed world-state projection cannot expose a state."
            )
        validate_trimmed_identifier(
            self.error,
            "World-state projection error",
        )
        if self.sequence is not None:
            if (
                not isinstance(self.sequence, int)
                or isinstance(self.sequence, bool)
                or self.sequence < 1
            ):
                raise ValueError(
                    "Projection diagnostic sequence must be a positive integer."
                )
        if self.event_id is not None:
            validate_trimmed_identifier(
                self.event_id,
                "Projection diagnostic event ID",
            )
        if self.event_type is not None:
            validate_trimmed_identifier(
                self.event_type,
                "Projection diagnostic event type",
            )
        if self.schema_version is not None:
            _validate_schema_version(self.schema_version)

    @classmethod
    def succeeded(cls, state: WorldState) -> "WorldStateProjectionResult":
        return cls(
            status=WorldStateProjectionStatus.SUCCESS,
            state=state,
        )

    @classmethod
    def failed(
        cls,
        status: WorldStateProjectionStatus,
        error: str,
        *,
        entry: Optional[GameEventJournalEntry] = None,
    ) -> "WorldStateProjectionResult":
        if status is WorldStateProjectionStatus.SUCCESS:
            raise ValueError("A failed projection requires a failure status.")
        if entry is None:
            return cls(status=status, error=error)
        return cls(
            status=status,
            error=error,
            sequence=entry.sequence,
            event_id=entry.event.event_id,
            event_type=entry.event.event_type,
            schema_version=entry.event.schema_version,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return defensive JSON data without payloads or reducer details."""

        serialized: dict[str, Any] = {"status": self.status.value}
        if self.status is WorldStateProjectionStatus.SUCCESS:
            serialized["state"] = self.state.to_dict()
            return serialized

        serialized["error"] = self.error
        diagnostics = {
            "sequence": self.sequence,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
        }
        serialized.update(
            {
                key: value
                for key, value in diagnostics.items()
                if value is not None
            }
        )
        return serialized


class WorldStateProjector:
    """Register exact reducers and apply ordered journal snapshots once."""

    def __init__(self) -> None:
        self.__reducers: dict[
            tuple[str, int],
            WorldStateReducer,
        ] = {}
        self.__lock = Lock()

    @property
    def registrations(self) -> tuple[ReducerRegistration, ...]:
        """Return an immutable snapshot sorted by event type then version."""

        with self.__lock:
            keys = tuple(sorted(self.__reducers))
        return tuple(
            ReducerRegistration(event_type, schema_version)
            for event_type, schema_version in keys
        )

    def register_reducer(
        self,
        event_type: str,
        schema_version: int,
        reducer: WorldStateReducer,
    ) -> None:
        """Register one synchronous exact-shape reducer for one exact key."""

        registration = ReducerRegistration(event_type, schema_version)
        if not callable(reducer):
            raise ValueError("Registered world-state reducer must be callable.")
        if inspect.iscoroutinefunction(reducer) or inspect.iscoroutinefunction(
            getattr(reducer, "__call__", None)
        ):
            raise ValueError(
                "Registered world-state reducer must be synchronous."
            )

        try:
            signature = inspect.signature(reducer)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Registered world-state reducer must have an inspectable "
                "signature."
            ) from error

        parameters = tuple(signature.parameters.values())
        if (
            len(parameters) != 2
            or any(
                parameter.kind
                is not inspect.Parameter.POSITIONAL_OR_KEYWORD
                or parameter.default is not inspect.Parameter.empty
                for parameter in parameters
            )
        ):
            raise ValueError(
                "Registered world-state reducer must accept exactly two "
                "required positional-or-keyword parameters."
            )

        key = (registration.event_type, registration.schema_version)
        with self.__lock:
            if key in self.__reducers:
                raise ValueError(
                    "Duplicate world-state reducer registration: "
                    f"{registration.event_type} schema "
                    f"{registration.schema_version}"
                )
            self.__reducers[key] = reducer

    def replay(
        self,
        entries: Iterable[GameEventJournalEntry],
    ) -> WorldStateProjectionResult:
        """Project one complete journal-entry snapshot from initial state."""

        return self.project(entries, WorldState.initial())

    def project(
        self,
        entries: Iterable[GameEventJournalEntry],
        state: WorldState,
    ) -> WorldStateProjectionResult:
        """Incrementally project entries immediately following one state."""

        if not isinstance(state, WorldState):
            return WorldStateProjectionResult.failed(
                WorldStateProjectionStatus.INVALID_STATE,
                _INVALID_STATE_ERROR,
            )
        try:
            state.validate()
        except (TypeError, ValueError):
            logger.exception("Invalid starting world state rejected")
            return WorldStateProjectionResult.failed(
                WorldStateProjectionStatus.INVALID_STATE,
                _INVALID_STATE_ERROR,
            )

        snapshot = self._materialize_entries(entries)
        if snapshot is None:
            return WorldStateProjectionResult.failed(
                WorldStateProjectionStatus.INVALID_ENTRY_OR_SEQUENCE,
                _INVALID_ENTRIES_ERROR,
            )

        invalid_entry = self._validate_entries(snapshot, state.last_sequence)
        if invalid_entry is not None:
            return invalid_entry
        if not snapshot:
            return WorldStateProjectionResult.succeeded(state)

        with self.__lock:
            reducers = dict(self.__reducers)

        resolved: list[tuple[GameEventJournalEntry, WorldStateReducer]] = []
        registered_event_types = {
            event_type for event_type, _ in reducers
        }
        for entry in snapshot:
            key = (entry.event.event_type, entry.event.schema_version)
            reducer = reducers.get(key)
            if reducer is None:
                if entry.event.event_type in registered_event_types:
                    return WorldStateProjectionResult.failed(
                        WorldStateProjectionStatus.UNSUPPORTED_SCHEMA_VERSION,
                        _UNSUPPORTED_SCHEMA_VERSION_ERROR,
                        entry=entry,
                    )
                return WorldStateProjectionResult.failed(
                    WorldStateProjectionStatus.UNKNOWN_EVENT_TYPE,
                    _UNKNOWN_EVENT_TYPE_ERROR,
                    entry=entry,
                )
            resolved.append((entry, reducer))

        candidate_data = state.data
        for entry, reducer in resolved:
            try:
                reducer_output = reducer(candidate_data, entry.event)
            except Exception:
                logger.exception(
                    "World-state reducer failed (sequence=%s, event_id=%s, "
                    "event_type=%s, schema_version=%s)",
                    entry.sequence,
                    entry.event.event_id,
                    entry.event.event_type,
                    entry.event.schema_version,
                )
                return WorldStateProjectionResult.failed(
                    WorldStateProjectionStatus.REDUCER_FAILURE,
                    _REDUCER_FAILURE_ERROR,
                    entry=entry,
                )

            if not isinstance(reducer_output, Mapping):
                return WorldStateProjectionResult.failed(
                    WorldStateProjectionStatus.INVALID_REDUCER_RESULT,
                    _INVALID_REDUCER_RESULT_ERROR,
                    entry=entry,
                )
            try:
                candidate_data = freeze_json_value(
                    reducer_output,
                    "World-state reducer output",
                )
            except Exception:
                logger.exception(
                    "World-state reducer returned invalid data "
                    "(sequence=%s, event_id=%s, event_type=%s, "
                    "schema_version=%s)",
                    entry.sequence,
                    entry.event.event_id,
                    entry.event.event_type,
                    entry.event.schema_version,
                )
                return WorldStateProjectionResult.failed(
                    WorldStateProjectionStatus.INVALID_REDUCER_RESULT,
                    _INVALID_REDUCER_RESULT_ERROR,
                    entry=entry,
                )

        completed_state = WorldState(
            data=candidate_data,
            last_sequence=snapshot[-1].sequence,
        )
        return WorldStateProjectionResult.succeeded(completed_state)

    @staticmethod
    def _materialize_entries(
        entries: Iterable[GameEventJournalEntry],
    ) -> Optional[tuple[GameEventJournalEntry, ...]]:
        if (
            isinstance(
                entries,
                (str, bytes, bytearray, Mapping, AbstractSet),
            )
            or not isinstance(entries, Iterable)
        ):
            return None
        try:
            return tuple(entries)
        except Exception:
            logger.exception("World-state journal-entry snapshot failed")
            return None

    @staticmethod
    def _validate_entries(
        entries: tuple[GameEventJournalEntry, ...],
        last_sequence: int,
    ) -> Optional[WorldStateProjectionResult]:
        expected_sequence = last_sequence + 1
        event_ids: set[str] = set()

        for offset, entry in enumerate(entries):
            if not isinstance(entry, GameEventJournalEntry):
                return WorldStateProjectionResult.failed(
                    WorldStateProjectionStatus.INVALID_ENTRY_OR_SEQUENCE,
                    _INVALID_ENTRIES_ERROR,
                )

            try:
                if (
                    not isinstance(entry.sequence, int)
                    or isinstance(entry.sequence, bool)
                    or entry.sequence < 1
                ):
                    raise ValueError("Invalid journal sequence.")
                if not isinstance(entry.event, GameEvent):
                    raise ValueError("Invalid journal event.")
                entry.event.validate()
            except (TypeError, ValueError):
                return WorldStateProjectionResult.failed(
                    WorldStateProjectionStatus.INVALID_ENTRY_OR_SEQUENCE,
                    _INVALID_ENTRIES_ERROR,
                )

            if entry.sequence != expected_sequence + offset:
                return WorldStateProjectionResult.failed(
                    WorldStateProjectionStatus.INVALID_ENTRY_OR_SEQUENCE,
                    _INVALID_ENTRIES_ERROR,
                    entry=entry,
                )
            if entry.event.event_id in event_ids:
                return WorldStateProjectionResult.failed(
                    WorldStateProjectionStatus.INVALID_ENTRY_OR_SEQUENCE,
                    _INVALID_ENTRIES_ERROR,
                    entry=entry,
                )
            event_ids.add(entry.event.event_id)

        return None
