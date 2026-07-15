"""Immutable results for one game-command handling attempt."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ._json import (
    freeze_json_value,
    thaw_json_value,
    validate_trimmed_identifier,
)
from .game_event import GameEvent


class GameResultValidationError(ValueError):
    """A result could not satisfy the command-handler result contract."""


class GameResultStatus(str, Enum):
    """Provider-independent outcomes of command validation and handling."""

    SUCCESS = "success"
    UNKNOWN_COMMAND = "unknown_command"
    INVALID_COMMAND = "invalid_command"
    INVALID_HANDLER_RESULT = "invalid_handler_result"
    HANDLER_FAILURE = "handler_failure"


@dataclass(frozen=True)
class GameResult:
    """The validated caller-facing result linked to one command ID."""

    command_id: str
    status: GameResultStatus
    output: Any = None
    error: Optional[str] = None
    events: tuple[GameEvent, ...] = ()

    def __post_init__(self) -> None:
        try:
            events = self._immutable_event_snapshot(self.events)
            object.__setattr__(self, "events", events)
            self.validate()
        except GameResultValidationError:
            raise
        except (TypeError, ValueError) as error:
            raise GameResultValidationError(str(error)) from error

        if self.output is not None:
            object.__setattr__(
                self,
                "output",
                freeze_json_value(self.output, "Game result output"),
            )

    def validate(self) -> None:
        """Validate invariants, including after receipt from a handler."""

        try:
            self._validate()
        except GameResultValidationError:
            raise
        except (TypeError, ValueError) as error:
            raise GameResultValidationError(str(error)) from error

    def _validate(self) -> None:
        validate_trimmed_identifier(self.command_id, "Result command ID")
        if not isinstance(self.status, GameResultStatus):
            raise GameResultValidationError(
                "Game result status must be a GameResultStatus value."
            )
        if not isinstance(self.events, tuple):
            raise GameResultValidationError(
                "Game result events must be an immutable ordered collection."
            )

        if self.status is GameResultStatus.SUCCESS:
            if self.error is not None:
                raise GameResultValidationError(
                    "Successful game results must not contain errors."
                )
        else:
            validate_trimmed_identifier(self.error, "Game result error")
            if self.output is not None:
                raise GameResultValidationError(
                    "Failed game results must not contain output."
                )
            if self.events:
                raise GameResultValidationError(
                    "Failed game results must not contain events."
                )

        if self.output is not None:
            freeze_json_value(self.output, "Game result output")

        event_ids: set[str] = set()
        for event in self.events:
            if not isinstance(event, GameEvent):
                raise GameResultValidationError(
                    "Game result events must contain only GameEvent values."
                )
            event.validate()
            if event.originating_command_id != self.command_id:
                raise GameResultValidationError(
                    "Game result events must reference the result command ID."
                )
            if event.event_id in event_ids:
                raise GameResultValidationError(
                    "Game result event IDs must be unique."
                )
            event_ids.add(event.event_id)

    @staticmethod
    def _immutable_event_snapshot(events: Any) -> tuple[GameEvent, ...]:
        if (
            isinstance(events, (str, bytes, bytearray, Mapping))
            or not isinstance(events, Sequence)
        ):
            raise GameResultValidationError(
                "Game result events must be an ordered collection."
            )
        return tuple(events)

    @classmethod
    def success(
        cls,
        command_id: str,
        output: Any = None,
        events: Sequence[GameEvent] = (),
    ) -> "GameResult":
        return cls(
            command_id=command_id,
            status=GameResultStatus.SUCCESS,
            output=output,
            events=events,
        )

    @classmethod
    def unknown_command(cls, command_id: str, error: str) -> "GameResult":
        return cls(
            command_id=command_id,
            status=GameResultStatus.UNKNOWN_COMMAND,
            error=error,
        )

    @classmethod
    def invalid_command(cls, command_id: str, error: str) -> "GameResult":
        return cls(
            command_id=command_id,
            status=GameResultStatus.INVALID_COMMAND,
            error=error,
        )

    @classmethod
    def invalid_handler_result(
        cls,
        command_id: str,
        error: str,
    ) -> "GameResult":
        return cls(
            command_id=command_id,
            status=GameResultStatus.INVALID_HANDLER_RESULT,
            error=error,
        )

    @classmethod
    def handler_failure(cls, command_id: str, error: str) -> "GameResult":
        return cls(
            command_id=command_id,
            status=GameResultStatus.HANDLER_FAILURE,
            error=error,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible transport representation."""

        return {
            "command_id": self.command_id,
            "error": self.error,
            "events": [event.to_dict() for event in self.events],
            "output": (
                None
                if self.output is None
                else thaw_json_value(self.output)
            ),
            "status": self.status.value,
        }
