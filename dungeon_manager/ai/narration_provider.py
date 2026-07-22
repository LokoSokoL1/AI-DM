"""Dedicated tool-free provider contract for verified presentation text."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from dungeon_manager.engine._json import validate_trimmed_identifier
from dungeon_manager.engine.verified_narration import VerifiedNarrationPacket


MAX_NARRATION_TEXT_LENGTH = 4000


class NarrationProviderStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(frozen=True)
class NarrationProviderResult:
    status: NarrationProviderStatus
    source_event_id: str
    source_event_sequence: int
    text: Optional[str] = None
    reason_code: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, NarrationProviderStatus):
            raise ValueError("Narration provider status must be typed.")
        validate_trimmed_identifier(self.source_event_id, "Narration provider source event ID")
        if (
            not isinstance(self.source_event_sequence, int)
            or isinstance(self.source_event_sequence, bool)
            or self.source_event_sequence < 1
        ):
            raise ValueError("Narration provider source event sequence must be positive.")
        if self.status is NarrationProviderStatus.SUCCESS:
            if (
                not isinstance(self.text, str)
                or not self.text.strip()
                or self.text != self.text.strip()
                or len(self.text) > MAX_NARRATION_TEXT_LENGTH
                or "\x00" in self.text
                or self.reason_code is not None
            ):
                raise ValueError("Successful narration provider text is invalid.")
        else:
            if self.text is not None:
                raise ValueError("Failed narration provider results cannot contain text.")
            validate_trimmed_identifier(self.reason_code, "Narration provider reason code")

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code,
            "source_event_id": self.source_event_id,
            "source_event_sequence": self.source_event_sequence,
            "status": self.status.value,
            "text": self.text,
        }


class NarrationProvider(ABC):
    """One-shot narration only; no tools, commands, runtime, or storage access."""

    @abstractmethod
    def narrate(self, packet: VerifiedNarrationPacket) -> NarrationProviderResult:
        """Return transient presentation text for one verified packet."""
