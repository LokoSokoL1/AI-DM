"""Narrow read-only ports for the bounded M2 permission core."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from .permission_contracts import (
    ActorAssignment,
    CampaignReference,
    ParticipantReference,
    PermissionGrant,
    SessionIdentity,
    SessionReference,
    VisibilityAudience,
    VisibilityEntryKey,
)


@runtime_checkable
class TrustedIdentityAuthorityPort(Protocol):
    def resolve_identity(
        self, session: SessionReference
    ) -> Optional[SessionIdentity]:
        ...


@runtime_checkable
class PermissionStatePort(Protocol):
    def assignments_for(
        self,
        participant: ParticipantReference,
        campaign: CampaignReference,
    ) -> tuple[ActorAssignment, ...]:
        ...

    def grants_for(
        self,
        participant: ParticipantReference,
        campaign: CampaignReference,
    ) -> tuple[PermissionGrant, ...]:
        ...


@runtime_checkable
class TrustedClockPort(Protocol):
    def now(self) -> datetime:
        ...


@runtime_checkable
class VisibilityAuthorityPort(Protocol):
    def audience_for(self, key: VisibilityEntryKey) -> VisibilityAudience:
        ...
