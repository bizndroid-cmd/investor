"""Forex service — live USD/INR rate via yfinance."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_cached_rate: dict[str, Any] | None = None
_cache_time: datetime | None = None
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _fetch_usdinr_sync() -> dict[str, Any] | None:
    """Fetch live USD/INR from yfinance (USDINR=X ticker)."""
    try:
        import yfinance

        ticker = yfinance.Ticker("USDINR=X")
        info = ticker.info or {}

        rate = info.get("regularMarketPrice") or info.get("previousClose", 0)
        prev_close = info.get("previousClose", rate)
        change = rate - prev_close if rate and prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        # Also get 52-week range
        high_52w = info.get("fiftyTwoWeekHigh", 0)
        low_52w = info.get("fiftyTwoWeekLow", 0)

        return {
            "rate": round(float(rate), 4),
            "previous_close": round(float(prev_close), 4),
            "change": round(float(change), 4),
            "change_pct": round(float(change_pct), 3),
            "high_52w": round(float(high_52w), 2),
            "low_52w": round(float(low_52w), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.warning("Failed to fetch USD/INR rate: %s", str(e))
        return None


async def get_usdinr_rate() -> dict[str, Any]:
    """Get live USD/INR rate with caching (5 min TTL)."""
    global _cached_rate, _cache_time

    now = datetime.now(timezone.utc)
    if _cached_rate and _cache_time and (now - _cache_time).total_seconds() < _CACHE_TTL_SECONDS:
        return _cached_rate

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _fetch_usdinr_sync)

    if result:
        _cached_rate = result
        _cache_time = now
        return result

    # Fallback if fetch fails
    if _cached_rate:
        return _cached_rate

    return {
        "rate": 83.5,
        "previous_close": 83.5,
        "change": 0,
        "change_pct": 0,
        "high_52w": 85.0,
        "low_52w": 82.0,
        "timestamp": now.isoformat(),
        "is_fallback": True,
    }
