"""Provider-independent command, policy, result, event, and audit boundary."""

from .audit import AuditStage, CommandAuditRecord

from .audited_pipeline import (
    AuditedCommandPipeline,
    AuditedCommandPipelineResult,
    AuditIntegrationStatus,
    EventPublicationDisposition,
    ProjectionDisposition,
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
from .event_journal_store import (
    EVENT_JOURNAL_STORAGE_FORMAT,
    EVENT_JOURNAL_STORAGE_SCHEMA_VERSION,
    EventJournalStore,
    EventJournalStoreResult,
    EventJournalStoreStatus,
)
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
from .world_state_holder import (
    ProjectionReasonCode,
    WorldStateHealth,
    WorldStateHolder,
    WorldStateSynchronizationStatus,
)
from .world_state_recovery import (
    WorldStateRecoveryResult,
    WorldStateRecoveryStatus,
    WorldStateRecoveryStrategy,
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
    "EVENT_JOURNAL_STORAGE_FORMAT",
    "EVENT_JOURNAL_STORAGE_SCHEMA_VERSION",
    "EventJournalStore",
    "EventJournalStoreResult",
    "EventJournalStoreStatus",
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
    "ProjectionDisposition",
    "ProjectionReasonCode",
    "ReducerRegistration",
    "WorldState",
    "WorldStateHealth",
    "WorldStateHolder",
    "WorldStateProjectionResult",
    "WorldStateProjectionStatus",
    "WorldStateProjector",
    "WorldStateRecoveryResult",
    "WorldStateRecoveryStatus",
    "WorldStateRecoveryStrategy",
    "WorldStateReducer",
    "WorldStateSynchronizationStatus",
    "resolve_automation_gate",
]
