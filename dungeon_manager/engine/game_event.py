"""Immutable facts that occurred in the game world."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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


def _generated_occurrence_time() -> datetime:
    return utc_now()


@dataclass(frozen=True)
class GameEvent:
    """A validated data-only fact, separate from command handling results."""

    event_type: str
    provenance: CommandProvenance
    payload: Any = field(default_factory=dict)
    originating_command_id: Optional[str] = None
    actor_id: Optional[str] = None
    schema_version: int = 1
    occurred_at: datetime = field(default_factory=_generated_occurrence_time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "occurred_at",
            canonical_utc_datetime(
                self.occurred_at,
                "Game event occurrence time",
            ),
        )
        object.__setattr__(
            self,
            "payload",
            freeze_json_value(self.payload, "Game event payload"),
        )
        self.validate()

    def validate(self) -> None:
        """Revalidate structure before appending across a journal boundary."""

        validate_trimmed_identifier(self.event_id, "Game event ID")
        validate_trimmed_identifier(self.event_type, "Game event type")
        if (
            not isinstance(self.schema_version, int)
            or isinstance(self.schema_version, bool)
            or self.schema_version < 1
        ):
            raise ValueError(
                "Game event schema version must be a positive integer."
            )
        if not isinstance(self.provenance, CommandProvenance):
            raise ValueError(
                "Game event provenance must be a CommandProvenance value."
            )
        self.provenance.validate()
        validate_optional_identifier(
            self.originating_command_id,
            "Originating command ID",
        )
        validate_optional_identifier(self.actor_id, "Game event actor ID")
        canonical = canonical_utc_datetime(
            self.occurred_at,
            "Game event occurrence time",
        )
        if (
            self.occurred_at.tzinfo is not timezone.utc
            or canonical != self.occurred_at
        ):
            raise ValueError(
                "Game event occurrence time must be canonical UTC."
            )
        freeze_json_value(self.payload, "Game event payload")

    def to_dict(self) -> dict[str, Any]:
        """Return an independent defensive JSON-compatible representation."""

        return {
            "actor_id": self.actor_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": serialize_utc_datetime(self.occurred_at),
            "originating_command_id": self.originating_command_id,
            "payload": thaw_json_value(self.payload),
            "provenance": self.provenance.to_dict(),
            "schema_version": self.schema_version,
        }
