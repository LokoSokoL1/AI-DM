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
from .game_event import GameEvent
from .journals import CommandAuditJournal, GameEventJournal
from .policy_gated_dispatcher import (
    PolicyGatedCommandDispatcher,
    PolicyGatedDispatchStatus,
)
from .result import GameResult, GameResultStatus
from .world_state import WorldState, WorldStateProjector
from .world_state_holder import WorldStateHolder


COMMAND_TYPE = "world.publish_test_events"
FIXED_UTC = datetime(2026, 7, 15, 20, 30, tzinfo=timezone.utc)


def make_command(command_id="command-publication-001"):
    return GameCommand(
        command_id=command_id,
        command_type=COMMAND_TYPE,
        provenance=CommandProvenance(
            source=CommandSource.AI,
            initiator_id="publication-test-model",
        ),
        actor_id="publication-test-actor",
        payload={"hidden_campaign": "never-audit-command-payload"},
    )


def make_event(command, number=1, *, payload=None):
    return GameEvent(
        event_id=f"event-publication-{command.command_id}-{number:03d}",
        event_type=f"world.publication_test_{number}",
        provenance=CommandProvenance(
            source=CommandSource.SYSTEM,
            initiator_id="publication-test-handler",
        ),
        actor_id=f"event-actor-{number}",
        originating_command_id=command.command_id,
        payload=(
            {"order": number, "nested": [{"value": number}]}
            if payload is None
            else payload
        ),
        occurred_at=FIXED_UTC,
    )


def make_approval(command):
    return HumanApprovalDecision(
        command_id=command.command_id,
        outcome=ApprovalOutcome.APPROVED,
        approver_id="human-gm",
        reason="private approval reason",
    )


def build_pipeline(
    handler,
    *,
    mode=AutomationMode.AUTOMATIC,
    capabilities=None,
    audit_journal=None,
    event_journal=None,
    engine=None,
    register_handler=True,
):
    calls = []
    selected_engine = GameEngine() if engine is None else engine
    if register_handler:
        def tracked_handler(command):
            calls.append(command)
            return handler(command)

        selected_engine.register_handler(COMMAND_TYPE, tracked_handler)

    selected_capabilities = capabilities
    if selected_capabilities is None:
        selected_capabilities = {
            COMMAND_TYPE: CapabilityAutomationRule(default_mode=mode)
        }
    dispatcher = PolicyGatedCommandDispatcher(
        AutomationPolicy(capabilities=selected_capabilities),
        selected_engine,
    )
    selected_audit_journal = (
        CommandAuditJournal() if audit_journal is None else audit_journal
    )
    selected_event_journal = (
        GameEventJournal() if event_journal is None else event_journal
    )
    projector = WorldStateProjector()
    for number in (1, 2, 3):
        projector.register_reducer(
            f"world.publication_test_{number}",
            1,
            lambda state, event: state,
        )
    audit_ids = itertools.count(1)
    pipeline = AuditedCommandPipeline(
        dispatcher,
        selected_audit_journal,
        selected_event_journal,
        projector,
        WorldStateHolder(
            WorldState(last_sequence=len(selected_event_journal.entries))
        ),
        audit_record_id_factory=(
            lambda: f"audit-publication-{next(audit_ids):03d}"
        ),
        clock=lambda: FIXED_UTC,
    )
    return (
        pipeline,
        dispatcher,
        selected_audit_journal,
        selected_event_journal,
        calls,
    )


class FailingEventJournal(GameEventJournal):
    def __init__(self):
        super().__init__()
        self.append_batch_attempts = 0
        self.attempted_batches = []

    def append_batch(self, events):
        self.append_batch_attempts += 1
        self.attempted_batches.append(tuple(events))
        raise RuntimeError("raw event backend secret")


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
        raise RuntimeError("raw coordinator engine secret")


def test_automatic_dispatch_publishes_one_event_once():
    command = make_command()
    event = make_event(command)
    expected = GameResult.success(command.command_id, events=(event,))
    pipeline, dispatcher, _, event_journal, calls = build_pipeline(
        lambda received: expected
    )

    result = pipeline.dispatch(command)

    assert result.audit_status is AuditIntegrationStatus.COMPLETED
    assert result.publication_disposition is (
        EventPublicationDisposition.PUBLISHED
    )
    assert result.publication_error is None
    assert result.policy_gated_result.game_result is expected
    assert result.published_event_entries == event_journal.entries
    assert tuple(entry.event for entry in event_journal.entries) == (event,)
    assert tuple(entry.sequence for entry in event_journal.entries) == (1,)
    assert calls == [command]
    assert dispatcher.dispatch_attempted_command_ids == (command.command_id,)


def test_human_approved_dispatch_publishes_ordered_event_batch():
    command = make_command()
    events = tuple(make_event(command, number) for number in (3, 1, 2))
    expected = GameResult.success(command.command_id, events=events)
    pipeline, _, _, event_journal, calls = build_pipeline(
        lambda received: expected,
        mode=AutomationMode.REQUIRE_CONFIRMATION,
    )

    result = pipeline.dispatch(command, make_approval(command))

    assert result.publication_disposition is (
        EventPublicationDisposition.PUBLISHED
    )
    assert result.policy_gated_result.game_result is expected
    assert tuple(entry.event for entry in result.published_event_entries) == (
        events
    )
    assert tuple(entry.sequence for entry in event_journal.entries) == (1, 2, 3)
    assert calls == [command]


def test_eventless_dispatched_result_is_a_no_op():
    command = make_command()
    expected = GameResult.success(command.command_id, {"handled": True})
    pipeline, _, _, event_journal, calls = build_pipeline(
        lambda received: expected
    )

    result = pipeline.dispatch(command)

    assert result.audit_status is AuditIntegrationStatus.COMPLETED
    assert result.publication_disposition is (
        EventPublicationDisposition.NO_EVENTS
    )
    assert result.policy_gated_result.game_result is expected
    assert result.published_event_entries == ()
    assert result.publication_error is None
    assert event_journal.entries == ()
    assert calls == [command]


def test_controlled_engine_failure_is_dispatched_but_has_no_events():
    command = make_command()
    pipeline, _, _, event_journal, calls = build_pipeline(
        lambda received: None,
        register_handler=False,
    )

    result = pipeline.dispatch(command)

    assert result.policy_gated_result.status is (
        PolicyGatedDispatchStatus.DISPATCHED
    )
    assert result.policy_gated_result.game_result.status is (
        GameResultStatus.UNKNOWN_COMMAND
    )
    assert result.publication_disposition is (
        EventPublicationDisposition.NO_EVENTS
    )
    assert event_journal.entries == ()
    assert calls == []


@pytest.mark.parametrize(
    ("mode", "expected_status"),
    [
        (
            AutomationMode.REQUIRE_CONFIRMATION,
            PolicyGatedDispatchStatus.AWAITING_APPROVAL,
        ),
        (AutomationMode.SUGGEST, PolicyGatedDispatchStatus.SUGGESTION_ONLY),
        (AutomationMode.DENY, PolicyGatedDispatchStatus.DENIED),
    ],
)
def test_policy_blocked_paths_never_publish(mode, expected_status):
    command = make_command()
    pipeline, dispatcher, _, event_journal, calls = build_pipeline(
        lambda received: GameResult.success(
            received.command_id,
            events=(make_event(received),),
        ),
        mode=mode,
    )

    result = pipeline.dispatch(command)

    assert result.policy_gated_result.status is expected_status
    assert result.publication_disposition is (
        EventPublicationDisposition.NOT_APPLICABLE
    )
    assert result.published_event_entries == ()
    assert event_journal.entries == ()
    assert calls == []
    assert dispatcher.dispatch_attempted_command_ids == ()


def test_unknown_capability_and_invalid_approval_never_publish():
    command = make_command()
    handler = lambda received: GameResult.success(
        received.command_id,
        events=(make_event(received),),
    )
    unknown_pipeline, _, _, unknown_events, unknown_calls = build_pipeline(
        handler,
        capabilities={},
    )
    invalid_pipeline, _, _, invalid_events, invalid_calls = build_pipeline(
        handler,
        mode=AutomationMode.REQUIRE_CONFIRMATION,
    )
    mismatched_approval = HumanApprovalDecision(
        command_id="different-command",
        outcome=ApprovalOutcome.APPROVED,
        approver_id="human-gm",
    )

    unknown = unknown_pipeline.dispatch(command)
    invalid = invalid_pipeline.dispatch(command, mismatched_approval)

    assert unknown.policy_gated_result.status is PolicyGatedDispatchStatus.DENIED
    assert invalid.policy_gated_result.status is PolicyGatedDispatchStatus.INVALID
    assert unknown.publication_disposition is (
        EventPublicationDisposition.NOT_APPLICABLE
    )
    assert invalid.publication_disposition is (
        EventPublicationDisposition.NOT_APPLICABLE
    )
    assert unknown_events.entries == invalid_events.entries == ()
    assert unknown_calls == invalid_calls == []


def test_pre_dispatch_audit_failure_prevents_dispatch_and_publication():
    command = make_command()
    audit_journal = FailingAuditJournal(fail_on_append=1)
    pipeline, dispatcher, _, event_journal, calls = build_pipeline(
        lambda received: GameResult.success(
            received.command_id,
            events=(make_event(received),),
        ),
        audit_journal=audit_journal,
    )

    result = pipeline.dispatch(command)

    assert result.audit_status is (
        AuditIntegrationStatus.PRE_DISPATCH_AUDIT_FAILURE
    )
    assert result.policy_gated_result is None
    assert result.publication_disposition is (
        EventPublicationDisposition.NOT_APPLICABLE
    )
    assert event_journal.entries == ()
    assert calls == []
    assert dispatcher.dispatch_attempted_command_ids == ()


def test_coordinator_failure_never_publishes_without_dispatched_result():
    command = make_command()
    pipeline, dispatcher, _, event_journal, calls = build_pipeline(
        lambda received: None,
        engine=ExplodingEngine(),
        register_handler=False,
    )

    result = pipeline.dispatch(command)

    assert result.policy_gated_result.status is (
        PolicyGatedDispatchStatus.COORDINATOR_FAILURE
    )
    assert result.policy_gated_result.dispatch_attempted is True
    assert result.publication_disposition is (
        EventPublicationDisposition.NOT_APPLICABLE
    )
    assert event_journal.entries == ()
    assert calls == []
    assert dispatcher.dispatch_attempted_command_ids == (command.command_id,)


def test_duplicate_command_does_not_republish_or_reinvoke_handler():
    command = make_command()
    event = make_event(command)
    expected = GameResult.success(command.command_id, events=(event,))
    pipeline, _, _, event_journal, calls = build_pipeline(
        lambda received: expected
    )

    first = pipeline.dispatch(command)
    before_duplicate = event_journal.entries
    duplicate = pipeline.dispatch(command)

    assert first.publication_disposition is (
        EventPublicationDisposition.PUBLISHED
    )
    assert duplicate.policy_gated_result.status is (
        PolicyGatedDispatchStatus.DUPLICATE
    )
    assert duplicate.publication_disposition is (
        EventPublicationDisposition.NOT_APPLICABLE
    )
    assert duplicate.published_event_entries == ()
    assert event_journal.entries is before_duplicate
    assert calls == [command]


def test_publication_failure_preserves_dispatch_replay_and_atomic_absence():
    command = make_command()
    payload_secret = "private-event-payload-secret"
    events = (
        make_event(command, 1, payload={"secret": payload_secret}),
        make_event(command, 2),
    )
    expected = GameResult.success(command.command_id, events=events)
    event_journal = FailingEventJournal()
    pipeline, dispatcher, audit_journal, _, calls = build_pipeline(
        lambda received: expected,
        event_journal=event_journal,
    )

    failed = pipeline.dispatch(command)

    assert failed.audit_status is (
        AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE
    )
    assert failed.publication_disposition is (
        EventPublicationDisposition.FAILED
    )
    assert failed.policy_gated_result.status is (
        PolicyGatedDispatchStatus.DISPATCHED
    )
    assert failed.policy_gated_result.game_result is expected
    assert failed.published_event_entries == ()
    assert event_journal.entries == ()
    assert event_journal.append_batch_attempts == 1
    assert event_journal.attempted_batches == [events]
    assert calls == [command]
    assert dispatcher.dispatch_attempted_command_ids == (command.command_id,)
    assert failed.publication_error
    assert "raw event backend secret" not in failed.publication_error
    assert payload_secret not in failed.publication_error
    assert "raw event backend secret" not in failed.error
    serialized_audit = json.dumps(audit_journal.to_list(), sort_keys=True)
    assert payload_secret not in serialized_audit
    assert "raw event backend secret" not in serialized_audit
    assert audit_journal.entries[-1].record.stage is (
        AuditStage.COORDINATOR_FAILURE
    )
    assert audit_journal.entries[-1].record.details == {
        "event_count": 2,
        "phase": "event_publication",
        "publication_disposition": "failed",
    }

    duplicate = pipeline.dispatch(command)

    assert duplicate.policy_gated_result.status is (
        PolicyGatedDispatchStatus.DUPLICATE
    )
    assert duplicate.publication_disposition is (
        EventPublicationDisposition.NOT_APPLICABLE
    )
    assert event_journal.append_batch_attempts == 1
    assert event_journal.entries == ()
    assert calls == [command]


def test_post_dispatch_audit_failure_cannot_suppress_published_events():
    command = make_command()
    events = (make_event(command, 1), make_event(command, 2))
    expected = GameResult.success(command.command_id, events=events)
    audit_journal = FailingAuditJournal(fail_on_append=5)
    pipeline, dispatcher, _, event_journal, calls = build_pipeline(
        lambda received: expected,
        audit_journal=audit_journal,
    )

    result = pipeline.dispatch(command)

    assert result.audit_status is (
        AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE
    )
    assert result.publication_disposition is (
        EventPublicationDisposition.PUBLISHED
    )
    assert result.policy_gated_result.game_result is expected
    assert result.published_event_entries == event_journal.entries
    assert tuple(entry.event for entry in event_journal.entries) == events
    assert calls == [command]
    assert dispatcher.dispatch_attempted_command_ids == (command.command_id,)
    assert "raw audit backend secret" not in result.error


def test_published_entry_snapshots_and_serialization_are_defensive():
    command = make_command()
    event = make_event(command)
    pipeline, _, _, event_journal, _ = build_pipeline(
        lambda received: GameResult.success(
            received.command_id,
            events=(event,),
        )
    )
    result = pipeline.dispatch(command)
    original_entries = event_journal.entries
    snapshot = result.published_event_entries

    with pytest.raises(AttributeError):
        snapshot.append(original_entries[0])
    with pytest.raises(FrozenInstanceError):
        original_entries[0].sequence = 99
    with pytest.raises(FrozenInstanceError):
        result.publication_disposition = EventPublicationDisposition.FAILED

    snapshot += (original_entries[0],)
    serialized = result.to_dict()
    serialized["published_event_entries"][0]["event"]["payload"][
        "nested"
    ][0]["value"] = 999
    serialized["policy_gated_result"]["game_result"]["events"][0][
        "payload"
    ]["nested"][0]["value"] = 999

    assert event_journal.entries == original_entries
    assert result.published_event_entries == original_entries
    fresh = result.to_dict()
    assert fresh["published_event_entries"][0]["event"]["payload"][
        "nested"
    ][0]["value"] == 1
    assert fresh["publication_disposition"] == "published"
    assert fresh["publication_error"] is None
    assert json.loads(json.dumps(fresh, allow_nan=False)) == fresh


def test_pipeline_requires_explicit_game_event_journal():
    dispatcher = PolicyGatedCommandDispatcher(
        AutomationPolicy(
            capabilities={
                COMMAND_TYPE: CapabilityAutomationRule(
                    default_mode=AutomationMode.AUTOMATIC
                )
            }
        ),
        GameEngine(),
    )

    with pytest.raises(ValueError, match="game event journal"):
        AuditedCommandPipeline(
            dispatcher,
            CommandAuditJournal(),
            None,
            WorldStateProjector(),
            WorldStateHolder(WorldState.initial()),
        )
