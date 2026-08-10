"""Phase 2 M3 coordinator beneath authorization and above M1 authority."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, Optional

from .contracts import (
    DiagnosticCode,
    DurableCommitState,
    OperationCorrelationRequest,
    OperationView,
    ResolveControlledRoundRequest,
    SelectPlayerCharacterRequest,
)
from .controlled_fixture import ControlledFixtureFacade
from .durable_operation_contracts import (
    CampaignOperationKey,
    CanonicalOperationIdentity,
    DurableOperationContractVersion,
    DurableOperationDiagnostic,
    DurableOperationDiagnosticCode,
    DurableOperationKind,
    DurableOperationLifecycle,
    DurableOperationSubmission,
    DurableReplayDisposition,
    DurableStoreDisposition,
    DurableTerminalOutcome,
)
from .durable_operation_ports import DurableOperationStorePort
from .permission_contracts import (
    ActorReference,
    CampaignReference,
    ParticipantReference,
)


_INCOMPATIBLE = {
    DurableStoreDisposition.INCOMPATIBLE,
}
_UNAVAILABLE = {
    DurableStoreDisposition.MALFORMED,
    DurableStoreDisposition.UNAVAILABLE,
}


def _terminal_outcome(operation: OperationView) -> DurableTerminalOutcome:
    value = operation.to_dict()
    diagnostic = value["diagnostic"]
    if isinstance(diagnostic, Mapping) and diagnostic.get("code") == (
        DiagnosticCode.PRESENTATION_FAILURE.value
    ):
        diagnostic = None
    return DurableTerminalOutcome(
        {
            "command": value["command"],
            "diagnostic": diagnostic,
            "durable_commit": value["durable_commit"],
            "events": value["events"],
            "local_publication": value["local_publication"],
            "mechanical_details": value["mechanical_details"],
            "mechanics": value["mechanics"],
            "operation": value["operation"],
            "projection": value["projection"],
            "submission": value["submission"],
            "synchronization": value["synchronization"],
            "version": value["version"],
        }
    )


class DurableOperationCoordinator:
    """Claim durable identity before delegating at most once to M1."""

    def __init__(
        self,
        authority: ControlledFixtureFacade,
        store: DurableOperationStorePort,
    ) -> None:
        if not isinstance(authority, ControlledFixtureFacade):
            raise ValueError("Durable coordinator requires the M1 facade.")
        if not isinstance(store, DurableOperationStorePort):
            raise ValueError("Durable operation store port is invalid.")
        self.__authority = authority
        self.__store = store

    def select_player_character(
        self,
        participant: ParticipantReference,
        campaign: CampaignReference,
        actor: ActorReference,
        request: SelectPlayerCharacterRequest,
    ) -> DurableOperationSubmission:
        if not isinstance(request, SelectPlayerCharacterRequest):
            raise ValueError("Selection request must be typed.")
        return self._submit(
            participant,
            campaign,
            actor,
            DurableOperationKind.SELECT_PLAYER_CHARACTER,
            request,
            self.__authority.select_player_character,
        )

    def resolve_controlled_round(
        self,
        participant: ParticipantReference,
        campaign: CampaignReference,
        actor: ActorReference,
        request: ResolveControlledRoundRequest,
    ) -> DurableOperationSubmission:
        if not isinstance(request, ResolveControlledRoundRequest):
            raise ValueError("Controlled-round request must be typed.")
        return self._submit(
            participant,
            campaign,
            actor,
            DurableOperationKind.RESOLVE_CONTROLLED_ROUND,
            request,
            self.__authority.resolve_controlled_round,
        )

    def _submit(
        self,
        participant: ParticipantReference,
        campaign: CampaignReference,
        actor: ActorReference,
        kind: DurableOperationKind,
        request: Any,
        delegate: Callable[[Any], OperationView],
    ) -> DurableOperationSubmission:
        if not isinstance(participant, ParticipantReference):
            raise ValueError("Resolved participant must be typed.")
        if not isinstance(campaign, CampaignReference):
            raise ValueError("Campaign must be typed.")
        if not isinstance(actor, ActorReference):
            raise ValueError("Target actor must be typed.")
        key = CampaignOperationKey(
            DurableOperationContractVersion.V1,
            campaign.value,
            request.operation.value,
        )
        identity = CanonicalOperationIdentity(
            DurableOperationContractVersion.V1,
            key,
            participant.value,
            kind,
            request.version.value,
            actor.value,
            request.to_dict(),
        )
        try:
            reservation = self.__store.reserve(identity)
        except Exception:
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.STORE_UNAVAILABLE,
            )
        if reservation.disposition is DurableStoreDisposition.COLLISION:
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.KEY_COLLISION,
                disposition=DurableReplayDisposition.COLLISION,
            )
        if reservation.disposition in _INCOMPATIBLE:
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.INCOMPATIBLE_STORE,
            )
        if reservation.disposition in _UNAVAILABLE:
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.STORE_UNAVAILABLE,
            )
        if reservation.disposition not in {
            DurableStoreDisposition.RESERVED,
            DurableStoreDisposition.EXACT,
        } or reservation.record is None:
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.STORE_UNAVAILABLE,
            )
        record = reservation.record
        if record.identity != identity:
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.KEY_COLLISION,
                disposition=DurableReplayDisposition.COLLISION,
            )
        if record.lifecycle is DurableOperationLifecycle.TERMINAL:
            return DurableOperationSubmission(
                DurableOperationContractVersion.V1,
                key,
                kind,
                DurableReplayDisposition.REPLAYED,
                DurableOperationLifecycle.TERMINAL,
                record.terminal_outcome,
            )
        if record.lifecycle is DurableOperationLifecycle.DISPATCH_STARTED:
            return self._recover_or_strand(identity, request)
        return self._claim_and_delegate(identity, request, delegate)

    def _claim_and_delegate(
        self,
        identity: CanonicalOperationIdentity,
        request: Any,
        delegate: Callable[[Any], OperationView],
    ) -> DurableOperationSubmission:
        key = identity.key
        kind = identity.kind
        try:
            marked = self.__store.mark_dispatch_started(identity)
        except Exception:
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.STORE_UNAVAILABLE,
            )
        if marked.disposition in _INCOMPATIBLE:
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.INCOMPATIBLE_STORE,
            )
        if marked.disposition in _UNAVAILABLE:
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.STORE_UNAVAILABLE,
            )
        if (
            marked.disposition is not DurableStoreDisposition.SUCCESS
            or marked.record is None
            or marked.record.lifecycle
            is not DurableOperationLifecycle.DISPATCH_STARTED
        ):
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.RECOVERY_REQUIRED,
                disposition=DurableReplayDisposition.RECOVERY_REQUIRED,
                lifecycle=DurableOperationLifecycle.DISPATCH_STARTED,
            )
        try:
            operation = delegate(request)
        except Exception:
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.RECOVERY_REQUIRED,
                disposition=DurableReplayDisposition.RECOVERY_REQUIRED,
                lifecycle=DurableOperationLifecycle.DISPATCH_STARTED,
            )
        if not isinstance(operation, OperationView):
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.RECOVERY_REQUIRED,
                disposition=DurableReplayDisposition.RECOVERY_REQUIRED,
                lifecycle=DurableOperationLifecycle.DISPATCH_STARTED,
            )
        outcome = _terminal_outcome(operation)
        try:
            terminal = self.__store.record_terminal(identity, outcome)
        except Exception:
            terminal = None
        if (
            terminal is None
            or terminal.disposition is not DurableStoreDisposition.SUCCESS
            or terminal.record is None
            or terminal.record.lifecycle is not DurableOperationLifecycle.TERMINAL
        ):
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.RECOVERY_REQUIRED,
                disposition=DurableReplayDisposition.RECOVERY_REQUIRED,
                lifecycle=DurableOperationLifecycle.DISPATCH_STARTED,
            )
        presentation = {
            "diagnostic": (
                operation.diagnostic.to_dict()
                if operation.diagnostic is not None
                and operation.diagnostic.code is DiagnosticCode.PRESENTATION_FAILURE
                else None
            ),
            "status": operation.presentation_status.value,
            "value": (
                None
                if operation.presentation is None
                else operation.presentation.to_dict()
            ),
        }
        return DurableOperationSubmission(
            DurableOperationContractVersion.V1,
            key,
            kind,
            DurableReplayDisposition.DELEGATED,
            DurableOperationLifecycle.TERMINAL,
            outcome,
            transient_presentation=presentation,
        )

    def _recover_or_strand(
        self,
        identity: CanonicalOperationIdentity,
        request: Any,
    ) -> DurableOperationSubmission:
        key = identity.key
        kind = identity.kind
        correlation = OperationCorrelationRequest(
            request.version,
            request.operation,
            request.command,
        )
        try:
            reconstructed = self.__authority.reconstruct_operation(correlation)
        except Exception:
            reconstructed = None
        if (
            not isinstance(reconstructed, OperationView)
            or reconstructed.durable_commit is not DurableCommitState.COMMITTED
            or not reconstructed.events
        ):
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.RECOVERY_REQUIRED,
                disposition=DurableReplayDisposition.RECOVERY_REQUIRED,
                lifecycle=DurableOperationLifecycle.DISPATCH_STARTED,
            )
        outcome = _terminal_outcome(reconstructed)
        try:
            terminal = self.__store.record_terminal(identity, outcome)
        except Exception:
            terminal = None
        if (
            terminal is None
            or terminal.disposition is not DurableStoreDisposition.SUCCESS
            or terminal.record is None
            or terminal.record.lifecycle is not DurableOperationLifecycle.TERMINAL
        ):
            return self._failure(
                key,
                kind,
                DurableOperationDiagnosticCode.RECOVERY_REQUIRED,
                disposition=DurableReplayDisposition.RECOVERY_REQUIRED,
                lifecycle=DurableOperationLifecycle.DISPATCH_STARTED,
            )
        return DurableOperationSubmission(
            DurableOperationContractVersion.V1,
            key,
            kind,
            DurableReplayDisposition.REPLAYED,
            DurableOperationLifecycle.TERMINAL,
            outcome,
        )

    @staticmethod
    def _failure(
        key: CampaignOperationKey,
        kind: DurableOperationKind,
        code: DurableOperationDiagnosticCode,
        *,
        disposition: DurableReplayDisposition = DurableReplayDisposition.UNAVAILABLE,
        lifecycle: DurableOperationLifecycle = DurableOperationLifecycle.RESERVED,
    ) -> DurableOperationSubmission:
        return DurableOperationSubmission(
            DurableOperationContractVersion.V1,
            key,
            kind,
            disposition,
            lifecycle,
            diagnostic=DurableOperationDiagnostic(code),
        )
