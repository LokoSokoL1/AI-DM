import itertools
import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from .audit import AuditStage
from .audited_pipeline import (
    AuditedCommandPipeline,
    AuditIntegrationStatus,
    EventPublicationDisposition,
)
from .automation import (
    ApprovalOutcome,
    AutomationMode,
    AutomationPolicy,
    CapabilityAutomationRule,
    HumanApprovalDecision,
)
from .command import CommandProvenance, CommandSource, GameCommand
from .game_engine import GameEngine
from .journals import CommandAuditJournal, GameEventJournal
from .policy_gated_dispatcher import (
    PolicyGatedCommandDispatcher,
    PolicyGatedDispatchStatus,
)
from .result import GameResult, GameResultStatus


FIXED_UTC = datetime(2026, 7, 15, 14, 30, 45, 123456, timezone.utc)
COMMAND_TYPE = "world.inspect"


def make_command(
    command_id="command-audited-001",
    payload=None,
):
    return GameCommand(
        command_id=command_id,
        command_type=COMMAND_TYPE,
        provenance=CommandProvenance(
            source=CommandSource.AI,
            initiator_id="local-model",
        ),
        actor_id="npc-scout-1",
        payload={} if payload is None else payload,
    )


def make_approval(command, command_id=None, reason=None):
    return HumanApprovalDecision(
        command_id=(
            command.command_id if command_id is None else command_id
        ),
        outcome=ApprovalOutcome.APPROVED,
        approver_id="human-gm",
        reason=reason,
    )


def sequential_ids(prefix="audit-record"):
    counter = itertools.count(1)
    return lambda: f"{prefix}-{next(counter):03d}"


def build_pipeline(
    mode=AutomationMode.AUTOMATIC,
    *,
    handler=None,
    register_handler=True,
    journal=None,
    event_journal=None,
    audit_record_id_factory=None,
    clock=None,
    engine=None,
    capabilities=None,
):
    calls = []
    selected_engine = GameEngine() if engine is None else engine

    if register_handler:
        selected_handler = handler
        if selected_handler is None:
            selected_handler = lambda command: GameResult.success(
                command.command_id,
                {"handled": True},
            )

        def tracked_handler(command):
            calls.append(command.command_id)
            return selected_handler(command)

        selected_engine.register_handler(COMMAND_TYPE, tracked_handler)

    selected_capabilities = capabilities
    if selected_capabilities is None:
        selected_capabilities = {
            COMMAND_TYPE: CapabilityAutomationRule(default_mode=mode)
        }
    policy = AutomationPolicy(capabilities=selected_capabilities)
    dispatcher = PolicyGatedCommandDispatcher(policy, selected_engine)
    selected_journal = (
        CommandAuditJournal() if journal is None else journal
    )
    selected_event_journal = (
        GameEventJournal() if event_journal is None else event_journal
    )
    pipeline = AuditedCommandPipeline(
        dispatcher,
        selected_journal,
        selected_event_journal,
        audit_record_id_factory=(
            sequential_ids()
            if audit_record_id_factory is None
            else audit_record_id_factory
        ),
        clock=(lambda: FIXED_UTC) if clock is None else clock,
    )
    return pipeline, dispatcher, selected_journal, calls


def stages(result):
    return tuple(entry.record.stage for entry in result.audit_entries)


def records(result):
    return tuple(entry.record for entry in result.audit_entries)


class FailingAuditJournal(CommandAuditJournal):
    def __init__(self, fail_on_append):
        super().__init__()
        self.fail_on_append = fail_on_append
        self.append_attempts = 0

    def append(self, record):
        self.append_attempts += 1
        if self.append_attempts == self.fail_on_append:
            raise RuntimeError("raw audit backend secret")
        return super().append(record)


class ExplodingEngine(GameEngine):
    def dispatch(self, command):
        raise RuntimeError("raw engine exception secret")


class ExplodingIntegratedDispatcher(PolicyGatedCommandDispatcher):
    def _dispatch_with_lifecycle(self, command, approval, lifecycle_recorder):
        raise RuntimeError("raw integration exception secret")


def test_automatic_dispatch_records_ordered_safe_lifecycle():
    command = make_command(payload={"hidden_campaign": "do-not-audit"})
    pipeline, dispatcher, journal, calls = build_pipeline()

    result = pipeline.dispatch(command)

    assert result.audit_status is AuditIntegrationStatus.COMPLETED
    assert result.error is None
    assert result.policy_gated_result.status is (
        PolicyGatedDispatchStatus.DISPATCHED
    )
    assert stages(result) == (
        AuditStage.COMMAND_PROPOSED,
        AuditStage.POLICY_EVALUATED,
        AuditStage.GATE_RESOLVED,
        AuditStage.DISPATCH_ATTEMPTED,
        AuditStage.DISPATCH_COMPLETED,
    )
    assert calls == [command.command_id]
    assert dispatcher.dispatch_attempted_command_ids == (command.command_id,)
    assert result.audit_entries == journal.entries
    assert all(
        record.provenance is command.provenance
        and record.actor_id == command.actor_id
        for record in records(result)
    )


def test_approved_dispatch_records_approval_and_dispatch_stages():
    command = make_command()
    approval = make_approval(
        command,
        reason="private approval reason must not be audited",
    )
    pipeline, _, _, calls = build_pipeline(
        AutomationMode.REQUIRE_CONFIRMATION
    )

    result = pipeline.dispatch(command, approval)

    assert result.audit_status is AuditIntegrationStatus.COMPLETED
    assert stages(result) == (
        AuditStage.COMMAND_PROPOSED,
        AuditStage.POLICY_EVALUATED,
        AuditStage.APPROVAL_EVALUATED,
        AuditStage.GATE_RESOLVED,
        AuditStage.DISPATCH_ATTEMPTED,
        AuditStage.DISPATCH_COMPLETED,
    )
    approval_record = records(result)[2]
    assert approval_record.outcome == "approved"
    assert approval_record.details == {
        "approver_id": "human-gm",
        "required": True,
    }
    assert calls == [command.command_id]


def test_awaiting_approval_records_blocked_path_without_dispatch():
    command = make_command()
    pipeline, dispatcher, _, calls = build_pipeline(
        AutomationMode.REQUIRE_CONFIRMATION
    )

    result = pipeline.dispatch(command)

    assert result.policy_gated_result.status is (
        PolicyGatedDispatchStatus.AWAITING_APPROVAL
    )
    assert stages(result) == (
        AuditStage.COMMAND_PROPOSED,
        AuditStage.POLICY_EVALUATED,
        AuditStage.APPROVAL_EVALUATED,
        AuditStage.GATE_RESOLVED,
        AuditStage.DISPATCH_BLOCKED,
    )
    assert records(result)[2].outcome == "not_supplied"
    assert calls == []
    assert dispatcher.dispatch_attempted_command_ids == ()


@pytest.mark.parametrize(
    ("mode", "expected_status"),
    [
        (
            AutomationMode.SUGGEST,
            PolicyGatedDispatchStatus.SUGGESTION_ONLY,
        ),
        (AutomationMode.DENY, PolicyGatedDispatchStatus.DENIED),
    ],
)
def test_suggestion_and_denial_record_blocked_paths(
    mode,
    expected_status,
):
    command = make_command()
    pipeline, dispatcher, _, calls = build_pipeline(mode)

    result = pipeline.dispatch(command)

    assert result.policy_gated_result.status is expected_status
    assert stages(result) == (
        AuditStage.COMMAND_PROPOSED,
        AuditStage.POLICY_EVALUATED,
        AuditStage.GATE_RESOLVED,
        AuditStage.DISPATCH_BLOCKED,
    )
    assert calls == []
    assert dispatcher.dispatch_attempted_command_ids == ()


def test_unknown_capability_is_audited_as_fail_closed_denial():
    command = make_command()
    pipeline, dispatcher, _, calls = build_pipeline(capabilities={})

    result = pipeline.dispatch(command)

    assert result.policy_gated_result.status is PolicyGatedDispatchStatus.DENIED
    policy_record = records(result)[1]
    assert policy_record.outcome == "deny"
    assert policy_record.details["reason_code"] == "unknown_capability"
    assert records(result)[-1].outcome == "denied"
    assert calls == []
    assert dispatcher.dispatch_attempted_command_ids == ()


@pytest.mark.parametrize(
    "approval_factory",
    [
        lambda command: make_approval(
            command,
            command_id="different-command-id",
        ),
        lambda command: object(),
    ],
    ids=["mismatched", "invalid"],
)
def test_invalid_or_mismatched_approval_records_invalid_blocked_path(
    approval_factory,
):
    command = make_command()
    pipeline, dispatcher, _, calls = build_pipeline(
        AutomationMode.REQUIRE_CONFIRMATION
    )

    result = pipeline.dispatch(command, approval_factory(command))

    assert result.policy_gated_result.status is (
        PolicyGatedDispatchStatus.INVALID
    )
    assert stages(result) == (
        AuditStage.COMMAND_PROPOSED,
        AuditStage.POLICY_EVALUATED,
        AuditStage.APPROVAL_EVALUATED,
        AuditStage.GATE_RESOLVED,
        AuditStage.DISPATCH_BLOCKED,
    )
    assert records(result)[2].outcome == "invalid"
    assert records(result)[3].outcome == "invalid"
    assert calls == []
    assert dispatcher.dispatch_attempted_command_ids == ()


def test_duplicate_submission_is_audited_without_another_dispatch():
    command = make_command()
    pipeline, _, journal, calls = build_pipeline()

    first = pipeline.dispatch(command)
    repeated = pipeline.dispatch(command)

    assert first.policy_gated_result.status is (
        PolicyGatedDispatchStatus.DISPATCHED
    )
    assert repeated.policy_gated_result.status is (
        PolicyGatedDispatchStatus.DUPLICATE
    )
    assert stages(repeated) == (
        AuditStage.COMMAND_PROPOSED,
        AuditStage.POLICY_EVALUATED,
        AuditStage.GATE_RESOLVED,
        AuditStage.DISPATCH_BLOCKED,
    )
    assert calls == [command.command_id]
    assert len(journal.entries) == 9


def test_unknown_engine_command_preserves_result_and_completion_status():
    command = make_command()
    pipeline, _, _, calls = build_pipeline(register_handler=False)

    result = pipeline.dispatch(command)

    game_result = result.policy_gated_result.game_result
    assert game_result.status is GameResultStatus.UNKNOWN_COMMAND
    assert records(result)[-1].outcome == "unknown_command"
    assert records(result)[-1].details["game_result_status"] == (
        "unknown_command"
    )
    assert calls == []


def test_handler_failure_preserves_controlled_result_without_raw_error_audit():
    def failing_handler(command):
        raise RuntimeError("raw handler exception secret")

    command = make_command()
    pipeline, _, journal, calls = build_pipeline(handler=failing_handler)

    result = pipeline.dispatch(command)

    game_result = result.policy_gated_result.game_result
    assert game_result.status is GameResultStatus.HANDLER_FAILURE
    assert records(result)[-1].outcome == "handler_failure"
    assert calls == [command.command_id]
    assert "raw handler exception secret" not in json.dumps(journal.to_list())


def test_domain_negative_output_and_payload_are_not_automatically_audited():
    payload_secret = "hidden-campaign-payload-secret"
    output_secret = "handler-output-secret"

    def domain_negative_handler(command):
        return GameResult.success(
            command.command_id,
            {"success": False, "private_reason": output_secret},
        )

    command = make_command(payload={"private": payload_secret})
    pipeline, _, journal, _ = build_pipeline(
        handler=domain_negative_handler
    )

    result = pipeline.dispatch(command)

    assert result.policy_gated_result.game_result.status is (
        GameResultStatus.SUCCESS
    )
    assert result.policy_gated_result.game_result.output["success"] is False
    serialized_audit = json.dumps(journal.to_list(), sort_keys=True)
    assert payload_secret not in serialized_audit
    assert output_secret not in serialized_audit
    assert "payload" not in serialized_audit
    assert "output" not in serialized_audit


def test_injected_audit_ids_and_timestamps_are_deterministic():
    command = make_command()
    generated_times = iter(
        FIXED_UTC.replace(microsecond=index)
        for index in range(1, 6)
    )
    pipeline, _, _, _ = build_pipeline(
        audit_record_id_factory=sequential_ids("deterministic-audit"),
        clock=lambda: next(generated_times),
    )

    result = pipeline.dispatch(command)

    assert tuple(
        record.audit_record_id for record in records(result)
    ) == tuple(
        f"deterministic-audit-{index:03d}" for index in range(1, 6)
    )
    assert tuple(record.recorded_at for record in records(result)) == tuple(
        FIXED_UTC.replace(microsecond=index) for index in range(1, 6)
    )


def test_failure_on_first_audit_append_prevents_all_dispatch_behavior():
    command = make_command()
    journal = FailingAuditJournal(fail_on_append=1)
    pipeline, dispatcher, _, calls = build_pipeline(journal=journal)

    result = pipeline.dispatch(command)

    assert result.audit_status is (
        AuditIntegrationStatus.PRE_DISPATCH_AUDIT_FAILURE
    )
    assert result.policy_gated_result is None
    assert result.audit_entries == ()
    assert journal.entries == ()
    assert journal.append_attempts == 1
    assert calls == []
    assert dispatcher.dispatch_attempted_command_ids == ()
    assert "raw audit backend secret" not in result.error


def test_failure_immediately_before_dispatch_does_not_consume_replay():
    command = make_command()
    journal = FailingAuditJournal(fail_on_append=4)
    pipeline, dispatcher, _, calls = build_pipeline(journal=journal)

    result = pipeline.dispatch(command)

    assert result.audit_status is (
        AuditIntegrationStatus.PRE_DISPATCH_AUDIT_FAILURE
    )
    assert result.policy_gated_result is None
    assert stages(result) == (
        AuditStage.COMMAND_PROPOSED,
        AuditStage.POLICY_EVALUATED,
        AuditStage.GATE_RESOLVED,
    )
    assert calls == []
    assert dispatcher.dispatch_attempted_command_ids == ()
    assert journal.entries == result.audit_entries


def test_blocked_append_failure_preserves_existing_behavioral_result():
    command = make_command()
    journal = FailingAuditJournal(fail_on_append=4)
    pipeline, dispatcher, _, calls = build_pipeline(
        AutomationMode.SUGGEST,
        journal=journal,
    )

    result = pipeline.dispatch(command)

    assert result.audit_status is (
        AuditIntegrationStatus.PRE_DISPATCH_AUDIT_FAILURE
    )
    assert result.policy_gated_result.status is (
        PolicyGatedDispatchStatus.SUGGESTION_ONLY
    )
    assert result.policy_gated_result.dispatch_attempted is False
    assert calls == []
    assert dispatcher.dispatch_attempted_command_ids == ()


def test_post_dispatch_audit_failure_preserves_result_replay_and_no_retry():
    command = make_command()
    journal = FailingAuditJournal(fail_on_append=5)
    pipeline, dispatcher, _, calls = build_pipeline(journal=journal)

    failed_audit = pipeline.dispatch(command)

    assert failed_audit.audit_status is (
        AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE
    )
    assert failed_audit.policy_gated_result.status is (
        PolicyGatedDispatchStatus.DISPATCHED
    )
    assert failed_audit.policy_gated_result.game_result.status is (
        GameResultStatus.SUCCESS
    )
    assert stages(failed_audit) == (
        AuditStage.COMMAND_PROPOSED,
        AuditStage.POLICY_EVALUATED,
        AuditStage.GATE_RESOLVED,
        AuditStage.DISPATCH_ATTEMPTED,
    )
    assert dispatcher.dispatch_attempted_command_ids == (command.command_id,)
    assert calls == [command.command_id]

    duplicate = pipeline.dispatch(command)

    assert duplicate.audit_status is AuditIntegrationStatus.COMPLETED
    assert duplicate.policy_gated_result.status is (
        PolicyGatedDispatchStatus.DUPLICATE
    )
    assert calls == [command.command_id]
    assert journal.entries[:4] == failed_audit.audit_entries
    assert journal.append_attempts == 9


def test_duplicate_generated_audit_id_fails_safely_with_partial_history():
    command = make_command()
    journal = CommandAuditJournal()
    pipeline, dispatcher, _, calls = build_pipeline(
        journal=journal,
        audit_record_id_factory=lambda: "duplicate-generated-audit-id",
    )

    result = pipeline.dispatch(command)

    assert result.audit_status is (
        AuditIntegrationStatus.PRE_DISPATCH_AUDIT_FAILURE
    )
    assert stages(result) == (AuditStage.COMMAND_PROPOSED,)
    assert journal.entries == result.audit_entries
    assert calls == []
    assert dispatcher.dispatch_attempted_command_ids == ()


def test_coordinator_failure_is_recorded_after_crossing_engine_boundary():
    command = make_command()
    pipeline, dispatcher, _, calls = build_pipeline(
        engine=ExplodingEngine(),
        register_handler=False,
    )

    result = pipeline.dispatch(command)

    assert result.audit_status is AuditIntegrationStatus.COMPLETED
    assert result.policy_gated_result.status is (
        PolicyGatedDispatchStatus.COORDINATOR_FAILURE
    )
    assert result.policy_gated_result.dispatch_attempted is True
    assert stages(result) == (
        AuditStage.COMMAND_PROPOSED,
        AuditStage.POLICY_EVALUATED,
        AuditStage.GATE_RESOLVED,
        AuditStage.DISPATCH_ATTEMPTED,
        AuditStage.COORDINATOR_FAILURE,
    )
    assert dispatcher.dispatch_attempted_command_ids == (command.command_id,)
    assert calls == []
    assert "raw engine exception secret" not in json.dumps(result.to_dict())


def test_unexpected_integration_failure_is_controlled_and_sanitized():
    policy = AutomationPolicy(
        capabilities={
            COMMAND_TYPE: CapabilityAutomationRule(
                default_mode=AutomationMode.AUTOMATIC
            )
        }
    )
    dispatcher = ExplodingIntegratedDispatcher(policy, GameEngine())
    journal = CommandAuditJournal()
    pipeline = AuditedCommandPipeline(
        dispatcher,
        journal,
        GameEventJournal(),
        audit_record_id_factory=sequential_ids(),
        clock=lambda: FIXED_UTC,
    )

    result = pipeline.dispatch(make_command())

    assert result.audit_status is (
        AuditIntegrationStatus.CONTROLLED_INTEGRATION_FAILURE
    )
    assert stages(result) == (AuditStage.COMMAND_PROPOSED,)
    assert result.policy_gated_result is None
    assert "raw integration exception secret" not in result.error


def test_returned_entries_and_serialization_cannot_mutate_journal_state():
    command = make_command()
    pipeline, _, journal, _ = build_pipeline()
    result = pipeline.dispatch(command)
    original_entries = journal.entries
    snapshot = result.audit_entries

    with pytest.raises(AttributeError):
        snapshot.append(original_entries[0])
    with pytest.raises(FrozenInstanceError):
        original_entries[0].sequence = 99
    with pytest.raises(FrozenInstanceError):
        result.error = "changed"

    snapshot += (original_entries[0],)
    serialized = result.to_dict()
    serialized["audit_entries"][0]["record"]["outcome"] = "changed"

    assert journal.entries == original_entries
    assert result.audit_entries == original_entries
    assert result.to_dict()["audit_entries"][0]["record"]["outcome"] == (
        "received"
    )
    assert json.loads(json.dumps(result.to_dict(), allow_nan=False)) == (
        result.to_dict()
    )


def test_audited_pipeline_produces_no_game_events():
    event_journal = GameEventJournal()
    pipeline, _, audit_journal, _ = build_pipeline(
        event_journal=event_journal
    )

    result = pipeline.dispatch(make_command())

    assert result.audit_status is AuditIntegrationStatus.COMPLETED
    assert result.publication_disposition is (
        EventPublicationDisposition.NO_EVENTS
    )
    assert audit_journal.entries
    assert event_journal.entries == ()
    assert result.published_event_entries == ()


def test_existing_unaudited_dispatch_remains_compatible_and_writes_no_audit():
    command = make_command()
    pipeline, dispatcher, journal, calls = build_pipeline()

    result = dispatcher.dispatch(command)

    assert result.status is PolicyGatedDispatchStatus.DISPATCHED
    assert result.game_result.status is GameResultStatus.SUCCESS
    assert calls == [command.command_id]
    assert journal.entries == ()
    assert pipeline is not None
