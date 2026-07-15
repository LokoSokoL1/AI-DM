"""Provider-independent command, policy, result, event, and audit boundary."""

from .audit import AuditStage, CommandAuditRecord

from .audited_pipeline import (
    AuditedCommandPipeline,
    AuditedCommandPipelineResult,
    AuditIntegrationStatus,
    EventPublicationDisposition,
)

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
from .game_event import GameEvent
from .journals import (
    CommandAuditJournal,
    CommandAuditJournalEntry,
    GameEventJournal,
    GameEventJournalEntry,
)
from .policy_gated_dispatcher import (
    PolicyGatedCommandDispatcher,
    PolicyGatedDispatchResult,
    PolicyGatedDispatchStatus,
)
from .result import GameResult, GameResultStatus
from .world_state import (
    ReducerRegistration,
    WorldState,
    WorldStateProjectionResult,
    WorldStateProjectionStatus,
    WorldStateProjector,
    WorldStateReducer,
)

__all__ = [
    "ApprovalOutcome",
    "AuditedCommandPipeline",
    "AuditedCommandPipelineResult",
    "AuditIntegrationStatus",
    "AuditStage",
    "AutomationMode",
    "AutomationPolicy",
    "CapabilityAutomationRule",
    "CommandHandler",
    "CommandAuditJournal",
    "CommandAuditJournalEntry",
    "CommandAuditRecord",
    "CommandProvenance",
    "CommandSource",
    "EventPublicationDisposition",
    "GameCommand",
    "GameEngine",
    "GameEvent",
    "GameEventJournal",
    "GameEventJournalEntry",
    "GameResult",
    "GameResultStatus",
    "GateDisposition",
    "GateDispositionStatus",
    "GateReasonCode",
    "HumanApprovalDecision",
    "PolicyDecision",
    "PolicyGatedCommandDispatcher",
    "PolicyGatedDispatchResult",
    "PolicyGatedDispatchStatus",
    "PolicyReasonCode",
    "ReducerRegistration",
    "WorldState",
    "WorldStateProjectionResult",
    "WorldStateProjectionStatus",
    "WorldStateProjector",
    "WorldStateReducer",
    "resolve_automation_gate",
]
