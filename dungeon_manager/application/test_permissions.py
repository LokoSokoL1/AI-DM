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
    PermissionGrant,
    PermissionReason,
    PermissionRequest,
    PerspectiveKind,
    SessionIdentity,
    SessionReference,
    SpeakerMode,
    SpeakerSelection,
    ViewingPerspective,
    VisibilityAudience,
    VisibilityAudienceKind,
    VisibilityEntryKey,
)
from .permissions import evaluate_permission, filter_visible_entries


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
CAMPAIGN = CampaignReference("vertical-slice-v1")
NEKRIA = ActorReference("nekria")
GOBLIN = ActorReference("goblin-1")
PLAYER = ParticipantReference("player-1")
DM = ParticipantReference("dm-1")
PLAYER_SESSION = SessionReference("session-player-1")
DM_SESSION = SessionReference("session-dm-1")
_DEFAULT_IDENTITY = object()


def identity(
    *,
    participant=PLAYER,
    session=PLAYER_SESSION,
    role=BaseRole.PLAYER,
    state=IdentityState.ACTIVE,
    expires_at=None,
):
    return SessionIdentity(session, participant, role, state, expires_at)


def request(
    capability,
    *,
    session=PLAYER_SESSION,
    actor=NEKRIA,
    speaker=None,
    perspective=None,
):
    return PermissionRequest(
        PermissionContractVersion.V1,
        session,
        CAMPAIGN,
        capability,
        (
            SpeakerSelection(SpeakerMode.ACTOR, actor)
            if speaker is None
            else speaker
        ),
        (
            ViewingPerspective(PerspectiveKind.PARTICIPANT, PLAYER)
            if perspective is None
            else perspective
        ),
        actor,
    )


def assignment(actor=NEKRIA):
    return ActorAssignment(PLAYER, CAMPAIGN, actor)


def grant(
    capability,
    *,
    actor=GOBLIN,
    state=GrantState.ACTIVE,
    expires_at=None,
    slug="grant",
):
    return PermissionGrant(
        GrantReference(f"{slug}-{capability.value}"),
        PLAYER,
        CAMPAIGN,
        actor,
        capability,
        state,
        expires_at,
    )


def evaluate(
    permission_request,
    *,
    resolved=_DEFAULT_IDENTITY,
    assignments=(),
    grants=(),
    now=NOW,
):
    return evaluate_permission(
        identity() if resolved is _DEFAULT_IDENTITY else resolved,
        permission_request,
        tuple(assignments),
        tuple(grants),
        now,
    )


@pytest.mark.parametrize(
    ("resolved", "reason"),
    [
        (False, PermissionReason.IDENTITY_UNRESOLVED),
        (
            identity(state=IdentityState.REVOKED),
            PermissionReason.IDENTITY_REVOKED,
        ),
        (
            identity(expires_at=NOW),
            PermissionReason.IDENTITY_EXPIRED,
        ),
    ],
)
def test_unknown_revoked_and_expired_identity_fail_closed(resolved, reason):
    value = None if resolved is False else resolved
    decision = evaluate(
        request(PermissionCapability.INSPECT),
        resolved=value,
    )

    assert decision.allowed is False
    assert decision.reason is reason
    assert decision.actor_control is ActorControlDisposition.AI_DEFAULT


def test_forged_session_speaker_actor_and_perspective_never_create_authority():
    forged_session = request(
        PermissionCapability.ACT_AS,
        session=SessionReference("I-am-the-DM"),
        actor=GOBLIN,
        speaker=SpeakerSelection(SpeakerMode.DM),
        perspective=ViewingPerspective(PerspectiveKind.DM),
    )
    forged_labels = request(
        PermissionCapability.ACT_AS,
        actor=GOBLIN,
        speaker=SpeakerSelection(SpeakerMode.ACTOR, GOBLIN),
    )

    unresolved = evaluate_permission(None, forged_session, (), (), NOW)
    unassigned = evaluate(forged_labels)

    assert unresolved.reason is PermissionReason.IDENTITY_UNRESOLVED
    assert unassigned.reason is PermissionReason.ASSIGNMENT_OR_GRANT_REQUIRED
    assert unresolved.actor_control is ActorControlDisposition.AI_DEFAULT
    assert unassigned.actor_control is ActorControlDisposition.AI_DEFAULT


def test_assigned_player_character_authorizes_speak_and_act_independently():
    speak = evaluate(
        request(PermissionCapability.SPEAK_AS),
        assignments=(assignment(),),
    )
    act = evaluate(
        request(PermissionCapability.ACT_AS),
        assignments=(assignment(),),
    )

    assert speak.allowed is True
    assert speak.actor_control is ActorControlDisposition.AI_DEFAULT
    assert act.allowed is True
    assert act.actor_control is ActorControlDisposition.DIRECT_CONTROL


def test_ooc_is_non_authoritative_and_dm_mode_does_not_imply_actor_control():
    ooc = SpeakerSelection(SpeakerMode.OOC)
    dm_speaker = SpeakerSelection(SpeakerMode.DM)
    ooc_speech = evaluate(
        request(PermissionCapability.SPEAK_AS, actor=None, speaker=ooc)
    )
    ooc_action = evaluate(
        request(
            PermissionCapability.ACT_AS,
            speaker=ooc,
        ),
        assignments=(assignment(),),
    )
    dm_identity = identity(
        participant=DM,
        session=DM_SESSION,
        role=BaseRole.DM,
    )
    dm_action = evaluate(
        request(
            PermissionCapability.ACT_AS,
            session=DM_SESSION,
            actor=GOBLIN,
            speaker=dm_speaker,
            perspective=ViewingPerspective(PerspectiveKind.DM),
        ),
        resolved=dm_identity,
    )

    assert ooc_speech.allowed is True
    assert ooc_action.reason is PermissionReason.SPEAKER_NOT_ALLOWED
    assert dm_action.reason is PermissionReason.SPEAKER_NOT_ALLOWED


def test_dm_speaker_and_dm_perspective_require_the_resolved_dm_role():
    player_dm_mode = evaluate(
        request(
            PermissionCapability.INSPECT,
            actor=None,
            speaker=SpeakerSelection(SpeakerMode.DM),
            perspective=ViewingPerspective(PerspectiveKind.DM),
        )
    )
    dm_identity = identity(
        participant=DM,
        session=DM_SESSION,
        role=BaseRole.DM,
    )
    dm_request = request(
        PermissionCapability.INSPECT,
        session=DM_SESSION,
        actor=None,
        speaker=SpeakerSelection(SpeakerMode.DM),
        perspective=ViewingPerspective(PerspectiveKind.DM),
    )
    dm_allowed = evaluate(dm_request, resolved=dm_identity)

    assert player_dm_mode.allowed is False
    assert player_dm_mode.reason in {
        PermissionReason.PERSPECTIVE_NOT_ALLOWED,
        PermissionReason.ROLE_NOT_ALLOWED,
    }
    assert dm_allowed.allowed is True


def test_speak_as_and_act_as_grants_are_scoped_and_independent():
    goblin_speaker = SpeakerSelection(SpeakerMode.ACTOR, GOBLIN)
    speak_request = request(
        PermissionCapability.SPEAK_AS,
        actor=GOBLIN,
        speaker=goblin_speaker,
    )
    act_request = request(
        PermissionCapability.ACT_AS,
        actor=GOBLIN,
        speaker=goblin_speaker,
    )
    speak_only = grant(GrantCapability.SPEAK_AS)
    act_only = grant(GrantCapability.ACT_AS)

    assert evaluate(speak_request, grants=(speak_only,)).allowed is True
    assert evaluate(act_request, grants=(speak_only,)).allowed is False
    assert evaluate(speak_request, grants=(act_only,)).allowed is False
    act_decision = evaluate(act_request, grants=(act_only,))
    assert act_decision.allowed is True
    assert (
        act_decision.actor_control
        is ActorControlDisposition.DIRECT_CONTROL
    )


def test_grants_are_independently_revocable_and_expiry_uses_trusted_clock():
    act_request = request(
        PermissionCapability.ACT_AS,
        actor=GOBLIN,
        speaker=SpeakerSelection(SpeakerMode.ACTOR, GOBLIN),
    )
    revoked = grant(
        GrantCapability.ACT_AS,
        state=GrantState.REVOKED,
        slug="revoked",
    )
    expired = grant(
        GrantCapability.ACT_AS,
        expires_at=NOW,
        slug="expired",
    )
    future = grant(
        GrantCapability.ACT_AS,
        expires_at=NOW + timedelta(microseconds=1),
        slug="future",
    )

    assert evaluate(
        act_request, grants=(revoked,)
    ).reason is PermissionReason.GRANT_REVOKED
    assert evaluate(
        act_request, grants=(expired,)
    ).reason is PermissionReason.GRANT_EXPIRED
    assert evaluate(act_request, grants=(future,)).allowed is True


def test_grants_do_not_cross_participant_campaign_actor_or_capability_scope():
    other_campaign = PermissionGrant(
        GrantReference("other-campaign"),
        PLAYER,
        CampaignReference("other-campaign"),
        GOBLIN,
        GrantCapability.ACT_AS,
    )
    other_actor = grant(GrantCapability.ACT_AS, actor=NEKRIA)
    request_value = request(
        PermissionCapability.ACT_AS,
        actor=GOBLIN,
        speaker=SpeakerSelection(SpeakerMode.ACTOR, GOBLIN),
    )

    decision = evaluate(
        request_value,
        grants=(other_campaign, other_actor),
    )

    assert decision.allowed is False
    assert decision.reason is PermissionReason.ASSIGNMENT_OR_GRANT_REQUIRED


def test_speaker_change_never_changes_participant_perspective_authority():
    wrong_perspective = ViewingPerspective(
        PerspectiveKind.PARTICIPANT,
        ParticipantReference("other-player"),
    )
    ooc = request(
        PermissionCapability.INSPECT,
        actor=None,
        speaker=SpeakerSelection(SpeakerMode.OOC),
        perspective=wrong_perspective,
    )
    actor_mode = request(
        PermissionCapability.INSPECT,
        speaker=SpeakerSelection(SpeakerMode.ACTOR, NEKRIA),
        perspective=wrong_perspective,
    )

    assert evaluate(ooc).reason is PermissionReason.PERSPECTIVE_NOT_ALLOWED
    assert (
        evaluate(actor_mode).reason
        is PermissionReason.PERSPECTIVE_NOT_ALLOWED
    )


def test_explicit_visibility_filter_supports_all_four_audiences_without_placeholders():
    entries = (
        AudienceScopedEntry(
            VisibilityEntryKey.FIXTURE_INSPECTION,
            VisibilityAudience(VisibilityAudienceKind.PUBLIC),
            {"value": "public"},
        ),
        AudienceScopedEntry(
            VisibilityEntryKey.CAPABILITY_AVAILABILITY,
            VisibilityAudience(
                VisibilityAudienceKind.PARTICIPANTS, (PLAYER,)
            ),
            {"value": "participant"},
        ),
        AudienceScopedEntry(
            VisibilityEntryKey.ROUND_OPERATION,
            VisibilityAudience(VisibilityAudienceKind.DM_ONLY),
            {"value": "dm"},
        ),
        AudienceScopedEntry(
            VisibilityEntryKey.RECONSTRUCTION_OPERATION,
            VisibilityAudience(
                VisibilityAudienceKind.NO_CLIENT_DISCLOSURE
            ),
            {"value": "never"},
        ),
    )

    player_entries = filter_visible_entries(entries, identity())
    dm_entries = filter_visible_entries(
        entries,
        identity(
            participant=DM,
            session=DM_SESSION,
            role=BaseRole.DM,
        ),
    )

    assert [item.payload["value"] for item in player_entries] == [
        "public",
        "participant",
    ]
    assert [item.payload["value"] for item in dm_entries] == ["public", "dm"]
    assert all(item.key is not VisibilityEntryKey.RECONSTRUCTION_OPERATION for item in player_entries + dm_entries)
