from __future__ import annotations

from abc import ABC, abstractmethod

from backend.models.domain import HistoricalDataPoint, PriceQuote, TimeRange


class IMarketDataService(ABC):
    """Abstract base class for the market data service.

    Provides current and historical price data for stock tickers.
    Prices are cached in Redis; Finnhub is the primary source with
    yfinance as a fallback for historical data.
    """

    @abstractmethod
    async def get_current_price(self, ticker: str) -> PriceQuote:
        """Return the current price quote for a single ticker.

        Checks the Redis cache first (TTL 30 s during market hours).
        Falls back to the last cached value with ``is_stale=True`` on error.
        """
        ...

    @abstractmethod
    async def get_batch_prices(self, tickers: list[str]) -> dict[str, PriceQuote]:
        """Return current price quotes for multiple tickers in one call.

        Fans out to ``get_current_price`` concurrently while respecting
        the Finnhub rate limit (60 req/min).
        """
        ...

    @abstractmethod
    async def get_historical_data(
        self,
        ticker: str,
        range: TimeRange,
    ) -> list[HistoricalDataPoint]:
        """Return OHLCV history for the given ticker and time range.

        Uses yfinance for all supported ranges (1d – 5y).
        Returns an empty list on failure.
        """
        ...
