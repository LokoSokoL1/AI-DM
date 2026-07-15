"""Provider-independent command and result boundary for the game engine."""

from .command import CommandProvenance, CommandSource, GameCommand
from .game_engine import CommandHandler, GameEngine
from .result import GameResult, GameResultStatus

__all__ = [
    "CommandHandler",
    "CommandProvenance",
    "CommandSource",
    "GameCommand",
    "GameEngine",
    "GameResult",
    "GameResultStatus",
]
