"""Immutable client-neutral contracts for the bounded M2 permission core."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Optional


_MAX_IDENTIFIER_LENGTH = 256


def _validated_identifier(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > _MAX_IDENTIFIER_LENGTH
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{label} must be a safe non-empty trimmed string.")
    return value


def _canonical_time(value: Any, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware.")
    canonical = value.astimezone(timezone.utc)
    if canonical.utcoffset() != timezone.utc.utcoffset(canonical):
        raise ValueError(f"{label} must convert to UTC.")
    return canonical


def _serialized_time(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _copy_json(value: Any, path: str, ancestors: set[int]) -> Any:
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in ancestors:
            raise ValueError(f"{path} must not contain circular references.")
        ancestors.add(identity)
        try:
            copied = {}
            for key, child in value.items():
                if not isinstance(key, str):
                    raise ValueError(f"{path} keys must be strings.")
                copied[key] = _copy_json(child, f"{path}.{key}", ancestors)
            return copied
        finally:
            ancestors.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in ancestors:
            raise ValueError(f"{path} must not contain circular references.")
        ancestors.add(identity)
        try:
            return [
                _copy_json(child, f"{path}[{index}]", ancestors)
                for index, child in enumerate(value)
            ]
        finally:
            ancestors.remove(identity)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError(f"{path} must contain only finite JSON-compatible values.")


def _freeze_json(value: Any, path: str) -> Any:
    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType(
                {key: freeze(child) for key, child in item.items()}
            )
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(_copy_json(value, path, set()))


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(child) for child in value]
    return value


class _ContractValue:
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


class PermissionContractVersion(str, Enum):
    V1 = "phase2-m2-v1"


class BaseRole(str, Enum):
    PLAYER = "player"
    DM = "dm"


class IdentityState(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class SpeakerMode(str, Enum):
    OOC = "ooc"
    DM = "dm"
    ACTOR = "actor"


class GrantCapability(str, Enum):
    SPEAK_AS = "speak_as"
    ACT_AS = "act_as"


class GrantState(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class PerspectiveKind(str, Enum):
    PARTICIPANT = "participant"
    DM = "dm"


class VisibilityAudienceKind(str, Enum):
    PUBLIC = "public"
    PARTICIPANTS = "participants"
    DM_ONLY = "dm_only"
    NO_CLIENT_DISCLOSURE = "no_client_disclosure"


class PermissionCapability(str, Enum):
    INSPECT = "controlled_fixture.inspect"
    DISCOVER_CAPABILITIES = "controlled_fixture.discover_capabilities"
    SELECT_PLAYER_CHARACTER = "controlled_fixture.select_player_character"
    RESOLVE_CONTROLLED_ROUND = "controlled_fixture.resolve_controlled_round"
    RECONSTRUCT_OPERATION = "controlled_fixture.reconstruct_operation"
    SPEAK_AS = "controlled_fixture.speak_as"
    ACT_AS = "controlled_fixture.act_as"


class PermissionReason(str, Enum):
    ALLOWED = "allowed"
    IDENTITY_UNRESOLVED = "identity_unresolved"
    IDENTITY_REVOKED = "identity_revoked"
    IDENTITY_EXPIRED = "identity_expired"
    ROLE_NOT_ALLOWED = "role_not_allowed"
    SPEAKER_NOT_ALLOWED = "speaker_not_allowed"
    PERSPECTIVE_NOT_ALLOWED = "perspective_not_allowed"
    ACTOR_REQUIRED = "actor_required"
    ASSIGNMENT_OR_GRANT_REQUIRED = "assignment_or_grant_required"
    GRANT_REVOKED = "grant_revoked"
    GRANT_EXPIRED = "grant_expired"
    CAPABILITY_DENIED = "capability_denied"
    INVALID_AUTHORITY_RESPONSE = "invalid_authority_response"


class ActorControlDisposition(str, Enum):
    AI_DEFAULT = "ai_default"
    DIRECT_CONTROL = "direct_control"


class PermissionedViewKind(str, Enum):
    INSPECTION = "inspection"
    CAPABILITIES = "capabilities"
    SELECTION = "selection"
    ROUND = "round"
    RECONSTRUCTION = "reconstruction"


class VisibilityEntryKey(str, Enum):
    FIXTURE_INSPECTION = "controlled_fixture.inspection"
    CAPABILITY_AVAILABILITY = "controlled_fixture.capabilities"
    SELECTION_OPERATION = "controlled_fixture.selection_operation"
    ROUND_OPERATION = "controlled_fixture.round_operation"
    RECONSTRUCTION_OPERATION = "controlled_fixture.reconstruction_operation"


@dataclass(frozen=True)
class SessionReference(_ContractValue):
    value: str

    def __post_init__(self) -> None:
        _validated_identifier(self.value, "Session reference")

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value}


@dataclass(frozen=True)
class ParticipantReference(_ContractValue):
    value: str

    def __post_init__(self) -> None:
        _validated_identifier(self.value, "Participant reference")

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value}


@dataclass(frozen=True)
class CampaignReference(_ContractValue):
    value: str

    def __post_init__(self) -> None:
        _validated_identifier(self.value, "Campaign reference")

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value}


@dataclass(frozen=True)
class ActorReference(_ContractValue):
    value: str

    def __post_init__(self) -> None:
        _validated_identifier(self.value, "Actor reference")

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value}


@dataclass(frozen=True)
class GrantReference(_ContractValue):
    value: str

    def __post_init__(self) -> None:
        _validated_identifier(self.value, "Grant reference")

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value}


@dataclass(frozen=True)
class SessionIdentity(_ContractValue):
    session: SessionReference
    participant: ParticipantReference
    role: BaseRole
    state: IdentityState = IdentityState.ACTIVE
    expires_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not isinstance(self.session, SessionReference):
            raise ValueError("Session identity session must be typed.")
        if not isinstance(self.participant, ParticipantReference):
            raise ValueError("Session identity participant must be typed.")
        if not isinstance(self.role, BaseRole):
            raise ValueError("Session identity role must be typed.")
        if not isinstance(self.state, IdentityState):
            raise ValueError("Session identity state must be typed.")
        if self.expires_at is not None:
            object.__setattr__(
                self,
                "expires_at",
                _canonical_time(self.expires_at, "Session identity expiry"),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "expires_at": (
                None
                if self.expires_at is None
                else _serialized_time(self.expires_at)
            ),
            "participant": self.participant.to_dict(),
            "role": self.role.value,
            "session": self.session.to_dict(),
            "state": self.state.value,
        }


@dataclass(frozen=True)
class SpeakerSelection(_ContractValue):
    mode: SpeakerMode
    actor: Optional[ActorReference] = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, SpeakerMode):
            raise ValueError("Speaker mode must be typed.")
        if self.mode is SpeakerMode.ACTOR:
            if not isinstance(self.actor, ActorReference):
                raise ValueError("Actor speaker mode requires an actor.")
        elif self.actor is not None:
            raise ValueError("Non-actor speaker modes cannot carry an actor.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": None if self.actor is None else self.actor.to_dict(),
            "mode": self.mode.value,
        }


@dataclass(frozen=True)
class ViewingPerspective(_ContractValue):
    kind: PerspectiveKind
    participant: Optional[ParticipantReference] = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PerspectiveKind):
            raise ValueError("Viewing perspective kind must be typed.")
        if self.kind is PerspectiveKind.PARTICIPANT:
            if not isinstance(self.participant, ParticipantReference):
                raise ValueError(
                    "Participant perspective requires a participant."
                )
        elif self.participant is not None:
            raise ValueError("DM perspective cannot carry a participant.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "participant": (
                None
                if self.participant is None
                else self.participant.to_dict()
            ),
        }


@dataclass(frozen=True)
class ActorAssignment(_ContractValue):
    participant: ParticipantReference
    campaign: CampaignReference
    actor: ActorReference

    def __post_init__(self) -> None:
        if not isinstance(self.participant, ParticipantReference):
            raise ValueError("Assignment participant must be typed.")
        if not isinstance(self.campaign, CampaignReference):
            raise ValueError("Assignment campaign must be typed.")
        if not isinstance(self.actor, ActorReference):
            raise ValueError("Assignment actor must be typed.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor.to_dict(),
            "campaign": self.campaign.to_dict(),
            "participant": self.participant.to_dict(),
        }


@dataclass(frozen=True)
class PermissionGrant(_ContractValue):
    grant: GrantReference
    participant: ParticipantReference
    campaign: CampaignReference
    actor: ActorReference
    capability: GrantCapability
    state: GrantState = GrantState.ACTIVE
    expires_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not isinstance(self.grant, GrantReference):
            raise ValueError("Permission grant identity must be typed.")
        if not isinstance(self.participant, ParticipantReference):
            raise ValueError("Permission grant participant must be typed.")
        if not isinstance(self.campaign, CampaignReference):
            raise ValueError("Permission grant campaign must be typed.")
        if not isinstance(self.actor, ActorReference):
            raise ValueError("Permission grant actor must be typed.")
        if not isinstance(self.capability, GrantCapability):
            raise ValueError("Permission grant capability must be typed.")
        if not isinstance(self.state, GrantState):
            raise ValueError("Permission grant state must be typed.")
        if self.expires_at is not None:
            object.__setattr__(
                self,
                "expires_at",
                _canonical_time(self.expires_at, "Permission grant expiry"),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor.to_dict(),
            "campaign": self.campaign.to_dict(),
            "capability": self.capability.value,
            "expires_at": (
                None
                if self.expires_at is None
                else _serialized_time(self.expires_at)
            ),
            "grant": self.grant.to_dict(),
            "participant": self.participant.to_dict(),
            "state": self.state.value,
        }


@dataclass(frozen=True)
class PermissionRequest(_ContractValue):
    version: PermissionContractVersion
    session: SessionReference
    campaign: CampaignReference
    capability: PermissionCapability
    speaker: SpeakerSelection
    perspective: ViewingPerspective
    actor: Optional[ActorReference] = None

    def __post_init__(self) -> None:
        if not isinstance(self.version, PermissionContractVersion):
            raise ValueError("Permission contract version must be typed.")
        if not isinstance(self.session, SessionReference):
            raise ValueError("Permission request session must be typed.")
        if not isinstance(self.campaign, CampaignReference):
            raise ValueError("Permission request campaign must be typed.")
        if not isinstance(self.capability, PermissionCapability):
            raise ValueError("Permission request capability must be typed.")
        if not isinstance(self.speaker, SpeakerSelection):
            raise ValueError("Permission request speaker must be typed.")
        if not isinstance(self.perspective, ViewingPerspective):
            raise ValueError("Permission request perspective must be typed.")
        if self.actor is not None and not isinstance(
            self.actor, ActorReference
        ):
            raise ValueError("Permission request actor must be typed.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": None if self.actor is None else self.actor.to_dict(),
            "campaign": self.campaign.to_dict(),
            "capability": self.capability.value,
            "perspective": self.perspective.to_dict(),
            "session": self.session.to_dict(),
            "speaker": self.speaker.to_dict(),
            "version": self.version.value,
        }


@dataclass(frozen=True)
class PermissionDecision(_ContractValue):
    version: PermissionContractVersion
    allowed: bool
    reason: PermissionReason
    actor_control: ActorControlDisposition = (
        ActorControlDisposition.AI_DEFAULT
    )

    def __post_init__(self) -> None:
        if not isinstance(self.version, PermissionContractVersion):
            raise ValueError("Permission decision version must be typed.")
        if not isinstance(self.allowed, bool):
            raise ValueError("Permission decision allow state must be boolean.")
        if not isinstance(self.reason, PermissionReason):
            raise ValueError("Permission decision reason must be typed.")
        if not isinstance(self.actor_control, ActorControlDisposition):
            raise ValueError("Actor control disposition must be typed.")
        if (
            self.allowed
            and self.reason is not PermissionReason.ALLOWED
        ) or (
            not self.allowed
            and self.reason is PermissionReason.ALLOWED
        ):
            raise ValueError("Permission decision allow state and reason differ.")
        if (
            not self.allowed
            and self.actor_control
            is not ActorControlDisposition.AI_DEFAULT
        ):
            raise ValueError("Denied permissions cannot claim direct control.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_control": self.actor_control.value,
            "allowed": self.allowed,
            "reason": self.reason.value,
            "version": self.version.value,
        }


@dataclass(frozen=True)
class VisibilityAudience(_ContractValue):
    kind: VisibilityAudienceKind
    participants: tuple[ParticipantReference, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, VisibilityAudienceKind):
            raise ValueError("Visibility audience kind must be typed.")
        participants = tuple(self.participants)
        if any(
            not isinstance(item, ParticipantReference) for item in participants
        ):
            raise ValueError("Visibility participants must be typed.")
        if len(set(participants)) != len(participants):
            raise ValueError("Visibility participants must be unique.")
        participants = tuple(sorted(participants, key=lambda item: item.value))
        if self.kind is VisibilityAudienceKind.PARTICIPANTS:
            if not participants:
                raise ValueError(
                    "Participant visibility requires at least one participant."
                )
        elif participants:
            raise ValueError(
                "Only participant visibility may carry participants."
            )
        object.__setattr__(self, "participants", participants)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "participants": [item.to_dict() for item in self.participants],
        }


@dataclass(frozen=True)
class AudienceScopedEntry(_ContractValue):
    key: VisibilityEntryKey
    audience: VisibilityAudience
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.key, VisibilityEntryKey):
            raise ValueError("Visibility entry key must be typed.")
        if not isinstance(self.audience, VisibilityAudience):
            raise ValueError("Visibility entry audience must be typed.")
        if not isinstance(self.payload, Mapping):
            raise ValueError("Visibility entry payload must be an object.")
        object.__setattr__(
            self,
            "payload",
            _freeze_json(self.payload, "Visibility entry payload"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "audience": self.audience.to_dict(),
            "key": self.key.value,
            "payload": _thaw_json(self.payload),
        }


@dataclass(frozen=True)
class VisibleEntry(_ContractValue):
    key: VisibilityEntryKey
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.key, VisibilityEntryKey):
            raise ValueError("Visible entry key must be typed.")
        if not isinstance(self.payload, Mapping):
            raise ValueError("Visible entry payload must be an object.")
        object.__setattr__(
            self,
            "payload",
            _freeze_json(self.payload, "Visible entry payload"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key.value, "payload": _thaw_json(self.payload)}


@dataclass(frozen=True)
class PermissionedView(_ContractValue):
    version: PermissionContractVersion
    kind: PermissionedViewKind
    decision: PermissionDecision
    entries: tuple[VisibleEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.version, PermissionContractVersion):
            raise ValueError("Permissioned view version must be typed.")
        if not isinstance(self.kind, PermissionedViewKind):
            raise ValueError("Permissioned view kind must be typed.")
        if (
            not isinstance(self.decision, PermissionDecision)
            or self.decision.version is not self.version
        ):
            raise ValueError("Permissioned view decision is invalid.")
        entries = tuple(self.entries)
        if any(not isinstance(item, VisibleEntry) for item in entries):
            raise ValueError("Permissioned view entries must be typed.")
        if len({item.key for item in entries}) != len(entries):
            raise ValueError("Permissioned view entry keys must be unique.")
        if not self.decision.allowed and entries:
            raise ValueError("Denied permissioned views cannot disclose entries.")
        object.__setattr__(self, "entries", entries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.to_dict(),
            "entries": [item.to_dict() for item in self.entries],
            "kind": self.kind.value,
            "version": self.version.value,
        }
