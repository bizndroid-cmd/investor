"""Abstract interface for news feed providers.

Implementations:
- IndianNewsFeedProvider — RSS from Economic Times, LiveMint, Moneycontrol
- USNewsFeedProvider — RSS from Yahoo Finance, MarketWatch
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.models.domain import RawNewsArticle


class INewsFeedProvider(ABC):
    """Abstract base for news article fetching per geography."""

    @abstractmethod
    async def fetch_articles(self, portfolio_tickers: list[str]) -> list[RawNewsArticle]:
        """Fetch news articles relevant to the given tickers.

        Returns list of RawNewsArticle with title, source, content, published_at.
        """
        ...
