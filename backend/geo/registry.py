"""Geography Registry — frozen dataclass configurations for each supported market.

Adding a new geography:
1. Create a GeographyConfig instance with all required fields
2. Add it to _REGISTRY at module level
3. Implement any geography-specific providers (fundamentals, news feeds)

No database, no I/O — pure static config loaded at import time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Supported geography identifiers
GeoId = Literal["IN", "US"]


@dataclass(frozen=True)
class GeographyConfig:
    """Complete configuration for a supported geography/market.

    All geography-dependent behavior in the application derives from these fields.
    """

    geo_id: str
    """Two-letter geography identifier (e.g., "IN", "US")."""

    display_name: str
    """Human-readable name (e.g., "India", "United States")."""

    currency_code: str
    """ISO 4217 currency code (e.g., "INR", "USD")."""

    currency_symbol: str
    """Currency symbol for display (e.g., "₹", "$")."""

    currency_locale: str
    """Locale string for number formatting (e.g., "en-IN", "en-US")."""

    decimal_places: int
    """Decimal places for currency display."""

    exchanges: tuple[str, ...]
    """Supported stock exchanges (e.g., ("NSE", "BSE"))."""

    yfinance_suffix: str
    """Suffix appended to tickers for yfinance queries (e.g., ".NS", "")."""

    market_open: str
    """Market opening time in local timezone, HH:MM format (e.g., "09:15")."""

    market_close: str
    """Market closing time in local timezone, HH:MM format (e.g., "15:30")."""

    timezone: str
    """IANA timezone for the exchange (e.g., "Asia/Kolkata", "America/New_York")."""

    trading_days: tuple[int, ...]
    """Days of week when market is open. 0=Monday, 6=Sunday."""

    fundamentals_source: str
    """Identifier for fundamentals provider ("screener" or "yfinance")."""

    news_feed_ids: tuple[str, ...]
    """Identifiers for news feed providers to use."""

    sector_map: dict[str, str]
    """Mapping of ticker symbols to sector names for this geography."""

    dividend_frequency: str
    """Typical dividend payment frequency ("annual", "semi-annual", "quarterly")."""


# =============================================================================
# INDIA CONFIGURATION
# =============================================================================

_INDIA_SECTOR_MAP: dict[str, str] = {
    # Energy
    "RELIANCE": "energy",
    "ONGC": "energy",
    "IOC": "energy",
    "TATAPOWER": "energy",
    # Banking
    "HDFCBANK": "banking",
    "IDFCFIRSTB": "banking",
    "PNB": "banking",
    "YESBANK": "banking",
    "ICICIBANK": "banking",
    "SBIN": "banking",
    "KOTAKBANK": "banking",
    "AXISBANK": "banking",
    # IT
    "TCS": "it",
    "WIPRO": "it",
    "INFY": "it",
    "HCLTECH": "it",
    "TECHM": "it",
    # Engineering
    "LT": "engineering",
    "BHEL": "engineering",
    "RANEHOLDIN": "engineering",
    # FMCG
    "ITC": "fmcg",
    "HINDUNILVR": "fmcg",
    "NESTLEIND": "fmcg",
    # Hospitality
    "ITCHOTELS": "hospitality",
    # Infrastructure
    "ADANIPORTS": "infrastructure",
    "BIBCL": "infrastructure",
    # Auto
    "ASHOKLEY": "auto",
    "MOTHERSON": "auto",
    "EXIDEIND": "auto",
    "MSUMI": "auto",
    "TMPV": "auto",
    "TMCV": "auto",
    "TATAMOTORS": "auto",
    "MARUTI": "auto",
    "M&M": "auto",
    # Financials
    "JIOFIN": "financials",
    "BAJFINANCE": "financials",
    "BAJAJFINSV": "financials",
    # Technology
    "SERVOTECH": "technology",
    # Chemicals
    "PENIND": "chemicals",
    # Mining
    "VEDL": "mining",
    "COALINDIA": "mining",
    # Pharma
    "SUNPHARMA": "pharma",
    "DRREDDY": "pharma",
    "CIPLA": "pharma",
    # Telecom
    "BHARTIARTL": "telecom",
}

_INDIA = GeographyConfig(
    geo_id="IN",
    display_name="India",
    currency_code="INR",
    currency_symbol="₹",
    currency_locale="en-IN",
    decimal_places=2,
    exchanges=("NSE", "BSE"),
    yfinance_suffix=".NS",
    market_open="09:15",
    market_close="15:30",
    timezone="Asia/Kolkata",
    trading_days=(0, 1, 2, 3, 4),  # Mon-Fri
    fundamentals_source="screener",
    news_feed_ids=("indian_rss", "newsapi_ai"),
    sector_map=_INDIA_SECTOR_MAP,
    dividend_frequency="annual",
)


# =============================================================================
# UNITED STATES CONFIGURATION
# =============================================================================

_US_SECTOR_MAP: dict[str, str] = {
    # Technology
    "AAPL": "technology",
    "MSFT": "technology",
    "GOOGL": "technology",
    "GOOG": "technology",
    "META": "technology",
    "NVDA": "technology",
    "AMD": "technology",
    "INTC": "technology",
    "CRM": "technology",
    "ORCL": "technology",
    "ADBE": "technology",
    # E-Commerce / Consumer
    "AMZN": "consumer_discretionary",
    "TSLA": "consumer_discretionary",
    "NKE": "consumer_discretionary",
    "SBUX": "consumer_discretionary",
    "MCD": "consumer_discretionary",
    # Banking / Financials
    "JPM": "banking",
    "BAC": "banking",
    "GS": "banking",
    "MS": "banking",
    "WFC": "banking",
    "C": "banking",
    "V": "financials",
    "MA": "financials",
    "BRK.B": "financials",
    "BLK": "financials",
    # Healthcare / Pharma
    "JNJ": "healthcare",
    "UNH": "healthcare",
    "PFE": "pharma",
    "ABBV": "pharma",
    "MRK": "pharma",
    "LLY": "pharma",
    # Energy
    "XOM": "energy",
    "CVX": "energy",
    "COP": "energy",
    # Industrials
    "BA": "industrials",
    "CAT": "industrials",
    "HON": "industrials",
    "GE": "industrials",
    "UPS": "industrials",
    # Consumer Staples
    "PG": "consumer_staples",
    "KO": "consumer_staples",
    "PEP": "consumer_staples",
    "WMT": "consumer_staples",
    "COST": "consumer_staples",
    # Telecom
    "T": "telecom",
    "VZ": "telecom",
    "TMUS": "telecom",
    # Real Estate
    "AMT": "real_estate",
    "PLD": "real_estate",
    "SPG": "real_estate",
    # Utilities
    "NEE": "utilities",
    "DUK": "utilities",
    "SO": "utilities",
}

_US = GeographyConfig(
    geo_id="US",
    display_name="United States",
    currency_code="USD",
    currency_symbol="$",
    currency_locale="en-US",
    decimal_places=2,
    exchanges=("NYSE", "NASDAQ"),
    yfinance_suffix="",
    market_open="09:30",
    market_close="16:00",
    timezone="America/New_York",
    trading_days=(0, 1, 2, 3, 4),  # Mon-Fri
    fundamentals_source="yfinance",
    news_feed_ids=("us_rss",),
    sector_map=_US_SECTOR_MAP,
    dividend_frequency="quarterly",
)


# =============================================================================
# REGISTRY
# =============================================================================

_REGISTRY: dict[str, GeographyConfig] = {
    "IN": _INDIA,
    "US": _US,
}


def get_geo(geo_id: str) -> GeographyConfig:
    """Look up geography configuration by identifier.

    Args:
        geo_id: Two-letter geography code (e.g., "IN", "US").

    Returns:
        GeographyConfig for the requested geography.

    Raises:
        ValueError: If geo_id is not registered.
    """
    config = _REGISTRY.get(geo_id)
    if config is None:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(
            f"Geography '{geo_id}' is not supported. Available: {available}"
        )
    return config


def list_geos() -> list[str]:
    """Return all registered geography identifiers."""
    return sorted(_REGISTRY.keys())
