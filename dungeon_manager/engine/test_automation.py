import json
from dataclasses import FrozenInstanceError

import pytest

from .automation import (
    ApprovalOutcome,
    AutomationMode,
    AutomationPolicy,
    CapabilityAutomationRule,
    GateDispositionStatus,
    GateReasonCode,
    HumanApprovalDecision,
    PolicyReasonCode,
    resolve_automation_gate,
)
from .command import CommandProvenance, CommandSource, GameCommand
from .game_engine import GameEngine
from .result import GameResult


def make_command(
    command_type="test.inspect",
    source=CommandSource.AI,
    command_id="command-policy-001",
    payload=None,
    initiator_id="policy-test",
    actor_id="actor-test",
):
    return GameCommand(
        command_id=command_id,
        command_type=command_type,
        provenance=CommandProvenance(
            source=source,
            initiator_id=initiator_id,
        ),
        payload={} if payload is None else payload,
        actor_id=actor_id,
    )


def policy_with_mode(mode):
    return AutomationPolicy(
        capabilities={
            "test.inspect": CapabilityAutomationRule(default_mode=mode),
        }
    )


@pytest.mark.parametrize("mode", list(AutomationMode))
def test_policy_supports_every_automation_mode(mode):
    decision = policy_with_mode(mode).evaluate(make_command())

    assert decision.mode is mode
    assert decision.reason_code is PolicyReasonCode.CAPABILITY_RULE
    assert decision.requires_human_confirmation is (
        mode is AutomationMode.REQUIRE_CONFIRMATION
    )


def test_same_capability_can_select_different_modes_for_every_initiator_kind():
    expected = {
        CommandSource.HUMAN: AutomationMode.AUTOMATIC,
        CommandSource.AI: AutomationMode.REQUIRE_CONFIRMATION,
        CommandSource.SYSTEM: AutomationMode.SUGGEST,
        CommandSource.EXTERNAL: AutomationMode.DENY,
    }
    policy = AutomationPolicy(
        capabilities={
            "test.inspect": CapabilityAutomationRule(
                initiator_modes=expected,
            )
        }
    )

    decisions = {
        source: policy.evaluate(make_command(source=source))
        for source in CommandSource
    }

    assert {
        source: decision.mode
        for source, decision in decisions.items()
    } == expected
    assert all(
        decision.reason_code is PolicyReasonCode.EXACT_RULE
        for decision in decisions.values()
    )


def test_policy_rule_precedence_is_exact_then_capability_then_initiator():
    policy = AutomationPolicy(
        capabilities={
            "test.exact": CapabilityAutomationRule(
                default_mode=AutomationMode.AUTOMATIC,
                initiator_modes={CommandSource.AI: AutomationMode.SUGGEST},
            ),
            "test.initiator": CapabilityAutomationRule(),
        },
        initiator_rules={
            CommandSource.AI: AutomationMode.DENY,
            CommandSource.HUMAN: AutomationMode.REQUIRE_CONFIRMATION,
        },
    )

    exact = policy.evaluate(make_command("test.exact", CommandSource.AI))
    capability = policy.evaluate(
        make_command("test.exact", CommandSource.HUMAN)
    )
    initiator = policy.evaluate(
        make_command("test.initiator", CommandSource.HUMAN)
    )

    assert (exact.mode, exact.reason_code) == (
        AutomationMode.SUGGEST,
        PolicyReasonCode.EXACT_RULE,
    )
    assert (capability.mode, capability.reason_code) == (
        AutomationMode.AUTOMATIC,
        PolicyReasonCode.CAPABILITY_RULE,
    )
    assert (initiator.mode, initiator.reason_code) == (
        AutomationMode.REQUIRE_CONFIRMATION,
        PolicyReasonCode.INITIATOR_RULE,
    )


def test_empty_policy_denies_unknown_capability_with_stable_reason():
    first = AutomationPolicy().evaluate(make_command())
    second = AutomationPolicy().evaluate(make_command())

    assert first == second
    assert first.mode is AutomationMode.DENY
    assert first.reason_code is PolicyReasonCode.UNKNOWN_CAPABILITY
    assert first.explanation == (
        "The capability is unknown to this automation policy, so it is denied."
    )


def test_unknown_capability_is_denied_before_automatic_initiator_rule():
    policy = AutomationPolicy(
        capabilities={
            "test.known": CapabilityAutomationRule(),
        },
        initiator_rules={CommandSource.AI: AutomationMode.AUTOMATIC},
    )

    decision = policy.evaluate(make_command("test.unknown", CommandSource.AI))

    assert decision.mode is AutomationMode.DENY
    assert decision.reason_code is PolicyReasonCode.UNKNOWN_CAPABILITY


def test_configured_capability_without_applicable_rule_is_denied():
    policy = AutomationPolicy(
        capabilities={"test.inspect": CapabilityAutomationRule()}
    )

    decision = policy.evaluate(make_command(source=CommandSource.EXTERNAL))

    assert decision.mode is AutomationMode.DENY
    assert decision.reason_code is PolicyReasonCode.UNCONFIGURED_CAPABILITY


def test_capability_matching_is_exact_and_case_sensitive():
    policy = policy_with_mode(AutomationMode.AUTOMATIC)

    decision = policy.evaluate(make_command(command_type="Test.inspect"))

    assert decision.mode is AutomationMode.DENY
    assert decision.reason_code is PolicyReasonCode.UNKNOWN_CAPABILITY


def test_command_payload_cannot_override_capability_mode_or_approval():
    policy = policy_with_mode(AutomationMode.DENY)
    command = make_command(
        payload={
            "approval": "approved",
            "authorization": "granted",
            "automation_mode": "automatic",
            "capability": "test.automatic",
            "initiator_kind": "human",
        }
    )

    decision = policy.evaluate(command)

    assert decision.capability == command.command_type
    assert decision.initiator_kind is CommandSource.AI
    assert decision.mode is AutomationMode.DENY


def test_policy_configuration_is_deeply_immutable_and_defensively_copied():
    exact_modes = {CommandSource.AI: AutomationMode.REQUIRE_CONFIRMATION}
    rule = CapabilityAutomationRule(
        default_mode=AutomationMode.SUGGEST,
        initiator_modes=exact_modes,
    )
    capabilities = {"test.inspect": rule}
    initiator_rules = {CommandSource.HUMAN: AutomationMode.AUTOMATIC}
    policy = AutomationPolicy(capabilities, initiator_rules)

    exact_modes[CommandSource.AI] = AutomationMode.AUTOMATIC
    capabilities["test.inspect"] = CapabilityAutomationRule(
        default_mode=AutomationMode.AUTOMATIC
    )
    initiator_rules[CommandSource.HUMAN] = AutomationMode.DENY
    object.__setattr__(rule, "default_mode", AutomationMode.DENY)

    assert policy.evaluate(make_command()).mode is (
        AutomationMode.REQUIRE_CONFIRMATION
    )
    assert policy.evaluate(
        make_command(source=CommandSource.HUMAN)
    ).mode is AutomationMode.SUGGEST
    with pytest.raises(TypeError):
        policy.capabilities["test.inspect"] = rule
    with pytest.raises(TypeError):
        policy.capabilities["test.inspect"].initiator_modes[
            CommandSource.AI
        ] = AutomationMode.AUTOMATIC
    with pytest.raises(FrozenInstanceError):
        policy.initiator_rules = {}


def test_policy_serialization_is_json_compatible_independent_and_deterministic():
    policy = AutomationPolicy(
        capabilities={
            "test.second": CapabilityAutomationRule(
                default_mode=AutomationMode.SUGGEST,
            ),
            "test.first": CapabilityAutomationRule(
                initiator_modes={
                    CommandSource.SYSTEM: AutomationMode.AUTOMATIC,
                    CommandSource.AI: AutomationMode.REQUIRE_CONFIRMATION,
                }
            ),
        },
        initiator_rules={CommandSource.EXTERNAL: AutomationMode.DENY},
    )

    serialized = policy.to_dict()
    serialized["capabilities"]["test.first"]["initiator_modes"]["ai"] = (
        "automatic"
    )

    fresh = policy.to_dict()
    assert list(fresh["capabilities"]) == ["test.first", "test.second"]
    assert fresh["capabilities"]["test.first"]["initiator_modes"]["ai"] == (
        "require_confirmation"
    )
    assert json.loads(json.dumps(fresh, allow_nan=False)) == fresh
    assert policy.to_dict() == fresh


@pytest.mark.parametrize(
    "factory",
    [
        lambda: CapabilityAutomationRule(default_mode="automatic"),
        lambda: CapabilityAutomationRule(
            initiator_modes={"ai": AutomationMode.AUTOMATIC}
        ),
        lambda: CapabilityAutomationRule(
            initiator_modes={CommandSource.AI: "automatic"}
        ),
        lambda: AutomationPolicy(capabilities=[]),
        lambda: AutomationPolicy(
            capabilities={" padded ": CapabilityAutomationRule()}
        ),
        lambda: AutomationPolicy(capabilities={"test.inspect": {}}),
        lambda: AutomationPolicy(
            initiator_rules={"human": AutomationMode.AUTOMATIC}
        ),
    ],
    ids=[
        "untyped-capability-default",
        "untyped-capability-initiator",
        "untyped-capability-mode",
        "non-mapping-capabilities",
        "padded-capability",
        "untyped-capability-rule",
        "untyped-policy-initiator",
    ],
)
def test_invalid_policy_configuration_is_rejected(factory):
    with pytest.raises(ValueError):
        factory()


def test_policy_decision_preserves_identity_and_serializes_defensively():
    command = make_command(
        source=CommandSource.EXTERNAL,
        initiator_id="foundry-connector",
        actor_id="token-17",
    )
    decision = policy_with_mode(AutomationMode.SUGGEST).evaluate(command)

    serialized = decision.to_dict()
    serialized["actor_id"] = "changed"

    assert decision.to_dict() == {
        "actor_id": "token-17",
        "capability": "test.inspect",
        "command_id": "command-policy-001",
        "explanation": "A capability policy rule selected this mode.",
        "initiator_id": "foundry-connector",
        "initiator_kind": "external",
        "mode": "suggest",
        "reason_code": "capability_rule",
        "requires_human_confirmation": False,
    }
    assert json.loads(json.dumps(decision.to_dict())) == decision.to_dict()
    with pytest.raises(FrozenInstanceError):
        decision.mode = AutomationMode.AUTOMATIC


def test_actor_identity_does_not_change_policy_selection():
    policy = policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION)

    first = policy.evaluate(make_command(actor_id="actor-one"))
    second = policy.evaluate(make_command(actor_id="actor-two"))

    assert first.mode is second.mode
    assert first.reason_code is second.reason_code
    assert first.actor_id != second.actor_id


def test_repeated_evaluation_of_same_command_is_equivalent():
    policy = AutomationPolicy(
        capabilities={
            "test.inspect": CapabilityAutomationRule(
                initiator_modes={
                    CommandSource.AI: AutomationMode.REQUIRE_CONFIRMATION
                }
            )
        }
    )
    command = make_command()

    assert policy.evaluate(command) == policy.evaluate(command)
    assert policy.evaluate(command).to_dict() == policy.evaluate(command).to_dict()


def test_automatic_decision_becomes_ready_without_dispatch():
    decision = policy_with_mode(AutomationMode.AUTOMATIC).evaluate(make_command())

    disposition = resolve_automation_gate(decision)

    assert disposition.status is GateDispositionStatus.READY
    assert disposition.reason_code is GateReasonCode.AUTOMATIC_READY
    assert disposition.automation_approval_satisfied is True


def test_confirmation_without_approval_awaits_human_decision():
    decision = policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION).evaluate(
        make_command()
    )

    disposition = resolve_automation_gate(decision)

    assert disposition.status is GateDispositionStatus.AWAITING_APPROVAL
    assert disposition.reason_code is GateReasonCode.CONFIRMATION_REQUIRED
    assert disposition.automation_approval_satisfied is False


def test_matching_human_approval_makes_confirmation_ready():
    command = make_command()
    before = command.to_dict()
    decision = policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION).evaluate(
        command
    )
    approval = HumanApprovalDecision(
        command_id=command.command_id,
        outcome=ApprovalOutcome.APPROVED,
        approver_id="human-gm",
        reason="Reviewed and approved.",
    )

    disposition = resolve_automation_gate(decision, approval)

    assert disposition.status is GateDispositionStatus.READY
    assert disposition.reason_code is GateReasonCode.HUMAN_APPROVED
    assert command.to_dict() == before


def test_matching_human_denial_denies_confirmation():
    command = make_command()
    decision = policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION).evaluate(
        command
    )
    approval = HumanApprovalDecision(
        command_id=command.command_id,
        outcome=ApprovalOutcome.DENIED,
        approver_id="human-gm",
    )

    disposition = resolve_automation_gate(decision, approval)

    assert disposition.status is GateDispositionStatus.DENIED
    assert disposition.reason_code is GateReasonCode.HUMAN_DENIED
    assert disposition.automation_approval_satisfied is False


def test_ai_self_approval_is_rejected_at_record_construction():
    with pytest.raises(ValueError, match="Only a human"):
        HumanApprovalDecision(
            command_id="command-policy-001",
            outcome=ApprovalOutcome.APPROVED,
            approver_id="local-model",
            approver_kind=CommandSource.AI,
        )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: HumanApprovalDecision(
            command_id=" ",
            outcome=ApprovalOutcome.APPROVED,
            approver_id="human-gm",
        ),
        lambda: HumanApprovalDecision(
            command_id="command-policy-001",
            outcome="approved",
            approver_id="human-gm",
        ),
        lambda: HumanApprovalDecision(
            command_id="command-policy-001",
            outcome=ApprovalOutcome.APPROVED,
            approver_id=" ",
        ),
        lambda: HumanApprovalDecision(
            command_id="command-policy-001",
            outcome=ApprovalOutcome.APPROVED,
            approver_id="human-gm",
            reason=" ",
        ),
    ],
    ids=["invalid-command", "untyped-outcome", "empty-human", "empty-reason"],
)
def test_invalid_human_approval_records_are_rejected(factory):
    with pytest.raises(ValueError):
        factory()


def test_approval_record_is_immutable_and_json_compatible():
    approval = HumanApprovalDecision(
        command_id="command-policy-001",
        outcome=ApprovalOutcome.APPROVED,
        approver_id="human-gm",
        reason="Approved after review.",
    )

    assert approval.to_dict() == {
        "approver_id": "human-gm",
        "approver_kind": "human",
        "command_id": "command-policy-001",
        "outcome": "approved",
        "reason": "Approved after review.",
    }
    assert json.loads(json.dumps(approval.to_dict())) == approval.to_dict()
    with pytest.raises(FrozenInstanceError):
        approval.outcome = ApprovalOutcome.DENIED


def test_mismatched_approval_command_id_is_invalid_and_never_ready():
    decision = policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION).evaluate(
        make_command()
    )
    approval = HumanApprovalDecision(
        command_id="different-command",
        outcome=ApprovalOutcome.APPROVED,
        approver_id="human-gm",
    )

    disposition = resolve_automation_gate(decision, approval)

    assert disposition.status is GateDispositionStatus.INVALID
    assert disposition.reason_code is GateReasonCode.APPROVAL_COMMAND_MISMATCH
    assert disposition.automation_approval_satisfied is False


@pytest.mark.parametrize(
    ("mode", "status"),
    [
        (AutomationMode.SUGGEST, GateDispositionStatus.SUGGEST_ONLY),
        (AutomationMode.DENY, GateDispositionStatus.DENIED),
    ],
)
def test_non_confirmation_modes_resolve_safely_without_approval(mode, status):
    decision = policy_with_mode(mode).evaluate(make_command())

    disposition = resolve_automation_gate(decision)

    assert disposition.status is status
    assert disposition.automation_approval_satisfied is False


@pytest.mark.parametrize(
    "mode",
    [
        AutomationMode.AUTOMATIC,
        AutomationMode.SUGGEST,
        AutomationMode.DENY,
    ],
)
def test_unnecessary_approval_is_invalid_and_cannot_make_mode_ready(mode):
    command = make_command()
    decision = policy_with_mode(mode).evaluate(command)
    approval = HumanApprovalDecision(
        command_id=command.command_id,
        outcome=ApprovalOutcome.APPROVED,
        approver_id="human-gm",
    )

    disposition = resolve_automation_gate(decision, approval)

    assert disposition.status is GateDispositionStatus.INVALID
    assert disposition.reason_code is GateReasonCode.UNEXPECTED_APPROVAL
    assert disposition.automation_approval_satisfied is False


def test_structurally_corrupted_approval_fails_closed():
    command = make_command()
    decision = policy_with_mode(AutomationMode.REQUIRE_CONFIRMATION).evaluate(
        command
    )
    approval = HumanApprovalDecision(
        command_id=command.command_id,
        outcome=ApprovalOutcome.APPROVED,
        approver_id="human-gm",
    )
    object.__setattr__(approval, "approver_kind", CommandSource.AI)

    disposition = resolve_automation_gate(decision, approval)

    assert disposition.status is GateDispositionStatus.INVALID
    assert disposition.reason_code is GateReasonCode.INVALID_APPROVAL
    assert disposition.automation_approval_satisfied is False


def test_structurally_corrupted_policy_decision_fails_closed():
    decision = policy_with_mode(AutomationMode.AUTOMATIC).evaluate(make_command())
    object.__setattr__(decision, "mode", "automatic")

    disposition = resolve_automation_gate(decision)

    assert disposition.status is GateDispositionStatus.INVALID
    assert disposition.reason_code is GateReasonCode.INVALID_POLICY_DECISION
    assert disposition.automation_approval_satisfied is False


def test_gate_disposition_is_immutable_and_json_compatible():
    decision = policy_with_mode(AutomationMode.AUTOMATIC).evaluate(make_command())
    disposition = resolve_automation_gate(decision)

    serialized = disposition.to_dict()
    serialized["status"] = "denied"

    assert disposition.to_dict()["status"] == "ready"
    assert json.loads(json.dumps(disposition.to_dict())) == disposition.to_dict()
    with pytest.raises(FrozenInstanceError):
        disposition.status = GateDispositionStatus.DENIED


def test_policy_and_gate_never_invoke_handler_or_dispatcher():
    calls = []
    engine = GameEngine()
    engine.register_handler(
        "test.inspect",
        lambda command: calls.append(command) or GameResult.success(
            command.command_id
        ),
    )
    command = make_command()

    decision = policy_with_mode(AutomationMode.AUTOMATIC).evaluate(command)
    disposition = resolve_automation_gate(decision)

    assert disposition.status is GateDispositionStatus.READY
    assert calls == []
    assert engine.registered_command_types == ("test.inspect",)
