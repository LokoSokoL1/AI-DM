"""Immutable results for one game-command handling attempt."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ._json import (
    freeze_json_value,
    thaw_json_value,
    validate_trimmed_identifier,
)


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

    def __post_init__(self) -> None:
        self.validate()
        if self.output is not None:
            object.__setattr__(
                self,
                "output",
                freeze_json_value(self.output, "Game result output"),
            )

    def validate(self) -> None:
        """Validate invariants, including after receipt from a handler."""

        validate_trimmed_identifier(self.command_id, "Result command ID")
        if not isinstance(self.status, GameResultStatus):
            raise ValueError("Game result status must be a GameResultStatus value.")

        if self.status is GameResultStatus.SUCCESS:
            if self.error is not None:
                raise ValueError("Successful game results must not contain errors.")
        else:
            validate_trimmed_identifier(self.error, "Game result error")
            if self.output is not None:
                raise ValueError("Failed game results must not contain output.")

        if self.output is not None:
            freeze_json_value(self.output, "Game result output")

    @classmethod
    def success(cls, command_id: str, output: Any = None) -> "GameResult":
        return cls(
            command_id=command_id,
            status=GameResultStatus.SUCCESS,
            output=output,
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
            "output": (
                None
                if self.output is None
                else thaw_json_value(self.output)
            ),
            "status": self.status.value,
        }
