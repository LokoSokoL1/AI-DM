"""Pure deterministic permission evaluation and explicit audience filtering."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .permission_contracts import (
    ActorAssignment,
    ActorControlDisposition,
    AudienceScopedEntry,
    BaseRole,
    GrantCapability,
    GrantState,
    IdentityState,
    PermissionCapability,
    PermissionContractVersion,
    PermissionDecision,
    PermissionGrant,
    PermissionReason,
    PermissionRequest,
    PerspectiveKind,
    SessionIdentity,
    SpeakerMode,
    VisibilityAudienceKind,
    VisibleEntry,
)


_ACT_CAPABILITIES = {
    PermissionCapability.SELECT_PLAYER_CHARACTER,
    PermissionCapability.RESOLVE_CONTROLLED_ROUND,
    PermissionCapability.RECONSTRUCT_OPERATION,
    PermissionCapability.ACT_AS,
}


def _decision(
    allowed: bool,
    reason: PermissionReason,
    *,
    direct_control: bool = False,
) -> PermissionDecision:
    return PermissionDecision(
        PermissionContractVersion.V1,
        allowed,
        reason,
        (
            ActorControlDisposition.DIRECT_CONTROL
            if direct_control
            else ActorControlDisposition.AI_DEFAULT
        ),
    )


def _matching_assignment(
    identity: SessionIdentity,
    request: PermissionRequest,
    assignments: tuple[ActorAssignment, ...],
) -> bool:
    return request.actor is not None and any(
        assignment.participant == identity.participant
        and assignment.campaign == request.campaign
        and assignment.actor == request.actor
        for assignment in assignments
    )


def _grant_decision(
    identity: SessionIdentity,
    request: PermissionRequest,
    grants: tuple[PermissionGrant, ...],
    capability: GrantCapability,
    now: datetime,
) -> PermissionDecision:
    matching = tuple(
        grant
        for grant in grants
        if request.actor is not None
        and grant.participant == identity.participant
        and grant.campaign == request.campaign
        and grant.actor == request.actor
        and grant.capability is capability
    )
    if any(
        grant.state is GrantState.ACTIVE
        and (grant.expires_at is None or now < grant.expires_at)
        for grant in matching
    ):
        return _decision(
            True,
            PermissionReason.ALLOWED,
            direct_control=capability is GrantCapability.ACT_AS,
        )
    if any(grant.state is GrantState.REVOKED for grant in matching):
        return _decision(False, PermissionReason.GRANT_REVOKED)
    if any(
        grant.state is GrantState.ACTIVE
        and grant.expires_at is not None
        and now >= grant.expires_at
        for grant in matching
    ):
        return _decision(False, PermissionReason.GRANT_EXPIRED)
    return _decision(False, PermissionReason.ASSIGNMENT_OR_GRANT_REQUIRED)


def evaluate_permission(
    identity: Optional[SessionIdentity],
    request: PermissionRequest,
    assignments: tuple[ActorAssignment, ...],
    grants: tuple[PermissionGrant, ...],
    now: datetime,
) -> PermissionDecision:
    """Evaluate one exact request without mutation or external calls."""

    if not isinstance(request, PermissionRequest):
        raise ValueError("Permission request must be typed.")
    if not isinstance(now, datetime) or now.tzinfo is None:
        return _decision(False, PermissionReason.INVALID_AUTHORITY_RESPONSE)
    now = now.astimezone(timezone.utc)
    if identity is None:
        return _decision(False, PermissionReason.IDENTITY_UNRESOLVED)
    if not isinstance(identity, SessionIdentity) or identity.session != (
        request.session
    ):
        return _decision(False, PermissionReason.INVALID_AUTHORITY_RESPONSE)
    if identity.state is IdentityState.REVOKED:
        return _decision(False, PermissionReason.IDENTITY_REVOKED)
    if identity.expires_at is not None and now >= identity.expires_at:
        return _decision(False, PermissionReason.IDENTITY_EXPIRED)
    if any(not isinstance(item, ActorAssignment) for item in assignments):
        return _decision(False, PermissionReason.INVALID_AUTHORITY_RESPONSE)
    if any(not isinstance(item, PermissionGrant) for item in grants):
        return _decision(False, PermissionReason.INVALID_AUTHORITY_RESPONSE)

    perspective = request.perspective
    if (
        perspective.kind is PerspectiveKind.PARTICIPANT
        and perspective.participant != identity.participant
    ):
        return _decision(False, PermissionReason.PERSPECTIVE_NOT_ALLOWED)
    if (
        perspective.kind is PerspectiveKind.DM
        and identity.role is not BaseRole.DM
    ):
        return _decision(False, PermissionReason.PERSPECTIVE_NOT_ALLOWED)

    speaker = request.speaker
    if speaker.mode is SpeakerMode.DM and identity.role is not BaseRole.DM:
        return _decision(False, PermissionReason.ROLE_NOT_ALLOWED)
    if speaker.mode is SpeakerMode.ACTOR and (
        request.actor is None or speaker.actor != request.actor
    ):
        return _decision(False, PermissionReason.SPEAKER_NOT_ALLOWED)

    if request.capability in {
        PermissionCapability.INSPECT,
        PermissionCapability.DISCOVER_CAPABILITIES,
    }:
        return _decision(True, PermissionReason.ALLOWED)

    if request.capability is PermissionCapability.SPEAK_AS:
        if speaker.mode is SpeakerMode.OOC:
            return _decision(True, PermissionReason.ALLOWED)
        if speaker.mode is SpeakerMode.DM:
            return _decision(True, PermissionReason.ALLOWED)
        if request.actor is None:
            return _decision(False, PermissionReason.ACTOR_REQUIRED)
        if _matching_assignment(identity, request, assignments):
            return _decision(True, PermissionReason.ALLOWED)
        return _grant_decision(
            identity,
            request,
            grants,
            GrantCapability.SPEAK_AS,
            now,
        )

    if request.capability in _ACT_CAPABILITIES:
        if request.actor is None:
            return _decision(False, PermissionReason.ACTOR_REQUIRED)
        if speaker.mode is not SpeakerMode.ACTOR:
            return _decision(False, PermissionReason.SPEAKER_NOT_ALLOWED)
        if _matching_assignment(identity, request, assignments):
            return _decision(
                True, PermissionReason.ALLOWED, direct_control=True
            )
        return _grant_decision(
            identity,
            request,
            grants,
            GrantCapability.ACT_AS,
            now,
        )

    return _decision(False, PermissionReason.CAPABILITY_DENIED)


def filter_visible_entries(
    entries: tuple[AudienceScopedEntry, ...],
    identity: SessionIdentity,
) -> tuple[VisibleEntry, ...]:
    """Return only entries whose explicit audience admits the identity."""

    if not isinstance(identity, SessionIdentity):
        raise ValueError("Visibility filtering requires a resolved identity.")
    result = []
    for entry in tuple(entries):
        if not isinstance(entry, AudienceScopedEntry):
            raise ValueError("Visibility filtering entries must be typed.")
        audience = entry.audience
        visible = (
            audience.kind is VisibilityAudienceKind.PUBLIC
            or (
                audience.kind is VisibilityAudienceKind.PARTICIPANTS
                and identity.participant in audience.participants
            )
            or (
                audience.kind is VisibilityAudienceKind.DM_ONLY
                and identity.role is BaseRole.DM
            )
        )
        if visible:
            result.append(VisibleEntry(entry.key, entry.payload))
    return tuple(result)
