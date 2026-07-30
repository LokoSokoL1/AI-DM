"""Concrete edge adapters for client-neutral application ports."""

from .in_process_controlled_fixture import InProcessControlledFixtureAdapter
from .in_process_permissions import (
    InProcessPermissionContext,
    compose_permissioned_controlled_fixture,
)

__all__ = [
    "InProcessControlledFixtureAdapter",
    "InProcessPermissionContext",
    "compose_permissioned_controlled_fixture",
]
