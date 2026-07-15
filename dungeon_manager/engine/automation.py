"""Pure automation policy, human approval, and gate disposition types."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Optional

from ._json import (
    validate_optional_identifier,
    validate_trimmed_identifier,
)
from .command import CommandSource, GameCommand


class AutomationMode(str, Enum):
    """How far automation confirmation allows one command to proceed."""

    DENY = "deny"
    SUGGEST = "suggest"
    REQUIRE_CONFIRMATION = "require_confirmation"
    AUTOMATIC = "automatic"


class PolicyReasonCode(str, Enum):
    """Stable reasons for selecting an automation mode."""

    EXACT_RULE = "exact_rule"
    CAPABILITY_RULE = "capability_rule"
    INITIATOR_RULE = "initiator_rule"
    UNKNOWN_CAPABILITY = "unknown_capability"
    UNCONFIGURED_CAPABILITY = "unconfigured_capability"


class ApprovalOutcome(str, Enum):
    """An explicit human response to a confirmation request."""

    APPROVED = "approved"
    DENIED = "denied"


class GateDispositionStatus(str, Enum):
    """The automation gate state before any command dispatch."""

    READY = "ready"
    AWAITING_APPROVAL = "awaiting_approval"
    SUGGEST_ONLY = "suggest_only"
    DENIED = "denied"
    INVALID = "invalid"


class GateReasonCode(str, Enum):
    """Stable reasons for one automation gate disposition."""

    AUTOMATIC_READY = "automatic_ready"
    CONFIRMATION_REQUIRED = "confirmation_required"
    HUMAN_APPROVED = "human_approved"
    HUMAN_DENIED = "human_denied"
    SUGGEST_ONLY = "suggest_only"
    POLICY_DENIED = "policy_denied"
    INVALID_POLICY_DECISION = "invalid_policy_decision"
    INVALID_APPROVAL = "invalid_approval"
    APPROVAL_COMMAND_MISMATCH = "approval_command_mismatch"
    UNEXPECTED_APPROVAL = "unexpected_approval"


_POLICY_EXPLANATIONS = {
    PolicyReasonCode.EXACT_RULE: (
        "An exact capability and initiator policy rule selected this mode."
    ),
    PolicyReasonCode.CAPABILITY_RULE: (
        "A capability policy rule selected this mode."
    ),
    PolicyReasonCode.INITIATOR_RULE: (
        "An initiator policy rule selected this mode for a configured "
        "capability."
    ),
    PolicyReasonCode.UNKNOWN_CAPABILITY: (
        "The capability is unknown to this automation policy, so it is denied."
    ),
    PolicyReasonCode.UNCONFIGURED_CAPABILITY: (
        "No applicable automation rule is configured for this capability and "
        "initiator, so it is denied."
    ),
}


_GATE_EXPLANATIONS = {
    GateReasonCode.AUTOMATIC_READY: (
        "Automation confirmation is satisfied; dispatch has not occurred."
    ),
    GateReasonCode.CONFIRMATION_REQUIRED: (
        "An explicit matching human approval decision is required."
    ),
    GateReasonCode.HUMAN_APPROVED: (
        "A matching human approval satisfied automation confirmation; "
        "dispatch has not occurred."
    ),
    GateReasonCode.HUMAN_DENIED: "A matching human decision denied the command.",
    GateReasonCode.SUGGEST_ONLY: (
        "The command may be presented only as a suggestion."
    ),
    GateReasonCode.POLICY_DENIED: "The automation policy denied the command.",
    GateReasonCode.INVALID_POLICY_DECISION: (
        "The automation policy decision is structurally invalid."
    ),
    GateReasonCode.INVALID_APPROVAL: (
        "The supplied approval decision is structurally invalid."
    ),
    GateReasonCode.APPROVAL_COMMAND_MISMATCH: (
        "The approval decision belongs to a different command."
    ),
    GateReasonCode.UNEXPECTED_APPROVAL: (
        "An approval decision is not valid for this automation mode."
    ),
}


def _freeze_initiator_modes(
    modes: Mapping[CommandSource, AutomationMode],
    label: str,
) -> Mapping[CommandSource, AutomationMode]:
    if not isinstance(modes, Mapping):
        raise ValueError(f"{label} must be a mapping.")

    copied = {}
    for source, mode in modes.items():
        if not isinstance(source, CommandSource):
            raise ValueError(f"{label} keys must be CommandSource values.")
        if not isinstance(mode, AutomationMode):
            raise ValueError(f"{label} values must be AutomationMode values.")
        copied[source] = mode

    return MappingProxyType(
        dict(sorted(copied.items(), key=lambda item: item[0].value))
    )


@dataclass(frozen=True)
class CapabilityAutomationRule:
    """Rules for one exact, case-sensitive command capability."""

    default_mode: Optional[AutomationMode] = None
    initiator_modes: Mapping[CommandSource, AutomationMode] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if (
            self.default_mode is not None
            and not isinstance(self.default_mode, AutomationMode)
        ):
            raise ValueError(
                "Capability default mode must be an AutomationMode value."
            )
        object.__setattr__(
            self,
            "initiator_modes",
            _freeze_initiator_modes(
                self.initiator_modes,
                "Capability initiator modes",
            ),
        )

    def validate(self) -> None:
        """Revalidate a rule received across the policy boundary."""

        if (
            self.default_mode is not None
            and not isinstance(self.default_mode, AutomationMode)
        ):
            raise ValueError(
                "Capability default mode must be an AutomationMode value."
            )
        _freeze_initiator_modes(
            self.initiator_modes,
            "Capability initiator modes",
        )

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible representation."""

        return {
            "default_mode": (
                None if self.default_mode is None else self.default_mode.value
            ),
            "initiator_modes": {
                source.value: mode.value
                for source, mode in self.initiator_modes.items()
            },
        }


@dataclass(frozen=True)
class PolicyDecision:
    """Immutable automation decision for one command and capability."""

    command_id: str
    capability: str
    initiator_kind: CommandSource
    mode: AutomationMode
    reason_code: PolicyReasonCode
    explanation: str
    initiator_id: Optional[str] = None
    actor_id: Optional[str] = None

    def __post_init__(self) -> None:
        self.validate()

    @property
    def requires_human_confirmation(self) -> bool:
        return self.mode is AutomationMode.REQUIRE_CONFIRMATION

    def validate(self) -> None:
        """Revalidate a decision before resolving the automation gate."""

        validate_trimmed_identifier(self.command_id, "Policy command ID")
        validate_trimmed_identifier(self.capability, "Policy capability")
        if not isinstance(self.initiator_kind, CommandSource):
            raise ValueError(
                "Policy initiator kind must be a CommandSource value."
            )
        if not isinstance(self.mode, AutomationMode):
            raise ValueError("Policy mode must be an AutomationMode value.")
        if not isinstance(self.reason_code, PolicyReasonCode):
            raise ValueError(
                "Policy reason code must be a PolicyReasonCode value."
            )
        validate_trimmed_identifier(
            self.explanation,
            "Policy explanation",
        )
        validate_optional_identifier(
            self.initiator_id,
            "Policy initiator ID",
        )
        validate_optional_identifier(self.actor_id, "Policy actor ID")

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible representation."""

        return {
            "actor_id": self.actor_id,
            "capability": self.capability,
            "command_id": self.command_id,
            "explanation": self.explanation,
            "initiator_id": self.initiator_id,
            "initiator_kind": self.initiator_kind.value,
            "mode": self.mode.value,
            "reason_code": self.reason_code.value,
            "requires_human_confirmation": self.requires_human_confirmation,
        }


@dataclass(frozen=True)
class AutomationPolicy:
    """Immutable fail-closed rules for configured command capabilities.

    Precedence is exact capability-and-initiator rule, capability default,
    policy-wide initiator rule for a configured capability, then denial.
    Unknown capabilities are denied before policy-wide initiator rules apply.
    """

    capabilities: Mapping[str, CapabilityAutomationRule] = field(
        default_factory=dict
    )
    initiator_rules: Mapping[CommandSource, AutomationMode] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not isinstance(self.capabilities, Mapping):
            raise ValueError("Policy capabilities must be a mapping.")

        copied_capabilities = {}
        for capability, rule in self.capabilities.items():
            validate_trimmed_identifier(capability, "Policy capability")
            if not isinstance(rule, CapabilityAutomationRule):
                raise ValueError(
                    "Policy capability values must be "
                    "CapabilityAutomationRule values."
                )
            rule.validate()
            copied_capabilities[capability] = CapabilityAutomationRule(
                default_mode=rule.default_mode,
                initiator_modes=rule.initiator_modes,
            )

        object.__setattr__(
            self,
            "capabilities",
            MappingProxyType(dict(sorted(copied_capabilities.items()))),
        )
        object.__setattr__(
            self,
            "initiator_rules",
            _freeze_initiator_modes(
                self.initiator_rules,
                "Policy initiator rules",
            ),
        )

    def evaluate(self, command: GameCommand) -> PolicyDecision:
        """Evaluate one command without authorizing, dispatching, or executing."""

        if not isinstance(command, GameCommand):
            raise TypeError("AutomationPolicy.evaluate requires a GameCommand.")
        command.validate()

        capability = command.command_type
        rule = self.capabilities.get(capability)
        if rule is None:
            return self._decision(
                command,
                AutomationMode.DENY,
                PolicyReasonCode.UNKNOWN_CAPABILITY,
            )

        exact_mode = rule.initiator_modes.get(command.provenance.source)
        if exact_mode is not None:
            return self._decision(
                command,
                exact_mode,
                PolicyReasonCode.EXACT_RULE,
            )

        if rule.default_mode is not None:
            return self._decision(
                command,
                rule.default_mode,
                PolicyReasonCode.CAPABILITY_RULE,
            )

        initiator_mode = self.initiator_rules.get(command.provenance.source)
        if initiator_mode is not None:
            return self._decision(
                command,
                initiator_mode,
                PolicyReasonCode.INITIATOR_RULE,
            )

        return self._decision(
            command,
            AutomationMode.DENY,
            PolicyReasonCode.UNCONFIGURED_CAPABILITY,
        )

    def _decision(
        self,
        command: GameCommand,
        mode: AutomationMode,
        reason_code: PolicyReasonCode,
    ) -> PolicyDecision:
        return PolicyDecision(
            command_id=command.command_id,
            capability=command.command_type,
            initiator_kind=command.provenance.source,
            mode=mode,
            reason_code=reason_code,
            explanation=_POLICY_EXPLANATIONS[reason_code],
            initiator_id=command.provenance.initiator_id,
            actor_id=command.actor_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible configuration copy."""

        return {
            "capabilities": {
                capability: rule.to_dict()
                for capability, rule in self.capabilities.items()
            },
            "initiator_rules": {
                source.value: mode.value
                for source, mode in self.initiator_rules.items()
            },
        }


@dataclass(frozen=True)
class HumanApprovalDecision:
    """One explicit human response for a matching command confirmation."""

    command_id: str
    outcome: ApprovalOutcome
    approver_id: str
    approver_kind: CommandSource = CommandSource.HUMAN
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Revalidate an approval before resolving the automation gate."""

        validate_trimmed_identifier(self.command_id, "Approval command ID")
        if not isinstance(self.outcome, ApprovalOutcome):
            raise ValueError(
                "Approval outcome must be an ApprovalOutcome value."
            )
        validate_trimmed_identifier(self.approver_id, "Human approver ID")
        if self.approver_kind is not CommandSource.HUMAN:
            raise ValueError("Only a human initiator may provide approval.")
        if self.reason is not None:
            validate_trimmed_identifier(self.reason, "Approval reason")

    def to_dict(self) -> dict[str, Optional[str]]:
        """Return an independent JSON-compatible representation."""

        return {
            "approver_id": self.approver_id,
            "approver_kind": self.approver_kind.value,
            "command_id": self.command_id,
            "outcome": self.outcome.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class GateDisposition:
    """Immutable automation gate outcome; it performs no dispatch."""

    command_id: str
    capability: str
    status: GateDispositionStatus
    reason_code: GateReasonCode
    explanation: str

    def __post_init__(self) -> None:
        validate_trimmed_identifier(self.command_id, "Gate command ID")
        validate_trimmed_identifier(self.capability, "Gate capability")
        if not isinstance(self.status, GateDispositionStatus):
            raise ValueError(
                "Gate status must be a GateDispositionStatus value."
            )
        if not isinstance(self.reason_code, GateReasonCode):
            raise ValueError(
                "Gate reason code must be a GateReasonCode value."
            )
        validate_trimmed_identifier(self.explanation, "Gate explanation")

    @property
    def automation_approval_satisfied(self) -> bool:
        return self.status is GateDispositionStatus.READY

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible representation."""

        return {
            "automation_approval_satisfied": (
                self.automation_approval_satisfied
            ),
            "capability": self.capability,
            "command_id": self.command_id,
            "explanation": self.explanation,
            "reason_code": self.reason_code.value,
            "status": self.status.value,
        }


def _gate_disposition(
    decision: PolicyDecision,
    status: GateDispositionStatus,
    reason_code: GateReasonCode,
) -> GateDisposition:
    return GateDisposition(
        command_id=decision.command_id,
        capability=decision.capability,
        status=status,
        reason_code=reason_code,
        explanation=_GATE_EXPLANATIONS[reason_code],
    )


def resolve_automation_gate(
    decision: PolicyDecision,
    approval: Optional[HumanApprovalDecision] = None,
) -> GateDisposition:
    """Resolve policy and optional human approval without dispatching anything."""

    if not isinstance(decision, PolicyDecision):
        raise TypeError(
            "resolve_automation_gate requires a PolicyDecision."
        )

    try:
        decision.validate()
    except (TypeError, ValueError):
        validate_trimmed_identifier(
            getattr(decision, "command_id", None),
            "Gate command ID",
        )
        validate_trimmed_identifier(
            getattr(decision, "capability", None),
            "Gate capability",
        )
        return _gate_disposition(
            decision,
            GateDispositionStatus.INVALID,
            GateReasonCode.INVALID_POLICY_DECISION,
        )

    if approval is not None:
        if not isinstance(approval, HumanApprovalDecision):
            return _gate_disposition(
                decision,
                GateDispositionStatus.INVALID,
                GateReasonCode.INVALID_APPROVAL,
            )
        try:
            approval.validate()
        except (TypeError, ValueError):
            return _gate_disposition(
                decision,
                GateDispositionStatus.INVALID,
                GateReasonCode.INVALID_APPROVAL,
            )
        if approval.command_id != decision.command_id:
            return _gate_disposition(
                decision,
                GateDispositionStatus.INVALID,
                GateReasonCode.APPROVAL_COMMAND_MISMATCH,
            )

    if decision.mode is AutomationMode.AUTOMATIC:
        if approval is not None:
            return _gate_disposition(
                decision,
                GateDispositionStatus.INVALID,
                GateReasonCode.UNEXPECTED_APPROVAL,
            )
        return _gate_disposition(
            decision,
            GateDispositionStatus.READY,
            GateReasonCode.AUTOMATIC_READY,
        )

    if decision.mode is AutomationMode.REQUIRE_CONFIRMATION:
        if approval is None:
            return _gate_disposition(
                decision,
                GateDispositionStatus.AWAITING_APPROVAL,
                GateReasonCode.CONFIRMATION_REQUIRED,
            )
        if approval.outcome is ApprovalOutcome.APPROVED:
            return _gate_disposition(
                decision,
                GateDispositionStatus.READY,
                GateReasonCode.HUMAN_APPROVED,
            )
        return _gate_disposition(
            decision,
            GateDispositionStatus.DENIED,
            GateReasonCode.HUMAN_DENIED,
        )

    if approval is not None:
        return _gate_disposition(
            decision,
            GateDispositionStatus.INVALID,
            GateReasonCode.UNEXPECTED_APPROVAL,
        )

    if decision.mode is AutomationMode.SUGGEST:
        return _gate_disposition(
            decision,
            GateDispositionStatus.SUGGEST_ONLY,
            GateReasonCode.SUGGEST_ONLY,
        )

    return _gate_disposition(
        decision,
        GateDispositionStatus.DENIED,
        GateReasonCode.POLICY_DENIED,
    )
