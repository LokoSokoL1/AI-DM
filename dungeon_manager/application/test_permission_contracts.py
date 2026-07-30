import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from .permission_contracts import (
    ActorAssignment,
    ActorControlDisposition,
    ActorReference,
    AudienceScopedEntry,
    BaseRole,
    CampaignReference,
    GrantCapability,
    GrantReference,
    GrantState,
    IdentityState,
    ParticipantReference,
    PermissionCapability,
    PermissionContractVersion,
    PermissionDecision,
    PermissionGrant,
    PermissionReason,
    PermissionRequest,
    PermissionedView,
    PermissionedViewKind,
    PerspectiveKind,
    SessionIdentity,
    SessionReference,
    SpeakerMode,
    SpeakerSelection,
    ViewingPerspective,
    VisibilityAudience,
    VisibilityAudienceKind,
    VisibilityEntryKey,
    VisibleEntry,
)


TIME = datetime(2026, 7, 30, 10, 0, 0, 123456, timezone.utc)


def participant(value="player-1"):
    return ParticipantReference(value)


def campaign():
    return CampaignReference("vertical-slice-v1")


def actor(value="nekria"):
    return ActorReference(value)


def player_request():
    return PermissionRequest(
        PermissionContractVersion.V1,
        SessionReference("session-player-1"),
        campaign(),
        PermissionCapability.RESOLVE_CONTROLLED_ROUND,
        SpeakerSelection(SpeakerMode.ACTOR, actor()),
        ViewingPerspective(PerspectiveKind.PARTICIPANT, participant()),
        actor(),
    )


def test_reference_types_are_distinct_immutable_equal_and_deterministic():
    references = (
        SessionReference("session-1"),
        ParticipantReference("participant-1"),
        CampaignReference("campaign-1"),
        ActorReference("actor-1"),
        GrantReference("grant-1"),
    )

    assert [item.to_dict() for item in references] == [
        {"value": "session-1"},
        {"value": "participant-1"},
        {"value": "campaign-1"},
        {"value": "actor-1"},
        {"value": "grant-1"},
    ]
    assert all(json.loads(item.to_json()) == item.to_dict() for item in references)
    assert SessionReference("same") != ParticipantReference("same")
    with pytest.raises(FrozenInstanceError):
        references[0].value = "changed"
    with pytest.raises(ValueError, match="safe"):
        ActorReference(" padded ")


def test_session_identity_is_typed_immutable_and_canonicalizes_expiry():
    shifted = TIME.astimezone(timezone(timedelta(hours=2)))
    identity = SessionIdentity(
        SessionReference("session-player-1"),
        participant(),
        BaseRole.PLAYER,
        IdentityState.ACTIVE,
        shifted,
    )

    assert identity.expires_at == TIME
    assert identity.to_dict()["expires_at"] == "2026-07-30T10:00:00.123456Z"
    assert json.loads(identity.to_json()) == identity.to_dict()
    with pytest.raises(ValueError, match="role"):
        SessionIdentity(
            SessionReference("session"),
            participant(),
            "player",
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        SessionIdentity(
            SessionReference("session"),
            participant(),
            BaseRole.PLAYER,
            expires_at=datetime(2026, 7, 30),
        )


def test_speaker_actor_and_viewing_perspective_are_separate_contracts():
    speaker = SpeakerSelection(SpeakerMode.ACTOR, actor())
    perspective = ViewingPerspective(
        PerspectiveKind.PARTICIPANT, participant()
    )

    assert speaker.to_dict() == {
        "actor": {"value": "nekria"},
        "mode": "actor",
    }
    assert perspective.to_dict() == {
        "kind": "participant",
        "participant": {"value": "player-1"},
    }
    with pytest.raises(ValueError, match="requires an actor"):
        SpeakerSelection(SpeakerMode.ACTOR)
    with pytest.raises(ValueError, match="cannot carry"):
        SpeakerSelection(SpeakerMode.OOC, actor())
    with pytest.raises(ValueError, match="requires a participant"):
        ViewingPerspective(PerspectiveKind.PARTICIPANT)
    with pytest.raises(ValueError, match="cannot carry"):
        ViewingPerspective(PerspectiveKind.DM, participant())


def test_assignment_and_grants_keep_scope_capability_state_and_expiry_distinct():
    assignment = ActorAssignment(participant(), campaign(), actor())
    speak = PermissionGrant(
        GrantReference("grant-speak"),
        participant(),
        campaign(),
        actor("goblin-1"),
        GrantCapability.SPEAK_AS,
    )
    act = PermissionGrant(
        GrantReference("grant-act"),
        participant(),
        campaign(),
        actor("goblin-1"),
        GrantCapability.ACT_AS,
        GrantState.REVOKED,
        TIME,
    )

    assert assignment.to_dict()["actor"] == {"value": "nekria"}
    assert speak.capability is GrantCapability.SPEAK_AS
    assert act.capability is GrantCapability.ACT_AS
    assert act.state is GrantState.REVOKED
    assert act.to_dict()["expires_at"] == "2026-07-30T10:00:00.123456Z"
    assert speak != act
    assert json.loads(act.to_json()) == act.to_dict()


def test_permission_request_keeps_all_authority_concepts_separate():
    request = player_request()

    serialized = request.to_dict()
    assert serialized["session"] == {"value": "session-player-1"}
    assert serialized["campaign"] == {"value": "vertical-slice-v1"}
    assert serialized["capability"] == (
        "controlled_fixture.resolve_controlled_round"
    )
    assert serialized["speaker"]["mode"] == "actor"
    assert serialized["actor"] == {"value": "nekria"}
    assert serialized["perspective"]["participant"] == {"value": "player-1"}
    assert json.loads(request.to_json()) == serialized
    with pytest.raises(ValueError, match="version"):
        PermissionRequest(
            "phase2-m2-v1",
            request.session,
            request.campaign,
            request.capability,
            request.speaker,
            request.perspective,
            request.actor,
        )


def test_permission_decision_is_bounded_and_cannot_conflate_denial_with_control():
    allowed = PermissionDecision(
        PermissionContractVersion.V1,
        True,
        PermissionReason.ALLOWED,
        ActorControlDisposition.DIRECT_CONTROL,
    )
    denied = PermissionDecision(
        PermissionContractVersion.V1,
        False,
        PermissionReason.ASSIGNMENT_OR_GRANT_REQUIRED,
    )

    assert allowed.to_dict()["actor_control"] == "direct_control"
    assert denied.to_dict()["reason"] == "assignment_or_grant_required"
    with pytest.raises(ValueError, match="differ"):
        PermissionDecision(
            PermissionContractVersion.V1,
            True,
            PermissionReason.CAPABILITY_DENIED,
        )
    with pytest.raises(ValueError, match="cannot claim"):
        PermissionDecision(
            PermissionContractVersion.V1,
            False,
            PermissionReason.CAPABILITY_DENIED,
            ActorControlDisposition.DIRECT_CONTROL,
        )


def test_visibility_audience_defensively_copies_and_sorts_participants():
    participants = [participant("player-2"), participant("player-1")]
    audience = VisibilityAudience(
        VisibilityAudienceKind.PARTICIPANTS, participants
    )
    participants.clear()

    assert tuple(item.value for item in audience.participants) == (
        "player-1",
        "player-2",
    )
    assert json.loads(audience.to_json()) == audience.to_dict()
    with pytest.raises(ValueError, match="at least one"):
        VisibilityAudience(VisibilityAudienceKind.PARTICIPANTS)
    with pytest.raises(ValueError, match="Only participant"):
        VisibilityAudience(
            VisibilityAudienceKind.PUBLIC, (participant(),)
        )


def test_visibility_entries_are_immutable_defensive_and_hide_audience_after_filter():
    payload = {"facts": [{"event": "event-1"}]}
    scoped = AudienceScopedEntry(
        VisibilityEntryKey.RECONSTRUCTION_OPERATION,
        VisibilityAudience(VisibilityAudienceKind.PUBLIC),
        payload,
    )
    payload["facts"][0]["event"] = "changed"
    visible = VisibleEntry(scoped.key, scoped.payload)

    assert scoped.payload["facts"][0]["event"] == "event-1"
    assert "audience" in scoped.to_dict()
    assert "audience" not in visible.to_dict()
    with pytest.raises(TypeError):
        scoped.payload["facts"][0]["event"] = "changed"
    assert json.loads(visible.to_json()) == visible.to_dict()


def test_permissioned_view_never_discloses_entries_on_denial():
    denied = PermissionDecision(
        PermissionContractVersion.V1,
        False,
        PermissionReason.IDENTITY_UNRESOLVED,
    )
    entry = VisibleEntry(
        VisibilityEntryKey.FIXTURE_INSPECTION,
        {"event": "hidden"},
    )

    view = PermissionedView(
        PermissionContractVersion.V1,
        PermissionedViewKind.INSPECTION,
        denied,
    )
    assert view.entries == ()
    assert json.loads(view.to_json()) == view.to_dict()
    with pytest.raises(ValueError, match="cannot disclose"):
        PermissionedView(
            PermissionContractVersion.V1,
            PermissionedViewKind.INSPECTION,
            denied,
            (entry,),
        )


def test_unknown_role_speaker_capability_grant_and_visibility_states_fail_closed():
    with pytest.raises(ValueError, match="role"):
        SessionIdentity(
            SessionReference("session"),
            participant(),
            "administrator",
        )
    with pytest.raises(ValueError, match="Speaker mode"):
        SpeakerSelection("dm")
    with pytest.raises(ValueError, match="capability"):
        PermissionGrant(
            GrantReference("grant"),
            participant(),
            campaign(),
            actor(),
            "act_as",
        )
    with pytest.raises(ValueError, match="state"):
        PermissionGrant(
            GrantReference("grant"),
            participant(),
            campaign(),
            actor(),
            GrantCapability.ACT_AS,
            "active",
        )
    with pytest.raises(ValueError, match="audience kind"):
        VisibilityAudience("public")
    with pytest.raises(ValueError, match="capability"):
        PermissionRequest(
            PermissionContractVersion.V1,
            SessionReference("session"),
            campaign(),
            "controlled_fixture.inspect",
            SpeakerSelection(SpeakerMode.OOC),
            ViewingPerspective(PerspectiveKind.PARTICIPANT, participant()),
        )
