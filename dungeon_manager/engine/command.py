"""Immutable command intentions and their provider-independent provenance."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ._json import (
    freeze_json_value,
    thaw_json_value,
    validate_optional_identifier,
    validate_trimmed_identifier,
)


class CommandSource(str, Enum):
    """The kind of initiator that created a command intention."""

    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"
    EXTERNAL = "external"


@dataclass(frozen=True)
class CommandProvenance:
    """Origin metadata, separate from actor roles and authorization."""

    source: CommandSource
    initiator_id: Optional[str] = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.source, CommandSource):
            raise ValueError("Command source must be a CommandSource value.")
        validate_optional_identifier(
            self.initiator_id,
            "Command initiator ID",
        )

    def to_dict(self) -> dict[str, Optional[str]]:
        """Return an independent JSON-compatible representation."""

        return {
            "source": self.source.value,
            "initiator_id": self.initiator_id,
        }


@dataclass(frozen=True)
class GameCommand:
    """A validated intention that contains no authorization or execution."""

    command_type: str
    provenance: CommandProvenance
    payload: Mapping[str, Any] = field(default_factory=dict)
    actor_id: Optional[str] = None
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        validate_trimmed_identifier(self.command_id, "Command ID")
        validate_trimmed_identifier(self.command_type, "Command type")
        if not isinstance(self.provenance, CommandProvenance):
            raise ValueError(
                "Command provenance must be a CommandProvenance value."
            )
        self.provenance.validate()
        validate_optional_identifier(self.actor_id, "Command actor ID")
        if not isinstance(self.payload, Mapping):
            raise ValueError("Command payload must be a JSON object.")

        object.__setattr__(
            self,
            "payload",
            freeze_json_value(self.payload, "Command payload"),
        )

    def validate(self) -> None:
        """Revalidate structure before dispatching across the trust boundary."""

        validate_trimmed_identifier(self.command_id, "Command ID")
        validate_trimmed_identifier(self.command_type, "Command type")
        if not isinstance(self.provenance, CommandProvenance):
            raise ValueError(
                "Command provenance must be a CommandProvenance value."
            )
        self.provenance.validate()
        validate_optional_identifier(self.actor_id, "Command actor ID")
        if not isinstance(self.payload, Mapping):
            raise ValueError("Command payload must be a JSON object.")
        freeze_json_value(self.payload, "Command payload")

    def to_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible transport representation."""

        return {
            "actor_id": self.actor_id,
            "command_id": self.command_id,
            "command_type": self.command_type,
            "payload": thaw_json_value(self.payload),
            "provenance": self.provenance.to_dict(),
        }
