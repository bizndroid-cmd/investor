"""YFinance Fundamentals Provider — US stock fundamentals from yfinance.

Uses yfinance Ticker.info to extract P/E, ROE, market cap, dividend yield, etc.
For US geography stocks that don't have screener.in coverage.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from backend.interfaces.fundamentals_provider import IFundamentalsProvider

logger = logging.getLogger(__name__)


class YFinanceFundamentalsProvider(IFundamentalsProvider):
    """Fetches fundamentals from yfinance Ticker.info for US stocks."""

    async def fetch_fundamentals(self, ticker: str) -> dict | None:
        """Fetch fundamentals from yfinance."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync, ticker)

    async def get_cached_fundamentals(self, ticker: str) -> dict | None:
        """No separate cache — yfinance is fetched fresh each time.

        For production, would cache in DB like ScreenerService does.
        """
        return await self.fetch_fundamentals(ticker)

    def _fetch_sync(self, ticker: str) -> dict | None:
        """Synchronous yfinance info fetch."""
        try:
            import yfinance

            stock = yfinance.Ticker(ticker)
            info = stock.info

            if not info or info.get("regularMarketPrice") is None:
                return None

            return {
                "ticker": ticker,
                "market_cap": str(info.get("marketCap", "")) or None,
                "current_price": str(info.get("regularMarketPrice", "")) or None,
                "pe_ratio": str(round(info.get("trailingPE", 0), 2)) if info.get("trailingPE") else None,
                "book_value": str(round(info.get("bookValue", 0), 2)) if info.get("bookValue") else None,
                "dividend_yield": str(round(info.get("dividendYield", 0) * 100, 2)) if info.get("dividendYield") else None,
                "roce": None,  # Not available from yfinance
                "roe": str(round(info.get("returnOnEquity", 0) * 100, 2)) if info.get("returnOnEquity") else None,
                "face_value": None,
                "high_low": f"{info.get('fiftyTwoWeekHigh', '')}/{info.get('fiftyTwoWeekLow', '')}" if info.get("fiftyTwoWeekHigh") else None,
                "pros": None,
                "cons": None,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.warning("yfinance fundamentals failed for %s: %s", ticker, str(e))
            return None
