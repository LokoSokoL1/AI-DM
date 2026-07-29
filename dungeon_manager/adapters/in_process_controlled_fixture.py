"""In-process adapter from the controlled runtimes to client-neutral M1 views."""

from __future__ import annotations

from typing import Any, Optional, Protocol

from dungeon_manager.application.contracts import (
    AuthorityReference,
    ClientDiagnostic,
    ClientDiceMode,
    ContractVersion,
    ControlledFixtureView,
    DiagnosticCode,
    DurableCommitState,
    IdentityKind,
    LocalPublicationState,
    MechanicalState,
    OperationCorrelationRequest,
    OperationView,
    PresentationState,
    ProjectionState,
    ResolveControlledRoundRequest,
    SelectPlayerCharacterRequest,
    SequencedEventReference,
    SubmissionState,
    SynchronizationState,
    TransientPresentation,
)
from dungeon_manager.campaign_runtime import CampaignRuntime
from dungeon_manager.combat_runtime import (
    CombatCompositionStatus,
    compose_controlled_combat_domain,
)
from dungeon_manager.controlled_round_runtime import (
    ControlledRoundRuntime,
    ControlledRoundRuntimeResult,
    ControlledRoundRuntimeStatus,
)
from dungeon_manager.engine.audited_pipeline import (
    AuditIntegrationStatus,
    AuditedCommandPipelineResult,
    EventPublicationDisposition,
    ProjectionDisposition,
)
from dungeon_manager.engine.dice import AutomaticFaceSource, DiceRollMode
from dungeon_manager.engine.durable_journal import (
    DurableJournalHealthStatus,
    DurablePublicationStatus,
)
from dungeon_manager.engine.policy_gated_dispatcher import (
    PolicyGatedDispatchStatus,
)
from dungeon_manager.engine.result import GameResultStatus
from dungeon_manager.engine.world_state_holder import (
    WorldStateSynchronizationStatus,
)


class _TransientPresentationPort(Protocol):
    def narrate(self, result: Any) -> Any:
        ...


_INPUT_REQUIRED_STATUSES = {
    ControlledRoundRuntimeStatus.INITIATIVE_INPUT_REQUIRED,
    ControlledRoundRuntimeStatus.ATTACK_INPUT_REQUIRED,
    ControlledRoundRuntimeStatus.DAMAGE_INPUT_REQUIRED,
}


def _reference(kind: IdentityKind, value: str) -> AuthorityReference:
    return AuthorityReference(kind, value)


def _event_reference(event_id: str, sequence: int) -> SequencedEventReference:
    return SequencedEventReference(
        _reference(IdentityKind.EVENT, event_id), sequence
    )


def _events_from_pipeline(
    result: AuditedCommandPipelineResult,
) -> tuple[SequencedEventReference, ...]:
    if result.published_event_entries:
        return tuple(
            _event_reference(entry.event.event_id, entry.sequence)
            for entry in result.published_event_entries
        )
    durable = result.durable_publication
    gated = result.policy_gated_result
    game_result = None if gated is None else gated.game_result
    if (
        durable.durable_commit_confirmed
        and durable.previous_tail is not None
        and game_result is not None
    ):
        return tuple(
            _event_reference(event.event_id, durable.previous_tail + index)
            for index, event in enumerate(game_result.events, start=1)
        )
    return ()


def _submission_state(
    result: AuditedCommandPipelineResult,
) -> SubmissionState:
    gated = result.policy_gated_result
    if (
        result.audit_status is AuditIntegrationStatus.PRE_DISPATCH_AUDIT_FAILURE
        or gated is None
    ):
        return SubmissionState.REJECTED
    if gated.status is PolicyGatedDispatchStatus.DISPATCHED:
        return SubmissionState.ACCEPTED
    if gated.status is PolicyGatedDispatchStatus.COORDINATOR_FAILURE:
        return SubmissionState.UNKNOWN
    return SubmissionState.REJECTED


def _durable_state(
    result: AuditedCommandPipelineResult,
) -> DurableCommitState:
    status = result.durable_publication.status
    if result.durable_publication.durable_commit_confirmed:
        return DurableCommitState.COMMITTED
    if status in {
        DurablePublicationStatus.NOT_APPLICABLE,
        DurablePublicationStatus.NO_EVENTS,
        DurablePublicationStatus.NOT_CONFIGURED,
    }:
        return DurableCommitState.NOT_APPLICABLE
    return DurableCommitState.NOT_COMMITTED


def _local_publication_state(
    result: AuditedCommandPipelineResult,
) -> LocalPublicationState:
    if (
        result.publication_disposition
        is EventPublicationDisposition.PUBLISHED
    ):
        return LocalPublicationState.PUBLISHED
    if (
        result.durable_publication.durable_commit_confirmed
        or result.publication_disposition is EventPublicationDisposition.FAILED
    ):
        return LocalPublicationState.NOT_PUBLISHED
    return LocalPublicationState.NOT_APPLICABLE


def _projection_state(
    result: AuditedCommandPipelineResult,
) -> ProjectionState:
    return {
        ProjectionDisposition.NOT_APPLICABLE: ProjectionState.NOT_APPLICABLE,
        ProjectionDisposition.UNCHANGED: ProjectionState.NOT_APPLICABLE,
        ProjectionDisposition.PROJECTED: ProjectionState.PROJECTED,
        ProjectionDisposition.FAILED: ProjectionState.FAILED,
        ProjectionDisposition.UNAVAILABLE: ProjectionState.FAILED,
    }[result.projection_disposition]


def _synchronization_state(
    runtime: CampaignRuntime,
    result: Optional[AuditedCommandPipelineResult] = None,
) -> SynchronizationState:
    durable_health = (
        runtime.pipeline.durable_journal_health
        if result is None
        else result.durable_journal_health
    )
    projection_health = runtime.state_holder.health
    if (
        durable_health.status is DurableJournalHealthStatus.SYNCHRONIZED
        and projection_health.status
        is WorldStateSynchronizationStatus.SYNCHRONIZED
        and durable_health.durable_tail == durable_health.local_tail
        and projection_health.committed_sequence
        == projection_health.journal_sequence
        and durable_health.local_tail == projection_health.journal_sequence
    ):
        return SynchronizationState.SYNCHRONIZED
    return SynchronizationState.OUT_OF_SYNC


def _diagnostic_for(
    *,
    submission: SubmissionState,
    mechanics: MechanicalState,
    durable: DurableCommitState,
    publication: LocalPublicationState,
    projection: ProjectionState,
    synchronization: SynchronizationState,
) -> Optional[ClientDiagnostic]:
    if submission is SubmissionState.REJECTED:
        return ClientDiagnostic(DiagnosticCode.SUBMISSION_REJECTED)
    if submission is SubmissionState.UNKNOWN:
        return ClientDiagnostic(DiagnosticCode.INTERNAL_FAILURE)
    if mechanics is MechanicalState.FAILED:
        return ClientDiagnostic(DiagnosticCode.MECHANICAL_FAILURE)
    if durable is DurableCommitState.NOT_COMMITTED:
        return ClientDiagnostic(DiagnosticCode.DURABLE_COMMIT_FAILURE)
    if (
        durable is DurableCommitState.COMMITTED
        and publication is LocalPublicationState.NOT_PUBLISHED
    ):
        return ClientDiagnostic(DiagnosticCode.LOCAL_PUBLICATION_FAILURE)
    if projection is ProjectionState.FAILED:
        return ClientDiagnostic(DiagnosticCode.PROJECTION_FAILURE)
    if synchronization is SynchronizationState.OUT_OF_SYNC:
        return ClientDiagnostic(DiagnosticCode.SYNCHRONIZATION_FAILURE)
    return None


def _operation_from_pipeline(
    runtime: CampaignRuntime,
    request: Any,
    pipeline: AuditedCommandPipelineResult,
    mechanics: MechanicalState,
    details: Any,
) -> OperationView:
    submission = _submission_state(pipeline)
    if submission is SubmissionState.REJECTED:
        mechanics = MechanicalState.NOT_ATTEMPTED
    elif submission is SubmissionState.UNKNOWN:
        mechanics = MechanicalState.UNKNOWN
    durable = _durable_state(pipeline)
    publication = _local_publication_state(pipeline)
    projection = _projection_state(pipeline)
    synchronization = _synchronization_state(runtime, pipeline)
    return OperationView(
        version=request.version,
        operation=request.operation,
        command=request.command,
        submission=submission,
        mechanics=mechanics,
        durable_commit=durable,
        local_publication=publication,
        projection=projection,
        synchronization=synchronization,
        events=_events_from_pipeline(pipeline),
        mechanical_details=details if isinstance(details, dict) else {},
        diagnostic=_diagnostic_for(
            submission=submission,
            mechanics=mechanics,
            durable=durable,
            publication=publication,
            projection=projection,
            synchronization=synchronization,
        ),
    )


class InProcessControlledFixtureAdapter:
    """Translate one real controlled runtime without relocating authority."""

    def __init__(
        self,
        runtime: CampaignRuntime,
        *,
        automatic_source: Optional[AutomaticFaceSource] = None,
        presentation: Optional[_TransientPresentationPort] = None,
    ) -> None:
        if not isinstance(runtime, CampaignRuntime):
            raise ValueError(
                "In-process controlled fixture adapter requires a runtime."
            )
        if automatic_source is not None and not isinstance(
            automatic_source, AutomaticFaceSource
        ):
            raise ValueError("Automatic dice source is invalid.")
        if presentation is not None and not callable(
            getattr(presentation, "narrate", None)
        ):
            raise ValueError("Transient presentation port is invalid.")
        self.__runtime = runtime
        self.__automatic_source = automatic_source
        self.__presentation = presentation
        self.__round_runtime: Optional[ControlledRoundRuntime] = None

    @property
    def transient_presentation_available(self) -> bool:
        return self.__presentation is not None

    def inspect(self) -> ControlledFixtureView:
        runtime = self.__runtime
        state = runtime.state_holder.snapshot
        actors = tuple(
            _reference(IdentityKind.ACTOR, participant_id)
            for participant_id in runtime.participant_ids
        )
        selectable = tuple(
            _reference(IdentityKind.ACTOR, participant_id)
            for participant_id
            in runtime.definition.selectable_player_character_ids
        )
        selected = runtime.selected_player_character_id
        entries = runtime.event_journal.entries
        return ControlledFixtureView(
            version=ContractVersion.V1,
            campaign=_reference(
                IdentityKind.CAMPAIGN, runtime.definition.campaign_id
            ),
            scene=_reference(IdentityKind.SCENE, runtime.current_scene_id),
            actors=actors,
            selectable_player_characters=selectable,
            selected_player_character=(
                None
                if selected is None
                else _reference(IdentityKind.ACTOR, selected)
            ),
            events=tuple(
                _event_reference(entry.event.event_id, entry.sequence)
                for entry in entries
            ),
            journal_tail=runtime.event_journal.tail_sequence,
            projection_sequence=state.last_sequence,
            synchronization=_synchronization_state(runtime),
            controlled_round_resolved="controlled_combat" in state.data,
        )

    def select_player_character(
        self, request: SelectPlayerCharacterRequest
    ) -> OperationView:
        if not isinstance(request, SelectPlayerCharacterRequest):
            raise ValueError("Selection request must be typed.")
        pipeline = self.__runtime.select_player_character(
            request.actor.value,
            command_id=request.command.value,
            event_id=request.event.value,
            occurred_at=request.occurred_at,
        )
        if not isinstance(pipeline, AuditedCommandPipelineResult):
            raise ValueError("Selection pipeline result is invalid.")
        gated = pipeline.policy_gated_result
        game_result = None if gated is None else gated.game_result
        details = (
            {}
            if game_result is None or game_result.output is None
            else dict(game_result.output)
        )
        mechanics = MechanicalState.FAILED
        if (
            game_result is not None
            and game_result.status is GameResultStatus.SUCCESS
            and details.get("outcome") in {"selected", "already_selected"}
        ):
            mechanics = MechanicalState.SUCCEEDED
        return _operation_from_pipeline(
            self.__runtime, request, pipeline, mechanics, details
        )

    def resolve_controlled_round(
        self, request: ResolveControlledRoundRequest
    ) -> OperationView:
        if not isinstance(request, ResolveControlledRoundRequest):
            raise ValueError("Controlled-round request must be typed.")
        if self.__round_runtime is None:
            composition = compose_controlled_combat_domain(self.__runtime)
            if composition.status is not CombatCompositionStatus.SUCCESS:
                return OperationView(
                    version=request.version,
                    operation=request.operation,
                    command=request.command,
                    submission=SubmissionState.REJECTED,
                    mechanics=MechanicalState.NOT_ATTEMPTED,
                    durable_commit=DurableCommitState.NOT_APPLICABLE,
                    local_publication=LocalPublicationState.NOT_APPLICABLE,
                    projection=ProjectionState.NOT_APPLICABLE,
                    synchronization=_synchronization_state(self.__runtime),
                    diagnostic=ClientDiagnostic(
                        DiagnosticCode.SUBMISSION_REJECTED
                    ),
                )
            self.__round_runtime = ControlledRoundRuntime(
                self.__runtime, composition.domain
            )
        result = self.__round_runtime.resolve(
            command_id=request.command.value,
            event_id=request.event.value,
            occurred_at=request.occurred_at,
            mode={
                ClientDiceMode.MANUAL: DiceRollMode.MANUAL,
                ClientDiceMode.AUTOMATIC: DiceRollMode.AUTOMATIC,
            }[request.dice_mode],
            roll_ids=dict(request.roll_ids),
            manual_faces=dict(request.manual_faces),
            automatic_source=self.__automatic_source,
        )
        if not isinstance(result, ControlledRoundRuntimeResult) or not isinstance(
            result.pipeline_result, AuditedCommandPipelineResult
        ):
            raise ValueError("Controlled-round pipeline result is invalid.")
        if result.status in _INPUT_REQUIRED_STATUSES:
            mechanics = MechanicalState.INPUT_REQUIRED
        elif result.status in {
            ControlledRoundRuntimeStatus.SUCCESS,
            ControlledRoundRuntimeStatus.ALREADY_RESOLVED,
        }:
            mechanics = MechanicalState.SUCCEEDED
        elif (
            result.status is ControlledRoundRuntimeStatus.PUBLICATION_FAILURE
            and result.details.get("outcome") == "resolved"
        ):
            mechanics = MechanicalState.SUCCEEDED
        else:
            mechanics = MechanicalState.FAILED
        operation = _operation_from_pipeline(
            self.__runtime,
            request,
            result.pipeline_result,
            mechanics,
            dict(result.details),
        )
        if (
            operation.mechanics is not MechanicalState.SUCCEEDED
            or self.__presentation is None
            or not operation.events
            or operation.synchronization
            is not SynchronizationState.SYNCHRONIZED
        ):
            return operation
        try:
            presented = self.__presentation.narrate(result)
            if getattr(getattr(presented, "status", None), "value", None) != (
                "success"
            ):
                raise ValueError("Presentation did not succeed.")
            source = _event_reference(
                presented.source_event_id, presented.source_event_sequence
            )
            if source not in operation.events:
                raise ValueError("Presentation source does not match.")
            presentation = TransientPresentation(presented.text, source)
        except Exception:
            return OperationView(
                **{
                    **operation.__dict__,
                    "presentation_status": PresentationState.FAILED,
                    "diagnostic": ClientDiagnostic(
                        DiagnosticCode.PRESENTATION_FAILURE
                    ),
                }
            )
        return OperationView(
            **{
                **operation.__dict__,
                "presentation_status": PresentationState.SUCCEEDED,
                "presentation": presentation,
            }
        )

    def reconstruct_operation(
        self, request: OperationCorrelationRequest
    ) -> OperationView:
        if not isinstance(request, OperationCorrelationRequest):
            raise ValueError("Operation correlation request must be typed.")
        matching = tuple(
            entry
            for entry in self.__runtime.event_journal.entries
            if entry.event.originating_command_id == request.command.value
        )
        if not matching:
            return OperationView(
                version=request.version,
                operation=request.operation,
                command=request.command,
                submission=SubmissionState.UNKNOWN,
                mechanics=MechanicalState.UNKNOWN,
                durable_commit=DurableCommitState.UNKNOWN,
                local_publication=LocalPublicationState.UNKNOWN,
                projection=ProjectionState.UNKNOWN,
                synchronization=_synchronization_state(self.__runtime),
                diagnostic=ClientDiagnostic(
                    DiagnosticCode.CORRELATION_NOT_FOUND
                ),
            )
        synchronization = _synchronization_state(self.__runtime)
        projected = (
            self.__runtime.state_holder.snapshot.last_sequence
            >= matching[-1].sequence
        )
        return OperationView(
            version=request.version,
            operation=request.operation,
            command=request.command,
            submission=SubmissionState.ACCEPTED,
            mechanics=MechanicalState.SUCCEEDED,
            durable_commit=DurableCommitState.COMMITTED,
            local_publication=LocalPublicationState.PUBLISHED,
            projection=(
                ProjectionState.PROJECTED
                if projected
                else ProjectionState.NOT_PROJECTED
            ),
            synchronization=synchronization,
            events=tuple(
                _event_reference(entry.event.event_id, entry.sequence)
                for entry in matching
            ),
        )
