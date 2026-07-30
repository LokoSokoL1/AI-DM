"""Deterministic process-local M2 identity, permission, and visibility adapter."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Optional

from dungeon_manager.application.controlled_fixture import (
    ControlledFixtureFacade,
)
from dungeon_manager.application.permission_contracts import (
    ActorAssignment,
    ActorReference,
    CampaignReference,
    ParticipantReference,
    PermissionGrant,
    SessionIdentity,
    SessionReference,
    VisibilityAudience,
    VisibilityAudienceKind,
    VisibilityEntryKey,
)
from dungeon_manager.application.permissioned_controlled_fixture import (
    PermissionedControlledFixtureFacade,
)


class InProcessPermissionContext:
    """Immutable preconfigured authority data for the controlled fixture."""

    def __init__(
        self,
        *,
        identities: Mapping[SessionReference, SessionIdentity],
        assignments: Iterable[ActorAssignment] = (),
        grants: Iterable[PermissionGrant] = (),
        audiences: Mapping[VisibilityEntryKey, VisibilityAudience],
        now: datetime,
    ) -> None:
        if not isinstance(identities, Mapping):
            raise ValueError("Process-local identities must be a mapping.")
        copied_identities = {}
        for session, identity in identities.items():
            if (
                not isinstance(session, SessionReference)
                or not isinstance(identity, SessionIdentity)
                or identity.session != session
            ):
                raise ValueError("Process-local identity entry is invalid.")
            copied_identities[session] = identity
        copied_assignments = tuple(assignments)
        copied_grants = tuple(grants)
        if any(
            not isinstance(item, ActorAssignment)
            for item in copied_assignments
        ):
            raise ValueError("Process-local assignments must be typed.")
        if len(set(copied_assignments)) != len(copied_assignments):
            raise ValueError("Process-local assignments must be unique.")
        if any(not isinstance(item, PermissionGrant) for item in copied_grants):
            raise ValueError("Process-local grants must be typed.")
        if len({item.grant for item in copied_grants}) != len(copied_grants):
            raise ValueError("Process-local grant identities must be unique.")
        if not isinstance(audiences, Mapping):
            raise ValueError("Process-local audiences must be a mapping.")
        copied_audiences = {}
        for key, audience in audiences.items():
            if (
                not isinstance(key, VisibilityEntryKey)
                or not isinstance(audience, VisibilityAudience)
            ):
                raise ValueError("Process-local audience entry is invalid.")
            copied_audiences[key] = audience
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("Process-local clock must be timezone-aware.")
        self.__identities = MappingProxyType(copied_identities)
        self.__assignments = copied_assignments
        self.__grants = copied_grants
        self.__audiences = MappingProxyType(copied_audiences)
        self.__now = now.astimezone(timezone.utc)

    def resolve_identity(
        self, session: SessionReference
    ) -> Optional[SessionIdentity]:
        if not isinstance(session, SessionReference):
            raise ValueError("Session reference must be typed.")
        return self.__identities.get(session)

    def assignments_for(
        self,
        participant: ParticipantReference,
        campaign: CampaignReference,
    ) -> tuple[ActorAssignment, ...]:
        if not isinstance(participant, ParticipantReference) or not isinstance(
            campaign, CampaignReference
        ):
            raise ValueError("Permission assignment scope must be typed.")
        return tuple(
            assignment
            for assignment in self.__assignments
            if assignment.participant == participant
            and assignment.campaign == campaign
        )

    def grants_for(
        self,
        participant: ParticipantReference,
        campaign: CampaignReference,
    ) -> tuple[PermissionGrant, ...]:
        if not isinstance(participant, ParticipantReference) or not isinstance(
            campaign, CampaignReference
        ):
            raise ValueError("Permission grant scope must be typed.")
        return tuple(
            grant
            for grant in self.__grants
            if grant.participant == participant and grant.campaign == campaign
        )

    def now(self) -> datetime:
        return self.__now

    def audience_for(self, key: VisibilityEntryKey) -> VisibilityAudience:
        if not isinstance(key, VisibilityEntryKey):
            raise ValueError("Visibility entry key must be typed.")
        return self.__audiences.get(
            key,
            VisibilityAudience(
                VisibilityAudienceKind.NO_CLIENT_DISCLOSURE
            ),
        )


def compose_permissioned_controlled_fixture(
    authority: ControlledFixtureFacade,
    context: InProcessPermissionContext,
    *,
    campaign: CampaignReference,
    controlled_actor: ActorReference,
) -> PermissionedControlledFixtureFacade:
    """Compose the bounded M2 wrapper without adding durable permission state."""

    if not isinstance(context, InProcessPermissionContext):
        raise ValueError("Permission context must be process-local and typed.")
    return PermissionedControlledFixtureFacade(
        authority,
        context,
        context,
        context,
        context,
        campaign=campaign,
        controlled_actor=controlled_actor,
    )
