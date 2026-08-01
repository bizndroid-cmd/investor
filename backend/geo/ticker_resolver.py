"""Ticker Resolver — converts raw ticker symbols to exchange-specific format.

Handles yfinance suffix appending/stripping based on geography.
Examples:
    resolve("RELIANCE", "IN") → "RELIANCE.NS"
    resolve("AAPL", "US") → "AAPL"
    strip_suffix("RELIANCE.NS", "IN") → "RELIANCE"

Round-trip guarantee: strip_suffix(resolve(t, g), g) == t
"""

from __future__ import annotations

from backend.geo.registry import get_geo


def resolve(ticker: str, geo_id: str, exchange: str | None = None) -> str:
    """Append the correct yfinance suffix for the geography.

    Args:
        ticker: Raw ticker symbol (e.g., "RELIANCE", "AAPL").
        geo_id: Geography identifier (e.g., "IN", "US").
        exchange: Optional explicit exchange override (e.g., "BSE" to use ".BO").

    Returns:
        Ticker with appropriate suffix appended.
    """
    if exchange:
        # Known exchange suffix overrides
        exchange_suffixes = {
            "BSE": ".BO",
            "NSE": ".NS",
            "NYSE": "",
            "NASDAQ": "",
            "LSE": ".L",
        }
        suffix = exchange_suffixes.get(exchange.upper(), "")
        return f"{ticker}{suffix}"

    geo = get_geo(geo_id)
    return f"{ticker}{geo.yfinance_suffix}"


def strip_suffix(resolved_ticker: str, geo_id: str) -> str:
    """Strip the geography suffix to recover the raw ticker.

    Args:
        resolved_ticker: Ticker with suffix (e.g., "RELIANCE.NS").
        geo_id: Geography identifier used during resolution.

    Returns:
        Raw ticker without suffix.
    """
    geo = get_geo(geo_id)
    suffix = geo.yfinance_suffix
    if suffix and resolved_ticker.endswith(suffix):
        return resolved_ticker[: -len(suffix)]
    return resolved_ticker
