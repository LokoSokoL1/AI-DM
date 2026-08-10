"""Bounded M3 composition for authorized controlled-fixture submissions."""

from __future__ import annotations

from pathlib import Path

from dungeon_manager.application.controlled_fixture import (
    ControlledFixtureFacade,
)
from dungeon_manager.application.durable_operation import (
    DurableOperationCoordinator,
)
from dungeon_manager.application.permission_contracts import (
    ActorReference,
    CampaignReference,
)
from dungeon_manager.application.permissioned_controlled_fixture import (
    PermissionedControlledFixtureFacade,
)

from .in_process_permissions import (
    InProcessPermissionContext,
    compose_permissioned_controlled_fixture,
)
from .sqlite_durable_operations import SQLiteDurableOperationStore


def compose_durable_permissioned_controlled_fixture(
    authority: ControlledFixtureFacade,
    context: InProcessPermissionContext,
    operation_store_path: str | Path,
    *,
    campaign: CampaignReference,
    controlled_actor: ActorReference,
) -> PermissionedControlledFixtureFacade:
    """Place durable identity beneath M2 and above the unchanged M1 facade."""

    store = SQLiteDurableOperationStore(operation_store_path)
    coordinator = DurableOperationCoordinator(authority, store)
    return compose_permissioned_controlled_fixture(
        authority,
        context,
        campaign=campaign,
        controlled_actor=controlled_actor,
        durable_operations=coordinator,
    )
