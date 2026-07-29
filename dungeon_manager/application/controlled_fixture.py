"""Headless client-neutral façade for the existing controlled fixture."""

from __future__ import annotations

from typing import Any

from .contracts import (
    CapabilityDescriptor,
    CapabilityKey,
    CapabilityReason,
    CapabilityStatus,
    ClientDiagnostic,
    ContractVersion,
    ControlledFixtureView,
    DiagnosticCode,
    DurableCommitState,
    LocalPublicationState,
    MechanicalState,
    OperationCorrelationRequest,
    OperationView,
    PresentationState,
    ProjectionState,
    ResolveControlledRoundRequest,
    SelectPlayerCharacterRequest,
    SubmissionState,
    SynchronizationState,
)
from .ports import ControlledFixtureAuthorityPort


class ControlledFixtureUnavailableError(RuntimeError):
    """A sanitized failure to inspect the in-process controlled fixture."""


def _validate_version(version: Any) -> ContractVersion:
    if not isinstance(version, ContractVersion):
        raise ValueError("Unknown client-neutral contract version.")
    return version


class ControlledFixtureFacade:
    """Fail-closed application boundary with no client or provider dependency."""

    def __init__(self, authority: ControlledFixtureAuthorityPort) -> None:
        if not isinstance(authority, ControlledFixtureAuthorityPort):
            raise ValueError(
                "Controlled fixture façade requires an authority port."
            )
        self.__authority = authority

    def inspect(
        self, version: ContractVersion = ContractVersion.V1
    ) -> ControlledFixtureView:
        _validate_version(version)
        try:
            view = self.__authority.inspect()
        except Exception as error:
            raise ControlledFixtureUnavailableError(
                "Controlled fixture inspection is unavailable."
            ) from None
        if (
            not isinstance(view, ControlledFixtureView)
            or view.version is not version
        ):
            raise ControlledFixtureUnavailableError(
                "Controlled fixture inspection is unavailable."
            )
        return view

    def capability(
        self,
        key: CapabilityKey,
        version: ContractVersion = ContractVersion.V1,
    ) -> CapabilityDescriptor:
        _validate_version(version)
        if not isinstance(key, CapabilityKey):
            raise ValueError("Unknown client-neutral capability key.")
        view = self.inspect(version)
        if key is CapabilityKey.CONTROLLED_GOBLIN_ACTION:
            return CapabilityDescriptor(
                version,
                key,
                CapabilityStatus.UNSUPPORTED,
                CapabilityReason.CONTROLLED_FIXTURE_HAS_NO_GOBLIN_ACTION,
            )
        if key is CapabilityKey.RESOLVE_CONTROLLED_ROUND:
            if view.controlled_round_resolved:
                return CapabilityDescriptor(
                    version,
                    key,
                    CapabilityStatus.UNAVAILABLE,
                    CapabilityReason.ROUND_ALREADY_RESOLVED,
                )
            if view.selected_player_character is None:
                return CapabilityDescriptor(
                    version,
                    key,
                    CapabilityStatus.UNAVAILABLE,
                    CapabilityReason.PLAYER_SELECTION_REQUIRED,
                )
        if key is CapabilityKey.VERIFIED_TRANSIENT_NARRATION and not (
            self.__authority.transient_presentation_available
        ):
            return CapabilityDescriptor(
                version,
                key,
                CapabilityStatus.UNAVAILABLE,
                CapabilityReason.PRESENTATION_NOT_CONFIGURED,
            )
        return CapabilityDescriptor(version, key, CapabilityStatus.SUPPORTED)

    def capabilities(
        self, version: ContractVersion = ContractVersion.V1
    ) -> tuple[CapabilityDescriptor, ...]:
        _validate_version(version)
        return tuple(self.capability(key, version) for key in CapabilityKey)

    def select_player_character(
        self, request: SelectPlayerCharacterRequest
    ) -> OperationView:
        if not isinstance(request, SelectPlayerCharacterRequest):
            raise ValueError("Selection request must be typed.")
        _validate_version(request.version)
        try:
            result = self.__authority.select_player_character(request)
        except Exception:
            return self._unknown_failure(request)
        return self._validated_result(request, result)

    def resolve_controlled_round(
        self, request: ResolveControlledRoundRequest
    ) -> OperationView:
        if not isinstance(request, ResolveControlledRoundRequest):
            raise ValueError("Controlled-round request must be typed.")
        _validate_version(request.version)
        try:
            result = self.__authority.resolve_controlled_round(request)
        except Exception:
            return self._unknown_failure(request)
        return self._validated_result(request, result)

    def reconstruct_operation(
        self, request: OperationCorrelationRequest
    ) -> OperationView:
        if not isinstance(request, OperationCorrelationRequest):
            raise ValueError("Operation correlation request must be typed.")
        _validate_version(request.version)
        try:
            result = self.__authority.reconstruct_operation(request)
        except Exception:
            return self._unknown_failure(request)
        return self._validated_result(request, result)

    @staticmethod
    def _validated_result(request: Any, result: Any) -> OperationView:
        if (
            not isinstance(result, OperationView)
            or result.version is not request.version
            or result.operation != request.operation
            or result.command != request.command
        ):
            return ControlledFixtureFacade._unknown_failure(request)
        return result

    @staticmethod
    def _unknown_failure(request: Any) -> OperationView:
        return OperationView(
            version=request.version,
            operation=request.operation,
            command=request.command,
            submission=SubmissionState.UNKNOWN,
            mechanics=MechanicalState.UNKNOWN,
            durable_commit=DurableCommitState.UNKNOWN,
            local_publication=LocalPublicationState.UNKNOWN,
            projection=ProjectionState.UNKNOWN,
            synchronization=SynchronizationState.UNKNOWN,
            presentation_status=PresentationState.UNKNOWN,
            diagnostic=ClientDiagnostic(DiagnosticCode.INTERNAL_FAILURE),
        )
