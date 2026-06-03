from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from backend.models.domain import Order, OrderFilters, OrderRequest


class IOrderService(ABC):
    """Abstract base class for the order service.

    Handles order placement, idempotency, persistence, and history retrieval.
    Delegates actual order submission to the appropriate IBrokerConnector.
    """

    @abstractmethod
    async def place_order(self, user_id: UUID, request: OrderRequest) -> Order:
        """Place an order via the appropriate broker connector.

        Performs an idempotency check (duplicate pending order within 10 s),
        persists the order to the database, and emits a WebSocket update.
        Retries once on transient network errors (500 ms then 1000 ms backoff).
        """
        ...

    @abstractmethod
    async def get_order_history(
        self,
        user_id: UUID,
        filters: OrderFilters | None = None,
    ) -> list[Order]:
        """Return the order history for the given user, with optional filters."""
        ...

    @abstractmethod
    async def get_order_status(self, user_id: UUID, order_id: UUID) -> Order:
        """Return the current state of a single order by its ID."""
        ...
