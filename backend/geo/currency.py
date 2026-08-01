"""Currency Formatter — formats monetary values per geography.

Backend usage (Telegram messages, API responses):
    from backend.geo.currency import format_currency
    format_currency(Decimal("100000"), "IN")  → "₹1,00,000.00"
    format_currency(Decimal("100000"), "US")  → "$100,000.00"

Frontend has its own implementation using Intl.NumberFormat.
"""

from __future__ import annotations

import locale as locale_module
from decimal import Decimal

from backend.geo.registry import get_geo


def format_currency(value: Decimal | float | int, geo_id: str) -> str:
    """Format a monetary value using the geography's currency rules.

    Args:
        value: Numeric value to format.
        geo_id: Geography identifier (e.g., "IN", "US").

    Returns:
        Formatted string with currency symbol and locale-appropriate grouping.
    """
    geo = get_geo(geo_id)
    num = float(value) if not isinstance(value, float) else value

    if geo_id == "IN":
        return _format_inr(num, geo.currency_symbol, geo.decimal_places)
    else:
        return _format_western(num, geo.currency_symbol, geo.decimal_places)


def _format_inr(value: float, symbol: str, decimals: int) -> str:
    """Format using Indian numbering system (lakh/crore grouping).

    Pattern: X,XX,XX,XXX.DD (last group of 3, then groups of 2)
    """
    is_negative = value < 0
    value = abs(value)

    # Split integer and decimal parts
    int_part = int(value)
    dec_part = round(value - int_part, decimals)

    # Format integer with Indian grouping
    int_str = str(int_part)
    if len(int_str) <= 3:
        grouped = int_str
    else:
        # Last 3 digits, then groups of 2
        last_three = int_str[-3:]
        remaining = int_str[:-3]
        groups = []
        while remaining:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        groups.reverse()
        grouped = ",".join(groups) + "," + last_three

    # Build result
    if decimals > 0:
        dec_str = f"{dec_part:.{decimals}f}"[2:]  # Remove "0."
        result = f"{symbol}{grouped}.{dec_str}"
    else:
        result = f"{symbol}{grouped}"

    if is_negative:
        result = f"-{result}"

    return result


def _format_western(value: float, symbol: str, decimals: int) -> str:
    """Format using Western numbering system (comma every 3 digits)."""
    is_negative = value < 0
    value = abs(value)

    if decimals > 0:
        formatted = f"{value:,.{decimals}f}"
    else:
        formatted = f"{int(value):,}"

    result = f"{symbol}{formatted}"
    if is_negative:
        result = f"-{result}"

    return result
