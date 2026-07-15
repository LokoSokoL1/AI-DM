"""Synchronous registration and one-attempt game-command dispatch."""

import inspect
import logging
from collections.abc import Callable

from ._json import validate_trimmed_identifier
from .command import GameCommand
from .result import GameResult, GameResultValidationError


logger = logging.getLogger("DungeonManager")

CommandHandler = Callable[[GameCommand], GameResult]

_UNKNOWN_COMMAND_ERROR = "No handler is registered for this command type."
_INVALID_COMMAND_ERROR = "The game command is structurally invalid."
_INVALID_HANDLER_RESULT_ERROR = (
    "The command handler returned an invalid result."
)
_HANDLER_FAILURE_ERROR = "The command handler failed."


class GameEngine:
    """Register exact command types and dispatch to at most one handler once."""

    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    @property
    def registered_command_types(self) -> tuple[str, ...]:
        """Return a deterministic immutable snapshot of registered types."""

        return tuple(sorted(self._handlers))

    def register_handler(
        self,
        command_type: str,
        handler: CommandHandler,
    ) -> None:
        """Register one callable with the exact one-command handler shape."""

        validate_trimmed_identifier(command_type, "Registered command type")
        if command_type in self._handlers:
            raise ValueError(
                f"Duplicate command handler registration: {command_type}"
            )
        if not callable(handler):
            raise ValueError("Registered command handler must be callable.")
        if inspect.iscoroutinefunction(handler):
            raise ValueError("Registered command handler must be synchronous.")

        try:
            signature = inspect.signature(handler)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Registered command handler must have an inspectable signature."
            ) from error

        parameters = tuple(signature.parameters.values())
        supported_kinds = {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
        if (
            len(parameters) != 1
            or parameters[0].kind not in supported_kinds
        ):
            raise ValueError(
                "Registered command handler must accept exactly one command."
            )

        self._handlers[command_type] = handler

    def dispatch(self, command: GameCommand) -> GameResult:
        """Invoke the exact matching handler once, with no retry or fallback."""

        if not isinstance(command, GameCommand):
            raise TypeError("GameEngine.dispatch requires a GameCommand.")

        try:
            command.validate()
        except (TypeError, ValueError):
            logger.exception(
                "Invalid game command rejected before dispatch (command_id=%r)",
                getattr(command, "command_id", None),
            )
            return GameResult.invalid_command(
                command_id=command.command_id,
                error=_INVALID_COMMAND_ERROR,
            )

        handler = self._handlers.get(command.command_type)
        if handler is None:
            logger.warning(
                "Unknown game command type %s (command_id=%s)",
                command.command_type,
                command.command_id,
            )
            return GameResult.unknown_command(
                command_id=command.command_id,
                error=_UNKNOWN_COMMAND_ERROR,
            )

        try:
            result = handler(command)
        except GameResultValidationError:
            logger.exception(
                "Game command handler constructed an invalid result for %s "
                "(command_id=%s)",
                command.command_type,
                command.command_id,
            )
            return GameResult.invalid_handler_result(
                command_id=command.command_id,
                error=_INVALID_HANDLER_RESULT_ERROR,
            )
        except Exception:
            logger.exception(
                "Game command handler failed for %s (command_id=%s)",
                command.command_type,
                command.command_id,
            )
            return GameResult.handler_failure(
                command_id=command.command_id,
                error=_HANDLER_FAILURE_ERROR,
            )

        if not isinstance(result, GameResult):
            logger.error(
                "Game command handler returned %s instead of GameResult for %s "
                "(command_id=%s)",
                type(result).__name__,
                command.command_type,
                command.command_id,
            )
            return GameResult.invalid_handler_result(
                command_id=command.command_id,
                error=_INVALID_HANDLER_RESULT_ERROR,
            )

        try:
            result.validate()
        except (TypeError, ValueError):
            logger.exception(
                "Game command handler returned a structurally invalid result "
                "for %s (command_id=%s)",
                command.command_type,
                command.command_id,
            )
            return GameResult.invalid_handler_result(
                command_id=command.command_id,
                error=_INVALID_HANDLER_RESULT_ERROR,
            )

        if result.command_id != command.command_id:
            logger.error(
                "Game command handler returned mismatched command ID %s for %s "
                "(expected=%s)",
                result.command_id,
                command.command_type,
                command.command_id,
            )
            return GameResult.invalid_handler_result(
                command_id=command.command_id,
                error=_INVALID_HANDLER_RESULT_ERROR,
            )

        return result
