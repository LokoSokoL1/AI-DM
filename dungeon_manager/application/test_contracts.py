import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from .contracts import (
    AuthorityReference,
    CapabilityDescriptor,
    CapabilityKey,
    CapabilityReason,
    CapabilityStatus,
    ClientDiagnostic,
    ClientDiceMode,
    ContractVersion,
    ControlledFixtureView,
    DiagnosticCode,
    DurableCommitState,
    IdentityKind,
    LocalPublicationState,
    MechanicalState,
    OperationCorrelationRequest,
    OperationView,
    PresentationState,
    ProjectionState,
    ResolveControlledRoundRequest,
    SelectPlayerCharacterRequest,
    SequencedEventReference,
    SubmissionState,
    SynchronizationState,
    TransientPresentation,
)


TIME = datetime(2026, 7, 29, 15, 0, 0, 123456, timezone.utc)
STAGES = ("nekria_initiative", "goblin_initiative", "attack", "damage")


def ref(kind, value):
    return AuthorityReference(kind, value)


def operation_ref(value="operation-1"):
    return ref(IdentityKind.CALLER_OPERATION, value)


def command_ref(value="command-1"):
    return ref(IdentityKind.COMMAND, value)


def event_ref(value="event-1", sequence=1):
    return SequencedEventReference(ref(IdentityKind.EVENT, value), sequence)


def selection_request():
    return SelectPlayerCharacterRequest(
        ContractVersion.V1,
        operation_ref(),
        command_ref(),
        ref(IdentityKind.EVENT, "event-1"),
        ref(IdentityKind.ACTOR, "nekria"),
        TIME,
    )


def round_request(*, mode=ClientDiceMode.MANUAL, faces=None):
    return ResolveControlledRoundRequest(
        ContractVersion.V1,
        operation_ref("round-operation"),
        command_ref("round-command"),
        ref(IdentityKind.EVENT, "round-event"),
        TIME,
        mode,
        {stage: f"{stage}-roll" for stage in STAGES},
        (
            {stage: None for stage in STAGES}
            if faces is None
            else faces
        ),
    )


def test_authority_references_are_typed_immutable_equal_and_deterministic():
    first = ref(IdentityKind.CAMPAIGN, "vertical-slice-v1")
    second = ref(IdentityKind.CAMPAIGN, "vertical-slice-v1")

    assert first == second
    assert first.to_dict() == {
        "kind": "campaign",
        "value": "vertical-slice-v1",
    }
    assert first.to_json() == (
        '{"kind":"campaign","value":"vertical-slice-v1"}'
    )
    with pytest.raises(FrozenInstanceError):
        first.value = "other"
    with pytest.raises(ValueError, match="kind"):
        AuthorityReference("campaign", "vertical-slice-v1")
    with pytest.raises(ValueError, match="safe"):
        ref(IdentityKind.CAMPAIGN, " padded ")


def test_sequenced_event_reference_validates_kind_sequence_and_serialization():
    reference = event_ref()

    assert reference == event_ref()
    assert json.loads(reference.to_json()) == reference.to_dict()
    with pytest.raises(ValueError, match="event ID"):
        SequencedEventReference(command_ref(), 1)
    with pytest.raises(ValueError, match="positive"):
        SequencedEventReference(ref(IdentityKind.EVENT, "event"), 0)


def test_client_diagnostics_are_closed_fixed_messages_without_detail_channel():
    diagnostic = ClientDiagnostic(DiagnosticCode.INTERNAL_FAILURE)

    assert diagnostic.to_dict() == {
        "code": "internal_failure",
        "message": (
            "The client-neutral operation failed without exposing internal details."
        ),
    }
    assert "exception" not in diagnostic.to_json().lower()
    with pytest.raises(TypeError):
        ClientDiagnostic(
            DiagnosticCode.INTERNAL_FAILURE,
            "C:\\secret\\journal.sqlite",
        )
    with pytest.raises(ValueError, match="typed"):
        ClientDiagnostic("internal_failure")


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (CapabilityStatus.SUPPORTED, None),
        (
            CapabilityStatus.UNSUPPORTED,
            CapabilityReason.CONTROLLED_FIXTURE_HAS_NO_GOBLIN_ACTION,
        ),
        (
            CapabilityStatus.UNAVAILABLE,
            CapabilityReason.PLAYER_SELECTION_REQUIRED,
        ),
    ],
)
def test_capability_descriptor_explicit_states_are_typed_and_serializable(
    status, reason
):
    descriptor = CapabilityDescriptor(
        ContractVersion.V1,
        CapabilityKey.RESOLVE_CONTROLLED_ROUND,
        status,
        reason,
    )

    assert json.loads(descriptor.to_json()) == descriptor.to_dict()
    assert descriptor == CapabilityDescriptor(
        ContractVersion.V1,
        CapabilityKey.RESOLVE_CONTROLLED_ROUND,
        status,
        reason,
    )


def test_capability_descriptor_rejects_unknown_or_conflated_states():
    with pytest.raises(ValueError, match="version"):
        CapabilityDescriptor(
            "phase2-m1-v1",
            CapabilityKey.INSPECT_CONTROLLED_FIXTURE,
            CapabilityStatus.SUPPORTED,
        )
    with pytest.raises(ValueError, match="reason"):
        CapabilityDescriptor(
            ContractVersion.V1,
            CapabilityKey.INSPECT_CONTROLLED_FIXTURE,
            CapabilityStatus.UNAVAILABLE,
        )
    with pytest.raises(ValueError, match="cannot contain"):
        CapabilityDescriptor(
            ContractVersion.V1,
            CapabilityKey.INSPECT_CONTROLLED_FIXTURE,
            CapabilityStatus.SUPPORTED,
            CapabilityReason.PLAYER_SELECTION_REQUIRED,
        )


def test_transient_presentation_is_source_bound_immutable_and_validated():
    presentation = TransientPresentation("A verified result.", event_ref())

    assert json.loads(presentation.to_json()) == presentation.to_dict()
    with pytest.raises(FrozenInstanceError):
        presentation.text = "changed"
    with pytest.raises(ValueError, match="text"):
        TransientPresentation(" ", event_ref())


def test_controlled_fixture_view_defensively_copies_and_validates_identity_sets():
    actors = [
        ref(IdentityKind.ACTOR, "nekria"),
        ref(IdentityKind.ACTOR, "goblin-1"),
    ]
    events = [event_ref()]
    view = ControlledFixtureView(
        ContractVersion.V1,
        ref(IdentityKind.CAMPAIGN, "vertical-slice-v1"),
        ref(IdentityKind.SCENE, "controlled-goblin-encounter"),
        actors,
        [actors[0]],
        actors[0],
        events,
        1,
        1,
        SynchronizationState.SYNCHRONIZED,
        False,
    )
    actors.append(ref(IdentityKind.ACTOR, "invented"))
    events.clear()

    assert tuple(item.value for item in view.actors) == ("nekria", "goblin-1")
    assert view.events == (event_ref(),)
    assert json.loads(view.to_json()) == view.to_dict()
    with pytest.raises(ValueError, match="Selectable"):
        ControlledFixtureView(
            ContractVersion.V1,
            ref(IdentityKind.CAMPAIGN, "campaign"),
            ref(IdentityKind.SCENE, "scene"),
            [ref(IdentityKind.ACTOR, "actor")],
            [ref(IdentityKind.ACTOR, "missing")],
            None,
            (),
            0,
            0,
            SynchronizationState.SYNCHRONIZED,
            False,
        )


def test_selection_request_keeps_operation_command_event_and_actor_separate():
    request = selection_request()

    assert request.operation.kind is IdentityKind.CALLER_OPERATION
    assert request.command.kind is IdentityKind.COMMAND
    assert request.event.kind is IdentityKind.EVENT
    assert request.actor.kind is IdentityKind.ACTOR
    assert len(
        {
            request.operation.value,
            request.command.value,
            request.event.value,
            request.actor.value,
        }
    ) == 4
    assert json.loads(request.to_json()) == request.to_dict()
    shifted = SelectPlayerCharacterRequest(
        request.version,
        request.operation,
        request.command,
        request.event,
        request.actor,
        TIME.astimezone(timezone(timedelta(hours=2))),
    )
    assert shifted == request


def test_selection_request_rejects_identity_kind_conflation():
    with pytest.raises(ValueError, match="operation"):
        SelectPlayerCharacterRequest(
            ContractVersion.V1,
            command_ref(),
            command_ref(),
            ref(IdentityKind.EVENT, "event"),
            ref(IdentityKind.ACTOR, "nekria"),
            TIME,
        )


def test_round_request_is_defensive_deterministic_and_cannot_inject_auto_faces():
    roll_ids = {stage: f"{stage}-id" for stage in STAGES}
    faces = {
        "nekria_initiative": 12,
        "goblin_initiative": None,
        "attack": None,
        "damage": None,
    }
    request = ResolveControlledRoundRequest(
        ContractVersion.V1,
        operation_ref("round-op"),
        command_ref("round-command"),
        ref(IdentityKind.EVENT, "round-event"),
        TIME,
        ClientDiceMode.MANUAL,
        roll_ids,
        faces,
    )
    roll_ids["attack"] = "changed"
    faces["nekria_initiative"] = 1

    assert request.roll_ids["attack"] == "attack-id"
    assert request.manual_faces["nekria_initiative"] == 12
    with pytest.raises(TypeError):
        request.roll_ids["attack"] = "changed"
    assert json.loads(request.to_json()) == request.to_dict()
    with pytest.raises(ValueError, match="cannot inject"):
        round_request(
            mode=ClientDiceMode.AUTOMATIC,
            faces={stage: 1 for stage in STAGES},
        )


def test_operation_correlation_request_is_a_non_authorizing_value():
    request = OperationCorrelationRequest(
        ContractVersion.V1, operation_ref(), command_ref()
    )

    assert request.to_dict()["operation"]["kind"] == "caller_operation"
    assert request.to_dict()["command"]["kind"] == "command"
    assert json.loads(request.to_json()) == request.to_dict()


def operation_view(**overrides):
    values = {
        "version": ContractVersion.V1,
        "operation": operation_ref(),
        "command": command_ref(),
        "submission": SubmissionState.ACCEPTED,
        "mechanics": MechanicalState.SUCCEEDED,
        "durable_commit": DurableCommitState.COMMITTED,
        "local_publication": LocalPublicationState.PUBLISHED,
        "projection": ProjectionState.PROJECTED,
        "synchronization": SynchronizationState.SYNCHRONIZED,
        "events": (event_ref(),),
        "mechanical_details": {"outcome": "resolved", "faces": [12, 4]},
    }
    values.update(overrides)
    return OperationView(**values)


@pytest.mark.parametrize(
    "view",
    [
        operation_view(),
        operation_view(
            submission=SubmissionState.REJECTED,
            mechanics=MechanicalState.NOT_ATTEMPTED,
            durable_commit=DurableCommitState.NOT_APPLICABLE,
            local_publication=LocalPublicationState.NOT_APPLICABLE,
            projection=ProjectionState.NOT_APPLICABLE,
            synchronization=SynchronizationState.SYNCHRONIZED,
            events=(),
            mechanical_details={},
            diagnostic=ClientDiagnostic(DiagnosticCode.SUBMISSION_REJECTED),
        ),
        operation_view(
            mechanics=MechanicalState.INPUT_REQUIRED,
            durable_commit=DurableCommitState.NOT_APPLICABLE,
            local_publication=LocalPublicationState.NOT_APPLICABLE,
            projection=ProjectionState.NOT_APPLICABLE,
            events=(),
            mechanical_details={"outcome": "attack_input_required"},
        ),
        operation_view(
            mechanics=MechanicalState.FAILED,
            durable_commit=DurableCommitState.NOT_APPLICABLE,
            local_publication=LocalPublicationState.NOT_APPLICABLE,
            projection=ProjectionState.NOT_APPLICABLE,
            events=(),
            mechanical_details={},
            diagnostic=ClientDiagnostic(DiagnosticCode.MECHANICAL_FAILURE),
        ),
        operation_view(
            local_publication=LocalPublicationState.NOT_PUBLISHED,
            projection=ProjectionState.NOT_PROJECTED,
            synchronization=SynchronizationState.OUT_OF_SYNC,
            diagnostic=ClientDiagnostic(
                DiagnosticCode.LOCAL_PUBLICATION_FAILURE
            ),
        ),
        operation_view(
            projection=ProjectionState.NOT_PROJECTED,
            synchronization=SynchronizationState.OUT_OF_SYNC,
            diagnostic=ClientDiagnostic(
                DiagnosticCode.SYNCHRONIZATION_FAILURE
            ),
        ),
        operation_view(
            synchronization=SynchronizationState.OUT_OF_SYNC,
            diagnostic=ClientDiagnostic(
                DiagnosticCode.SYNCHRONIZATION_FAILURE
            ),
        ),
        operation_view(
            presentation_status=PresentationState.FAILED,
            diagnostic=ClientDiagnostic(DiagnosticCode.PRESENTATION_FAILURE),
        ),
        operation_view(
            presentation_status=PresentationState.SUCCEEDED,
            presentation=TransientPresentation("Resolved.", event_ref()),
        ),
    ],
    ids=[
        "synchronized",
        "rejected",
        "input-required",
        "mechanical-failed",
        "durable-only",
        "locally-published",
        "projected",
        "presentation-failed",
        "presentation-succeeded",
    ],
)
def test_operation_view_keeps_every_authority_stage_distinct(view):
    serialized = view.to_dict()

    assert json.loads(view.to_json()) == serialized
    assert set(serialized) == {
        "command",
        "diagnostic",
        "durable_commit",
        "events",
        "local_publication",
        "mechanical_details",
        "mechanics",
        "operation",
        "presentation",
        "presentation_status",
        "projection",
        "submission",
        "synchronization",
        "version",
    }


def test_operation_view_defensively_copies_mechanical_details_and_is_equal():
    details = {"rolls": [{"face": 12}]}
    first = operation_view(mechanical_details=details)
    details["rolls"][0]["face"] = 1
    second = operation_view(mechanical_details={"rolls": [{"face": 12}]})

    assert first == second
    assert first.mechanical_details["rolls"][0]["face"] == 12
    with pytest.raises(TypeError):
        first.mechanical_details["rolls"][0]["face"] = 1


def test_operation_view_rejects_status_conflation():
    with pytest.raises(ValueError, match="submission state"):
        operation_view(submission="accepted")
    with pytest.raises(ValueError, match="Rejected"):
        operation_view(submission=SubmissionState.REJECTED)
    with pytest.raises(ValueError, match="Local publication"):
        operation_view(durable_commit=DurableCommitState.NOT_COMMITTED)
    with pytest.raises(ValueError, match="Projection"):
        operation_view(
            local_publication=LocalPublicationState.NOT_PUBLISHED
        )
    with pytest.raises(ValueError, match="Successful presentation"):
        operation_view(
            presentation_status=PresentationState.SUCCEEDED,
            presentation=None,
        )
