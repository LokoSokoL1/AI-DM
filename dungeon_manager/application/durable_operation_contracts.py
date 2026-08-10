"""Immutable client-neutral contracts for Phase 2 durable operations."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Optional


_MAX_IDENTIFIER_LENGTH = 256
_MAX_CANONICAL_REQUEST_BYTES = 65536


def _identifier(value: Any, label: str) -> str:
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


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        _thaw_json(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class DurableOperationContractVersion(str, Enum):
    V1 = "phase2-m3-v1"


class DurableOperationKind(str, Enum):
    SELECT_PLAYER_CHARACTER = "controlled_fixture.select_player_character"
    RESOLVE_CONTROLLED_ROUND = "controlled_fixture.resolve_controlled_round"


class DurableOperationLifecycle(str, Enum):
    RESERVED = "reserved"
    DISPATCH_STARTED = "dispatch_started"
    TERMINAL = "terminal"


class DurableReplayDisposition(str, Enum):
    DELEGATED = "delegated"
    REPLAYED = "replayed"
    COLLISION = "collision"
    RECOVERY_REQUIRED = "recovery_required"
    UNAVAILABLE = "unavailable"


class DurableOperationDiagnosticCode(str, Enum):
    KEY_COLLISION = "operation_key_collision"
    INCOMPATIBLE_STORE = "operation_store_incompatible"
    STORE_UNAVAILABLE = "operation_store_unavailable"
    RECOVERY_REQUIRED = "operation_recovery_required"


_DIAGNOSTIC_MESSAGES = {
    DurableOperationDiagnosticCode.KEY_COLLISION: (
        "The operation key is already bound to a different request."
    ),
    DurableOperationDiagnosticCode.INCOMPATIBLE_STORE: (
        "The durable operation store is incompatible."
    ),
    DurableOperationDiagnosticCode.STORE_UNAVAILABLE: (
        "The durable operation store is unavailable."
    ),
    DurableOperationDiagnosticCode.RECOVERY_REQUIRED: (
        "The operation may have started and requires explicit recovery."
    ),
}


class DurableStoreDisposition(str, Enum):
    RESERVED = "reserved"
    EXACT = "exact"
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    COLLISION = "collision"
    CONFLICT = "conflict"
    INCOMPATIBLE = "incompatible"
    MALFORMED = "malformed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CampaignOperationKey:
    version: DurableOperationContractVersion
    campaign_id: str
    operation_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.version, DurableOperationContractVersion):
            raise ValueError("Operation-key contract version must be typed.")
        _identifier(self.campaign_id, "Campaign ID")
        _identifier(self.operation_key, "Operation key")

    def to_dict(self) -> dict[str, str]:
        return {
            "campaign_id": self.campaign_id,
            "operation_key": self.operation_key,
            "version": self.version.value,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "CampaignOperationKey":
        if not isinstance(value, Mapping) or set(value) != {
            "campaign_id",
            "operation_key",
            "version",
        }:
            raise ValueError("Stored operation key is malformed.")
        return cls(
            DurableOperationContractVersion(value["version"]),
            value["campaign_id"],
            value["operation_key"],
        )


@dataclass(frozen=True)
class CanonicalOperationIdentity:
    version: DurableOperationContractVersion
    key: CampaignOperationKey
    participant_id: str
    kind: DurableOperationKind
    request_contract_version: str
    actor_id: Optional[str]
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.version, DurableOperationContractVersion):
            raise ValueError("Canonical identity version must be typed.")
        if not isinstance(self.key, CampaignOperationKey):
            raise ValueError("Canonical identity key must be typed.")
        if self.key.version is not self.version:
            raise ValueError("Canonical identity versions must match.")
        _identifier(self.participant_id, "Participant ID")
        if not isinstance(self.kind, DurableOperationKind):
            raise ValueError("Durable operation kind must be typed.")
        _identifier(self.request_contract_version, "Request contract version")
        if self.actor_id is not None:
            _identifier(self.actor_id, "Actor ID")
        if self.kind in {
            DurableOperationKind.SELECT_PLAYER_CHARACTER,
            DurableOperationKind.RESOLVE_CONTROLLED_ROUND,
        } and self.actor_id is None:
            raise ValueError("This operation kind requires a target actor.")
        frozen = _freeze_json(self.payload, "Canonical operation payload")
        object.__setattr__(self, "payload", frozen)
        if len(self.canonical_json.encode("utf-8")) > _MAX_CANONICAL_REQUEST_BYTES:
            raise ValueError("Canonical operation request is too large.")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "key": self.key.to_dict(),
            "kind": self.kind.value,
            "participant_id": self.participant_id,
            "payload": _thaw_json(self.payload),
            "request_contract_version": self.request_contract_version,
            "version": self.version.value,
        }

    @property
    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.canonical_dict(), "fingerprint": self.fingerprint}

    @classmethod
    def from_canonical_json(cls, value: str) -> "CanonicalOperationIdentity":
        if not isinstance(value, str):
            raise ValueError("Stored canonical request is malformed.")
        decoded = json.loads(value)
        if not isinstance(decoded, Mapping) or set(decoded) != {
            "actor_id",
            "key",
            "kind",
            "participant_id",
            "payload",
            "request_contract_version",
            "version",
        }:
            raise ValueError("Stored canonical request is malformed.")
        identity = cls(
            DurableOperationContractVersion(decoded["version"]),
            CampaignOperationKey.from_dict(decoded["key"]),
            decoded["participant_id"],
            DurableOperationKind(decoded["kind"]),
            decoded["request_contract_version"],
            decoded["actor_id"],
            decoded["payload"],
        )
        if identity.canonical_json != value:
            raise ValueError("Stored canonical request is not canonical.")
        return identity


@dataclass(frozen=True)
class DurableTerminalOutcome:
    """Sanitized terminal M1 correlation and mechanics; never presentation text."""

    value: Mapping[str, Any]

    def __post_init__(self) -> None:
        frozen = _freeze_json(self.value, "Durable terminal outcome")
        required = {
            "command",
            "diagnostic",
            "durable_commit",
            "events",
            "local_publication",
            "mechanical_details",
            "mechanics",
            "operation",
            "projection",
            "submission",
            "synchronization",
            "version",
        }
        if not isinstance(frozen, Mapping) or set(frozen) != required:
            raise ValueError("Durable terminal outcome shape is invalid.")
        object.__setattr__(self, "value", frozen)

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json(self.value)

    @property
    def canonical_json(self) -> str:
        return _canonical_json(self.value)

    @classmethod
    def from_json(cls, value: str) -> "DurableTerminalOutcome":
        if not isinstance(value, str):
            raise ValueError("Stored terminal outcome is malformed.")
        decoded = json.loads(value)
        outcome = cls(decoded)
        if outcome.canonical_json != value:
            raise ValueError("Stored terminal outcome is not canonical.")
        return outcome


@dataclass(frozen=True)
class DurableOperationRecord:
    identity: CanonicalOperationIdentity
    lifecycle: DurableOperationLifecycle
    terminal_outcome: Optional[DurableTerminalOutcome] = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, CanonicalOperationIdentity):
            raise ValueError("Durable operation identity must be typed.")
        if not isinstance(self.lifecycle, DurableOperationLifecycle):
            raise ValueError("Durable operation lifecycle must be typed.")
        if self.lifecycle is DurableOperationLifecycle.TERMINAL:
            if not isinstance(self.terminal_outcome, DurableTerminalOutcome):
                raise ValueError("Terminal operation requires terminal evidence.")
        elif self.terminal_outcome is not None:
            raise ValueError("Non-terminal operation cannot contain an outcome.")


@dataclass(frozen=True)
class DurableStoreResult:
    disposition: DurableStoreDisposition
    record: Optional[DurableOperationRecord] = None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, DurableStoreDisposition):
            raise ValueError("Durable store disposition must be typed.")
        if self.record is not None and not isinstance(
            self.record, DurableOperationRecord
        ):
            raise ValueError("Durable store record must be typed.")
        if self.disposition in {
            DurableStoreDisposition.RESERVED,
            DurableStoreDisposition.EXACT,
            DurableStoreDisposition.SUCCESS,
        } and self.record is None:
            raise ValueError("Successful durable store results require a record.")
        if self.disposition not in {
            DurableStoreDisposition.RESERVED,
            DurableStoreDisposition.EXACT,
            DurableStoreDisposition.SUCCESS,
        } and self.record is not None:
            raise ValueError("Failed durable store results cannot disclose a record.")


@dataclass(frozen=True)
class DurableOperationDiagnostic:
    code: DurableOperationDiagnosticCode

    def __post_init__(self) -> None:
        if not isinstance(self.code, DurableOperationDiagnosticCode):
            raise ValueError("Durable operation diagnostic code must be typed.")

    @property
    def message(self) -> str:
        return _DIAGNOSTIC_MESSAGES[self.code]

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True)
class DurableOperationSubmission:
    version: DurableOperationContractVersion
    key: CampaignOperationKey
    kind: DurableOperationKind
    disposition: DurableReplayDisposition
    lifecycle: DurableOperationLifecycle
    terminal_outcome: Optional[DurableTerminalOutcome] = None
    diagnostic: Optional[DurableOperationDiagnostic] = None
    transient_presentation: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.version, DurableOperationContractVersion):
            raise ValueError("Durable submission version must be typed.")
        if not isinstance(self.key, CampaignOperationKey):
            raise ValueError("Durable submission key must be typed.")
        if not isinstance(self.kind, DurableOperationKind):
            raise ValueError("Durable submission kind must be typed.")
        if not isinstance(self.disposition, DurableReplayDisposition):
            raise ValueError("Durable replay disposition must be typed.")
        if not isinstance(self.lifecycle, DurableOperationLifecycle):
            raise ValueError("Durable submission lifecycle must be typed.")
        if self.terminal_outcome is not None and not isinstance(
            self.terminal_outcome, DurableTerminalOutcome
        ):
            raise ValueError("Durable terminal outcome must be typed.")
        if self.diagnostic is not None and not isinstance(
            self.diagnostic, DurableOperationDiagnostic
        ):
            raise ValueError("Durable diagnostic must be typed.")
        if self.disposition in {
            DurableReplayDisposition.DELEGATED,
            DurableReplayDisposition.REPLAYED,
        }:
            if (
                self.lifecycle is not DurableOperationLifecycle.TERMINAL
                or self.terminal_outcome is None
                or self.diagnostic is not None
            ):
                raise ValueError("Completed submissions require terminal evidence.")
        elif self.terminal_outcome is not None:
            raise ValueError("Incomplete submissions cannot disclose an outcome.")
        if self.transient_presentation is not None:
            if self.disposition is not DurableReplayDisposition.DELEGATED:
                raise ValueError("Only new delegation may return presentation text.")
            object.__setattr__(
                self,
                "transient_presentation",
                _freeze_json(
                    self.transient_presentation, "Transient presentation"
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnostic": (
                None if self.diagnostic is None else self.diagnostic.to_dict()
            ),
            "disposition": self.disposition.value,
            "key": self.key.to_dict(),
            "kind": self.kind.value,
            "lifecycle": self.lifecycle.value,
            "terminal_outcome": (
                None
                if self.terminal_outcome is None
                else self.terminal_outcome.to_dict()
            ),
            "transient_presentation": (
                None
                if self.transient_presentation is None
                else _thaw_json(self.transient_presentation)
            ),
            "version": self.version.value,
        }

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())
