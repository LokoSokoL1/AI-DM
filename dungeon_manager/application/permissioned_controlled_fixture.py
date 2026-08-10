"""M2 permissioned coordinator around the M1 controlled-fixture façade."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .contracts import (
    CapabilityDescriptor,
    CapabilityKey,
    ControlledFixtureView,
    OperationCorrelationRequest,
    OperationView,
    ResolveControlledRoundRequest,
    SelectPlayerCharacterRequest,
)
from .controlled_fixture import ControlledFixtureFacade
from .durable_operation import DurableOperationCoordinator
from .durable_operation_contracts import DurableOperationSubmission
from .permission_contracts import (
    ActorAssignment,
    ActorReference,
    AudienceScopedEntry,
    CampaignReference,
    PermissionCapability,
    PermissionContractVersion,
    PermissionDecision,
    PermissionGrant,
    PermissionReason,
    PermissionRequest,
    PermissionedView,
    PermissionedViewKind,
    SessionIdentity,
    VisibilityAudience,
    VisibilityEntryKey,
)
from .permission_ports import (
    PermissionStatePort,
    TrustedClockPort,
    TrustedIdentityAuthorityPort,
    VisibilityAuthorityPort,
)
from .permissions import evaluate_permission, filter_visible_entries


_CAPABILITY_PERMISSION = {
    CapabilityKey.INSPECT_CONTROLLED_FIXTURE: PermissionCapability.INSPECT,
    CapabilityKey.SELECT_PLAYER_CHARACTER: (
        PermissionCapability.SELECT_PLAYER_CHARACTER
    ),
    CapabilityKey.RESOLVE_CONTROLLED_ROUND: (
        PermissionCapability.RESOLVE_CONTROLLED_ROUND
    ),
    CapabilityKey.RECONSTRUCT_OPERATION: (
        PermissionCapability.RECONSTRUCT_OPERATION
    ),
    CapabilityKey.VERIFIED_TRANSIENT_NARRATION: (
        PermissionCapability.RESOLVE_CONTROLLED_ROUND
    ),
}


def _denied(
    kind: PermissionedViewKind,
    reason: PermissionReason,
) -> PermissionedView:
    return PermissionedView(
        PermissionContractVersion.V1,
        kind,
        PermissionDecision(
            PermissionContractVersion.V1,
            False,
            reason,
        ),
    )


class PermissionedControlledFixtureFacade:
    """Resolve, authorize, delegate once, then apply explicit visibility."""

    def __init__(
        self,
        authority: ControlledFixtureFacade,
        identity_authority: TrustedIdentityAuthorityPort,
        permission_state: PermissionStatePort,
        clock: TrustedClockPort,
        visibility: VisibilityAuthorityPort,
        *,
        campaign: CampaignReference,
        controlled_actor: ActorReference,
        durable_operations: DurableOperationCoordinator | None = None,
    ) -> None:
        if not isinstance(authority, ControlledFixtureFacade):
            raise ValueError("Permissioned façade requires the M1 façade.")
        if not isinstance(identity_authority, TrustedIdentityAuthorityPort):
            raise ValueError("Trusted identity authority port is invalid.")
        if not isinstance(permission_state, PermissionStatePort):
            raise ValueError("Permission state port is invalid.")
        if not isinstance(clock, TrustedClockPort):
            raise ValueError("Trusted clock port is invalid.")
        if not isinstance(visibility, VisibilityAuthorityPort):
            raise ValueError("Visibility authority port is invalid.")
        if not isinstance(campaign, CampaignReference):
            raise ValueError("Controlled campaign reference must be typed.")
        if not isinstance(controlled_actor, ActorReference):
            raise ValueError("Controlled actor reference must be typed.")
        if durable_operations is not None and not isinstance(
            durable_operations, DurableOperationCoordinator
        ):
            raise ValueError("Durable operation coordinator is invalid.")
        self.__authority = authority
        self.__identity_authority = identity_authority
        self.__permission_state = permission_state
        self.__clock = clock
        self.__visibility = visibility
        self.__campaign = campaign
        self.__controlled_actor = controlled_actor
        self.__durable_operations = durable_operations

    def inspect(self, request: PermissionRequest) -> PermissionedView:
        authorized = self._authorize(
            request,
            PermissionCapability.INSPECT,
            PermissionedViewKind.INSPECTION,
        )
        if isinstance(authorized, PermissionedView):
            return authorized
        decision, identity, _, _, _ = authorized
        try:
            result = self.__authority.inspect()
        except Exception:
            return PermissionedView(
                PermissionContractVersion.V1,
                PermissionedViewKind.INSPECTION,
                decision,
            )
        if not isinstance(result, ControlledFixtureView):
            return PermissionedView(
                PermissionContractVersion.V1,
                PermissionedViewKind.INSPECTION,
                decision,
            )
        return self._visible(
            PermissionedViewKind.INSPECTION,
            decision,
            identity,
            VisibilityEntryKey.FIXTURE_INSPECTION,
            result.to_dict(),
        )

    def capabilities(self, request: PermissionRequest) -> PermissionedView:
        authorized = self._authorize(
            request,
            PermissionCapability.DISCOVER_CAPABILITIES,
            PermissionedViewKind.CAPABILITIES,
        )
        if isinstance(authorized, PermissionedView):
            return authorized
        decision, identity, assignments, grants, now = authorized
        try:
            descriptors = self.__authority.capabilities()
        except Exception:
            return PermissionedView(
                PermissionContractVersion.V1,
                PermissionedViewKind.CAPABILITIES,
                decision,
            )
        if any(not isinstance(item, CapabilityDescriptor) for item in descriptors):
            return PermissionedView(
                PermissionContractVersion.V1,
                PermissionedViewKind.CAPABILITIES,
                decision,
            )
        visible_descriptors = []
        for descriptor in descriptors:
            required = _CAPABILITY_PERMISSION.get(descriptor.key)
            if required is None:
                visible_descriptors.append(descriptor)
                continue
            capability_request = replace(request, capability=required)
            capability_decision = evaluate_permission(
                identity,
                capability_request,
                assignments,
                grants,
                now,
            )
            if capability_decision.allowed:
                visible_descriptors.append(descriptor)
        return self._visible(
            PermissionedViewKind.CAPABILITIES,
            decision,
            identity,
            VisibilityEntryKey.CAPABILITY_AVAILABILITY,
            {"capabilities": [item.to_dict() for item in visible_descriptors]},
        )

    def select_player_character(
        self,
        request: PermissionRequest,
        operation: SelectPlayerCharacterRequest,
    ) -> PermissionedView:
        if not isinstance(request, PermissionRequest):
            raise ValueError("Permission request must be typed.")
        if not isinstance(operation, SelectPlayerCharacterRequest):
            raise ValueError("M1 selection request must be typed.")
        if (
            request.actor is None
            or request.actor.value != operation.actor.value
            or request.actor != self.__controlled_actor
        ):
            return _denied(
                PermissionedViewKind.SELECTION,
                PermissionReason.CAPABILITY_DENIED,
            )
        return self._permissioned_operation(
            request,
            PermissionCapability.SELECT_PLAYER_CHARACTER,
            PermissionedViewKind.SELECTION,
            VisibilityEntryKey.SELECTION_OPERATION,
            self.__authority.select_player_character,
            operation,
        )

    def resolve_controlled_round(
        self,
        request: PermissionRequest,
        operation: ResolveControlledRoundRequest,
    ) -> PermissionedView:
        if not isinstance(request, PermissionRequest):
            raise ValueError("Permission request must be typed.")
        if not isinstance(operation, ResolveControlledRoundRequest):
            raise ValueError("M1 controlled-round request must be typed.")
        if request.actor != self.__controlled_actor:
            return _denied(
                PermissionedViewKind.ROUND,
                PermissionReason.CAPABILITY_DENIED,
            )
        return self._permissioned_operation(
            request,
            PermissionCapability.RESOLVE_CONTROLLED_ROUND,
            PermissionedViewKind.ROUND,
            VisibilityEntryKey.ROUND_OPERATION,
            self.__authority.resolve_controlled_round,
            operation,
        )

    def reconstruct_operation(
        self,
        request: PermissionRequest,
        operation: OperationCorrelationRequest,
    ) -> PermissionedView:
        if not isinstance(request, PermissionRequest):
            raise ValueError("Permission request must be typed.")
        if not isinstance(operation, OperationCorrelationRequest):
            raise ValueError("M1 correlation request must be typed.")
        if request.actor != self.__controlled_actor:
            return _denied(
                PermissionedViewKind.RECONSTRUCTION,
                PermissionReason.CAPABILITY_DENIED,
            )
        return self._permissioned_operation(
            request,
            PermissionCapability.RECONSTRUCT_OPERATION,
            PermissionedViewKind.RECONSTRUCTION,
            VisibilityEntryKey.RECONSTRUCTION_OPERATION,
            self.__authority.reconstruct_operation,
            operation,
        )

    def _permissioned_operation(
        self,
        request: PermissionRequest,
        capability: PermissionCapability,
        kind: PermissionedViewKind,
        key: VisibilityEntryKey,
        delegate: Any,
        operation: Any,
    ) -> PermissionedView:
        authorized = self._authorize(request, capability, kind)
        if isinstance(authorized, PermissionedView):
            return authorized
        decision, identity, _, _, _ = authorized
        try:
            if self.__durable_operations is None:
                result = delegate(operation)
            elif capability is PermissionCapability.SELECT_PLAYER_CHARACTER:
                result = self.__durable_operations.select_player_character(
                    identity.participant,
                    request.campaign,
                    request.actor,
                    operation,
                )
            elif capability is PermissionCapability.RESOLVE_CONTROLLED_ROUND:
                result = self.__durable_operations.resolve_controlled_round(
                    identity.participant,
                    request.campaign,
                    request.actor,
                    operation,
                )
            else:
                result = delegate(operation)
        except Exception:
            return PermissionedView(
                PermissionContractVersion.V1, kind, decision
            )
        if not isinstance(result, (OperationView, DurableOperationSubmission)):
            return PermissionedView(
                PermissionContractVersion.V1, kind, decision
            )
        return self._visible(
            kind,
            decision,
            identity,
            key,
            result.to_dict(),
        )

    def _authorize(
        self,
        request: PermissionRequest,
        expected: PermissionCapability,
        kind: PermissionedViewKind,
    ) -> Any:
        if not isinstance(request, PermissionRequest):
            raise ValueError("Permission request must be typed.")
        if (
            request.version is not PermissionContractVersion.V1
            or request.capability is not expected
            or request.campaign != self.__campaign
        ):
            return _denied(kind, PermissionReason.CAPABILITY_DENIED)
        try:
            now = self.__clock.now()
            identity = self.__identity_authority.resolve_identity(
                request.session
            )
        except Exception:
            return _denied(kind, PermissionReason.INVALID_AUTHORITY_RESPONSE)
        if identity is None:
            decision = evaluate_permission(None, request, (), (), now)
            return PermissionedView(request.version, kind, decision)
        if not isinstance(identity, SessionIdentity):
            return _denied(kind, PermissionReason.INVALID_AUTHORITY_RESPONSE)
        try:
            assignments = tuple(
                self.__permission_state.assignments_for(
                    identity.participant, request.campaign
                )
            )
            grants = tuple(
                self.__permission_state.grants_for(
                    identity.participant, request.campaign
                )
            )
            decision = evaluate_permission(
                identity, request, assignments, grants, now
            )
        except Exception:
            return _denied(kind, PermissionReason.INVALID_AUTHORITY_RESPONSE)
        if not decision.allowed:
            return PermissionedView(request.version, kind, decision)
        return decision, identity, assignments, grants, now

    def _visible(
        self,
        kind: PermissionedViewKind,
        decision: PermissionDecision,
        identity: SessionIdentity,
        key: VisibilityEntryKey,
        payload: dict[str, Any],
    ) -> PermissionedView:
        try:
            audience = self.__visibility.audience_for(key)
            if not isinstance(audience, VisibilityAudience):
                raise ValueError("Visibility authority returned an invalid value.")
            entries = filter_visible_entries(
                (AudienceScopedEntry(key, audience, payload),),
                identity,
            )
        except Exception:
            entries = ()
        return PermissionedView(
            PermissionContractVersion.V1,
            kind,
            decision,
            entries,
        )
