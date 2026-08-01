"""Market Hours Service — determines exchange open/closed status per geography.

Replaces the hardcoded _is_market_hours() function in market_data_service.py.
Uses timezone-aware comparison based on geography registry config.
"""

from __future__ import annotations

from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

from backend.geo.registry import get_geo

# Cache TTL values (seconds)
MARKET_OPEN_TTL = 30
MARKET_CLOSED_TTL = 300


def is_market_open(geo_id: str) -> bool:
    """Determine if the exchange for the given geography is currently open.

    Args:
        geo_id: Geography identifier (e.g., "IN", "US").

    Returns:
        True if current time falls within market hours on a trading day.
    """
    geo = get_geo(geo_id)
    tz = ZoneInfo(geo.timezone)
    now = datetime.now(tz)

    # Check if today is a trading day
    if now.weekday() not in geo.trading_days:
        return False

    # Parse market hours
    open_h, open_m = map(int, geo.market_open.split(":"))
    close_h, close_m = map(int, geo.market_close.split(":"))

    market_open = dt_time(open_h, open_m)
    market_close = dt_time(close_h, close_m)
    current_time = now.time()

    return market_open <= current_time <= market_close


def get_cache_ttl(geo_id: str) -> int:
    """Return appropriate cache TTL based on market status.

    Args:
        geo_id: Geography identifier.

    Returns:
        30 seconds during market hours, 300 seconds otherwise.
    """
    return MARKET_OPEN_TTL if is_market_open(geo_id) else MARKET_CLOSED_TTL
