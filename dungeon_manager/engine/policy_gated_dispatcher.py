"""Policy-gated one-attempt command dispatch coordination."""

import logging
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Any, Optional, Protocol

from ._json import validate_trimmed_identifier
from .automation import (
    AutomationPolicy,
    GateDisposition,
    GateDispositionStatus,
    GateReasonCode,
    HumanApprovalDecision,
    PolicyDecision,
    resolve_automation_gate,
)
from .command import GameCommand
from .game_engine import GameEngine
from .result import GameResult


logger = logging.getLogger("DungeonManager")

_DISPATCHED_EXPLANATION = (
    "The command was submitted to the game engine exactly once."
)
_DUPLICATE_EXPLANATION = (
    "This coordinator already attempted dispatch for this command ID."
)
_POLICY_FAILURE_EXPLANATION = (
    "The automation policy could not safely evaluate this command."
)
_GATE_FAILURE_EXPLANATION = (
    "The automation gate could not safely resolve this command."
)
_DISPATCH_FAILURE_EXPLANATION = (
    "The dispatch attempt did not return a valid game result."
)


class _DispatchLifecycleRecorder(Protocol):
    """Internal synchronous observations around authoritative dispatch logic."""

    def policy_evaluated(
        self,
        command: GameCommand,
        decision: PolicyDecision,
    ) -> None:
        ...

    def gate_resolved(
        self,
        command: GameCommand,
        decision: PolicyDecision,
        approval: Optional[HumanApprovalDecision],
        disposition: GateDisposition,
    ) -> None:
        ...

    def dispatch_blocked(
        self,
        command: GameCommand,
        result: "PolicyGatedDispatchResult",
    ) -> None:
        ...

    def dispatch_attempted(
        self,
        command: GameCommand,
        decision: PolicyDecision,
        approval: Optional[HumanApprovalDecision],
        disposition: GateDisposition,
    ) -> None:
        ...

    def dispatch_completed(
        self,
        command: GameCommand,
        result: "PolicyGatedDispatchResult",
    ) -> None:
        ...

    def coordinator_failed(
        self,
        command: GameCommand,
        result: "PolicyGatedDispatchResult",
    ) -> None:
        ...


class PolicyGatedDispatchStatus(str, Enum):
    """Caller-facing outcomes of one coordinated command submission."""

    DISPATCHED = "dispatched"
    AWAITING_APPROVAL = "awaiting_approval"
    SUGGESTION_ONLY = "suggestion_only"
    DENIED = "denied"
    INVALID = "invalid"
    DUPLICATE = "duplicate"
    COORDINATOR_FAILURE = "coordinator_failure"


_BLOCKED_STATUS_BY_GATE = {
    GateDispositionStatus.AWAITING_APPROVAL: (
        PolicyGatedDispatchStatus.AWAITING_APPROVAL
    ),
    GateDispositionStatus.SUGGEST_ONLY: (
        PolicyGatedDispatchStatus.SUGGESTION_ONLY
    ),
    GateDispositionStatus.DENIED: PolicyGatedDispatchStatus.DENIED,
    GateDispositionStatus.INVALID: PolicyGatedDispatchStatus.INVALID,
}

_EXPECTED_GATE_BY_STATUS = {
    PolicyGatedDispatchStatus.DISPATCHED: GateDispositionStatus.READY,
    PolicyGatedDispatchStatus.AWAITING_APPROVAL: (
        GateDispositionStatus.AWAITING_APPROVAL
    ),
    PolicyGatedDispatchStatus.SUGGESTION_ONLY: (
        GateDispositionStatus.SUGGEST_ONLY
    ),
    PolicyGatedDispatchStatus.DENIED: GateDispositionStatus.DENIED,
    PolicyGatedDispatchStatus.INVALID: GateDispositionStatus.INVALID,
    PolicyGatedDispatchStatus.DUPLICATE: GateDispositionStatus.READY,
}


@dataclass(frozen=True)
class PolicyGatedDispatchResult:
    """Immutable aggregate for policy, gate, and optional engine dispatch."""

    command_id: str
    status: PolicyGatedDispatchStatus
    explanation: str
    dispatch_attempted: bool = False
    policy_decision: Optional[PolicyDecision] = None
    gate_disposition: Optional[GateDisposition] = None
    approval_decision: Optional[HumanApprovalDecision] = None
    game_result: Optional[GameResult] = None

    def __post_init__(self) -> None:
        validate_trimmed_identifier(
            self.command_id,
            "Dispatch result command ID",
        )
        if not isinstance(self.status, PolicyGatedDispatchStatus):
            raise ValueError(
                "Dispatch result status must be a "
                "PolicyGatedDispatchStatus value."
            )
        validate_trimmed_identifier(
            self.explanation,
            "Dispatch result explanation",
        )
        if not isinstance(self.dispatch_attempted, bool):
            raise ValueError("Dispatch-attempt state must be a boolean.")

        self._validate_policy_decision()
        self._validate_gate_disposition()
        self._validate_approval_decision()
        self._validate_game_result()
        self._validate_status_invariants()

    def _validate_policy_decision(self) -> None:
        if self.policy_decision is None:
            return
        if not isinstance(self.policy_decision, PolicyDecision):
            raise ValueError(
                "Dispatch policy decision must be a PolicyDecision value."
            )
        self.policy_decision.validate()
        if self.policy_decision.command_id != self.command_id:
            raise ValueError(
                "Dispatch policy decision must match the result command ID."
            )

    def _validate_gate_disposition(self) -> None:
        if self.gate_disposition is None:
            return
        if not isinstance(self.gate_disposition, GateDisposition):
            raise ValueError(
                "Dispatch gate disposition must be a GateDisposition value."
            )
        GateDisposition(
            command_id=self.gate_disposition.command_id,
            capability=self.gate_disposition.capability,
            status=self.gate_disposition.status,
            reason_code=self.gate_disposition.reason_code,
            explanation=self.gate_disposition.explanation,
        )
        if self.gate_disposition.command_id != self.command_id:
            raise ValueError(
                "Dispatch gate disposition must match the result command ID."
            )
        if (
            self.policy_decision is not None
            and self.gate_disposition.capability
            != self.policy_decision.capability
        ):
            raise ValueError(
                "Dispatch policy and gate capabilities must match."
            )

    def _validate_approval_decision(self) -> None:
        if self.approval_decision is None:
            return
        if not isinstance(self.approval_decision, HumanApprovalDecision):
            raise ValueError(
                "Dispatch approval decision must be a "
                "HumanApprovalDecision value."
            )
        self.approval_decision.validate()

    def _validate_game_result(self) -> None:
        if self.game_result is None:
            return
        if not isinstance(self.game_result, GameResult):
            raise ValueError(
                "Dispatch game result must be a GameResult value."
            )
        self.game_result.validate()
        if self.game_result.command_id != self.command_id:
            raise ValueError(
                "Dispatch game result must match the result command ID."
            )

    def _validate_status_invariants(self) -> None:
        if self.status is PolicyGatedDispatchStatus.COORDINATOR_FAILURE:
            if self.game_result is not None:
                raise ValueError(
                    "Coordinator failures must not contain a game result."
                )
            return

        if self.policy_decision is None:
            invalid_policy_state = (
                self.status is PolicyGatedDispatchStatus.INVALID
                and self.gate_disposition is not None
                and self.gate_disposition.reason_code
                is GateReasonCode.INVALID_POLICY_DECISION
            )
            if not invalid_policy_state:
                raise ValueError(
                    "Coordinated results require a valid policy decision."
                )
        if self.gate_disposition is None:
            raise ValueError(
                "Coordinated results require a gate disposition."
            )

        expected_gate = _EXPECTED_GATE_BY_STATUS[self.status]
        if self.gate_disposition.status is not expected_gate:
            raise ValueError(
                "Dispatch result status must match its gate disposition."
            )

        if self.status is PolicyGatedDispatchStatus.DISPATCHED:
            if not self.dispatch_attempted or self.game_result is None:
                raise ValueError(
                    "Dispatched results require one dispatch attempt and a "
                    "game result."
                )
            return

        if self.dispatch_attempted:
            raise ValueError(
                "Only dispatched or coordinator-failure results may record "
                "a dispatch attempt."
            )
        if self.game_result is not None:
            raise ValueError(
                "Only dispatched results may contain a game result."
            )

    def to_dict(self) -> dict[str, Any]:
        """Return an independent defensive JSON-compatible representation."""

        return {
            "approval_decision": (
                None
                if self.approval_decision is None
                else self.approval_decision.to_dict()
            ),
            "command_id": self.command_id,
            "dispatch_attempted": self.dispatch_attempted,
            "explanation": self.explanation,
            "game_result": (
                None
                if self.game_result is None
                else self.game_result.to_dict()
            ),
            "gate_disposition": (
                None
                if self.gate_disposition is None
                else self.gate_disposition.to_dict()
            ),
            "policy_decision": (
                None
                if self.policy_decision is None
                else self.policy_decision.to_dict()
            ),
            "status": self.status.value,
        }


class PolicyGatedCommandDispatcher:
    """Compose policy, approval resolution, and exact engine dispatch once."""

    def __init__(
        self,
        automation_policy: AutomationPolicy,
        game_engine: GameEngine,
    ) -> None:
        if not isinstance(automation_policy, AutomationPolicy):
            raise ValueError(
                "Policy-gated dispatch requires an AutomationPolicy."
            )
        if not isinstance(game_engine, GameEngine):
            raise ValueError("Policy-gated dispatch requires a GameEngine.")

        self.__automation_policy = automation_policy
        self.__game_engine = game_engine
        self.__dispatch_attempted_command_ids: set[str] = set()
        self.__replay_lock = Lock()

    @property
    def dispatch_attempted_command_ids(self) -> tuple[str, ...]:
        """Return an immutable process-local replay-state snapshot."""

        with self.__replay_lock:
            return tuple(sorted(self.__dispatch_attempted_command_ids))

    def dispatch(
        self,
        command: GameCommand,
        approval: Optional[HumanApprovalDecision] = None,
    ) -> PolicyGatedDispatchResult:
        """Evaluate, resolve, and dispatch once only when the gate is ready."""

        return self._dispatch_with_lifecycle(command, approval, None)

    def _dispatch_with_lifecycle(
        self,
        command: GameCommand,
        approval: Optional[HumanApprovalDecision],
        lifecycle_recorder: Optional[_DispatchLifecycleRecorder],
    ) -> PolicyGatedDispatchResult:
        """Internal audited integration without widening the public API."""

        if not isinstance(command, GameCommand):
            raise TypeError(
                "PolicyGatedCommandDispatcher.dispatch requires a GameCommand."
            )

        decision = self._evaluate_policy(command, approval)
        if isinstance(decision, PolicyGatedDispatchResult):
            if lifecycle_recorder is not None:
                lifecycle_recorder.coordinator_failed(command, decision)
            return decision

        auditable_decision = self._validated_decision_for_command(
            decision,
            command,
        )
        if auditable_decision is not None and lifecycle_recorder is not None:
            lifecycle_recorder.policy_evaluated(
                command,
                auditable_decision,
            )

        disposition = self._resolve_gate(command, decision, approval)
        if isinstance(disposition, PolicyGatedDispatchResult):
            if lifecycle_recorder is not None:
                lifecycle_recorder.coordinator_failed(command, disposition)
            return disposition

        valid_decision = self._validated_decision_for_command(
            decision,
            command,
        )
        if valid_decision is None:
            if (
                disposition.status is GateDispositionStatus.INVALID
                and disposition.reason_code
                is GateReasonCode.INVALID_POLICY_DECISION
                and self._invalid_policy_disposition_matches_command(
                    disposition,
                    command,
                )
            ):
                result = PolicyGatedDispatchResult(
                    command_id=command.command_id,
                    status=PolicyGatedDispatchStatus.INVALID,
                    explanation=disposition.explanation,
                    gate_disposition=disposition,
                    approval_decision=self._validated_approval(approval),
                )
                if lifecycle_recorder is not None:
                    lifecycle_recorder.dispatch_blocked(command, result)
                return result
            logger.error(
                "Automation policy returned a decision that did not match "
                "the command (command_id=%s)",
                command.command_id,
            )
            result = self._coordinator_failure(
                command,
                _POLICY_FAILURE_EXPLANATION,
                approval=approval,
            )
            if lifecycle_recorder is not None:
                lifecycle_recorder.coordinator_failed(command, result)
            return result

        if not self._disposition_matches(
            disposition,
            command,
            valid_decision,
        ):
            logger.error(
                "Automation gate returned a disposition that did not match "
                "the command (command_id=%s)",
                command.command_id,
            )
            result = self._coordinator_failure(
                command,
                _GATE_FAILURE_EXPLANATION,
                policy_decision=valid_decision,
                approval=approval,
            )
            if lifecycle_recorder is not None:
                lifecycle_recorder.coordinator_failed(command, result)
            return result

        if lifecycle_recorder is not None:
            lifecycle_recorder.gate_resolved(
                command,
                valid_decision,
                approval,
                disposition,
            )

        if disposition.status is not GateDispositionStatus.READY:
            result_status = _BLOCKED_STATUS_BY_GATE.get(disposition.status)
            if result_status is None:
                logger.error(
                    "Automation gate returned an unsupported status for "
                    "command_id=%s",
                    command.command_id,
                )
                result = self._coordinator_failure(
                    command,
                    _GATE_FAILURE_EXPLANATION,
                    policy_decision=valid_decision,
                    gate_disposition=disposition,
                    approval=approval,
                )
                if lifecycle_recorder is not None:
                    lifecycle_recorder.coordinator_failed(command, result)
                return result
            result = PolicyGatedDispatchResult(
                command_id=command.command_id,
                status=result_status,
                explanation=disposition.explanation,
                policy_decision=valid_decision,
                gate_disposition=disposition,
                approval_decision=self._validated_approval(approval),
            )
            if lifecycle_recorder is not None:
                lifecycle_recorder.dispatch_blocked(command, result)
            return result

        duplicate_result = None
        with self.__replay_lock:
            if command.command_id in self.__dispatch_attempted_command_ids:
                duplicate_result = PolicyGatedDispatchResult(
                    command_id=command.command_id,
                    status=PolicyGatedDispatchStatus.DUPLICATE,
                    explanation=_DUPLICATE_EXPLANATION,
                    policy_decision=valid_decision,
                    gate_disposition=disposition,
                    approval_decision=self._validated_approval(approval),
                )
            else:
                if lifecycle_recorder is not None:
                    lifecycle_recorder.dispatch_attempted(
                        command,
                        valid_decision,
                        approval,
                        disposition,
                    )
                self.__dispatch_attempted_command_ids.add(command.command_id)

        if duplicate_result is not None:
            if lifecycle_recorder is not None:
                lifecycle_recorder.dispatch_blocked(
                    command,
                    duplicate_result,
                )
            return duplicate_result

        try:
            game_result = self.__game_engine.dispatch(command)
            if not isinstance(game_result, GameResult):
                raise ValueError(
                    "GameEngine.dispatch returned a non-GameResult value."
                )
            game_result.validate()
            if game_result.command_id != command.command_id:
                raise ValueError(
                    "GameEngine.dispatch returned a mismatched command ID."
                )
        except Exception:
            logger.exception(
                "Policy-gated command dispatch failed after the attempt was "
                "recorded (command_id=%s)",
                command.command_id,
            )
            result = self._coordinator_failure(
                command,
                _DISPATCH_FAILURE_EXPLANATION,
                dispatch_attempted=True,
                policy_decision=valid_decision,
                gate_disposition=disposition,
                approval=approval,
            )
            if lifecycle_recorder is not None:
                lifecycle_recorder.coordinator_failed(command, result)
            return result

        result = PolicyGatedDispatchResult(
            command_id=command.command_id,
            status=PolicyGatedDispatchStatus.DISPATCHED,
            explanation=_DISPATCHED_EXPLANATION,
            dispatch_attempted=True,
            policy_decision=valid_decision,
            gate_disposition=disposition,
            approval_decision=self._validated_approval(approval),
            game_result=game_result,
        )
        if lifecycle_recorder is not None:
            lifecycle_recorder.dispatch_completed(command, result)
        return result

    def _evaluate_policy(
        self,
        command: GameCommand,
        approval: Optional[HumanApprovalDecision],
    ) -> Any:
        try:
            return self.__automation_policy.evaluate(command)
        except Exception:
            logger.exception(
                "Automation policy evaluation failed closed "
                "(command_id=%s)",
                command.command_id,
            )
            return self._coordinator_failure(
                command,
                _POLICY_FAILURE_EXPLANATION,
                approval=approval,
            )

    def _resolve_gate(
        self,
        command: GameCommand,
        decision: Any,
        approval: Optional[HumanApprovalDecision],
    ) -> Any:
        try:
            return resolve_automation_gate(decision, approval)
        except Exception:
            logger.exception(
                "Automation gate resolution failed closed (command_id=%s)",
                command.command_id,
            )
            valid_decision = self._validated_decision_for_command(
                decision,
                command,
            )
            return self._coordinator_failure(
                command,
                _GATE_FAILURE_EXPLANATION,
                policy_decision=valid_decision,
                approval=approval,
            )

    @staticmethod
    def _validated_decision_for_command(
        decision: Any,
        command: GameCommand,
    ) -> Optional[PolicyDecision]:
        if not isinstance(decision, PolicyDecision):
            return None
        try:
            decision.validate()
        except (TypeError, ValueError):
            return None
        if (
            decision.command_id != command.command_id
            or decision.capability != command.command_type
            or decision.initiator_kind is not command.provenance.source
            or decision.initiator_id != command.provenance.initiator_id
            or decision.actor_id != command.actor_id
        ):
            return None
        return decision

    @staticmethod
    def _disposition_matches(
        disposition: Any,
        command: GameCommand,
        decision: PolicyDecision,
    ) -> bool:
        if not isinstance(disposition, GateDisposition):
            return False
        try:
            GateDisposition(
                command_id=disposition.command_id,
                capability=disposition.capability,
                status=disposition.status,
                reason_code=disposition.reason_code,
                explanation=disposition.explanation,
            )
        except (TypeError, ValueError):
            return False
        return (
            disposition.command_id == command.command_id
            and disposition.command_id == decision.command_id
            and disposition.capability == command.command_type
            and disposition.capability == decision.capability
        )

    @staticmethod
    def _invalid_policy_disposition_matches_command(
        disposition: Any,
        command: GameCommand,
    ) -> bool:
        if not isinstance(disposition, GateDisposition):
            return False
        try:
            GateDisposition(
                command_id=disposition.command_id,
                capability=disposition.capability,
                status=disposition.status,
                reason_code=disposition.reason_code,
                explanation=disposition.explanation,
            )
        except (TypeError, ValueError):
            return False
        return (
            disposition.command_id == command.command_id
            and disposition.capability == command.command_type
        )

    @staticmethod
    def _validated_approval(
        approval: Optional[HumanApprovalDecision],
    ) -> Optional[HumanApprovalDecision]:
        if not isinstance(approval, HumanApprovalDecision):
            return None
        try:
            approval.validate()
        except (TypeError, ValueError):
            return None
        return approval

    def _coordinator_failure(
        self,
        command: GameCommand,
        explanation: str,
        dispatch_attempted: bool = False,
        policy_decision: Optional[PolicyDecision] = None,
        gate_disposition: Optional[GateDisposition] = None,
        approval: Optional[HumanApprovalDecision] = None,
    ) -> PolicyGatedDispatchResult:
        return PolicyGatedDispatchResult(
            command_id=command.command_id,
            status=PolicyGatedDispatchStatus.COORDINATOR_FAILURE,
            explanation=explanation,
            dispatch_attempted=dispatch_attempted,
            policy_decision=policy_decision,
            gate_disposition=gate_disposition,
            approval_decision=self._validated_approval(approval),
        )
