import inspect
import json
import logging
from dataclasses import FrozenInstanceError

import pytest

from . import policy_gated_dispatcher as dispatcher_module
from .automation import (
    ApprovalOutcome,
    AutomationMode,
    AutomationPolicy,
    CapabilityAutomationRule,
    GateDispositionStatus,
    GateReasonCode,
    HumanApprovalDecision,
    PolicyReasonCode,
)
from .command import CommandProvenance, CommandSource, GameCommand
from .game_engine import GameEngine
from .policy_gated_dispatcher import (
    PolicyGatedCommandDispatcher,
    PolicyGatedDispatchResult,
    PolicyGatedDispatchStatus,
)
from .result import GameResult, GameResultStatus


COMMAND_TYPE = "test.inspect"


def make_command(
    command_id="command-gated-001",
    command_type=COMMAND_TYPE,
    payload=None,
):
    return GameCommand(
        command_id=command_id,
        command_type=command_type,
        payload={"location": "Old Crypt"} if payload is None else payload,
        provenance=CommandProvenance(
            source=CommandSource.AI,
            initiator_id="policy-gated-test",
        ),
        actor_id="actor-test",
    )


def policy_with_mode(mode, command_type=COMMAND_TYPE):
    return AutomationPolicy(
        capabilities={
            command_type: CapabilityAutomationRule(default_mode=mode),
        }
    )


def human_decision(command, outcome=ApprovalOutcome.APPROVED):
    return HumanApprovalDecision(
        command_id=command.command_id,
        outcome=outcome,
        approver_id="human-gm",
        reason="Reviewed by the test GM.",
    )


def engine_with_handler(handler):
    engine = GameEngine()
    engine.register_handler(COMMAND_TYPE, handler)
    return engine


class CountingPolicy(AutomationPolicy):
    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, "evaluated_commands", [])

    def evaluate(self, command):
        self.evaluated_commands.append(command)
        return super().evaluate(command)


class ExplodingPolicy(AutomationPolicy):
    def evaluate(self, command):
        raise RuntimeError("private policy detail")


class InvalidDecisionPolicy(AutomationPolicy):
    def evaluate(self, command):
        decision = super().evaluate(command)
        object.__setattr__(decision, "mode", "automatic")
        return decision


class MismatchedInvalidDecisionPolicy(AutomationPolicy):
    def evaluate(self, command):
        decision = super().evaluate(command)
        object.__setattr__(decision, "command_id", "different-command")
        object.__setattr__(decision, "mode", "automatic")
        return decision


class ExplodingEngine(GameEngine):
    def __init__(self):
        super().__init__()
        self.calls = []

    def dispatch(self, command):
        self.calls.append(command)
        raise RuntimeError("private engine detail")


def test_automatic_command_evaluates_policy_and_dispatches_exactly_once():
    command = make_command()
    calls = []
    expected = GameResult.success(command.command_id, {"inspected": True})
    engine = engine_with_handler(
        lambda received: calls.append(received) or expected
    )
    policy = CountingPolicy(
        capabilities={
            COMMAND_TYPE: CapabilityAutomationRule(
                default_mode=AutomationMode.AUTOMATIC
            )
        }
    )
    dispatcher = PolicyGatedCommandDispatcher(policy, engine)

    result = dispatcher.dispatch(command)

    assert result.status is PolicyGatedDispatchStatus.DISPATCHED
    assert result.dispatch_attempted is True
    assert result.game_result is expected
    assert result.policy_decision.mode is AutomationMode.AUTOMATIC
    assert result.gate_disposition.status is GateDispositionStatus.READY
    assert policy.evaluated_commands == [command]
    assert calls == [command]


def test_confirmation_without_approval_awaits_without_dispatch():
    calls = []
    command = make_command()
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION),
        engine_with_handler(lambda received: calls.append(received)),
    )

    result = dispatcher.dispatch(command)

    assert result.status is PolicyGatedDispatchStatus.AWAITING_APPROVAL
    assert result.dispatch_attempted is False
    assert result.game_result is None
    assert result.gate_disposition.reason_code is (
        GateReasonCode.CONFIRMATION_REQUIRED
    )
    assert dispatcher.dispatch_attempted_command_ids == ()
    assert calls == []


def test_matching_human_approval_dispatches_exactly_once():
    calls = []
    command = make_command()
    approval = human_decision(command)
    expected = GameResult.success(command.command_id)
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION),
        engine_with_handler(
            lambda received: calls.append(received) or expected
        ),
    )

    result = dispatcher.dispatch(command, approval)

    assert result.status is PolicyGatedDispatchStatus.DISPATCHED
    assert result.game_result is expected
    assert result.approval_decision is approval
    assert result.gate_disposition.reason_code is GateReasonCode.HUMAN_APPROVED
    assert calls == [command]


@pytest.mark.parametrize(
    ("mode", "approval_outcome", "expected_status"),
    [
        (
            AutomationMode.REQUIRE_CONFIRMATION,
            ApprovalOutcome.DENIED,
            PolicyGatedDispatchStatus.DENIED,
        ),
        (
            AutomationMode.SUGGEST,
            None,
            PolicyGatedDispatchStatus.SUGGESTION_ONLY,
        ),
        (
            AutomationMode.DENY,
            None,
            PolicyGatedDispatchStatus.DENIED,
        ),
    ],
    ids=["human-denial", "suggestion", "policy-denial"],
)
def test_denial_suggestion_and_policy_denial_never_dispatch(
    mode,
    approval_outcome,
    expected_status,
):
    calls = []
    command = make_command()
    approval = (
        None
        if approval_outcome is None
        else human_decision(command, approval_outcome)
    )
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(mode),
        engine_with_handler(lambda received: calls.append(received)),
    )

    result = dispatcher.dispatch(command, approval)

    assert result.status is expected_status
    assert result.dispatch_attempted is False
    assert result.game_result is None
    assert dispatcher.dispatch_attempted_command_ids == ()
    assert calls == []


def test_unknown_capability_fails_closed_without_dispatch():
    calls = []
    command = make_command(command_type="test.unknown")
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine_with_handler(lambda received: calls.append(received)),
    )

    result = dispatcher.dispatch(command)

    assert result.status is PolicyGatedDispatchStatus.DENIED
    assert result.policy_decision.reason_code is (
        PolicyReasonCode.UNKNOWN_CAPABILITY
    )
    assert result.gate_disposition.reason_code is GateReasonCode.POLICY_DENIED
    assert calls == []


@pytest.mark.parametrize("approval", [object()], ids=["wrong-type"])
def test_invalid_approval_never_dispatches(approval):
    calls = []
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION),
        engine_with_handler(lambda received: calls.append(received)),
    )

    result = dispatcher.dispatch(make_command(), approval)

    assert result.status is PolicyGatedDispatchStatus.INVALID
    assert result.gate_disposition.reason_code is (
        GateReasonCode.INVALID_APPROVAL
    )
    assert result.approval_decision is None
    assert calls == []


def test_mismatched_approval_never_dispatches_and_is_preserved_for_audit():
    calls = []
    approval = human_decision(make_command(command_id="different-command"))
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION),
        engine_with_handler(lambda received: calls.append(received)),
    )

    result = dispatcher.dispatch(make_command(), approval)

    assert result.status is PolicyGatedDispatchStatus.INVALID
    assert result.gate_disposition.reason_code is (
        GateReasonCode.APPROVAL_COMMAND_MISMATCH
    )
    assert result.approval_decision is approval
    assert calls == []


def test_corrupted_ai_self_approval_never_dispatches():
    calls = []
    command = make_command()
    approval = human_decision(command)
    object.__setattr__(approval, "approver_kind", CommandSource.AI)
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION),
        engine_with_handler(lambda received: calls.append(received)),
    )

    result = dispatcher.dispatch(command, approval)

    assert result.status is PolicyGatedDispatchStatus.INVALID
    assert result.gate_disposition.reason_code is (
        GateReasonCode.INVALID_APPROVAL
    )
    assert result.approval_decision is None
    assert calls == []


def test_unnecessary_approval_for_automatic_command_never_dispatches():
    calls = []
    command = make_command()
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine_with_handler(lambda received: calls.append(received)),
    )

    result = dispatcher.dispatch(command, human_decision(command))

    assert result.status is PolicyGatedDispatchStatus.INVALID
    assert result.gate_disposition.reason_code is (
        GateReasonCode.UNEXPECTED_APPROVAL
    )
    assert dispatcher.dispatch_attempted_command_ids == ()
    assert calls == []


def test_public_dispatch_api_cannot_accept_policy_or_gate_injection():
    parameters = inspect.signature(
        PolicyGatedCommandDispatcher.dispatch
    ).parameters

    assert tuple(parameters) == ("self", "command", "approval")
    assert "mode" not in parameters
    assert "policy_decision" not in parameters
    assert "capability" not in parameters
    assert "gate_disposition" not in parameters


def test_dispatched_unknown_command_result_remains_visible():
    command = make_command()
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        GameEngine(),
    )

    result = dispatcher.dispatch(command)

    assert result.status is PolicyGatedDispatchStatus.DISPATCHED
    assert result.game_result.status is GameResultStatus.UNKNOWN_COMMAND
    assert result.game_result.error == (
        "No handler is registered for this command type."
    )


def test_invalid_handler_result_remains_visible():
    command = make_command()
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine_with_handler(lambda received: {"success": True}),
    )

    result = dispatcher.dispatch(command)

    assert result.status is PolicyGatedDispatchStatus.DISPATCHED
    assert result.game_result.status is (
        GameResultStatus.INVALID_HANDLER_RESULT
    )


def test_handler_failure_remains_visible_and_is_not_retried():
    calls = []

    def failing_handler(command):
        calls.append(command)
        raise RuntimeError("private handler detail")

    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine_with_handler(failing_handler),
    )

    result = dispatcher.dispatch(make_command())

    assert result.status is PolicyGatedDispatchStatus.DISPATCHED
    assert result.game_result.status is GameResultStatus.HANDLER_FAILURE
    assert result.game_result.error == "The command handler failed."
    assert calls == [make_command()]


def test_normal_domain_negative_output_is_a_normal_dispatched_success():
    command = make_command()
    expected = GameResult.success(
        command.command_id,
        {"success": False, "message": "Nothing to inspect."},
    )
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine_with_handler(lambda received: expected),
    )

    result = dispatcher.dispatch(command)

    assert result.status is PolicyGatedDispatchStatus.DISPATCHED
    assert result.game_result is expected
    assert result.game_result.status is GameResultStatus.SUCCESS
    assert result.game_result.output["success"] is False


def test_repeated_automatic_command_is_blocked_as_duplicate():
    calls = []
    command = make_command()
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine_with_handler(
            lambda received: calls.append(received)
            or GameResult.success(received.command_id)
        ),
    )

    first = dispatcher.dispatch(command)
    repeated = dispatcher.dispatch(command)

    assert first.status is PolicyGatedDispatchStatus.DISPATCHED
    assert repeated.status is PolicyGatedDispatchStatus.DUPLICATE
    assert repeated.dispatch_attempted is False
    assert repeated.game_result is None
    assert calls == [command]


def test_repeated_approved_command_is_blocked_as_duplicate():
    calls = []
    command = make_command()
    approval = human_decision(command)
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION),
        engine_with_handler(
            lambda received: calls.append(received)
            or GameResult.success(received.command_id)
        ),
    )

    first = dispatcher.dispatch(command, approval)
    repeated = dispatcher.dispatch(command, approval)

    assert first.status is PolicyGatedDispatchStatus.DISPATCHED
    assert repeated.status is PolicyGatedDispatchStatus.DUPLICATE
    assert calls == [command]


def test_same_payload_with_different_command_ids_dispatches_separately():
    calls = []
    first = make_command(command_id="command-gated-first")
    second = make_command(command_id="command-gated-second")
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine_with_handler(
            lambda received: calls.append(received)
            or GameResult.success(received.command_id)
        ),
    )

    first_result = dispatcher.dispatch(first)
    second_result = dispatcher.dispatch(second)

    assert first_result.status is PolicyGatedDispatchStatus.DISPATCHED
    assert second_result.status is PolicyGatedDispatchStatus.DISPATCHED
    assert calls == [first, second]


def test_awaiting_command_does_not_consume_replay_protection():
    calls = []
    command = make_command()
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION),
        engine_with_handler(
            lambda received: calls.append(received)
            or GameResult.success(received.command_id)
        ),
    )

    awaiting = dispatcher.dispatch(command)
    approved = dispatcher.dispatch(command, human_decision(command))

    assert awaiting.status is PolicyGatedDispatchStatus.AWAITING_APPROVAL
    assert approved.status is PolicyGatedDispatchStatus.DISPATCHED
    assert calls == [command]


def test_denied_approval_does_not_consume_replay_protection():
    calls = []
    command = make_command()
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION),
        engine_with_handler(
            lambda received: calls.append(received)
            or GameResult.success(received.command_id)
        ),
    )

    denied = dispatcher.dispatch(
        command,
        human_decision(command, ApprovalOutcome.DENIED),
    )
    approved = dispatcher.dispatch(command, human_decision(command))

    assert denied.status is PolicyGatedDispatchStatus.DENIED
    assert approved.status is PolicyGatedDispatchStatus.DISPATCHED
    assert calls == [command]


def test_replay_attempt_is_recorded_before_reentrant_engine_handling():
    command = make_command()
    nested_results = []
    calls = []
    engine = GameEngine()
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine,
    )

    def reentrant_handler(received):
        calls.append(received)
        nested_results.append(dispatcher.dispatch(received))
        return GameResult.success(received.command_id)

    engine.register_handler(COMMAND_TYPE, reentrant_handler)

    outer = dispatcher.dispatch(command)

    assert outer.status is PolicyGatedDispatchStatus.DISPATCHED
    assert nested_results[0].status is PolicyGatedDispatchStatus.DUPLICATE
    assert calls == [command]


def test_replay_snapshot_cannot_mutate_coordinator_state():
    command = make_command()
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine_with_handler(
            lambda received: GameResult.success(received.command_id)
        ),
    )
    dispatcher.dispatch(command)

    snapshot = dispatcher.dispatch_attempted_command_ids

    assert snapshot == (command.command_id,)
    with pytest.raises(AttributeError):
        snapshot.append("invented-command")
    snapshot += ("invented-command",)
    assert dispatcher.dispatch_attempted_command_ids == (command.command_id,)


def test_replay_protection_is_process_local_per_coordinator_instance():
    calls = []
    command = make_command()
    engine = engine_with_handler(
        lambda received: calls.append(received)
        or GameResult.success(received.command_id)
    )
    first = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine,
    )
    second = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine,
    )

    assert first.dispatch(command).status is (
        PolicyGatedDispatchStatus.DISPATCHED
    )
    assert second.dispatch(command).status is (
        PolicyGatedDispatchStatus.DISPATCHED
    )
    assert calls == [command, command]


def test_policy_exception_fails_closed_without_exposing_detail(caplog):
    calls = []
    dispatcher = PolicyGatedCommandDispatcher(
        ExplodingPolicy(),
        engine_with_handler(lambda received: calls.append(received)),
    )

    with caplog.at_level(logging.ERROR, logger="DungeonManager"):
        result = dispatcher.dispatch(make_command())

    assert result.status is PolicyGatedDispatchStatus.COORDINATOR_FAILURE
    assert result.dispatch_attempted is False
    assert result.policy_decision is None
    assert result.gate_disposition is None
    assert "private policy detail" not in result.explanation
    assert "private policy detail" not in json.dumps(result.to_dict())
    assert "private policy detail" in caplog.text
    assert calls == []


def test_invalid_policy_decision_fails_closed_as_invalid_state():
    calls = []
    policy = InvalidDecisionPolicy(
        capabilities={
            COMMAND_TYPE: CapabilityAutomationRule(
                default_mode=AutomationMode.AUTOMATIC
            )
        }
    )
    dispatcher = PolicyGatedCommandDispatcher(
        policy,
        engine_with_handler(lambda received: calls.append(received)),
    )

    result = dispatcher.dispatch(make_command())

    assert result.status is PolicyGatedDispatchStatus.INVALID
    assert result.policy_decision is None
    assert result.gate_disposition.reason_code is (
        GateReasonCode.INVALID_POLICY_DECISION
    )
    assert calls == []


def test_mismatched_invalid_policy_decision_is_a_controlled_failure():
    calls = []
    policy = MismatchedInvalidDecisionPolicy(
        capabilities={
            COMMAND_TYPE: CapabilityAutomationRule(
                default_mode=AutomationMode.AUTOMATIC
            )
        }
    )
    dispatcher = PolicyGatedCommandDispatcher(
        policy,
        engine_with_handler(lambda received: calls.append(received)),
    )

    result = dispatcher.dispatch(make_command())

    assert result.status is PolicyGatedDispatchStatus.COORDINATOR_FAILURE
    assert result.dispatch_attempted is False
    assert result.policy_decision is None
    assert result.gate_disposition is None
    assert calls == []


def test_gate_exception_fails_closed_without_dispatch(monkeypatch):
    calls = []

    def exploding_gate(decision, approval=None):
        raise RuntimeError("private gate detail")

    monkeypatch.setattr(
        dispatcher_module,
        "resolve_automation_gate",
        exploding_gate,
    )
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine_with_handler(lambda received: calls.append(received)),
    )

    result = dispatcher.dispatch(make_command())

    assert result.status is PolicyGatedDispatchStatus.COORDINATOR_FAILURE
    assert result.dispatch_attempted is False
    assert result.policy_decision is not None
    assert result.gate_disposition is None
    assert "private gate detail" not in result.explanation
    assert calls == []


def test_unexpected_engine_exception_is_controlled_and_not_retried():
    command = make_command()
    engine = ExplodingEngine()
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.AUTOMATIC),
        engine,
    )

    first = dispatcher.dispatch(command)
    repeated = dispatcher.dispatch(command)

    assert first.status is PolicyGatedDispatchStatus.COORDINATOR_FAILURE
    assert first.dispatch_attempted is True
    assert first.game_result is None
    assert "private engine detail" not in first.explanation
    assert repeated.status is PolicyGatedDispatchStatus.DUPLICATE
    assert engine.calls == [command]


def test_combined_result_is_immutable_and_serializes_defensively():
    command = make_command()
    dispatcher = PolicyGatedCommandDispatcher(
        policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION),
        engine_with_handler(
            lambda received: GameResult.success(
                received.command_id,
                {"events": [{"kind": "test-only"}]},
            )
        ),
    )
    result = dispatcher.dispatch(command, human_decision(command))

    serialized = result.to_dict()
    serialized["policy_decision"]["mode"] = "deny"
    serialized["gate_disposition"]["status"] = "denied"
    serialized["game_result"]["output"]["events"][0]["kind"] = "changed"
    serialized["approval_decision"]["approver_id"] = "changed"

    fresh = result.to_dict()
    assert fresh["status"] == "dispatched"
    assert fresh["policy_decision"]["mode"] == "require_confirmation"
    assert fresh["gate_disposition"]["status"] == "ready"
    assert fresh["game_result"]["output"]["events"][0]["kind"] == (
        "test-only"
    )
    assert fresh["approval_decision"]["approver_id"] == "human-gm"
    assert json.loads(json.dumps(fresh, allow_nan=False)) == fresh
    with pytest.raises(FrozenInstanceError):
        result.status = PolicyGatedDispatchStatus.DENIED


def test_combined_result_rejects_game_result_on_blocked_status():
    command = make_command()
    policy = policy_with_mode(AutomationMode.DENY)
    decision = policy.evaluate(command)
    gate = dispatcher_module.resolve_automation_gate(decision)

    with pytest.raises(ValueError, match="Only dispatched"):
        PolicyGatedDispatchResult(
            command_id=command.command_id,
            status=PolicyGatedDispatchStatus.DENIED,
            explanation="Blocked.",
            policy_decision=decision,
            gate_disposition=gate,
            game_result=GameResult.success(command.command_id),
        )


def test_combined_result_rejects_dispatched_status_without_engine_result():
    command = make_command()
    policy = policy_with_mode(AutomationMode.AUTOMATIC)
    decision = policy.evaluate(command)
    gate = dispatcher_module.resolve_automation_gate(decision)

    with pytest.raises(ValueError, match="require one dispatch attempt"):
        PolicyGatedDispatchResult(
            command_id=command.command_id,
            status=PolicyGatedDispatchStatus.DISPATCHED,
            explanation="Invalid dispatched aggregate.",
            dispatch_attempted=True,
            policy_decision=decision,
            gate_disposition=gate,
        )


def test_combined_result_rejects_mismatched_engine_result():
    command = make_command()
    policy = policy_with_mode(AutomationMode.AUTOMATIC)
    decision = policy.evaluate(command)
    gate = dispatcher_module.resolve_automation_gate(decision)

    with pytest.raises(ValueError, match="game result must match"):
        PolicyGatedDispatchResult(
            command_id=command.command_id,
            status=PolicyGatedDispatchStatus.DISPATCHED,
            explanation="Invalid mismatched aggregate.",
            dispatch_attempted=True,
            policy_decision=decision,
            gate_disposition=gate,
            game_result=GameResult.success("different-command"),
        )
