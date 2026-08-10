"""Client-neutral durable-operation storage port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .durable_operation_contracts import (
    CampaignOperationKey,
    CanonicalOperationIdentity,
    DurableStoreResult,
    DurableTerminalOutcome,
)


@runtime_checkable
class DurableOperationStorePort(Protocol):
    """Persist one campaign-scoped operation lifecycle atomically."""

    def lookup(self, key: CampaignOperationKey) -> DurableStoreResult:
        ...

    def reserve(
        self, identity: CanonicalOperationIdentity
    ) -> DurableStoreResult:
        ...

    def mark_dispatch_started(
        self, identity: CanonicalOperationIdentity
    ) -> DurableStoreResult:
        ...

    def record_terminal(
        self,
        identity: CanonicalOperationIdentity,
        outcome: DurableTerminalOutcome,
    ) -> DurableStoreResult:
        ...
