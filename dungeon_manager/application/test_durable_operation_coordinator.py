from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from dungeon_manager.adapters.sqlite_durable_operations import (
    SQLiteDurableOperationStore,
)

from .contracts import (
    AuthorityReference,
    ContractVersion,
    DurableCommitState,
    IdentityKind,
    LocalPublicationState,
    MechanicalState,
    OperationView,
    ProjectionState,
    SelectPlayerCharacterRequest,
    SequencedEventReference,
    SubmissionState,
    SynchronizationState,
)
from .controlled_fixture import ControlledFixtureFacade
from .durable_operation import DurableOperationCoordinator
from .durable_operation_contracts import (
    CampaignOperationKey,
    CanonicalOperationIdentity,
    DurableOperationContractVersion,
    DurableOperationKind,
    DurableOperationLifecycle,
    DurableReplayDisposition,
    DurableStoreDisposition,
)
from .permission_contracts import (
    ActorReference,
    CampaignReference,
    ParticipantReference,
)


TIME = datetime(2026, 7, 30, 14, 0, tzinfo=timezone.utc)
PARTICIPANT = ParticipantReference("player-1")
CAMPAIGN = CampaignReference("vertical-slice-v1")
ACTOR = ActorReference("nekria")


def reference(kind, value):
    return AuthorityReference(kind, value)


def request(slug="one"):
    return SelectPlayerCharacterRequest(
        ContractVersion.V1,
        reference(IdentityKind.CALLER_OPERATION, f"operation-{slug}"),
        reference(IdentityKind.COMMAND, f"command-{slug}"),
        reference(IdentityKind.EVENT, f"event-{slug}"),
        reference(IdentityKind.ACTOR, "nekria"),
        TIME,
    )


def operation_view(value, *, stage="committed"):
    if stage == "rejected":
        return OperationView(
            value.version,
            value.operation,
            value.command,
            SubmissionState.REJECTED,
            MechanicalState.NOT_ATTEMPTED,
            DurableCommitState.NOT_APPLICABLE,
            LocalPublicationState.NOT_APPLICABLE,
            ProjectionState.NOT_APPLICABLE,
            SynchronizationState.SYNCHRONIZED,
        )
    if stage == "input_required":
        return OperationView(
            value.version,
            value.operation,
            value.command,
            SubmissionState.ACCEPTED,
            MechanicalState.INPUT_REQUIRED,
            DurableCommitState.NOT_APPLICABLE,
            LocalPublicationState.NOT_APPLICABLE,
            ProjectionState.NOT_APPLICABLE,
            SynchronizationState.SYNCHRONIZED,
        )
    if stage == "failed":
        return OperationView(
            value.version,
            value.operation,
            value.command,
            SubmissionState.ACCEPTED,
            MechanicalState.FAILED,
            DurableCommitState.NOT_APPLICABLE,
            LocalPublicationState.NOT_APPLICABLE,
            ProjectionState.NOT_APPLICABLE,
            SynchronizationState.SYNCHRONIZED,
        )
    if stage == "eventless":
        return OperationView(
            value.version,
            value.operation,
            value.command,
            SubmissionState.ACCEPTED,
            MechanicalState.SUCCEEDED,
            DurableCommitState.NOT_APPLICABLE,
            LocalPublicationState.NOT_APPLICABLE,
            ProjectionState.NOT_APPLICABLE,
            SynchronizationState.SYNCHRONIZED,
            mechanical_details={"outcome": "already_selected"},
        )
    event = SequencedEventReference(
        reference(IdentityKind.EVENT, value.event.value), 1
    )
    return OperationView(
        value.version,
        value.operation,
        value.command,
        SubmissionState.ACCEPTED,
        MechanicalState.SUCCEEDED,
        DurableCommitState.COMMITTED,
        LocalPublicationState.PUBLISHED,
        ProjectionState.PROJECTED,
        SynchronizationState.SYNCHRONIZED,
        events=(event,),
        mechanical_details={"outcome": "selected"},
    )


class FakeAuthority:
    transient_presentation_available = False

    def __init__(self, stage="committed"):
        self.stage = stage
        self.select_calls = 0
        self.reconstruct_calls = 0

    def inspect(self):
        raise AssertionError("Inspection is outside this test.")

    def select_player_character(self, value):
        self.select_calls += 1
        return operation_view(value, stage=self.stage)

    def resolve_controlled_round(self, value):
        raise AssertionError("Round is outside this test.")

    def reconstruct_operation(self, value):
        self.reconstruct_calls += 1
        correlated = request("one")
        correlated = replace(
            correlated,
            operation=value.operation,
            command=value.command,
        )
        return operation_view(correlated)


def coordinator(path, authority):
    return DurableOperationCoordinator(
        ControlledFixtureFacade(authority),
        SQLiteDurableOperationStore(path),
    )


def canonical(value):
    key = CampaignOperationKey(
        DurableOperationContractVersion.V1,
        CAMPAIGN.value,
        value.operation.value,
    )
    return CanonicalOperationIdentity(
        DurableOperationContractVersion.V1,
        key,
        PARTICIPANT.value,
        DurableOperationKind.SELECT_PLAYER_CHARACTER,
        value.version.value,
        ACTOR.value,
        value.to_dict(),
    )


@pytest.mark.parametrize(
    "stage", ("rejected", "input_required", "committed", "failed", "eventless")
)
def test_every_m1_terminal_stage_is_recorded_and_exact_retry_delegates_zero_times(
    tmp_path, stage
):
    authority = FakeAuthority(stage)
    durable = coordinator(tmp_path / f"{stage}.sqlite", authority)
    value = request(stage)

    first = durable.select_player_character(
        PARTICIPANT, CAMPAIGN, ACTOR, value
    )
    second = durable.select_player_character(
        PARTICIPANT, CAMPAIGN, ACTOR, value
    )

    assert first.disposition is DurableReplayDisposition.DELEGATED
    assert second.disposition is DurableReplayDisposition.REPLAYED
    assert first.terminal_outcome == second.terminal_outcome
    assert authority.select_calls == 1
    assert authority.reconstruct_calls == 0


def test_same_key_different_request_is_a_persistent_collision(tmp_path):
    path = tmp_path / "operations.sqlite"
    authority = FakeAuthority()
    first = request("one")
    durable = coordinator(path, authority)
    assert durable.select_player_character(
        PARTICIPANT, CAMPAIGN, ACTOR, first
    ).disposition is DurableReplayDisposition.DELEGATED

    changed = replace(
        first, command=reference(IdentityKind.COMMAND, "different-command")
    )
    restarted_authority = FakeAuthority()
    result = coordinator(path, restarted_authority).select_player_character(
        PARTICIPANT, CAMPAIGN, ACTOR, changed
    )

    assert result.disposition is DurableReplayDisposition.COLLISION
    assert result.terminal_outcome is None
    assert restarted_authority.select_calls == 0
    assert restarted_authority.reconstruct_calls == 0


def test_dispatch_started_without_event_proof_is_persistently_ambiguous(tmp_path):
    path = tmp_path / "operations.sqlite"
    value = request("one")
    store = SQLiteDurableOperationStore(path)
    identity = canonical(value)
    assert store.reserve(identity).disposition is DurableStoreDisposition.RESERVED
    assert (
        store.mark_dispatch_started(identity).disposition
        is DurableStoreDisposition.SUCCESS
    )
    authority = FakeAuthority("eventless")
    authority.reconstruct_operation = lambda correlation: operation_view(
        value, stage="eventless"
    )

    result = coordinator(path, authority).select_player_character(
        PARTICIPANT, CAMPAIGN, ACTOR, value
    )
    restarted = coordinator(path, authority).select_player_character(
        PARTICIPANT, CAMPAIGN, ACTOR, value
    )

    assert result.disposition is DurableReplayDisposition.RECOVERY_REQUIRED
    assert restarted.disposition is DurableReplayDisposition.RECOVERY_REQUIRED
    assert authority.select_calls == 0


def test_dispatch_started_with_durable_event_proof_reconstructs_without_dispatch(
    tmp_path,
):
    path = tmp_path / "operations.sqlite"
    value = request("one")
    store = SQLiteDurableOperationStore(path)
    identity = canonical(value)
    store.reserve(identity)
    store.mark_dispatch_started(identity)
    authority = FakeAuthority()

    first = coordinator(path, authority).select_player_character(
        PARTICIPANT, CAMPAIGN, ACTOR, value
    )
    second = coordinator(path, authority).select_player_character(
        PARTICIPANT, CAMPAIGN, ACTOR, value
    )

    assert first.disposition is DurableReplayDisposition.REPLAYED
    assert second.disposition is DurableReplayDisposition.REPLAYED
    assert authority.select_calls == 0
    assert authority.reconstruct_calls == 1
