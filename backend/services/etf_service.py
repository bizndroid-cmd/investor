"""ETF market data service — fetches prices, returns, and details via yfinance."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


def _get_yf_ticker(ticker: str, geo_id: str) -> str:
    """Resolve ticker to yfinance-compatible symbol."""
    from backend.geo.ticker_resolver import resolve

    return resolve(ticker, geo_id)


def _fetch_market_data_sync(ticker: str, geo_id: str) -> dict[str, Any] | None:
    """Synchronous yfinance call for ETF market data. Run in thread pool."""
    try:
        import yfinance

        yf_ticker = _get_yf_ticker(ticker, geo_id)
        etf = yfinance.Ticker(yf_ticker)
        info = etf.info or {}

        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("navPrice", 0)
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose", 0)
        day_change = (current_price - prev_close) if current_price and prev_close else 0
        day_change_pct = (day_change / prev_close * 100) if prev_close else 0

        return {
            "ticker": ticker,
            "geo_id": geo_id,
            "current_price": float(current_price or 0),
            "previous_close": float(prev_close or 0),
            "day_change": round(float(day_change), 2),
            "day_change_pct": round(float(day_change_pct), 2),
            "fifty_two_week_high": float(info.get("fiftyTwoWeekHigh", 0)),
            "fifty_two_week_low": float(info.get("fiftyTwoWeekLow", 0)),
            "expense_ratio": info.get("annualReportExpenseRatio") or info.get("expenseRatio"),
            "category": info.get("category", ""),
            "fund_family": info.get("fundFamily", ""),
            "total_assets": info.get("totalAssets", 0),
            "name": info.get("longName") or info.get("shortName", ""),
            "description": info.get("longBusinessSummary", ""),
        }
    except Exception as e:
        logger.warning(f"Failed to fetch ETF market data for {ticker} ({geo_id}): {e}")
        return None


def _fetch_returns_sync(ticker: str, geo_id: str) -> dict[str, float | None]:
    """Compute CAGR returns for various periods."""
    try:
        import yfinance

        yf_ticker = _get_yf_ticker(ticker, geo_id)
        etf = yfinance.Ticker(yf_ticker)
        hist = etf.history(period="max")

        if hist is None or hist.empty or len(hist) < 22:
            return {}

        closes = hist["Close"]
        current = float(closes.iloc[-1])

        def cagr(days: int) -> float | None:
            if len(closes) < days:
                return None
            past = float(closes.iloc[-days])
            if past <= 0:
                return None
            years = days / 252
            return round(((current / past) ** (1 / years) - 1) * 100, 2)

        return {
            "return_1m": cagr(22),
            "return_3m": cagr(66),
            "return_6m": cagr(132),
            "return_1y": cagr(252),
            "return_3y": cagr(756),
            "return_5y": cagr(1260),
        }
    except Exception as e:
        logger.warning(f"Failed to compute ETF returns for {ticker} ({geo_id}): {e}")
        return {}


def _fetch_details_sync(ticker: str, geo_id: str) -> dict[str, Any] | None:
    """Combine market data + returns + top holdings."""
    try:
        import yfinance

        yf_ticker = _get_yf_ticker(ticker, geo_id)
        etf = yfinance.Ticker(yf_ticker)
        info = etf.info or {}

        market_data = _fetch_market_data_sync(ticker, geo_id) or {}
        returns = _fetch_returns_sync(ticker, geo_id)

        # Top holdings from yfinance (if available)
        top_holdings = []
        try:
            holdings_df = etf.get_holdings()
            if holdings_df is not None and not holdings_df.empty:
                for _, row in holdings_df.head(10).iterrows():
                    top_holdings.append({
                        "symbol": row.get("Symbol", ""),
                        "name": row.get("Name", ""),
                        "weight": float(row.get("% Assets", 0)),
                    })
        except Exception:
            pass

        return {
            **market_data,
            "returns": returns,
            "top_holdings": top_holdings,
            "tracking_index": info.get("category", ""),
            "inception_date": info.get("fundInceptionDate", ""),
        }
    except Exception as e:
        logger.warning(f"Failed to fetch ETF details for {ticker} ({geo_id}): {e}")
        return None


async def get_etf_market_data(ticker: str, geo_id: str) -> dict[str, Any] | None:
    """Fetch current ETF market data (async wrapper)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_market_data_sync, ticker, geo_id)


async def get_etf_returns(ticker: str, geo_id: str) -> dict[str, float | None]:
    """Compute ETF returns for various periods (async wrapper)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_returns_sync, ticker, geo_id)


async def get_etf_details(ticker: str, geo_id: str) -> dict[str, Any] | None:
    """Full ETF details: market data + returns + top holdings."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_details_sync, ticker, geo_id)


def compute_projections(holdings_data: list[dict]) -> dict[str, Any]:
    """Project future value at historical CAGR for 1Y, 3Y, 5Y.

    holdings_data: list of dicts with current_value and return_1y/3y/5y.
    """
    total_current = sum(h.get("current_value", 0) for h in holdings_data)

    # Weighted average CAGR
    def weighted_cagr(key: str) -> float:
        total_weight = 0
        weighted_sum = 0
        for h in holdings_data:
            val = h.get("current_value", 0)
            ret = h.get(key)
            if ret is not None and val > 0:
                weighted_sum += ret * val
                total_weight += val
        return (weighted_sum / total_weight) if total_weight > 0 else 0

    cagr_1y = weighted_cagr("return_1y")
    cagr_3y = weighted_cagr("return_3y")
    cagr_5y = weighted_cagr("return_5y")

    return {
        "current_value": round(total_current, 2),
        "projected_1y": round(total_current * (1 + cagr_1y / 100), 2) if cagr_1y else None,
        "projected_3y": round(total_current * (1 + cagr_3y / 100) ** 3, 2) if cagr_3y else None,
        "projected_5y": round(total_current * (1 + cagr_5y / 100) ** 5, 2) if cagr_5y else None,
        "cagr_1y": cagr_1y,
        "cagr_3y": cagr_3y,
        "cagr_5y": cagr_5y,
    }


def get_category_allocation(holdings: list[dict]) -> list[dict]:
    """Group ETF holdings by category (gold, silver, equity, debt, international).

    Returns list of {category, value, percentage}.
    """
    category_map: dict[str, float] = {}
    total = 0.0

    for h in holdings:
        cat = _classify_category(h.get("category", ""), h.get("ticker", ""))
        val = h.get("current_value", 0)
        category_map[cat] = category_map.get(cat, 0) + val
        total += val

    return [
        {
            "category": cat,
            "value": round(val, 2),
            "percentage": round((val / total * 100) if total > 0 else 0, 1),
        }
        for cat, val in sorted(category_map.items(), key=lambda x: -x[1])
    ]


def _classify_category(yf_category: str, ticker: str) -> str:
    """Classify an ETF into broad allocation bucket."""
    t = ticker.upper()
    c = (yf_category or "").lower()

    # Gold ETFs
    if any(g in t for g in ["GOLD", "GLD", "SGLD"]):
        return "Gold"
    if "gold" in c:
        return "Gold"

    # Silver ETFs
    if any(s in t for s in ["SILVER", "SLV", "SILVERBEES"]):
        return "Silver"
    if "silver" in c:
        return "Silver"

    # Debt/Bond ETFs
    if any(d in t for d in ["LIQUIDBEES", "NIFTYBEES", "GILT", "BOND"]):
        if "GILT" in t or "BOND" in t or "LIQUID" in t:
            return "Debt"
    if "bond" in c or "debt" in c or "money market" in c or "liquid" in c:
        return "Debt"

    # International ETFs
    if any(i in t for i in ["N100", "NASDAQ", "MON100", "MAFANG"]):
        return "International"
    if "international" in c or "global" in c or "foreign" in c:
        return "International"

    # Default to Equity
    return "Equity"


def _fetch_history_sync(ticker: str, geo_id: str, start_date: str) -> dict[str, float] | None:
    """Fetch daily close prices from start_date to now. Returns {date_str: price}."""
    try:
        import yfinance

        yf_ticker = _get_yf_ticker(ticker, geo_id)
        etf = yfinance.Ticker(yf_ticker)
        hist = etf.history(start=start_date)

        if hist is None or hist.empty:
            return None

        result = {}
        for idx, row in hist.iterrows():
            date_str = idx.strftime("%Y-%m-%d")
            result[date_str] = float(row["Close"])
        return result
    except Exception as e:
        logger.warning(f"Failed to fetch ETF history for {ticker} ({geo_id}): {e}")
        return None


async def get_etf_history(ticker: str, geo_id: str, start_date: str) -> dict[str, float] | None:
    """Async wrapper for historical price data."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_history_sync, ticker, geo_id, start_date)
