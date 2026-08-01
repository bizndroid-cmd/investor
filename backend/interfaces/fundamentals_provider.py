"""Abstract interface for stock fundamentals data providers.

Implementations:
- ScreenerService (India) — scrapes screener.in
- YFinanceFundamentalsProvider (US) — uses yfinance Ticker.info
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IFundamentalsProvider(ABC):
    """Abstract base for fundamentals data retrieval."""

    @abstractmethod
    async def fetch_fundamentals(self, ticker: str) -> dict | None:
        """Fetch and return standardized fundamentals dict.

        Returns dict with keys: ticker, market_cap, pe_ratio, book_value,
        dividend_yield, roe, roce, fetched_at. Missing fields set to None.
        """
        ...

    @abstractmethod
    async def get_cached_fundamentals(self, ticker: str) -> dict | None:
        """Return stored fundamentals from cache/DB."""
        ...
