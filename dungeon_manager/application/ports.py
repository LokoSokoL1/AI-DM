"""Narrow inward-facing ports for the controlled client-neutral façade."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .contracts import (
    ControlledFixtureView,
    OperationCorrelationRequest,
    OperationView,
    ResolveControlledRoundRequest,
    SelectPlayerCharacterRequest,
)


@runtime_checkable
class ControlledFixtureAuthorityPort(Protocol):
    """Minimum authority-facing operations required by the M1 façade."""

    @property
    def transient_presentation_available(self) -> bool:
        ...

    def inspect(self) -> ControlledFixtureView:
        ...

    def select_player_character(
        self, request: SelectPlayerCharacterRequest
    ) -> OperationView:
        ...

    def resolve_controlled_round(
        self, request: ResolveControlledRoundRequest
    ) -> OperationView:
        ...

    def reconstruct_operation(
        self, request: OperationCorrelationRequest
    ) -> OperationView:
        ...
