"""Abstract interface for the News Service."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from backend.models.domain import PaginatedNewsResponse, RefreshStatus


class INewsService(ABC):
    """Contract for fetching, refreshing, and querying analyzed news."""

    @abstractmethod
    async def get_news_feed(
        self,
        user_id: UUID,
        sentiment: str | None = None,
        impact_level: str | None = None,
        ticker: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedNewsResponse:
        """Return a paginated, optionally filtered news feed for a user."""
        ...

    @abstractmethod
    async def trigger_refresh(self, user_id: UUID) -> RefreshStatus:
        """Trigger a manual news refresh cycle for the user."""
        ...
