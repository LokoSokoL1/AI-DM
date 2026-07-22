"""Eligibility and one-shot invocation boundary for controlled-round narration."""

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Any, Optional

from dungeon_manager.ai.narration_provider import (
    NarrationProvider,
    NarrationProviderResult,
    NarrationProviderStatus,
)
from dungeon_manager.campaign_runtime import CampaignRuntime
from dungeon_manager.controlled_round_runtime import (
    ControlledRoundRuntimeResult,
    ControlledRoundRuntimeStatus,
)
from dungeon_manager.engine._json import validate_trimmed_identifier
from dungeon_manager.engine.audited_pipeline import (
    AuditIntegrationStatus,
    AuditedCommandPipelineResult,
    EventPublicationDisposition,
    ProjectionDisposition,
)
from dungeon_manager.engine.controlled_round import (
    CONTROLLED_ROUND_EVENT,
    CONTROLLED_ROUND_SCHEMA_VERSION,
)
from dungeon_manager.engine.durable_journal import (
    DurableJournalHealthStatus,
    DurablePublicationStatus,
)
from dungeon_manager.engine.verified_narration import (
    NarrationPacketBuildStatus,
    VerifiedNarrationPacket,
    build_verified_narration_packet,
)


class VerifiedNarrationStatus(str, Enum):
    SUCCESS = "success"
    INVALID_INPUT = "invalid_input"
    INELIGIBLE = "ineligible"
    UNSYNCHRONIZED = "unsynchronized"
    SOURCE_MISMATCH = "source_mismatch"
    PROVIDER_FAILURE = "provider_failure"
    INVALID_PROVIDER_RESULT = "invalid_provider_result"
    ALREADY_ATTEMPTED = "already_attempted"


@dataclass(frozen=True)
class VerifiedNarrationResult:
    status: VerifiedNarrationStatus
    source_event_id: Optional[str] = None
    source_event_sequence: Optional[int] = None
    text: Optional[str] = None
    reason_code: Optional[str] = None
    packet: Optional[VerifiedNarrationPacket] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, VerifiedNarrationStatus):
            raise ValueError("Verified narration status must be typed.")
        if self.source_event_id is not None:
            validate_trimmed_identifier(self.source_event_id, "Narration source event ID")
        if self.source_event_sequence is not None and (
            not isinstance(self.source_event_sequence, int)
            or isinstance(self.source_event_sequence, bool)
            or self.source_event_sequence < 1
        ):
            raise ValueError("Narration source event sequence must be positive.")
        if self.status is VerifiedNarrationStatus.SUCCESS:
            if (
                not isinstance(self.packet, VerifiedNarrationPacket)
                or self.packet.source_event_id != self.source_event_id
                or self.packet.source_event_sequence != self.source_event_sequence
                or not isinstance(self.text, str)
                or not self.text
                or self.reason_code is not None
            ):
                raise ValueError("Successful verified narration is invalid.")
        else:
            if self.packet is not None or self.text is not None:
                raise ValueError("Failed verified narration cannot expose text or packet.")
            validate_trimmed_identifier(self.reason_code, "Verified narration reason code")

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code,
            "source_event_id": self.source_event_id,
            "source_event_sequence": self.source_event_sequence,
            "status": self.status.value,
            "text": self.text,
        }


def _failure(
    status: VerifiedNarrationStatus,
    reason_code: str,
    *,
    source_event_id: Optional[str] = None,
    source_event_sequence: Optional[int] = None,
) -> VerifiedNarrationResult:
    return VerifiedNarrationResult(
        status,
        source_event_id,
        source_event_sequence,
        reason_code=reason_code,
    )


class VerifiedNarrationBoundary:
    """Fail-closed bridge from one synchronized result to transient narration."""

    def __init__(self, runtime: CampaignRuntime, provider: NarrationProvider) -> None:
        if not isinstance(runtime, CampaignRuntime):
            raise ValueError("Verified narration requires a campaign runtime.")
        if not isinstance(provider, NarrationProvider):
            raise ValueError("Verified narration requires a narration-only provider.")
        self.__runtime = runtime
        self.__provider = provider
        self.__attempted_event_ids: set[str] = set()
        self.__lock = Lock()

    def narrate(self, result: Any) -> VerifiedNarrationResult:
        if not isinstance(result, ControlledRoundRuntimeResult):
            return _failure(VerifiedNarrationStatus.INVALID_INPUT, "invalid_controlled_round_result")
        if result.status is not ControlledRoundRuntimeStatus.SUCCESS:
            return _failure(VerifiedNarrationStatus.INELIGIBLE, "controlled_round_not_completed")
        pipeline_result = result.pipeline_result
        if not isinstance(pipeline_result, AuditedCommandPipelineResult):
            return _failure(VerifiedNarrationStatus.INELIGIBLE, "missing_pipeline_evidence")
        if (
            pipeline_result.audit_status is not AuditIntegrationStatus.COMPLETED
            or pipeline_result.publication_disposition is not EventPublicationDisposition.PUBLISHED
            or pipeline_result.projection_disposition is not ProjectionDisposition.PROJECTED
            or pipeline_result.durable_publication.status is not DurablePublicationStatus.COMMITTED_SYNCHRONIZED
            or not pipeline_result.durable_publication.durable_commit_confirmed
            or pipeline_result.durable_publication.appended_count != 1
            or pipeline_result.durable_journal_health.status is not DurableJournalHealthStatus.SYNCHRONIZED
            or len(pipeline_result.published_event_entries) != 1
        ):
            return _failure(VerifiedNarrationStatus.INELIGIBLE, "incomplete_pipeline_evidence")
        entry = pipeline_result.published_event_entries[0]
        event = entry.event
        source = {
            "source_event_id": event.event_id,
            "source_event_sequence": entry.sequence,
        }
        if (
            event.event_type != CONTROLLED_ROUND_EVENT
            or event.schema_version != CONTROLLED_ROUND_SCHEMA_VERSION
            or event.originating_command_id != pipeline_result.command_id
            or pipeline_result.projection_sequence != entry.sequence
            or pipeline_result.projection_target_sequence != entry.sequence
            or pipeline_result.durable_publication.resulting_tail != entry.sequence
            or pipeline_result.durable_journal_health.durable_tail != entry.sequence
            or pipeline_result.durable_journal_health.local_tail != entry.sequence
        ):
            return _failure(VerifiedNarrationStatus.SOURCE_MISMATCH, "pipeline_source_mismatch", **source)
        runtime_health = self.__runtime.pipeline.durable_journal_health
        local_entries = self.__runtime.event_journal.entries
        state = self.__runtime.state_holder.snapshot
        if (
            runtime_health.status is not DurableJournalHealthStatus.SYNCHRONIZED
            or runtime_health.durable_tail != entry.sequence
            or runtime_health.local_tail != entry.sequence
            or self.__runtime.event_journal.tail_sequence != entry.sequence
            or state.last_sequence != entry.sequence
            or len(local_entries) != entry.sequence
            or local_entries[-1] is not entry
        ):
            return _failure(VerifiedNarrationStatus.UNSYNCHRONIZED, "runtime_not_synchronized", **source)
        built = build_verified_narration_packet(entry, state)
        if built.status is not NarrationPacketBuildStatus.SUCCESS:
            return _failure(VerifiedNarrationStatus.SOURCE_MISMATCH, built.reason_code or "packet_source_mismatch", **source)
        packet = built.packet
        with self.__lock:
            if event.event_id in self.__attempted_event_ids:
                return _failure(VerifiedNarrationStatus.ALREADY_ATTEMPTED, "narration_already_attempted", **source)
            self.__attempted_event_ids.add(event.event_id)
        try:
            provider_result = self.__provider.narrate(packet)
        except Exception:
            return _failure(VerifiedNarrationStatus.PROVIDER_FAILURE, "narration_provider_failed", **source)
        if (
            not isinstance(provider_result, NarrationProviderResult)
            or provider_result.source_event_id != event.event_id
            or provider_result.source_event_sequence != entry.sequence
        ):
            return _failure(VerifiedNarrationStatus.INVALID_PROVIDER_RESULT, "invalid_provider_result", **source)
        if provider_result.status is NarrationProviderStatus.FAILURE:
            return _failure(VerifiedNarrationStatus.PROVIDER_FAILURE, provider_result.reason_code or "provider_rejected_narration", **source)
        return VerifiedNarrationResult(
            VerifiedNarrationStatus.SUCCESS,
            event.event_id,
            entry.sequence,
            provider_result.text,
            packet=packet,
        )
