"""Client-neutral immutable contracts for the bounded controlled fixture."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Optional


_CONTROLLED_ROLL_STAGES = (
    "nekria_initiative",
    "goblin_initiative",
    "attack",
    "damage",
)
_MAX_IDENTIFIER_LENGTH = 256
_MAX_PRESENTATION_LENGTH = 4000


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


def _canonical_time(value: Any, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware.")
    canonical = value.astimezone(timezone.utc)
    if canonical.utcoffset() != timezone.utc.utcoffset(canonical):
        raise ValueError(f"{label} must convert to UTC.")
    return canonical


def _serialized_time(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _validate_sequence(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
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


class ContractVersion(str, Enum):
    V1 = "phase2-m1-v1"


class IdentityKind(str, Enum):
    CAMPAIGN = "campaign"
    SCENE = "scene"
    ACTOR = "actor"
    COMMAND = "command"
    EVENT = "event"
    CALLER_OPERATION = "caller_operation"


class CapabilityKey(str, Enum):
    INSPECT_CONTROLLED_FIXTURE = "controlled_fixture.inspect"
    SELECT_PLAYER_CHARACTER = "controlled_fixture.select_player_character"
    RESOLVE_CONTROLLED_ROUND = "controlled_fixture.resolve_controlled_round"
    RECONSTRUCT_OPERATION = "controlled_fixture.reconstruct_operation"
    VERIFIED_TRANSIENT_NARRATION = (
        "controlled_fixture.verified_transient_narration"
    )
    CONTROLLED_GOBLIN_ACTION = "controlled_fixture.goblin_action"


class CapabilityStatus(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"


class CapabilityReason(str, Enum):
    PLAYER_SELECTION_REQUIRED = "player_selection_required"
    ROUND_ALREADY_RESOLVED = "round_already_resolved"
    PRESENTATION_NOT_CONFIGURED = "presentation_not_configured"
    CONTROLLED_FIXTURE_HAS_NO_GOBLIN_ACTION = (
        "controlled_fixture_has_no_goblin_action"
    )


class SubmissionState(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class MechanicalState(str, Enum):
    NOT_ATTEMPTED = "not_attempted"
    SUCCEEDED = "succeeded"
    INPUT_REQUIRED = "input_required"
    FAILED = "failed"
    UNKNOWN = "unknown"


class DurableCommitState(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    NOT_COMMITTED = "not_committed"
    COMMITTED = "committed"
    UNKNOWN = "unknown"


class LocalPublicationState(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    NOT_PUBLISHED = "not_published"
    PUBLISHED = "published"
    UNKNOWN = "unknown"


class ProjectionState(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    NOT_PROJECTED = "not_projected"
    PROJECTED = "projected"
    FAILED = "failed"
    UNKNOWN = "unknown"


class SynchronizationState(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    SYNCHRONIZED = "synchronized"
    OUT_OF_SYNC = "out_of_sync"
    UNKNOWN = "unknown"


class PresentationState(str, Enum):
    NOT_REQUESTED = "not_requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ClientDiceMode(str, Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class DiagnosticCode(str, Enum):
    INVALID_REQUEST = "invalid_request"
    SUBMISSION_REJECTED = "submission_rejected"
    MECHANICAL_FAILURE = "mechanical_failure"
    DURABLE_COMMIT_FAILURE = "durable_commit_failure"
    LOCAL_PUBLICATION_FAILURE = "local_publication_failure"
    PROJECTION_FAILURE = "projection_failure"
    SYNCHRONIZATION_FAILURE = "synchronization_failure"
    PRESENTATION_FAILURE = "presentation_failure"
    CORRELATION_NOT_FOUND = "correlation_not_found"
    INTERNAL_FAILURE = "internal_failure"


_DIAGNOSTIC_MESSAGES = {
    DiagnosticCode.INVALID_REQUEST: "The client request is invalid.",
    DiagnosticCode.SUBMISSION_REJECTED: "The operation was rejected safely.",
    DiagnosticCode.MECHANICAL_FAILURE: "Mechanical resolution failed safely.",
    DiagnosticCode.DURABLE_COMMIT_FAILURE: (
        "Durable event commitment was not confirmed."
    ),
    DiagnosticCode.LOCAL_PUBLICATION_FAILURE: (
        "The durable fact could not be published to the local event view."
    ),
    DiagnosticCode.PROJECTION_FAILURE: (
        "The durable fact could not be projected into the current view."
    ),
    DiagnosticCode.SYNCHRONIZATION_FAILURE: (
        "Authoritative history and the current view are not synchronized."
    ),
    DiagnosticCode.PRESENTATION_FAILURE: (
        "The authoritative result is safe, but presentation was unavailable."
    ),
    DiagnosticCode.CORRELATION_NOT_FOUND: (
        "No durable event matches the supplied command correlation."
    ),
    DiagnosticCode.INTERNAL_FAILURE: (
        "The client-neutral operation failed without exposing internal details."
    ),
}


@dataclass(frozen=True)
class AuthorityReference(_ContractValue):
    kind: IdentityKind
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IdentityKind):
            raise ValueError("Authority reference kind must be typed.")
        _validated_identifier(self.value, "Authority reference value")

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind.value, "value": self.value}


@dataclass(frozen=True)
class SequencedEventReference(_ContractValue):
    event: AuthorityReference
    sequence: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.event, AuthorityReference)
            or self.event.kind is not IdentityKind.EVENT
        ):
            raise ValueError("Sequenced event reference requires an event ID.")
        if _validate_sequence(self.sequence, "Event sequence") < 1:
            raise ValueError("Event sequence must be positive.")

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event.to_dict(), "sequence": self.sequence}


@dataclass(frozen=True)
class ClientDiagnostic(_ContractValue):
    code: DiagnosticCode

    def __post_init__(self) -> None:
        if not isinstance(self.code, DiagnosticCode):
            raise ValueError("Client diagnostic code must be typed.")

    @property
    def message(self) -> str:
        return _DIAGNOSTIC_MESSAGES[self.code]

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True)
class CapabilityDescriptor(_ContractValue):
    version: ContractVersion
    key: CapabilityKey
    status: CapabilityStatus
    reason: Optional[CapabilityReason] = None

    def __post_init__(self) -> None:
        if not isinstance(self.version, ContractVersion):
            raise ValueError("Capability contract version must be typed.")
        if not isinstance(self.key, CapabilityKey):
            raise ValueError("Capability key must be typed.")
        if not isinstance(self.status, CapabilityStatus):
            raise ValueError("Capability status must be typed.")
        if self.reason is not None and not isinstance(
            self.reason, CapabilityReason
        ):
            raise ValueError("Capability reason must be typed.")
        if self.status is CapabilityStatus.SUPPORTED and self.reason is not None:
            raise ValueError("Supported capabilities cannot contain a reason.")
        if (
            self.status is not CapabilityStatus.SUPPORTED
            and self.reason is None
        ):
            raise ValueError(
                "Unsupported or unavailable capabilities require a reason."
            )

    def to_dict(self) -> dict[str, Optional[str]]:
        return {
            "key": self.key.value,
            "reason": None if self.reason is None else self.reason.value,
            "status": self.status.value,
            "version": self.version.value,
        }


@dataclass(frozen=True)
class TransientPresentation(_ContractValue):
    text: str
    source_event: SequencedEventReference

    def __post_init__(self) -> None:
        if (
            not isinstance(self.text, str)
            or not self.text.strip()
            or self.text != self.text.strip()
            or len(self.text) > _MAX_PRESENTATION_LENGTH
            or "\x00" in self.text
        ):
            raise ValueError("Transient presentation text is invalid.")
        if not isinstance(self.source_event, SequencedEventReference):
            raise ValueError(
                "Transient presentation requires a source event reference."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_event": self.source_event.to_dict(),
            "text": self.text,
        }


@dataclass(frozen=True)
class ControlledFixtureView(_ContractValue):
    version: ContractVersion
    campaign: AuthorityReference
    scene: AuthorityReference
    actors: tuple[AuthorityReference, ...]
    selectable_player_characters: tuple[AuthorityReference, ...]
    selected_player_character: Optional[AuthorityReference]
    events: tuple[SequencedEventReference, ...]
    journal_tail: int
    projection_sequence: int
    synchronization: SynchronizationState
    controlled_round_resolved: bool

    def __post_init__(self) -> None:
        if not isinstance(self.version, ContractVersion):
            raise ValueError("Fixture view contract version must be typed.")
        for reference, kind, label in (
            (self.campaign, IdentityKind.CAMPAIGN, "campaign"),
            (self.scene, IdentityKind.SCENE, "scene"),
        ):
            if (
                not isinstance(reference, AuthorityReference)
                or reference.kind is not kind
            ):
                raise ValueError(f"Fixture view {label} reference is invalid.")
        actors = tuple(self.actors)
        selectable = tuple(self.selectable_player_characters)
        events = tuple(self.events)
        if not actors or any(
            not isinstance(item, AuthorityReference)
            or item.kind is not IdentityKind.ACTOR
            for item in actors
        ):
            raise ValueError("Fixture view actors must be actor references.")
        if len(set(actors)) != len(actors):
            raise ValueError("Fixture view actor references must be unique.")
        if any(item not in actors for item in selectable):
            raise ValueError("Selectable actors must belong to the fixture.")
        if self.selected_player_character is not None and (
            not isinstance(self.selected_player_character, AuthorityReference)
            or self.selected_player_character not in selectable
        ):
            raise ValueError("Selected actor must be selectable.")
        if any(not isinstance(item, SequencedEventReference) for item in events):
            raise ValueError("Fixture view events must be sequenced references.")
        journal_tail = _validate_sequence(self.journal_tail, "Journal tail")
        projection_sequence = _validate_sequence(
            self.projection_sequence, "Projection sequence"
        )
        if tuple(item.sequence for item in events) != tuple(
            range(1, journal_tail + 1)
        ):
            raise ValueError(
                "Fixture event references must cover the complete journal tail."
            )
        if projection_sequence > journal_tail:
            raise ValueError("Projection sequence cannot exceed the journal tail.")
        if not isinstance(self.synchronization, SynchronizationState):
            raise ValueError("Fixture synchronization state must be typed.")
        if self.synchronization not in {
            SynchronizationState.SYNCHRONIZED,
            SynchronizationState.OUT_OF_SYNC,
            SynchronizationState.UNKNOWN,
        }:
            raise ValueError("Fixture synchronization state is invalid.")
        if (
            self.synchronization is SynchronizationState.SYNCHRONIZED
            and projection_sequence != journal_tail
        ):
            raise ValueError(
                "Synchronized fixture views require matching projection and journal tails."
            )
        if not isinstance(self.controlled_round_resolved, bool):
            raise ValueError("Controlled-round state must be boolean.")
        object.__setattr__(self, "actors", actors)
        object.__setattr__(self, "selectable_player_characters", selectable)
        object.__setattr__(self, "events", events)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actors": [item.to_dict() for item in self.actors],
            "campaign": self.campaign.to_dict(),
            "controlled_round_resolved": self.controlled_round_resolved,
            "events": [item.to_dict() for item in self.events],
            "journal_tail": self.journal_tail,
            "projection_sequence": self.projection_sequence,
            "scene": self.scene.to_dict(),
            "selectable_player_characters": [
                item.to_dict() for item in self.selectable_player_characters
            ],
            "selected_player_character": (
                None
                if self.selected_player_character is None
                else self.selected_player_character.to_dict()
            ),
            "synchronization": self.synchronization.value,
            "version": self.version.value,
        }


def _validate_operation_references(
    version: Any,
    operation: Any,
    command: Any,
) -> None:
    if not isinstance(version, ContractVersion):
        raise ValueError("Request contract version must be typed.")
    if (
        not isinstance(operation, AuthorityReference)
        or operation.kind is not IdentityKind.CALLER_OPERATION
    ):
        raise ValueError("Request operation correlation is invalid.")
    if (
        not isinstance(command, AuthorityReference)
        or command.kind is not IdentityKind.COMMAND
    ):
        raise ValueError("Request command reference is invalid.")


@dataclass(frozen=True)
class SelectPlayerCharacterRequest(_ContractValue):
    version: ContractVersion
    operation: AuthorityReference
    command: AuthorityReference
    event: AuthorityReference
    actor: AuthorityReference
    occurred_at: datetime

    def __post_init__(self) -> None:
        _validate_operation_references(
            self.version, self.operation, self.command
        )
        if (
            not isinstance(self.event, AuthorityReference)
            or self.event.kind is not IdentityKind.EVENT
        ):
            raise ValueError("Selection request event reference is invalid.")
        if (
            not isinstance(self.actor, AuthorityReference)
            or self.actor.kind is not IdentityKind.ACTOR
        ):
            raise ValueError("Selection request actor reference is invalid.")
        object.__setattr__(
            self,
            "occurred_at",
            _canonical_time(self.occurred_at, "Selection occurrence time"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor.to_dict(),
            "command": self.command.to_dict(),
            "event": self.event.to_dict(),
            "occurred_at": _serialized_time(self.occurred_at),
            "operation": self.operation.to_dict(),
            "version": self.version.value,
        }


@dataclass(frozen=True)
class ResolveControlledRoundRequest(_ContractValue):
    version: ContractVersion
    operation: AuthorityReference
    command: AuthorityReference
    event: AuthorityReference
    occurred_at: datetime
    dice_mode: ClientDiceMode
    roll_ids: Mapping[str, str]
    manual_faces: Mapping[str, Optional[int]]

    def __post_init__(self) -> None:
        _validate_operation_references(
            self.version, self.operation, self.command
        )
        if (
            not isinstance(self.event, AuthorityReference)
            or self.event.kind is not IdentityKind.EVENT
        ):
            raise ValueError("Round request event reference is invalid.")
        if not isinstance(self.dice_mode, ClientDiceMode):
            raise ValueError("Round request dice mode must be typed.")
        if not isinstance(self.roll_ids, Mapping) or set(self.roll_ids) != set(
            _CONTROLLED_ROLL_STAGES
        ):
            raise ValueError("Round request roll IDs are incomplete.")
        roll_ids = {}
        for stage in _CONTROLLED_ROLL_STAGES:
            roll_ids[stage] = _validated_identifier(
                self.roll_ids[stage], f"{stage} roll ID"
            )
        if len(set(roll_ids.values())) != len(roll_ids):
            raise ValueError("Round request roll IDs must be unique.")
        if (
            not isinstance(self.manual_faces, Mapping)
            or set(self.manual_faces) != set(_CONTROLLED_ROLL_STAGES)
        ):
            raise ValueError("Round request manual faces are incomplete.")
        manual_faces = {}
        for stage in _CONTROLLED_ROLL_STAGES:
            face = self.manual_faces[stage]
            if face is not None and (
                not isinstance(face, int) or isinstance(face, bool)
            ):
                raise ValueError("Manual faces must be integers or null.")
            manual_faces[stage] = face
        if self.dice_mode is ClientDiceMode.AUTOMATIC and any(
            face is not None for face in manual_faces.values()
        ):
            raise ValueError(
                "Automatic requests cannot inject authoritative dice faces."
            )
        object.__setattr__(
            self,
            "occurred_at",
            _canonical_time(self.occurred_at, "Round occurrence time"),
        )
        object.__setattr__(
            self, "roll_ids", _freeze_json(roll_ids, "Round roll IDs")
        )
        object.__setattr__(
            self,
            "manual_faces",
            _freeze_json(manual_faces, "Round manual faces"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command.to_dict(),
            "dice_mode": self.dice_mode.value,
            "event": self.event.to_dict(),
            "manual_faces": _thaw_json(self.manual_faces),
            "occurred_at": _serialized_time(self.occurred_at),
            "operation": self.operation.to_dict(),
            "roll_ids": _thaw_json(self.roll_ids),
            "version": self.version.value,
        }


@dataclass(frozen=True)
class OperationCorrelationRequest(_ContractValue):
    version: ContractVersion
    operation: AuthorityReference
    command: AuthorityReference

    def __post_init__(self) -> None:
        _validate_operation_references(
            self.version, self.operation, self.command
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command.to_dict(),
            "operation": self.operation.to_dict(),
            "version": self.version.value,
        }


@dataclass(frozen=True)
class OperationView(_ContractValue):
    version: ContractVersion
    operation: AuthorityReference
    command: AuthorityReference
    submission: SubmissionState
    mechanics: MechanicalState
    durable_commit: DurableCommitState
    local_publication: LocalPublicationState
    projection: ProjectionState
    synchronization: SynchronizationState
    presentation_status: PresentationState = PresentationState.NOT_REQUESTED
    events: tuple[SequencedEventReference, ...] = ()
    mechanical_details: Mapping[str, Any] = field(default_factory=dict)
    presentation: Optional[TransientPresentation] = None
    diagnostic: Optional[ClientDiagnostic] = None

    def __post_init__(self) -> None:
        _validate_operation_references(
            self.version, self.operation, self.command
        )
        for value, expected_type, label in (
            (self.submission, SubmissionState, "submission"),
            (self.mechanics, MechanicalState, "mechanics"),
            (self.durable_commit, DurableCommitState, "durable commitment"),
            (
                self.local_publication,
                LocalPublicationState,
                "local publication",
            ),
            (self.projection, ProjectionState, "projection"),
            (
                self.synchronization,
                SynchronizationState,
                "synchronization",
            ),
            (
                self.presentation_status,
                PresentationState,
                "presentation",
            ),
        ):
            if not isinstance(value, expected_type):
                raise ValueError(f"Operation {label} state must be typed.")
        events = tuple(self.events)
        if any(not isinstance(item, SequencedEventReference) for item in events):
            raise ValueError("Operation events must be sequenced references.")
        if len({item.event for item in events}) != len(events):
            raise ValueError("Operation event references must be unique.")
        if tuple(item.sequence for item in events) != tuple(
            sorted(item.sequence for item in events)
        ):
            raise ValueError("Operation event references must be ordered.")
        if not isinstance(self.mechanical_details, Mapping):
            raise ValueError("Operation mechanical details must be an object.")
        if self.presentation is not None and not isinstance(
            self.presentation, TransientPresentation
        ):
            raise ValueError("Operation presentation must be typed.")
        if self.diagnostic is not None and not isinstance(
            self.diagnostic, ClientDiagnostic
        ):
            raise ValueError("Operation diagnostic must be typed.")

        if self.submission is SubmissionState.REJECTED:
            if (
                self.mechanics is not MechanicalState.NOT_ATTEMPTED
                or events
                or self.durable_commit is not DurableCommitState.NOT_APPLICABLE
                or self.local_publication
                is not LocalPublicationState.NOT_APPLICABLE
                or self.projection is not ProjectionState.NOT_APPLICABLE
                or self.presentation_status
                is not PresentationState.NOT_REQUESTED
            ):
                raise ValueError(
                    "Rejected submissions cannot claim authoritative progress."
                )
        if self.mechanics is MechanicalState.INPUT_REQUIRED and (
            events
            or self.durable_commit is not DurableCommitState.NOT_APPLICABLE
            or self.local_publication
            is not LocalPublicationState.NOT_APPLICABLE
            or self.projection is not ProjectionState.NOT_APPLICABLE
        ):
            raise ValueError(
                "Input-required operations cannot claim authoritative events."
            )
        if self.durable_commit is DurableCommitState.COMMITTED and not events:
            raise ValueError("Committed operations require durable event evidence.")
        if (
            self.local_publication is LocalPublicationState.PUBLISHED
            and self.durable_commit is not DurableCommitState.COMMITTED
        ):
            raise ValueError(
                "Local publication requires confirmed durable commitment."
            )
        if (
            self.projection is ProjectionState.PROJECTED
            and self.local_publication is not LocalPublicationState.PUBLISHED
        ):
            raise ValueError("Projection requires local event publication.")
        if self.presentation_status is PresentationState.SUCCEEDED:
            if (
                self.presentation is None
                or self.mechanics is not MechanicalState.SUCCEEDED
                or self.synchronization
                is not SynchronizationState.SYNCHRONIZED
            ):
                raise ValueError(
                    "Successful presentation requires synchronized mechanics."
                )
        elif self.presentation is not None:
            raise ValueError(
                "Only successful presentation may expose transient text."
            )
        if (
            self.presentation_status is PresentationState.FAILED
            and self.mechanics is not MechanicalState.SUCCEEDED
        ):
            raise ValueError(
                "Presentation failure must remain separate from successful mechanics."
            )
        object.__setattr__(self, "events", events)
        object.__setattr__(
            self,
            "mechanical_details",
            _freeze_json(self.mechanical_details, "Mechanical details"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command.to_dict(),
            "diagnostic": (
                None if self.diagnostic is None else self.diagnostic.to_dict()
            ),
            "durable_commit": self.durable_commit.value,
            "events": [item.to_dict() for item in self.events],
            "local_publication": self.local_publication.value,
            "mechanical_details": _thaw_json(self.mechanical_details),
            "mechanics": self.mechanics.value,
            "operation": self.operation.to_dict(),
            "presentation": (
                None if self.presentation is None else self.presentation.to_dict()
            ),
            "presentation_status": self.presentation_status.value,
            "projection": self.projection.value,
            "submission": self.submission.value,
            "synchronization": self.synchronization.value,
            "version": self.version.value,
        }
