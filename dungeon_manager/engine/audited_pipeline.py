"""Safe in-memory audit integration for policy-gated command dispatch."""

import logging
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock, local
from typing import Any, Optional

from ._json import validate_trimmed_identifier
from ._time import utc_now
from .audit import AuditStage, CommandAuditRecord
from .automation import (
    GateDisposition,
    GateReasonCode,
    HumanApprovalDecision,
    PolicyDecision,
)
from .command import GameCommand
from .journals import (
    CommandAuditJournal,
    CommandAuditJournalEntry,
    GameEventJournal,
    GameEventJournalEntry,
)
from .policy_gated_dispatcher import (
    PolicyGatedCommandDispatcher,
    PolicyGatedDispatchResult,
    PolicyGatedDispatchStatus,
)
from .world_state import (
    WorldStateProjectionResult,
    WorldStateProjectionStatus,
    WorldStateProjector,
)
from .world_state_holder import (
    ProjectionReasonCode,
    WorldStateHealth,
    WorldStateHolder,
    WorldStateSynchronizationStatus,
)


logger = logging.getLogger("DungeonManager")

AuditRecordIdFactory = Callable[[], str]
UtcClock = Callable[[], datetime]

_PRE_DISPATCH_AUDIT_ERROR = (
    "Audit recording failed before engine dispatch; the command was not "
    "dispatched."
)
_POST_DISPATCH_AUDIT_ERROR = (
    "Audit recording failed after engine dispatch; the command was not "
    "retried."
)
_EVENT_PUBLICATION_ERROR = (
    "Event publication failed after engine dispatch; the command and event "
    "batch were not retried."
)
_PROJECTION_FAILURE_ERROR = (
    "World-state projection failed after event publication; the command and "
    "reducer were not retried."
)
_PROJECTION_UNAVAILABLE_ERROR = (
    "World-state projection is unavailable; the command was not dispatched."
)
_REENTRANT_PIPELINE_ERROR = (
    "Re-entrant audited pipeline invocation was rejected before dispatch."
)
_INTEGRATION_ERROR = "The audited command pipeline failed safely."

_INVALID_APPROVAL_REASONS = {
    GateReasonCode.INVALID_APPROVAL,
    GateReasonCode.APPROVAL_COMMAND_MISMATCH,
    GateReasonCode.UNEXPECTED_APPROVAL,
}


def _generate_audit_record_id() -> str:
    return str(uuid.uuid4())


class AuditIntegrationStatus(str, Enum):
    """Outcome of audit integration around one command submission."""

    COMPLETED = "completed"
    PRE_DISPATCH_AUDIT_FAILURE = "pre_dispatch_audit_failure"
    POST_DISPATCH_AUDIT_FAILURE = "post_dispatch_audit_failure"
    CONTROLLED_INTEGRATION_FAILURE = "controlled_integration_failure"


class EventPublicationDisposition(str, Enum):
    """Outcome of event publication for one audited command submission."""

    NOT_APPLICABLE = "not_applicable"
    NO_EVENTS = "no_events"
    PUBLISHED = "published"
    FAILED = "failed"


class ProjectionDisposition(str, Enum):
    """Outcome of world-state projection for one pipeline submission."""

    NOT_APPLICABLE = "not_applicable"
    UNCHANGED = "unchanged"
    PROJECTED = "projected"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AuditedCommandPipelineResult:
    """Immutable audit outcome preserving any authoritative dispatch result."""

    command_id: str
    audit_status: AuditIntegrationStatus
    publication_disposition: EventPublicationDisposition
    projection_disposition: ProjectionDisposition
    projection_sequence: int
    projection_previous_sequence: int
    projection_target_sequence: int
    policy_gated_result: Optional[PolicyGatedDispatchResult] = None
    audit_entries: tuple[CommandAuditJournalEntry, ...] = field(
        default_factory=tuple
    )
    published_event_entries: tuple[GameEventJournalEntry, ...] = field(
        default_factory=tuple
    )
    error: Optional[str] = None
    publication_error: Optional[str] = None
    projection_error: Optional[str] = None
    projection_reason_code: Optional[ProjectionReasonCode] = None
    projector_status: Optional[WorldStateProjectionStatus] = None

    def __post_init__(self) -> None:
        validate_trimmed_identifier(
            self.command_id,
            "Audited pipeline command ID",
        )
        if not isinstance(self.audit_status, AuditIntegrationStatus):
            raise ValueError(
                "Audit integration status must be an "
                "AuditIntegrationStatus value."
            )
        if not isinstance(
            self.publication_disposition,
            EventPublicationDisposition,
        ):
            raise ValueError(
                "Event publication disposition must be an "
                "EventPublicationDisposition value."
            )
        if not isinstance(
            self.projection_disposition,
            ProjectionDisposition,
        ):
            raise ValueError(
                "Projection disposition must be a ProjectionDisposition "
                "value."
            )
        for sequence, label in (
            (self.projection_sequence, "Projection committed sequence"),
            (
                self.projection_previous_sequence,
                "Projection previous sequence",
            ),
            (self.projection_target_sequence, "Projection target sequence"),
        ):
            if (
                not isinstance(sequence, int)
                or isinstance(sequence, bool)
                or sequence < 0
            ):
                raise ValueError(f"{label} must be a non-negative integer.")
        if self.projection_reason_code is not None and not isinstance(
            self.projection_reason_code,
            ProjectionReasonCode,
        ):
            raise ValueError(
                "Projection reason code must be a ProjectionReasonCode value."
            )
        if self.projector_status is not None and not isinstance(
            self.projector_status,
            WorldStateProjectionStatus,
        ):
            raise ValueError(
                "Projector status must be a WorldStateProjectionStatus value."
            )

        if self.policy_gated_result is not None:
            if not isinstance(
                self.policy_gated_result,
                PolicyGatedDispatchResult,
            ):
                raise ValueError(
                    "Audited pipeline dispatch result must be a "
                    "PolicyGatedDispatchResult value."
                )
            if self.policy_gated_result.command_id != self.command_id:
                raise ValueError(
                    "Audited pipeline dispatch result must match the "
                    "command ID."
                )

        try:
            entries = tuple(self.audit_entries)
        except TypeError as error:
            raise ValueError(
                "Audited pipeline entries must be an iterable snapshot."
            ) from error
        for entry in entries:
            if not isinstance(entry, CommandAuditJournalEntry):
                raise ValueError(
                    "Audited pipeline entries must contain command-audit "
                    "journal entries."
                )
            entry.record.validate()
            if entry.record.command_id != self.command_id:
                raise ValueError(
                    "Audited pipeline entries must match the command ID."
                )
        object.__setattr__(self, "audit_entries", entries)

        try:
            published_entries = tuple(self.published_event_entries)
        except TypeError as error:
            raise ValueError(
                "Published event entries must be an iterable snapshot."
            ) from error
        for entry in published_entries:
            if not isinstance(entry, GameEventJournalEntry):
                raise ValueError(
                    "Published event entries must contain game-event journal "
                    "entries."
                )
            entry.event.validate()
        object.__setattr__(
            self,
            "published_event_entries",
            published_entries,
        )

        self._validate_publication()
        self._validate_projection()

        if self.audit_status is AuditIntegrationStatus.COMPLETED:
            if self.policy_gated_result is None:
                raise ValueError(
                    "Completed audit integration requires a dispatch result."
                )
            if self.error is not None:
                raise ValueError(
                    "Completed audit integration must not contain an error."
                )
            return

        validate_trimmed_identifier(
            self.error,
            "Audited pipeline error",
        )
        if (
            self.audit_status
            is AuditIntegrationStatus.PRE_DISPATCH_AUDIT_FAILURE
            and self.policy_gated_result is not None
            and self.policy_gated_result.dispatch_attempted
        ):
            raise ValueError(
                "Pre-dispatch audit failures cannot preserve an attempted "
                "dispatch result."
            )
        if (
            self.audit_status
            is AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE
            and (
                self.policy_gated_result is None
                or not self.policy_gated_result.dispatch_attempted
            )
        ):
            raise ValueError(
                "Post-dispatch audit failures require the attempted dispatch "
                "result."
            )

    def to_dict(self) -> dict[str, Any]:
        """Return an independent defensive JSON-compatible representation."""

        return {
            "audit_entries": [
                entry.to_dict() for entry in self.audit_entries
            ],
            "audit_status": self.audit_status.value,
            "command_id": self.command_id,
            "error": self.error,
            "publication_disposition": self.publication_disposition.value,
            "publication_error": self.publication_error,
            "projection_disposition": self.projection_disposition.value,
            "projection_error": self.projection_error,
            "projection_previous_sequence": self.projection_previous_sequence,
            "projection_reason_code": (
                None
                if self.projection_reason_code is None
                else self.projection_reason_code.value
            ),
            "projection_sequence": self.projection_sequence,
            "projection_target_sequence": self.projection_target_sequence,
            "projector_status": (
                None
                if self.projector_status is None
                else self.projector_status.value
            ),
            "published_event_entries": [
                entry.to_dict() for entry in self.published_event_entries
            ],
            "policy_gated_result": (
                None
                if self.policy_gated_result is None
                else self.policy_gated_result.to_dict()
            ),
        }

    def _validate_publication(self) -> None:
        dispatched_result = None
        if (
            self.policy_gated_result is not None
            and self.policy_gated_result.status
            is PolicyGatedDispatchStatus.DISPATCHED
        ):
            dispatched_result = self.policy_gated_result.game_result

        if (
            self.publication_disposition
            is EventPublicationDisposition.NOT_APPLICABLE
        ):
            if dispatched_result is not None:
                raise ValueError(
                    "Dispatched results require an applicable publication "
                    "disposition."
                )
            if self.published_event_entries or self.publication_error is not None:
                raise ValueError(
                    "Non-applicable publication cannot contain entries or an "
                    "error."
                )
            return

        if dispatched_result is None:
            raise ValueError(
                "Applicable event publication requires a dispatched result."
            )

        events = dispatched_result.events
        if (
            self.publication_disposition
            is EventPublicationDisposition.NO_EVENTS
        ):
            if events:
                raise ValueError(
                    "No-events publication requires an empty event result."
                )
            if self.published_event_entries or self.publication_error is not None:
                raise ValueError(
                    "No-events publication cannot contain entries or an error."
                )
            return

        if not events:
            raise ValueError(
                "Published or failed event publication requires result events."
            )

        if (
            self.publication_disposition
            is EventPublicationDisposition.PUBLISHED
        ):
            if self.publication_error is not None:
                raise ValueError(
                    "Successful event publication must not contain an error."
                )
            if len(self.published_event_entries) != len(events):
                raise ValueError(
                    "Published event entries must match the complete event "
                    "batch."
                )
            if any(
                entry.event is not event
                for entry, event in zip(
                    self.published_event_entries,
                    events,
                )
            ):
                raise ValueError(
                    "Published event entries must preserve the result events "
                    "in order."
                )
            first_sequence = self.published_event_entries[0].sequence
            if tuple(
                entry.sequence for entry in self.published_event_entries
            ) != tuple(
                range(first_sequence, first_sequence + len(events))
            ):
                raise ValueError(
                    "Published event entries must have contiguous sequences."
                )
            return

        if self.publication_disposition is EventPublicationDisposition.FAILED:
            if self.published_event_entries:
                raise ValueError(
                    "Failed event publication cannot contain appended entries."
                )
            validate_trimmed_identifier(
                self.publication_error,
                "Event publication error",
            )
            if (
                self.audit_status
                is not AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE
            ):
                raise ValueError(
                    "Failed event publication uses the post-dispatch failure "
                    "classification."
                )
            return

        raise ValueError("Unsupported event publication disposition.")

    def _validate_projection(self) -> None:
        disposition = self.projection_disposition
        if disposition is ProjectionDisposition.NOT_APPLICABLE:
            if self.publication_disposition not in {
                EventPublicationDisposition.NOT_APPLICABLE,
                EventPublicationDisposition.FAILED,
            }:
                raise ValueError(
                    "Non-applicable projection requires no successful event "
                    "publication."
                )
            if (
                self.projection_sequence
                != self.projection_previous_sequence
                or self.projection_target_sequence
                != self.projection_previous_sequence
            ):
                raise ValueError(
                    "Non-applicable projection cannot change sequences."
                )
            if any(
                value is not None
                for value in (
                    self.projection_error,
                    self.projection_reason_code,
                    self.projector_status,
                )
            ):
                raise ValueError(
                    "Non-applicable projection cannot contain projection "
                    "failure metadata."
                )
            return

        if disposition is ProjectionDisposition.UNCHANGED:
            if (
                self.publication_disposition
                is not EventPublicationDisposition.NO_EVENTS
            ):
                raise ValueError(
                    "Unchanged projection requires an eventless dispatched "
                    "result."
                )
            if not (
                self.projection_sequence
                == self.projection_previous_sequence
                == self.projection_target_sequence
            ):
                raise ValueError(
                    "Unchanged projection requires identical sequences."
                )
            if any(
                value is not None
                for value in (
                    self.projection_error,
                    self.projection_reason_code,
                    self.projector_status,
                )
            ):
                raise ValueError(
                    "Unchanged projection cannot contain failure metadata."
                )
            return

        if disposition is ProjectionDisposition.PROJECTED:
            if (
                self.publication_disposition
                is not EventPublicationDisposition.PUBLISHED
                or self.projector_status
                is not WorldStateProjectionStatus.SUCCESS
                or self.projection_reason_code is not None
                or self.projection_error is not None
                or self.projection_target_sequence
                != self.projection_sequence
                or self.projection_target_sequence
                <= self.projection_previous_sequence
            ):
                raise ValueError(
                    "Projected disposition requires one complete successful "
                    "projection."
                )
            if (
                not self.published_event_entries
                or self.published_event_entries[0].sequence
                != self.projection_previous_sequence + 1
                or self.published_event_entries[-1].sequence
                != self.projection_target_sequence
            ):
                raise ValueError(
                    "Projected disposition must match the published entry "
                    "range."
                )
            return

        if disposition is ProjectionDisposition.FAILED:
            if (
                self.publication_disposition
                is not EventPublicationDisposition.PUBLISHED
                or self.audit_status
                is not AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE
                or self.projection_sequence
                != self.projection_previous_sequence
                or self.projection_target_sequence
                <= self.projection_previous_sequence
                or not self.published_event_entries
                or self.published_event_entries[-1].sequence
                != self.projection_target_sequence
                or self.projection_reason_code not in {
                    ProjectionReasonCode.PROJECTION_FAILED,
                    ProjectionReasonCode.PROJECTOR_CONTRACT_FAILURE,
                }
            ):
                raise ValueError(
                    "Failed projection must preserve the previous state after "
                    "a published entry batch."
                )
            validate_trimmed_identifier(
                self.projection_error,
                "Projection error",
            )
            if self.projector_status is WorldStateProjectionStatus.SUCCESS:
                raise ValueError(
                    "Failed projection cannot report projector success."
                )
            return

        if disposition is ProjectionDisposition.UNAVAILABLE:
            if (
                self.publication_disposition
                is not EventPublicationDisposition.NOT_APPLICABLE
                or self.projection_sequence
                != self.projection_previous_sequence
                or self.projection_reason_code is None
                or self.projector_status is WorldStateProjectionStatus.SUCCESS
                or (
                    self.policy_gated_result is not None
                    and self.policy_gated_result.dispatch_attempted
                )
            ):
                raise ValueError(
                    "Unavailable projection must fail closed before dispatch."
                )
            validate_trimmed_identifier(
                self.projection_error,
                "Projection error",
            )
            return

        raise ValueError("Unsupported projection disposition.")


class _AuditAppendFailure(Exception):
    """Internal signal that one required audit append failed."""


class _EventPublicationFailure(Exception):
    """Internal signal that one atomic event batch publication failed."""


class _ProjectionFailure(Exception):
    """Internal signal that published entries could not be projected."""


class _AuditedLifecycleRecorder:
    """Translate authoritative lifecycle observations into safe records."""

    def __init__(
        self,
        command: GameCommand,
        journal: CommandAuditJournal,
        event_journal: GameEventJournal,
        projector: WorldStateProjector,
        state_holder: WorldStateHolder,
        audit_record_id_factory: AuditRecordIdFactory,
        clock: UtcClock,
    ) -> None:
        self._command = command
        self._journal = journal
        self._event_journal = event_journal
        self._projector = projector
        self._state_holder = state_holder
        self._audit_record_id_factory = audit_record_id_factory
        self._clock = clock
        self._entries: tuple[CommandAuditJournalEntry, ...] = ()
        self._published_event_entries: tuple[
            GameEventJournalEntry,
            ...,
        ] = ()
        self._publication_disposition = (
            EventPublicationDisposition.NOT_APPLICABLE
        )
        self._publication_error: Optional[str] = None
        health = state_holder.health
        self._projection_disposition = ProjectionDisposition.NOT_APPLICABLE
        self._projection_previous_sequence = health.committed_sequence
        self._projection_target_sequence = health.committed_sequence
        self._projection_error: Optional[str] = None
        self._projection_reason_code: Optional[ProjectionReasonCode] = None
        self._projector_status: Optional[WorldStateProjectionStatus] = None
        self._dispatch_result: Optional[PolicyGatedDispatchResult] = None
        self._engine_boundary_crossed = False

    @property
    def entries(self) -> tuple[CommandAuditJournalEntry, ...]:
        return self._entries

    @property
    def dispatch_result(self) -> Optional[PolicyGatedDispatchResult]:
        return self._dispatch_result

    @property
    def publication_disposition(self) -> EventPublicationDisposition:
        return self._publication_disposition

    @property
    def published_event_entries(self) -> tuple[GameEventJournalEntry, ...]:
        return self._published_event_entries

    @property
    def publication_error(self) -> Optional[str]:
        return self._publication_error

    @property
    def projection_disposition(self) -> ProjectionDisposition:
        return self._projection_disposition

    @property
    def projection_sequence(self) -> int:
        return self._state_holder.health.committed_sequence

    @property
    def projection_previous_sequence(self) -> int:
        return self._projection_previous_sequence

    @property
    def projection_target_sequence(self) -> int:
        return self._projection_target_sequence

    @property
    def projection_error(self) -> Optional[str]:
        return self._projection_error

    @property
    def projection_reason_code(self) -> Optional[ProjectionReasonCode]:
        return self._projection_reason_code

    @property
    def projector_status(self) -> Optional[WorldStateProjectionStatus]:
        return self._projector_status

    @property
    def engine_boundary_crossed(self) -> bool:
        return self._engine_boundary_crossed

    def command_proposed(self) -> None:
        self._append(AuditStage.COMMAND_PROPOSED, "received")

    def prepare_projection_unavailable(self, health: WorldStateHealth) -> None:
        if (
            not isinstance(health, WorldStateHealth)
            or health.status
            is not WorldStateSynchronizationStatus.OUT_OF_SYNC
            or health.reason_code is None
        ):
            raise ValueError(
                "Unavailable projection requires out-of-sync health."
            )
        self._projection_disposition = ProjectionDisposition.UNAVAILABLE
        self._projection_previous_sequence = health.committed_sequence
        self._projection_target_sequence = health.journal_sequence
        self._projection_error = _PROJECTION_UNAVAILABLE_ERROR
        self._projection_reason_code = health.reason_code
        self._projector_status = health.projector_status

    def record_projection_unavailable(self) -> None:
        if (
            self._projection_disposition
            is not ProjectionDisposition.UNAVAILABLE
            or self._projection_reason_code is None
        ):
            raise ValueError("Projection unavailability was not prepared.")
        self._append(
            AuditStage.COORDINATOR_FAILURE,
            "projection_unavailable",
            {
                "committed_sequence": self._projection_previous_sequence,
                "journal_sequence": self._projection_target_sequence,
                "projection_disposition": (
                    ProjectionDisposition.UNAVAILABLE.value
                ),
                "projection_reason_code": self._projection_reason_code.value,
                "projector_status": (
                    None
                    if self._projector_status is None
                    else self._projector_status.value
                ),
            },
        )

    def policy_evaluated(
        self,
        command: GameCommand,
        decision: PolicyDecision,
    ) -> None:
        self._append(
            AuditStage.POLICY_EVALUATED,
            decision.mode.value,
            {
                "mode": decision.mode.value,
                "reason_code": decision.reason_code.value,
            },
        )

    def gate_resolved(
        self,
        command: GameCommand,
        decision: PolicyDecision,
        approval: Optional[HumanApprovalDecision],
        disposition: GateDisposition,
    ) -> None:
        if approval is not None or decision.requires_human_confirmation:
            outcome, details = self._approval_details(
                decision,
                approval,
                disposition,
            )
            self._append(
                AuditStage.APPROVAL_EVALUATED,
                outcome,
                details,
            )

        self._append(
            AuditStage.GATE_RESOLVED,
            disposition.status.value,
            {
                "gate_disposition": disposition.status.value,
                "reason_code": disposition.reason_code.value,
            },
        )

    def dispatch_blocked(
        self,
        command: GameCommand,
        result: PolicyGatedDispatchResult,
    ) -> None:
        self._dispatch_result = result
        self._append(
            AuditStage.DISPATCH_BLOCKED,
            result.status.value,
            {"gated_dispatch_status": result.status.value},
        )

    def dispatch_attempted(
        self,
        command: GameCommand,
        decision: PolicyDecision,
        approval: Optional[HumanApprovalDecision],
        disposition: GateDisposition,
    ) -> None:
        self._append(
            AuditStage.DISPATCH_ATTEMPTED,
            "attempted",
            {"gate_disposition": disposition.status.value},
        )

    def dispatch_completed(
        self,
        command: GameCommand,
        result: PolicyGatedDispatchResult,
    ) -> None:
        self._dispatch_result = result
        self._engine_boundary_crossed = True
        game_result = result.game_result
        if game_result is None:
            raise _AuditAppendFailure from None

        events = game_result.events
        if not events:
            self._publication_disposition = (
                EventPublicationDisposition.NO_EVENTS
            )
            health = self._state_holder.health
            self._projection_disposition = ProjectionDisposition.UNCHANGED
            self._projection_previous_sequence = health.committed_sequence
            self._projection_target_sequence = health.committed_sequence
        else:
            self._publish_event_batch(events)
            self._project_published_entries()

        self._append(
            AuditStage.DISPATCH_COMPLETED,
            game_result.status.value,
            {
                "game_result_status": game_result.status.value,
                "gated_dispatch_status": result.status.value,
            },
        )

    def _publish_event_batch(self, events: tuple[Any, ...]) -> None:
        try:
            entries = self._event_journal.append_batch(events)
            if not isinstance(entries, tuple):
                raise ValueError(
                    "Game event journal returned a mutable batch snapshot."
                )
            if len(entries) != len(events):
                raise ValueError(
                    "Game event journal returned an incomplete batch snapshot."
                )
            for entry, event in zip(entries, events):
                if (
                    not isinstance(entry, GameEventJournalEntry)
                    or entry.event is not event
                ):
                    raise ValueError(
                        "Game event journal returned an invalid batch entry."
                    )
        except Exception:
            logger.error(
                "Required game event publication failed safely "
                "(command_id=%s, event_count=%s)",
                self._command.command_id,
                len(events),
            )
            self._publication_disposition = (
                EventPublicationDisposition.FAILED
            )
            self._publication_error = _EVENT_PUBLICATION_ERROR
            try:
                self._append(
                    AuditStage.COORDINATOR_FAILURE,
                    "event_publication_failed",
                    {
                        "event_count": len(events),
                        "phase": "event_publication",
                        "publication_disposition": (
                            EventPublicationDisposition.FAILED.value
                        ),
                    },
                )
            except _AuditAppendFailure:
                pass
            raise _EventPublicationFailure from None

        self._published_event_entries = entries
        self._publication_disposition = EventPublicationDisposition.PUBLISHED

    def _project_published_entries(self) -> None:
        state = self._state_holder.snapshot
        previous_sequence = state.last_sequence
        target_sequence = self._published_event_entries[-1].sequence
        self._projection_previous_sequence = previous_sequence
        self._projection_target_sequence = target_sequence

        try:
            projection_result = self._projector.project(
                self._published_event_entries,
                state,
            )
        except Exception:
            logger.error(
                "World-state projector contract failed safely "
                "(command_id=%s, previous_sequence=%s, target_sequence=%s, "
                "event_count=%s)",
                self._command.command_id,
                previous_sequence,
                target_sequence,
                len(self._published_event_entries),
            )
            self._fail_projection(
                ProjectionReasonCode.PROJECTOR_CONTRACT_FAILURE,
                None,
            )

        if not isinstance(projection_result, WorldStateProjectionResult):
            self._fail_projection(
                ProjectionReasonCode.PROJECTOR_CONTRACT_FAILURE,
                None,
            )
        if projection_result.status is not WorldStateProjectionStatus.SUCCESS:
            self._fail_projection(
                ProjectionReasonCode.PROJECTION_FAILED,
                projection_result.status,
            )

        try:
            self._state_holder._commit_projection(
                projection_result,
                expected_previous_sequence=previous_sequence,
                journal_sequence=target_sequence,
            )
        except Exception:
            logger.error(
                "Projected world-state commit failed safely "
                "(command_id=%s, previous_sequence=%s, target_sequence=%s, "
                "event_count=%s)",
                self._command.command_id,
                previous_sequence,
                target_sequence,
                len(self._published_event_entries),
            )
            self._fail_projection(
                ProjectionReasonCode.PROJECTOR_CONTRACT_FAILURE,
                None,
            )

        self._projection_disposition = ProjectionDisposition.PROJECTED
        self._projector_status = WorldStateProjectionStatus.SUCCESS

    def _fail_projection(
        self,
        reason_code: ProjectionReasonCode,
        projector_status: Optional[WorldStateProjectionStatus],
    ) -> None:
        self._projection_disposition = ProjectionDisposition.FAILED
        self._projection_error = _PROJECTION_FAILURE_ERROR
        self._projection_reason_code = reason_code
        self._projector_status = projector_status
        self._state_holder._mark_projection_failure(
            journal_sequence=self._projection_target_sequence,
            reason_code=reason_code,
            projector_status=projector_status,
        )
        try:
            self._append(
                AuditStage.COORDINATOR_FAILURE,
                "world_state_projection_failed",
                {
                    "event_count": len(self._published_event_entries),
                    "phase": "world_state_projection",
                    "previous_sequence": (
                        self._projection_previous_sequence
                    ),
                    "projection_disposition": (
                        ProjectionDisposition.FAILED.value
                    ),
                    "projection_reason_code": reason_code.value,
                    "projector_status": (
                        None
                        if projector_status is None
                        else projector_status.value
                    ),
                    "target_sequence": self._projection_target_sequence,
                },
            )
        except _AuditAppendFailure:
            pass
        raise _ProjectionFailure from None

    def coordinator_failed(
        self,
        command: GameCommand,
        result: PolicyGatedDispatchResult,
    ) -> None:
        self._dispatch_result = result
        self._engine_boundary_crossed = result.dispatch_attempted
        self._append(
            AuditStage.COORDINATOR_FAILURE,
            result.status.value,
            {
                "dispatch_attempted": result.dispatch_attempted,
                "gated_dispatch_status": result.status.value,
            },
        )

    @staticmethod
    def _approval_details(
        decision: PolicyDecision,
        approval: Any,
        disposition: GateDisposition,
    ) -> tuple[str, Mapping[str, Any]]:
        required = decision.requires_human_confirmation
        if approval is None:
            return "not_supplied", {"required": required}

        valid_approval = None
        if isinstance(approval, HumanApprovalDecision):
            try:
                approval.validate()
            except (TypeError, ValueError):
                pass
            else:
                valid_approval = approval

        if (
            valid_approval is None
            or disposition.reason_code in _INVALID_APPROVAL_REASONS
        ):
            details = {"required": required}
            if valid_approval is not None:
                details.update(
                    {
                        "approval_outcome": valid_approval.outcome.value,
                        "approver_id": valid_approval.approver_id,
                    }
                )
            return "invalid", details

        return valid_approval.outcome.value, {
            "approver_id": valid_approval.approver_id,
            "required": required,
        }

    def _append(
        self,
        stage: AuditStage,
        outcome: str,
        details: Optional[Mapping[str, Any]] = None,
    ) -> None:
        try:
            record = CommandAuditRecord(
                audit_record_id=self._audit_record_id_factory(),
                command_id=self._command.command_id,
                command_type=self._command.command_type,
                stage=stage,
                outcome=outcome,
                provenance=self._command.provenance,
                actor_id=self._command.actor_id,
                details=details,
                recorded_at=self._clock(),
            )
            entry = self._journal.append(record)
            if not isinstance(entry, CommandAuditJournalEntry):
                raise ValueError(
                    "Command audit journal returned an invalid entry."
                )
        except Exception:
            logger.error(
                "Required command audit append failed safely "
                "(command_id=%s, stage=%s)",
                self._command.command_id,
                stage.value,
            )
            raise _AuditAppendFailure from None

        self._entries = self._entries + (entry,)


class AuditedCommandPipeline:
    """Audit one authoritative policy-gated dispatch submission in order."""

    def __init__(
        self,
        dispatcher: PolicyGatedCommandDispatcher,
        audit_journal: CommandAuditJournal,
        event_journal: GameEventJournal,
        projector: WorldStateProjector,
        state_holder: WorldStateHolder,
        *,
        audit_record_id_factory: AuditRecordIdFactory = (
            _generate_audit_record_id
        ),
        clock: UtcClock = utc_now,
    ) -> None:
        if not isinstance(dispatcher, PolicyGatedCommandDispatcher):
            raise ValueError(
                "Audited command pipeline requires a policy-gated dispatcher."
            )
        if not isinstance(audit_journal, CommandAuditJournal):
            raise ValueError(
                "Audited command pipeline requires a command audit journal."
            )
        if not isinstance(event_journal, GameEventJournal):
            raise ValueError(
                "Audited command pipeline requires a game event journal."
            )
        if not isinstance(projector, WorldStateProjector):
            raise ValueError(
                "Audited command pipeline requires a world-state projector."
            )
        if not isinstance(state_holder, WorldStateHolder):
            raise ValueError(
                "Audited command pipeline requires a world-state holder."
            )
        if not callable(audit_record_id_factory):
            raise ValueError("Audit record ID factory must be callable.")
        if not callable(clock):
            raise ValueError("Audit clock must be callable.")

        self._dispatcher = dispatcher
        self._audit_journal = audit_journal
        self._event_journal = event_journal
        self._projector = projector
        self._state_holder = state_holder
        self._audit_record_id_factory = audit_record_id_factory
        self._clock = clock
        self._coordination_lock = Lock()
        self._coordination_context = local()

        self._state_holder._check_journal_sequence(
            self._journal_tail_sequence(),
            ProjectionReasonCode.INITIAL_SEQUENCE_MISMATCH,
        )

    def dispatch(
        self,
        command: GameCommand,
        approval: Optional[HumanApprovalDecision] = None,
    ) -> AuditedCommandPipelineResult:
        """Record one safe lifecycle without duplicating dispatch behavior."""

        if not isinstance(command, GameCommand):
            raise TypeError(
                "AuditedCommandPipeline.dispatch requires a GameCommand."
            )

        if getattr(self._coordination_context, "active", False):
            return self._reentrant_result(command)

        with self._coordination_lock:
            self._coordination_context.active = True
            try:
                return self._dispatch_coordinated(command, approval)
            finally:
                self._coordination_context.active = False

    def _dispatch_coordinated(
        self,
        command: GameCommand,
        approval: Optional[HumanApprovalDecision],
    ) -> AuditedCommandPipelineResult:
        recorder = _AuditedLifecycleRecorder(
            command,
            self._audit_journal,
            self._event_journal,
            self._projector,
            self._state_holder,
            self._audit_record_id_factory,
            self._clock,
        )

        health = self._state_holder.health
        if health.status is WorldStateSynchronizationStatus.SYNCHRONIZED:
            self._state_holder._check_journal_sequence(
                self._journal_tail_sequence(),
                ProjectionReasonCode.JOURNAL_SEQUENCE_MISMATCH,
            )
            health = self._state_holder.health

        if health.status is WorldStateSynchronizationStatus.OUT_OF_SYNC:
            recorder.prepare_projection_unavailable(health)
            try:
                recorder.command_proposed()
                recorder.record_projection_unavailable()
            except _AuditAppendFailure:
                return self._result_from_recorder(
                    recorder,
                    AuditIntegrationStatus.PRE_DISPATCH_AUDIT_FAILURE,
                    _PRE_DISPATCH_AUDIT_ERROR,
                )
            return self._result_from_recorder(
                recorder,
                AuditIntegrationStatus.CONTROLLED_INTEGRATION_FAILURE,
                _PROJECTION_UNAVAILABLE_ERROR,
            )

        try:
            recorder.command_proposed()
            dispatch_result = self._dispatcher._dispatch_with_lifecycle(
                command,
                approval,
                recorder,
            )
        except _ProjectionFailure:
            return self._result_from_recorder(
                recorder,
                AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE,
                _PROJECTION_FAILURE_ERROR,
            )
        except _EventPublicationFailure:
            return self._result_from_recorder(
                recorder,
                AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE,
                _EVENT_PUBLICATION_ERROR,
            )
        except _AuditAppendFailure:
            status = (
                AuditIntegrationStatus.POST_DISPATCH_AUDIT_FAILURE
                if recorder.engine_boundary_crossed
                else AuditIntegrationStatus.PRE_DISPATCH_AUDIT_FAILURE
            )
            error = (
                _POST_DISPATCH_AUDIT_ERROR
                if recorder.engine_boundary_crossed
                else _PRE_DISPATCH_AUDIT_ERROR
            )
            return self._result_from_recorder(recorder, status, error)
        except Exception:
            logger.error(
                "Audited command pipeline integration failed safely "
                "(command_id=%s)",
                command.command_id,
            )
            return self._result_from_recorder(
                recorder,
                AuditIntegrationStatus.CONTROLLED_INTEGRATION_FAILURE,
                _INTEGRATION_ERROR,
            )

        return self._result_from_recorder(
            recorder,
            AuditIntegrationStatus.COMPLETED,
            None,
            policy_gated_result=dispatch_result,
        )

    def _result_from_recorder(
        self,
        recorder: _AuditedLifecycleRecorder,
        audit_status: AuditIntegrationStatus,
        error: Optional[str],
        *,
        policy_gated_result: Optional[PolicyGatedDispatchResult] = None,
    ) -> AuditedCommandPipelineResult:
        preserved_result = (
            recorder.dispatch_result
            if policy_gated_result is None
            else policy_gated_result
        )
        return AuditedCommandPipelineResult(
            command_id=recorder._command.command_id,
            audit_status=audit_status,
            publication_disposition=recorder.publication_disposition,
            projection_disposition=recorder.projection_disposition,
            projection_sequence=recorder.projection_sequence,
            projection_previous_sequence=(
                recorder.projection_previous_sequence
            ),
            projection_target_sequence=recorder.projection_target_sequence,
            policy_gated_result=preserved_result,
            audit_entries=recorder.entries,
            published_event_entries=recorder.published_event_entries,
            error=error,
            publication_error=recorder.publication_error,
            projection_error=recorder.projection_error,
            projection_reason_code=recorder.projection_reason_code,
            projector_status=recorder.projector_status,
        )

    def _reentrant_result(
        self,
        command: GameCommand,
    ) -> AuditedCommandPipelineResult:
        health = self._state_holder.health
        return AuditedCommandPipelineResult(
            command_id=command.command_id,
            audit_status=AuditIntegrationStatus.CONTROLLED_INTEGRATION_FAILURE,
            publication_disposition=(
                EventPublicationDisposition.NOT_APPLICABLE
            ),
            projection_disposition=ProjectionDisposition.UNAVAILABLE,
            projection_sequence=health.committed_sequence,
            projection_previous_sequence=health.committed_sequence,
            projection_target_sequence=self._journal_tail_sequence(),
            error=_REENTRANT_PIPELINE_ERROR,
            projection_error=_REENTRANT_PIPELINE_ERROR,
            projection_reason_code=ProjectionReasonCode.REENTRANT_INVOCATION,
            projector_status=health.projector_status,
        )

    def _journal_tail_sequence(self) -> int:
        entries = self._event_journal.entries
        return 0 if not entries else entries[-1].sequence
