"""Sector Classification Provider — maps tickers to sectors per geography.

Uses the sector_map from the Geography Registry.
Falls back to "other" for unmapped tickers.

Usage:
    from backend.geo.sectors import get_sector
    get_sector("RELIANCE", "IN")  → "energy"
    get_sector("AAPL", "US")      → "technology"
    get_sector("UNKNOWN", "IN")   → "other"
"""

from __future__ import annotations

from backend.geo.registry import get_geo


def get_sector(ticker: str, geo_id: str) -> str:
    """Return the sector for a ticker using the geography's sector map.

    Args:
        ticker: Stock ticker symbol (e.g., "RELIANCE", "AAPL").
        geo_id: Geography identifier (e.g., "IN", "US").

    Returns:
        Sector name string, or "other" if ticker not in map.
    """
    geo = get_geo(geo_id)
    return geo.sector_map.get(ticker.upper(), "other")


def get_all_sectors(geo_id: str) -> list[str]:
    """Return all unique sector names for a geography.

    Args:
        geo_id: Geography identifier.

    Returns:
        Sorted list of unique sector names.
    """
    geo = get_geo(geo_id)
    return sorted(set(geo.sector_map.values()))
