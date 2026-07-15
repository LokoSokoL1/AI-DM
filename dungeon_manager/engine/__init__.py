"""Provider-independent command, policy, and result game-engine boundary."""

from .automation import (
    ApprovalOutcome,
    AutomationMode,
    AutomationPolicy,
    CapabilityAutomationRule,
    GateDisposition,
    GateDispositionStatus,
    GateReasonCode,
    HumanApprovalDecision,
    PolicyDecision,
    PolicyReasonCode,
    resolve_automation_gate,
)

from .command import CommandProvenance, CommandSource, GameCommand
from .game_engine import CommandHandler, GameEngine
from .result import GameResult, GameResultStatus

__all__ = [
    "ApprovalOutcome",
    "AutomationMode",
    "AutomationPolicy",
    "CapabilityAutomationRule",
    "CommandHandler",
    "CommandProvenance",
    "CommandSource",
    "GameCommand",
    "GameEngine",
    "GameResult",
    "GameResultStatus",
    "GateDisposition",
    "GateDispositionStatus",
    "GateReasonCode",
    "HumanApprovalDecision",
    "PolicyDecision",
    "PolicyReasonCode",
    "resolve_automation_gate",
]
