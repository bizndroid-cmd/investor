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
