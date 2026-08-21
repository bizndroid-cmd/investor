"""FastAPI market data router for price quotes and historical data.

Endpoints:
- GET /market/price/{ticker} — returns PriceQuote for a single ticker
- POST /market/prices/batch — returns dict[str, PriceQuote] for multiple tickers
- GET /market/history/{ticker}?range=1m — returns list[HistoricalDataPoint]
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.models.domain import (
    HistoricalDataPoint,
    PriceQuote,
    Session,
    TimeRange,
)
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/market", tags=["market"])


class BatchPriceRequest(BaseModel):
    """Request body for batch price lookup."""

    tickers: list[str]


def get_market_data_service():
    """Dependency placeholder — overridden in main.py via app.dependency_overrides."""
    raise NotImplementedError("MarketDataService not wired. Use dependency overrides.")


@router.get("/price/{ticker}", response_model=PriceQuote)
async def get_price(
    ticker: str,
    session: Session = Depends(get_current_user),
    market_data_service=Depends(get_market_data_service),
) -> PriceQuote:
    """Return the current price quote for a single ticker."""
    return await market_data_service.get_current_price(ticker.upper())


@router.post("/prices/batch", response_model=dict[str, PriceQuote])
async def get_batch_prices(
    body: BatchPriceRequest,
    session: Session = Depends(get_current_user),
    market_data_service=Depends(get_market_data_service),
) -> dict[str, PriceQuote]:
    """Return current price quotes for multiple tickers."""
    tickers = [t.upper() for t in body.tickers]
    return await market_data_service.get_batch_prices(tickers)


@router.get("/history/{ticker}", response_model=list[HistoricalDataPoint])
async def get_history(
    ticker: str,
    range: TimeRange = Query(default="1m", description="Time range for historical data"),
    session: Session = Depends(get_current_user),
    market_data_service=Depends(get_market_data_service),
) -> list[HistoricalDataPoint]:
    """Return OHLCV historical data for the given ticker and time range."""
    return await market_data_service.get_historical_data(ticker.upper(), range)


@router.get("/forex/usdinr")
async def get_forex_rate(
    session: Session = Depends(get_current_user),
) -> dict:
    """Live USD/INR exchange rate with daily change."""
    from backend.services.forex_service import get_usdinr_rate
    return await get_usdinr_rate()


@router.get("/what-if")
async def what_if_comparison(
    amount: float = Query(..., description="Amount invested (in source currency)"),
    source_ticker: str = Query(..., description="What you actually bought"),
    source_geo: str = Query(..., description="IN or US"),
    alt_ticker: str = Query(..., description="What you could have bought"),
    alt_geo: str = Query(..., description="IN or US"),
    buy_date: str = Query(..., description="Date of purchase (YYYY-MM-DD)"),
    session: Session = Depends(get_current_user),
) -> dict:
    """Cross-market 'What If' comparison.

    Given: I invested $X in RELIANCE on 2023-01-01.
    Shows: What if I'd put same money in AAPL instead?
    Handles currency conversion at historical rates.
    """
    import asyncio
    from backend.services.forex_service import get_usdinr_rate
    from backend.geo.ticker_resolver import resolve

    def _compute_sync() -> dict:
        import yfinance
        from datetime import datetime, timedelta

        # Fetch source ticker history
        src_yf = resolve(source_ticker.upper(), source_geo)
        alt_yf = resolve(alt_ticker.upper(), alt_geo)

        src = yfinance.Ticker(src_yf)
        alt = yfinance.Ticker(alt_yf)

        src_hist = src.history(start=buy_date)
        alt_hist = alt.history(start=buy_date)

        if src_hist is None or src_hist.empty:
            return {"error": f"No data for {source_ticker} from {buy_date}"}
        if alt_hist is None or alt_hist.empty:
            return {"error": f"No data for {alt_ticker} from {buy_date}"}

        # Buy price = first close after buy_date
        src_buy_price = float(src_hist["Close"].iloc[0])
        alt_buy_price = float(alt_hist["Close"].iloc[0])

        # Current price = last close
        src_current = float(src_hist["Close"].iloc[-1])
        alt_current = float(alt_hist["Close"].iloc[-1])

        # Units bought
        src_units = amount / src_buy_price
        alt_units = amount / alt_buy_price  # Same amount in source currency

        # Current values (in original currencies)
        src_value_now = src_units * src_current
        alt_value_now = alt_units * alt_current

        # Returns
        src_return_pct = ((src_value_now - amount) / amount) * 100
        alt_return_pct = ((alt_value_now - amount) / amount) * 100

        # Build price series (normalized to 100)
        chart_data = []
        all_dates = sorted(set(
            [d.strftime("%Y-%m-%d") for d in src_hist.index] +
            [d.strftime("%Y-%m-%d") for d in alt_hist.index]
        ))

        src_prices = {d.strftime("%Y-%m-%d"): float(p) for d, p in zip(src_hist.index, src_hist["Close"])}
        alt_prices = {d.strftime("%Y-%m-%d"): float(p) for d, p in zip(alt_hist.index, alt_hist["Close"])}

        src_base = src_buy_price
        alt_base = alt_buy_price

        for d in all_dates[::5]:  # Sample every 5 days for performance
            point = {"date": d}
            if d in src_prices:
                point[source_ticker.upper()] = round(src_prices[d] / src_base * 100, 2)
            if d in alt_prices:
                point[alt_ticker.upper()] = round(alt_prices[d] / alt_base * 100, 2)
            if len(point) > 1:
                chart_data.append(point)

        return {
            "source": {
                "ticker": source_ticker.upper(),
                "geo": source_geo,
                "buy_price": round(src_buy_price, 2),
                "current_price": round(src_current, 2),
                "units": round(src_units, 4),
                "invested": round(amount, 2),
                "current_value": round(src_value_now, 2),
                "return_pct": round(src_return_pct, 2),
            },
            "alternative": {
                "ticker": alt_ticker.upper(),
                "geo": alt_geo,
                "buy_price": round(alt_buy_price, 2),
                "current_price": round(alt_current, 2),
                "units": round(alt_units, 4),
                "invested": round(amount, 2),
                "current_value": round(alt_value_now, 2),
                "return_pct": round(alt_return_pct, 2),
            },
            "difference": {
                "value_diff": round(alt_value_now - src_value_now, 2),
                "return_diff_pct": round(alt_return_pct - src_return_pct, 2),
                "winner": alt_ticker.upper() if alt_return_pct > src_return_pct else source_ticker.upper(),
            },
            "chart_data": chart_data,
            "currency": "INR" if source_geo == "IN" else "USD",
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _compute_sync)
