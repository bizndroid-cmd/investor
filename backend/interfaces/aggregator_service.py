from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from backend.models.domain import BrokerId, NormalizedHolding, Portfolio, RefreshResult


class IAggregatorService(ABC):
    """Abstract base class for the holdings aggregation service.

    Responsible for fetching holdings from all connected broker connectors,
    normalizing them to the common schema, and computing portfolio summaries.
    """

    @abstractmethod
    async def get_portfolio(self, user_id: UUID) -> Portfolio:
        """Return the aggregated portfolio for the given user.

        Fetches from all connected brokers concurrently, normalizes holdings,
        enriches with current prices, and computes summary totals.
        Falls back to cached data with ``is_stale=True`` on connector failure.
        """
        ...

    @abstractmethod
    async def get_holdings_by_broker(
        self,
        user_id: UUID,
        broker_id: BrokerId,
    ) -> list[NormalizedHolding]:
        """Return normalized holdings for a single broker."""
        ...

    @abstractmethod
    async def refresh_all(self, user_id: UUID) -> list[RefreshResult]:
        """Trigger a fresh fetch from all connected brokers for the given user.

        Returns one ``RefreshResult`` per broker indicating success or failure.
        """
        ...
