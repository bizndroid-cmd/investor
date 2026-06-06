"""Market data service implementing IMarketDataService.

Provides current and historical price data for stock tickers.
Prices are cached in Redis; Finnhub is the primary source with
yfinance for historical data.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import redis.asyncio as aioredis

from backend.config import settings
from backend.interfaces.market_data_service import IMarketDataService
from backend.models.domain import HistoricalDataPoint, PriceQuote, TimeRange

logger = logging.getLogger(__name__)

# TTL for price cache
MARKET_HOURS_TTL = 30  # seconds
OFF_HOURS_TTL = 300  # 5 minutes

# Finnhub rate limit: 60 requests per minute
FINNHUB_RATE_LIMIT = 60

# yfinance period mapping
RANGE_MAP: dict[TimeRange, str] = {
    "1d": "1d",
    "1w": "5d",
    "1m": "1mo",
    "3m": "3mo",
    "1y": "1y",
    "5y": "5y",
}


def _is_market_hours() -> bool:
    """Check if US stock market is currently open (simplified).

    NYSE/NASDAQ: Mon-Fri 9:30 AM - 4:00 PM ET.
    This is a simplified check that doesn't account for holidays.
    """
    from datetime import time as dt_time

    now = datetime.now(timezone.utc)
    # Convert to ET (UTC-5 standard, UTC-4 DST) — simplified as UTC-5
    et_hour = (now.hour - 5) % 24
    weekday = now.weekday()  # 0=Monday, 6=Sunday

    if weekday >= 5:  # Weekend
        return False

    market_open = dt_time(9, 30)
    market_close = dt_time(16, 0)
    current_time = dt_time(et_hour, now.minute)

    return market_open <= current_time <= market_close


class MarketDataService(IMarketDataService):
    """Concrete implementation of IMarketDataService.

    Uses Finnhub for real-time quotes and yfinance for historical data.
    Caches prices in Redis with TTL based on market hours.
    """

    def __init__(self, redis: aioredis.Redis, finnhub_api_key: str) -> None:
        self._redis = redis
        self._finnhub_api_key = finnhub_api_key

    async def get_current_price(self, ticker: str) -> PriceQuote:
        """Return the current price quote for a single ticker.

        Checks Redis cache first. On miss, calls Finnhub REST API.
        On error/429, returns last cached value with is_stale=True.
        """
        cache_key = f"price:{ticker}"

        # Check cache
        cached = await self._redis.get(cache_key)
        if cached:
            try:
                return PriceQuote.model_validate_json(cached)
            except Exception:
                pass

        # Check rate limit
        await self._wait_for_rate_limit()

        # Fetch from Finnhub
        try:
            quote = await self._fetch_finnhub_quote(ticker)
            # Cache with appropriate TTL
            ttl = MARKET_HOURS_TTL if _is_market_hours() else OFF_HOURS_TTL
            await self._redis.set(cache_key, quote.model_dump_json(), ex=ttl)
            return quote
        except Exception as e:
            logger.warning("Finnhub fetch failed for %s: %s", ticker, str(e))

        # Fallback: try yfinance for current price
        try:
            quote = await self._fetch_yfinance_price(ticker)
            if quote and quote.price > 0:
                ttl = MARKET_HOURS_TTL if _is_market_hours() else OFF_HOURS_TTL
                await self._redis.set(cache_key, quote.model_dump_json(), ex=ttl)
                return quote
        except Exception as e:
            logger.warning("yfinance price fallback failed for %s: %s", ticker, str(e))

        # Return last cached value with is_stale=True
        if cached:
            try:
                stale_quote = PriceQuote.model_validate_json(cached)
                stale_quote.is_stale = True
                return stale_quote
            except Exception:
                pass
        # No cached data available — return a zero quote marked stale
        return PriceQuote(
            ticker=ticker,
            price=Decimal("0"),
            previous_close=Decimal("0"),
            change=Decimal("0"),
            change_percent=Decimal("0"),
            timestamp=datetime.now(timezone.utc),
            is_stale=True,
        )

    async def get_batch_prices(self, tickers: list[str]) -> dict[str, PriceQuote]:
        """Return current price quotes for multiple tickers concurrently.

        Uses Groww LTP API for Indian stocks (NSE tickers) if a Groww access token
        is available. Falls back to Finnhub for US stocks.
        """
        if not tickers:
            return {}

        quotes: dict[str, PriceQuote] = {}

        # Try Groww LTP API first (supports batch of up to 50)
        groww_token = settings.groww_access_token or settings.groww_api_key
        if groww_token:
            try:
                groww_quotes = await self._fetch_groww_ltp_batch(tickers, groww_token)
                quotes.update(groww_quotes)
            except Exception as e:
                logger.warning("Groww LTP batch fetch failed: %s", str(e))

        # For any tickers not resolved by Groww, fall back to Finnhub
        remaining = [t for t in tickers if t not in quotes]
        if remaining and self._finnhub_api_key:
            semaphore = asyncio.Semaphore(10)

            async def _fetch_with_semaphore(ticker: str) -> tuple[str, PriceQuote]:
                async with semaphore:
                    quote = await self.get_current_price(ticker)
                    return ticker, quote

            tasks = [_fetch_with_semaphore(t) for t in remaining]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error("Batch price fetch error: %s", str(result))
                    continue
                ticker, quote = result
                quotes[ticker] = quote

        return quotes

    async def get_historical_data(
        self,
        ticker: str,
        range: TimeRange,
    ) -> list[HistoricalDataPoint]:
        """Return OHLCV history for the given ticker and time range.

        Uses yfinance for all supported ranges. Returns empty list on failure.
        """
        period = RANGE_MAP.get(range, "1mo")

        try:
            # Run yfinance in a thread pool since it's synchronous
            loop = asyncio.get_event_loop()
            data_points = await loop.run_in_executor(
                None, self._fetch_yfinance_history, ticker, period
            )
            return data_points
        except Exception as e:
            logger.error("yfinance fetch failed for %s (%s): %s", ticker, range, str(e))
            return []

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    async def _fetch_finnhub_quote(self, ticker: str) -> PriceQuote:
        """Fetch a quote from Finnhub REST API."""
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={self._finnhub_api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)

            if response.status_code == 429:
                raise Exception("Finnhub rate limit exceeded (429)")

            response.raise_for_status()
            data = response.json()

        # Finnhub quote response fields:
        # c = current price, pc = previous close, d = change, dp = change percent
        current_price = Decimal(str(data.get("c", 0)))
        previous_close = Decimal(str(data.get("pc", 0)))
        change = Decimal(str(data.get("d", 0) or 0))
        change_percent = Decimal(str(data.get("dp", 0) or 0))

        # Increment rate limit counter
        await self._increment_rate_limit()

        return PriceQuote(
            ticker=ticker,
            price=current_price,
            previous_close=previous_close,
            change=change,
            change_percent=change_percent,
            timestamp=datetime.now(timezone.utc),
            is_stale=False,
        )

    async def _fetch_yfinance_price(self, ticker: str) -> PriceQuote | None:
        """Fetch current price from yfinance as fallback (NSE tickers get .NS suffix)."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._yfinance_price_sync, ticker)

    def _yfinance_price_sync(self, ticker: str) -> PriceQuote | None:
        """Synchronous yfinance price fetch."""
        try:
            import yfinance

            # NSE tickers need .NS suffix
            yf_ticker = f"{ticker}.NS"
            stock = yfinance.Ticker(yf_ticker)
            info = stock.fast_info

            current_price = Decimal(str(getattr(info, "last_price", 0) or 0))
            previous_close = Decimal(str(getattr(info, "previous_close", 0) or 0))

            if current_price <= 0:
                return None

            change = current_price - previous_close
            change_percent = (
                (change / previous_close * Decimal("100")) if previous_close > 0 else Decimal("0")
            )

            return PriceQuote(
                ticker=ticker,
                price=current_price,
                previous_close=previous_close,
                change=change,
                change_percent=change_percent,
                timestamp=datetime.now(timezone.utc),
                is_stale=False,
            )
        except Exception as e:
            logger.debug("yfinance price fetch failed for %s: %s", ticker, str(e))
            return None

    async def _wait_for_rate_limit(self) -> None:
        """Wait if we've hit the Finnhub rate limit (60 req/min)."""
        now = datetime.now(timezone.utc)
        minute_key = f"ratelimit:finnhub:{now.strftime('%Y%m%d%H%M')}"

        count = await self._redis.get(minute_key)
        if count and int(count) >= FINNHUB_RATE_LIMIT:
            # Wait until the next minute
            seconds_remaining = 60 - now.second
            logger.info("Rate limit reached, waiting %d seconds", seconds_remaining)
            await asyncio.sleep(seconds_remaining)

    async def _increment_rate_limit(self) -> None:
        """Increment the Finnhub rate limit counter for the current minute."""
        now = datetime.now(timezone.utc)
        minute_key = f"ratelimit:finnhub:{now.strftime('%Y%m%d%H%M')}"

        pipe = self._redis.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 120)  # Expire after 2 minutes
        await pipe.execute()

    def _fetch_yfinance_history(
        self, ticker: str, period: str
    ) -> list[HistoricalDataPoint]:
        """Synchronous yfinance download (runs in thread pool)."""
        import yfinance

        df = yfinance.download(ticker, period=period, progress=False)

        if df is None or df.empty:
            return []

        data_points: list[HistoricalDataPoint] = []
        for idx, row in df.iterrows():
            try:
                # Handle MultiIndex columns from yfinance
                open_val = row["Open"] if "Open" in row.index else row[("Open", ticker)]
                high_val = row["High"] if "High" in row.index else row[("High", ticker)]
                low_val = row["Low"] if "Low" in row.index else row[("Low", ticker)]
                close_val = row["Close"] if "Close" in row.index else row[("Close", ticker)]
                volume_val = row["Volume"] if "Volume" in row.index else row[("Volume", ticker)]

                data_points.append(
                    HistoricalDataPoint(
                        date=idx.to_pydatetime().replace(tzinfo=timezone.utc),
                        open=Decimal(str(float(open_val))),
                        high=Decimal(str(float(high_val))),
                        low=Decimal(str(float(low_val))),
                        close=Decimal(str(float(close_val))),
                        volume=int(float(volume_val)),
                    )
                )
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("Skipping data point for %s: %s", ticker, str(e))
                continue

        return data_points

    async def _fetch_groww_ltp_batch(
        self, tickers: list[str], access_token: str
    ) -> dict[str, PriceQuote]:
        """Fetch LTP from Groww API for a batch of tickers (up to 50 per call).

        Groww LTP API expects exchange_symbols in format: NSE_RELIANCE, NSE_HDFCBANK, etc.
        """
        quotes: dict[str, PriceQuote] = {}

        # Build exchange_symbols list (assume NSE for all tickers)
        exchange_symbols = [f"NSE_{ticker}" for ticker in tickers]

        # Groww supports up to 50 per call
        for i in range(0, len(exchange_symbols), 50):
            batch = exchange_symbols[i : i + 50]
            batch_tickers = tickers[i : i + 50]

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(
                        "https://api.groww.in/v1/live-data/ltp",
                        params={
                            "segment": "CASH",
                            "exchange_symbols": ",".join(batch),
                        },
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Accept": "application/json",
                            "X-API-VERSION": "1.0",
                        },
                    )
                    response.raise_for_status()
                    data = response.json()

                if data.get("status") != "SUCCESS":
                    logger.warning("Groww LTP returned non-SUCCESS: %s", data.get("status"))
                    continue

                payload = data.get("payload", {})
                for ticker, exchange_symbol in zip(batch_tickers, batch):
                    ltp = payload.get(exchange_symbol)
                    if ltp is not None:
                        price = Decimal(str(ltp))
                        # Cache the price
                        cache_key = f"price:{ticker}"
                        quote = PriceQuote(
                            ticker=ticker,
                            price=price,
                            previous_close=price,  # LTP doesn't give prev close
                            change=Decimal("0"),
                            change_percent=Decimal("0"),
                            timestamp=datetime.now(timezone.utc),
                            is_stale=False,
                        )
                        quotes[ticker] = quote
                        ttl = MARKET_HOURS_TTL if _is_market_hours() else OFF_HOURS_TTL
                        await self._redis.set(cache_key, quote.model_dump_json(), ex=ttl)
            except Exception as e:
                logger.warning("Groww LTP batch call failed: %s", str(e))

        return quotes
