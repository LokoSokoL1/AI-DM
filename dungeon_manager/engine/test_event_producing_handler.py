import itertools
import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

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


COMMAND_TYPE = "test.produce_events"
FIXED_UTC = datetime(2026, 7, 15, 18, 30, tzinfo=timezone.utc)
EVENT_PROVENANCE = CommandProvenance(
    source=CommandSource.SYSTEM,
    initiator_id="event-producing-handler",
)


def make_command(command_id="command-events-001"):
    return GameCommand(
        command_id=command_id,
        command_type=COMMAND_TYPE,
        provenance=CommandProvenance(
            source=CommandSource.AI,
            initiator_id="event-contract-test",
        ),
        actor_id="command-actor",
        payload={"request": "test-only"},
    )


def make_event(command, number=1, **overrides):
    values = {
        "event_id": f"event-produced-{number:03d}",
        "event_type": f"world.test_event_{number}",
        "provenance": EVENT_PROVENANCE,
        "actor_id": f"event-actor-{number}",
        "originating_command_id": command.command_id,
        "payload": {"order": number, "nested": [{"value": number}]},
        "occurred_at": FIXED_UTC,
    }
    values.update(overrides)
    return GameEvent(**values)


def engine_with_handler(handler):
    engine = GameEngine()
    engine.register_handler(COMMAND_TYPE, handler)
    return engine


def policy(mode):
    return AutomationPolicy(
        capabilities={
            COMMAND_TYPE: CapabilityAutomationRule(default_mode=mode)
        }
    )


def approval(command, outcome=ApprovalOutcome.APPROVED):
    return HumanApprovalDecision(
        command_id=command.command_id,
        outcome=outcome,
        approver_id="human-gm",
    )


def audited_pipeline(
    handler,
    *,
    mode=AutomationMode.AUTOMATIC,
    journal=None,
    event_journal=None,
):
    dispatcher = PolicyGatedCommandDispatcher(
        policy(mode),
        engine_with_handler(handler),
    )
    audit_journal = CommandAuditJournal() if journal is None else journal
    published_events = (
        GameEventJournal() if event_journal is None else event_journal
    )
    ids = itertools.count(1)
    pipeline = AuditedCommandPipeline(
        dispatcher,
        audit_journal,
        published_events,
        audit_record_id_factory=lambda: f"audit-events-{next(ids):03d}",
        clock=lambda: FIXED_UTC,
    )
    return pipeline, dispatcher, audit_journal


class FailingAuditJournal(CommandAuditJournal):
    def __init__(self, fail_on_append):
        super().__init__()
        self.fail_on_append = fail_on_append
        self.append_attempts = 0

    def append(self, record):
        self.append_attempts += 1
        if self.append_attempts == self.fail_on_append:
            raise RuntimeError("private audit failure")
        return super().append(record)


def assert_controlled_invalid_handler_result(result, command):
    assert result.status is GameResultStatus.INVALID_HANDLER_RESULT
    assert result.command_id == command.command_id
    assert result.error == "The command handler returned an invalid result."
    assert result.events == ()
    assert result.to_dict()["events"] == []


def test_existing_successful_handler_result_defaults_to_no_events():
    command = make_command()
    expected = GameResult.success(command.command_id, {"handled": True})
    engine = engine_with_handler(lambda received: expected)

    result = engine.dispatch(command)

    assert result is expected
    assert result.events == ()
    assert result.to_dict()["events"] == []


def test_one_valid_event_is_preserved_without_actor_or_provenance_rewriting():
    command = make_command()
    event = make_event(command)
    expected = GameResult.success(command.command_id, events=(event,))

    result = engine_with_handler(lambda received: expected).dispatch(command)

    assert result is expected
    assert result.events == (event,)
    assert result.events[0] is event
    assert event.actor_id != command.actor_id
    assert event.provenance is not command.provenance


def test_multiple_events_preserve_handler_order_and_identity():
    command = make_command()
    events = tuple(make_event(command, number) for number in (3, 1, 2))
    expected = GameResult.success(command.command_id, events=events)

    result = engine_with_handler(lambda received: expected).dispatch(command)

    assert result is expected
    assert result.events == events
    assert tuple(event.event_id for event in result.events) == (
        "event-produced-003",
        "event-produced-001",
        "event-produced-002",
    )


def test_event_collection_is_copied_to_an_immutable_tuple():
    command = make_command()
    event = make_event(command)
    supplied = [event]

    result = GameResult.success(command.command_id, events=supplied)
    supplied.clear()

    assert result.events == (event,)
    with pytest.raises(AttributeError):
        result.events.append(event)
    with pytest.raises(FrozenInstanceError):
        result.events = ()


def test_event_serialization_is_json_compatible_and_defensive():
    command = make_command()
    event = make_event(command)
    result = GameResult.success(
        command.command_id,
        {"handled": True},
        events=(event,),
    )

    serialized = result.to_dict()
    serialized["events"][0]["payload"]["nested"][0]["value"] = 99
    serialized["events"].append({"event_id": "invented"})

    fresh = result.to_dict()
    assert fresh["events"] == [event.to_dict()]
    assert fresh["events"][0]["payload"]["nested"][0]["value"] == 1
    assert json.loads(json.dumps(fresh, allow_nan=False)) == fresh


@pytest.mark.parametrize(
    "collection_factory",
    [
        lambda event: None,
        lambda event: {"first": event},
        lambda event: iter((event,)),
    ],
    ids=["none", "mapping", "one-shot-iterator"],
)
def test_structurally_invalid_event_collection_is_controlled(
    collection_factory,
):
    command = make_command()
    event = make_event(command)
    engine = engine_with_handler(
        lambda received: GameResult.success(
            received.command_id,
            events=collection_factory(event),
        )
    )

    assert_controlled_invalid_handler_result(engine.dispatch(command), command)


def test_non_game_event_value_is_a_controlled_invalid_handler_result():
    command = make_command()
    engine = engine_with_handler(
        lambda received: GameResult.success(
            received.command_id,
            events=({"event_id": "not-an-event"},),
        )
    )

    assert_controlled_invalid_handler_result(engine.dispatch(command), command)


def test_structurally_corrupted_game_event_is_revalidated_by_engine():
    command = make_command()
    event = make_event(command)
    expected = GameResult.success(command.command_id, events=(event,))
    object.__setattr__(event, "event_type", " ")
    engine = engine_with_handler(lambda received: expected)

    assert_controlled_invalid_handler_result(engine.dispatch(command), command)


def test_mismatched_event_command_linkage_is_not_repaired():
    command = make_command()
    event = make_event(
        command,
        originating_command_id="different-command-id",
    )
    engine = engine_with_handler(
        lambda received: GameResult.success(
            received.command_id,
            events=(event,),
        )
    )

    assert_controlled_invalid_handler_result(engine.dispatch(command), command)
    assert event.originating_command_id == "different-command-id"


def test_duplicate_event_ids_are_not_removed_or_replaced():
    command = make_command()
    first = make_event(command, 1)
    duplicate = make_event(command, 2, event_id=first.event_id)
    engine = engine_with_handler(
        lambda received: GameResult.success(
            received.command_id,
            events=(first, duplicate),
        )
    )

    assert_controlled_invalid_handler_result(engine.dispatch(command), command)
    assert first.event_id == duplicate.event_id


def test_failed_handler_result_cannot_carry_events():
    command = make_command()
    event = make_event(command)
    engine = engine_with_handler(
        lambda received: GameResult(
            command_id=received.command_id,
            status=GameResultStatus.HANDLER_FAILURE,
            error="Safe handler failure.",
            events=(event,),
        )
    )

    assert_controlled_invalid_handler_result(engine.dispatch(command), command)


def test_engine_generated_failures_always_have_no_events():
    unknown_command = make_command("command-events-unknown")
    unknown = GameEngine().dispatch(unknown_command)

    invalid_command = make_command("command-events-invalid")
    object.__setattr__(invalid_command, "command_type", " ")
    invalid = engine_with_handler(
        lambda received: GameResult.success(received.command_id)
    ).dispatch(invalid_command)

    wrong_type_command = make_command("command-events-wrong-type")
    wrong_type = engine_with_handler(
        lambda received: {"events": ["not-valid"]}
    ).dispatch(wrong_type_command)

    assert unknown.status is GameResultStatus.UNKNOWN_COMMAND
    assert invalid.status is GameResultStatus.INVALID_COMMAND
    assert wrong_type.status is GameResultStatus.INVALID_HANDLER_RESULT
    assert all(result.events == () for result in (unknown, invalid, wrong_type))


def test_handler_exception_does_not_leak_event_payload_text():
    command = make_command()

    def failing_handler(received):
        raise RuntimeError("private-event-payload-secret")

    result = engine_with_handler(failing_handler).dispatch(command)

    assert result.status is GameResultStatus.HANDLER_FAILURE
    assert result.events == ()
    assert "private-event-payload-secret" not in result.error
    assert "private-event-payload-secret" not in json.dumps(result.to_dict())


def test_domain_negative_success_remains_unchanged_and_may_have_no_events():
    command = make_command()
    expected = GameResult.success(
        command.command_id,
        {"success": False, "message": "Nothing changed."},
    )

    result = engine_with_handler(lambda received: expected).dispatch(command)

    assert result is expected
    assert result.status is GameResultStatus.SUCCESS
    assert result.output["success"] is False
    assert result.events == ()


@pytest.mark.parametrize(
    ("mode", "approval_outcome", "expected_status"),
    [
        (
            AutomationMode.REQUIRE_CONFIRMATION,
            None,
            PolicyGatedDispatchStatus.AWAITING_APPROVAL,
        ),
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
    ids=["awaiting", "human-denied", "suggested", "policy-denied"],
)
def test_policy_blocked_paths_never_invoke_event_producing_handler(
    mode,
    approval_outcome,
    expected_status,
):
    command = make_command()
    calls = []

    def handler(received):
        calls.append(received)
        return GameResult.success(
            received.command_id,
            events=(make_event(received),),
        )

    dispatcher = PolicyGatedCommandDispatcher(
        policy(mode),
        engine_with_handler(handler),
    )
    supplied_approval = (
        None
        if approval_outcome is None
        else approval(command, approval_outcome)
    )

    result = dispatcher.dispatch(command, supplied_approval)

    assert result.status is expected_status
    assert result.dispatch_attempted is False
    assert result.game_result is None
    assert calls == []


@pytest.mark.parametrize(
    "mode",
    [AutomationMode.AUTOMATIC, AutomationMode.REQUIRE_CONFIRMATION],
    ids=["automatic", "approved"],
)
def test_policy_dispatch_preserves_produced_events(mode):
    command = make_command()
    event = make_event(command)
    expected = GameResult.success(command.command_id, events=(event,))
    dispatcher = PolicyGatedCommandDispatcher(
        policy(mode),
        engine_with_handler(lambda received: expected),
    )
    supplied_approval = (
        None
        if mode is AutomationMode.AUTOMATIC
        else approval(command)
    )

    result = dispatcher.dispatch(command, supplied_approval)

    assert result.status is PolicyGatedDispatchStatus.DISPATCHED
    assert result.game_result is expected
    assert result.game_result.events == (event,)


def test_duplicate_dispatch_does_not_invoke_handler_or_produce_events_again():
    command = make_command()
    calls = []
    event = make_event(command)

    def handler(received):
        calls.append(received)
        return GameResult.success(received.command_id, events=(event,))

    dispatcher = PolicyGatedCommandDispatcher(
        policy(AutomationMode.AUTOMATIC),
        engine_with_handler(handler),
    )

    first = dispatcher.dispatch(command)
    duplicate = dispatcher.dispatch(command)

    assert first.game_result.events == (event,)
    assert duplicate.status is PolicyGatedDispatchStatus.DUPLICATE
    assert duplicate.game_result is None
    assert calls == [command]


def test_audited_pipeline_preserves_events_and_sanitizes_audit_details():
    command = make_command()
    secret = "private-event-payload-secret"
    event = make_event(command, payload={"secret": secret})
    expected = GameResult.success(command.command_id, events=(event,))
    pipeline, _, audit_journal = audited_pipeline(
        lambda received: expected
    )

    result = pipeline.dispatch(command)

    assert result.audit_status is AuditIntegrationStatus.COMPLETED
    assert result.policy_gated_result.game_result is expected
    assert result.policy_gated_result.game_result.events == (event,)
    assert result.publication_disposition is (
        EventPublicationDisposition.PUBLISHED
    )
    assert tuple(
        entry.event for entry in result.published_event_entries
    ) == (event,)
    assert secret not in json.dumps(audit_journal.to_list())

    serialized = result.to_dict()
    serialized["policy_gated_result"]["game_result"]["events"][0][
        "payload"
    ]["secret"] = "changed"
    assert (
        result.to_dict()["policy_gated_result"]["game_result"]["events"][0][
            "payload"
        ]["secret"]
        == secret
    )


def test_post_dispatch_audit_failure_preserves_original_events():
    command = make_command()
    event = make_event(command)
    expected = GameResult.success(command.command_id, events=(event,))
    journal = FailingAuditJournal(fail_on_append=5)
    event_journal = GameEventJournal()
    pipeline, dispatcher, _ = audited_pipeline(
        lambda received: expected,
        journal=journal,
        event_journal=event_journal,
    )

    result = pipeline.dispatch(command)

    assert result.audit_status is (
        AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE
    )
    assert result.policy_gated_result.game_result is expected
    assert result.policy_gated_result.game_result.events == (event,)
    assert result.publication_disposition is (
        EventPublicationDisposition.PUBLISHED
    )
    assert tuple(entry.event for entry in event_journal.entries) == (event,)
    assert dispatcher.dispatch_attempted_command_ids == (command.command_id,)


def test_event_producing_audited_dispatch_appends_one_atomic_batch():
    command = make_command()
    event = make_event(command)
    event_journal = GameEventJournal()
    pipeline, _, _ = audited_pipeline(
        lambda received: GameResult.success(
            received.command_id,
            events=(event,),
        ),
        event_journal=event_journal,
    )

    result = pipeline.dispatch(command)

    assert result.audit_status is AuditIntegrationStatus.COMPLETED
    assert result.policy_gated_result.game_result.events == (event,)
    assert result.publication_disposition is (
        EventPublicationDisposition.PUBLISHED
    )
    assert result.published_event_entries == event_journal.entries
    assert tuple(entry.event for entry in event_journal.entries) == (event,)
