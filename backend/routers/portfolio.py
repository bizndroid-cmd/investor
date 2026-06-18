"""FastAPI portfolio router for aggregated holdings and portfolio data.

Endpoints:
- GET /portfolio — returns full Portfolio for current user
- GET /portfolio/holdings — returns list of NormalizedHolding (optionally filtered by broker_id)
- POST /portfolio/refresh — triggers refresh_all, returns list of RefreshResult
"""

from __future__ import annotations

import logging
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.connectors.fidelity import FidelityConnector
from backend.connectors.groww import GrowwConnector
from backend.connectors.robinhood import RobinhoodConnector
from backend.connectors.zerodha import ZerodhaConnector
from backend.database import get_db
from backend.interfaces.broker_connector import IBrokerConnector
from backend.interfaces.market_data_service import IMarketDataService
from backend.models.domain import (
    BrokerId,
    NormalizedHolding,
    Portfolio,
    RefreshResult,
    Session,
)
from backend.config import settings
from backend.routers.auth import get_current_user, get_redis
from backend.services.aggregator_service import AggregatorService
from backend.services.market_data_service import MarketDataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# Registry of all available broker connectors
_CONNECTORS: dict[BrokerId, IBrokerConnector] = {
    "groww": GrowwConnector(),
    "zerodha": ZerodhaConnector(),
    "fidelity": FidelityConnector(),
    "robinhood": RobinhoodConnector(),
}


class _StubMarketDataService(IMarketDataService):
    """Stub market data service used until the real one is wired via DI."""

    async def get_current_price(self, ticker: str):
        from datetime import datetime, timezone
        from decimal import Decimal

        from backend.models.domain import PriceQuote

        return PriceQuote(
            ticker=ticker,
            price=Decimal("0"),
            previous_close=Decimal("0"),
            change=Decimal("0"),
            change_percent=Decimal("0"),
            timestamp=datetime.now(timezone.utc),
            is_stale=True,
        )

    async def get_batch_prices(self, tickers: list[str]):
        from datetime import datetime, timezone
        from decimal import Decimal

        from backend.models.domain import PriceQuote

        result = {}
        for ticker in tickers:
            result[ticker] = PriceQuote(
                ticker=ticker,
                price=Decimal("0"),
                previous_close=Decimal("0"),
                change=Decimal("0"),
                change_percent=Decimal("0"),
                timestamp=datetime.now(timezone.utc),
                is_stale=True,
            )
        return result

    async def get_historical_data(self, ticker: str, range):
        return []


# Placeholder for the market data service — will be replaced by DI in main.py
_market_data_service: IMarketDataService = _StubMarketDataService()


def get_aggregator_service(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> AggregatorService:
    """Dependency that provides an AggregatorService instance."""
    market_data_svc = MarketDataService(redis=redis, finnhub_api_key=settings.finnhub_api_key)
    return AggregatorService(
        db=db,
        redis=redis,
        connectors=_CONNECTORS,
        market_data_service=market_data_svc,
    )


@router.get("", response_model=Portfolio)
async def get_portfolio(
    session: Session = Depends(get_current_user),
    aggregator: AggregatorService = Depends(get_aggregator_service),
    db: AsyncSession = Depends(get_db),
) -> Portfolio:
    """Return the aggregated portfolio for the current user.
    
    Strategy: Serve from today's stored snapshot if available.
    Only fetches live from broker APIs once per day (on first access),
    then serves cached DB data for subsequent requests.
    """
    from backend.services.portfolio_snapshot_service import PortfolioSnapshotService
    from backend.models.orm import PortfolioDailySummary, PortfolioSnapshot
    from zoneinfo import ZoneInfo
    from datetime import datetime
    from decimal import Decimal
    from sqlalchemy import select

    IST = ZoneInfo("Asia/Kolkata")
    today = datetime.now(IST).date()

    # Check if we already have today's snapshot
    stmt = select(PortfolioDailySummary).where(
        PortfolioDailySummary.user_id == session.user_id,
        PortfolioDailySummary.snapshot_date == today,
    )
    result = await db.execute(stmt)
    existing_summary = result.scalar_one_or_none()

    # Fallback: if no today snapshot, try most recent available
    if not existing_summary:
        from sqlalchemy import desc
        stmt = (
            select(PortfolioDailySummary)
            .where(PortfolioDailySummary.user_id == session.user_id)
            .order_by(desc(PortfolioDailySummary.snapshot_date))
            .limit(1)
        )
        result = await db.execute(stmt)
        existing_summary = result.scalar_one_or_none()

    if existing_summary:
        # Serve from stored snapshot (no broker API call)
        holdings_stmt = select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == session.user_id,
            PortfolioSnapshot.snapshot_date == existing_summary.snapshot_date,
        )
        holdings_result = await db.execute(holdings_stmt)
        snapshot_holdings = holdings_result.scalars().all()

        holdings = [
            NormalizedHolding(
                ticker=h.ticker,
                company_name=h.ticker,
                broker_id=h.broker_id,
                quantity=h.quantity,
                avg_buy_price=h.avg_buy_price,
                current_price=h.current_price,
                current_value=h.current_value,
                gain_loss=h.gain_loss,
                gain_loss_percent=h.gain_loss_percent,
                currency=h.currency,
                last_updated=existing_summary.created_at,
                is_stale=False,
            )
            for h in snapshot_holdings
        ]

        return Portfolio(
            user_id=session.user_id,
            holdings=holdings,
            total_value=existing_summary.total_value,
            total_invested=existing_summary.total_invested,
            total_gain_loss=existing_summary.total_gain_loss,
            total_gain_loss_percent=existing_summary.total_gain_loss_percent,
            day_change=existing_summary.day_change,
            day_change_percent=existing_summary.day_change_percent,
            broker_statuses=[],
            last_refreshed=existing_summary.created_at,
        )

    # No snapshot for today — fetch live from broker APIs (first access of the day)
    portfolio = await aggregator.get_portfolio(user_id=session.user_id)

    # Store today's snapshot
    try:
        snapshot_svc = PortfolioSnapshotService(db=db)
        await snapshot_svc.capture_snapshot(user_id=session.user_id, portfolio=portfolio)
    except Exception as e:
        logger.debug("Snapshot capture skipped: %s", str(e))

    return portfolio


@router.get("/holdings", response_model=list[NormalizedHolding])
async def get_holdings(
    broker_id: Optional[BrokerId] = Query(default=None, description="Filter holdings by broker"),
    session: Session = Depends(get_current_user),
    aggregator: AggregatorService = Depends(get_aggregator_service),
) -> list[NormalizedHolding]:
    """Return normalized holdings, optionally filtered by broker_id."""
    if broker_id:
        return await aggregator.get_holdings_by_broker(
            user_id=session.user_id, broker_id=broker_id
        )
    # Return all holdings from the portfolio
    portfolio = await aggregator.get_portfolio(user_id=session.user_id)
    return portfolio.holdings


@router.post("/refresh", response_model=list[RefreshResult])
async def refresh_portfolio(
    session: Session = Depends(get_current_user),
    aggregator: AggregatorService = Depends(get_aggregator_service),
    db: AsyncSession = Depends(get_db),
) -> list[RefreshResult]:
    """Trigger a force-refresh from all connected brokers."""
    results = await aggregator.refresh_all(user_id=session.user_id)

    # Capture snapshot after refresh with fresh data
    try:
        portfolio = await aggregator.get_portfolio(user_id=session.user_id)
        from backend.services.portfolio_snapshot_service import PortfolioSnapshotService
        snapshot_svc = PortfolioSnapshotService(db=db)
        await snapshot_svc.capture_snapshot(user_id=session.user_id, portfolio=portfolio)
    except Exception as e:
        logger.debug("Snapshot capture after refresh skipped: %s", str(e))

    return results


@router.get("/fundamentals")
async def get_fundamentals(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get stock fundamentals for all portfolio tickers."""
    from backend.services.screener_service import ScreenerService
    from backend.models.orm import HoldingCache, PortfolioSnapshot
    from sqlalchemy import select, distinct

    # Try holdings cache first
    stmt = select(HoldingCache.ticker).where(HoldingCache.user_id == session.user_id)
    result = await db.execute(stmt)
    tickers = [r[0] for r in result.all()]

    # Fallback: get tickers from portfolio snapshots
    if not tickers:
        stmt = select(distinct(PortfolioSnapshot.ticker)).where(
            PortfolioSnapshot.user_id == session.user_id
        )
        result = await db.execute(stmt)
        tickers = [r[0] for r in result.all()]

    if not tickers:
        return []

    svc = ScreenerService(db=db)
    return await svc.get_all_fundamentals(tickers)


@router.post("/fundamentals/refresh")
async def refresh_fundamentals(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a refresh of stock fundamentals from screener.in."""
    from backend.services.screener_service import ScreenerService
    from backend.models.orm import HoldingCache, PortfolioSnapshot
    from sqlalchemy import select, distinct

    # Try holdings cache
    stmt = select(HoldingCache.ticker).where(HoldingCache.user_id == session.user_id)
    result = await db.execute(stmt)
    tickers = [r[0] for r in result.all()]

    # Fallback: portfolio snapshots
    if not tickers:
        stmt = select(distinct(PortfolioSnapshot.ticker)).where(
            PortfolioSnapshot.user_id == session.user_id
        )
        result = await db.execute(stmt)
        tickers = [r[0] for r in result.all()]

    if not tickers:
        return {"status": "no_tickers", "updated": 0}

    svc = ScreenerService(db=db)
    count = await svc.fetch_all_portfolio(tickers)
    return {"status": "completed", "updated": count, "total": len(tickers)}
