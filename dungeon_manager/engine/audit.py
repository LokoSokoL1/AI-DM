"""Immutable safe audit records for future command lifecycle tracing."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ._json import (
    freeze_json_value,
    thaw_json_value,
    validate_optional_identifier,
    validate_trimmed_identifier,
)
from ._time import (
    canonical_utc_datetime,
    serialize_utc_datetime,
    utc_now,
)
from .command import CommandProvenance


class AuditStage(str, Enum):
    """Stable stages in the future policy-gated command lifecycle."""

    COMMAND_PROPOSED = "command_proposed"
    POLICY_EVALUATED = "policy_evaluated"
    APPROVAL_EVALUATED = "approval_evaluated"
    APPROVAL_RECORDED = "approval_recorded"
    GATE_RESOLVED = "gate_resolved"
    DISPATCH_BLOCKED = "dispatch_blocked"
    DISPATCH_ATTEMPTED = "dispatch_attempted"
    DISPATCH_COMPLETED = "dispatch_completed"
    COORDINATOR_FAILURE = "coordinator_failure"


def _generated_recording_time() -> datetime:
    return utc_now()


@dataclass(frozen=True)
class CommandAuditRecord:
    """A data-only trace of one command decision or execution stage."""

    command_id: str
    command_type: str
    stage: AuditStage
    outcome: str
    provenance: CommandProvenance
    actor_id: Optional[str] = None
    details: Optional[Mapping[str, Any]] = None
    recorded_at: datetime = field(default_factory=_generated_recording_time)
    audit_record_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "recorded_at",
            canonical_utc_datetime(
                self.recorded_at,
                "Audit recording time",
            ),
        )
        if self.details is not None:
            if not isinstance(self.details, Mapping):
                raise ValueError("Audit details must be a JSON object.")
            object.__setattr__(
                self,
                "details",
                freeze_json_value(self.details, "Audit details"),
            )
        self.validate()

    def validate(self) -> None:
        """Revalidate structure before appending across a journal boundary."""

        validate_trimmed_identifier(
            self.audit_record_id,
            "Audit record ID",
        )
        validate_trimmed_identifier(self.command_id, "Audit command ID")
        validate_trimmed_identifier(self.command_type, "Audit command type")
        if not isinstance(self.stage, AuditStage):
            raise ValueError("Audit stage must be an AuditStage value.")
        validate_trimmed_identifier(self.outcome, "Audit outcome")
        if not isinstance(self.provenance, CommandProvenance):
            raise ValueError(
                "Audit provenance must be a CommandProvenance value."
            )
        self.provenance.validate()
        validate_optional_identifier(self.actor_id, "Audit actor ID")
        canonical = canonical_utc_datetime(
            self.recorded_at,
            "Audit recording time",
        )
        if (
            self.recorded_at.tzinfo is not timezone.utc
            or canonical != self.recorded_at
        ):
            raise ValueError("Audit recording time must be canonical UTC.")
        if self.details is not None:
            if not isinstance(self.details, Mapping):
                raise ValueError("Audit details must be a JSON object.")
            freeze_json_value(self.details, "Audit details")

    def to_dict(self) -> dict[str, Any]:
        """Return an independent defensive JSON-compatible representation."""

        return {
            "actor_id": self.actor_id,
            "audit_record_id": self.audit_record_id,
            "command_id": self.command_id,
            "command_type": self.command_type,
            "details": (
                None
                if self.details is None
                else thaw_json_value(self.details)
            ),
            "outcome": self.outcome,
            "provenance": self.provenance.to_dict(),
            "recorded_at": serialize_utc_datetime(self.recorded_at),
            "stage": self.stage.value,
        }
