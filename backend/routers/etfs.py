"""ETF Holdings API — track, manage, and analyze ETF investments.

Endpoints:
- GET /etfs — list holdings with market data
- POST /etfs — add new ETF holding
- PUT /etfs/{id} — update holding
- DELETE /etfs/{id} — remove holding
- GET /etfs/{id}/details — detailed ETF info card
- GET /etfs/insights — aggregate insights and projections
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_portfolio_id as get_portfolio_id_dep
from backend.models.domain import Session
from backend.models.orm import ETFHolding
from backend.routers.auth import get_current_user
from backend.services import etf_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/etfs", tags=["etfs"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class AddETFRequest(BaseModel):
    ticker: str = Field(..., max_length=20)
    quantity: Decimal = Field(..., gt=0)
    buy_price: Decimal = Field(..., gt=0)
    buy_date: date | None = None
    geo_id: str = Field(..., pattern="^(IN|US)$")


class UpdateETFRequest(BaseModel):
    quantity: Decimal | None = Field(None, gt=0)
    buy_price: Decimal | None = Field(None, gt=0)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_etf_holdings(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    portfolio_id=Depends(get_portfolio_id_dep),
) -> dict:
    """List user's ETF holdings with current market data."""
    filters = [ETFHolding.user_id == session.user_id]
    if portfolio_id:
        filters.append(ETFHolding.portfolio_id == portfolio_id)

    stmt = select(ETFHolding).where(*filters).order_by(ETFHolding.created_at.desc())
    result = await db.execute(stmt)
    holdings = result.scalars().all()

    if not holdings:
        return {"has_data": False, "holdings": [], "total_value_inr": 0, "total_value_usd": 0}

    # Fetch market data in parallel
    tasks = [
        etf_service.get_etf_market_data(h.ticker, h.geo_id)
        for h in holdings
    ]
    market_results = await asyncio.gather(*tasks, return_exceptions=True)

    enriched = []
    total_value_inr = Decimal("0")
    total_value_usd = Decimal("0")

    for h, mkt in zip(holdings, market_results):
        if isinstance(mkt, Exception) or mkt is None:
            mkt = {}

        current_price = Decimal(str(mkt.get("current_price", 0)))
        current_value = current_price * h.quantity
        invested_value = h.buy_price * h.quantity
        gain_loss = current_value - invested_value
        gain_loss_pct = (gain_loss / invested_value * 100) if invested_value > 0 else Decimal("0")

        if h.currency == "INR":
            total_value_inr += current_value
        else:
            total_value_usd += current_value

        enriched.append({
            "id": str(h.id),
            "ticker": h.ticker,
            "name": h.name or mkt.get("name", ""),
            "quantity": float(h.quantity),
            "buy_price": float(h.buy_price),
            "buy_date": h.buy_date.isoformat() if h.buy_date else None,
            "geo_id": h.geo_id,
            "currency": h.currency,
            "current_price": float(current_price),
            "current_value": round(float(current_value), 2),
            "invested_value": round(float(invested_value), 2),
            "gain_loss": round(float(gain_loss), 2),
            "gain_loss_pct": round(float(gain_loss_pct), 2),
            "day_change": mkt.get("day_change", 0),
            "day_change_pct": mkt.get("day_change_pct", 0),
            "category": mkt.get("category", ""),
            "expense_ratio": mkt.get("expense_ratio"),
        })

        # Update name if missing
        if not h.name and mkt.get("name"):
            h.name = mkt["name"]
            db.add(h)

    await db.commit()

    return {
        "has_data": True,
        "holdings": enriched,
        "total_value_inr": round(float(total_value_inr), 2),
        "total_value_usd": round(float(total_value_usd), 2),
    }


@router.post("", status_code=201)
async def add_etf_holding(
    body: AddETFRequest,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    portfolio_id=Depends(get_portfolio_id_dep),
) -> dict:
    """Add a new ETF holding."""
    currency = "INR" if body.geo_id == "IN" else "USD"

    # Check for duplicate
    stmt = select(ETFHolding).where(
        ETFHolding.user_id == session.user_id,
        ETFHolding.ticker == body.ticker.upper(),
        ETFHolding.geo_id == body.geo_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"ETF {body.ticker} ({body.geo_id}) already exists")

    holding = ETFHolding(
        id=uuid4(),
        user_id=session.user_id,
        ticker=body.ticker.upper(),
        quantity=body.quantity,
        buy_price=body.buy_price,
        buy_date=body.buy_date,
        geo_id=body.geo_id,
        currency=currency,
        portfolio_id=portfolio_id,
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)

    return {
        "id": str(holding.id),
        "ticker": holding.ticker,
        "quantity": float(holding.quantity),
        "buy_price": float(holding.buy_price),
        "buy_date": holding.buy_date.isoformat() if holding.buy_date else None,
        "geo_id": holding.geo_id,
        "currency": holding.currency,
    }


@router.put("/{holding_id}")
async def update_etf_holding(
    holding_id: UUID,
    body: UpdateETFRequest,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update an ETF holding's quantity or buy price."""
    stmt = select(ETFHolding).where(
        ETFHolding.id == holding_id,
        ETFHolding.user_id == session.user_id,
    )
    holding = (await db.execute(stmt)).scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=404, detail="ETF holding not found")

    if body.quantity is not None:
        holding.quantity = body.quantity
    if body.buy_price is not None:
        holding.buy_price = body.buy_price

    db.add(holding)
    await db.commit()
    await db.refresh(holding)

    return {
        "id": str(holding.id),
        "ticker": holding.ticker,
        "quantity": float(holding.quantity),
        "buy_price": float(holding.buy_price),
    }


@router.delete("/{holding_id}", status_code=204)
async def delete_etf_holding(
    holding_id: UUID,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove an ETF holding."""
    stmt = select(ETFHolding).where(
        ETFHolding.id == holding_id,
        ETFHolding.user_id == session.user_id,
    )
    holding = (await db.execute(stmt)).scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=404, detail="ETF holding not found")

    await db.delete(holding)
    await db.commit()
    return Response(status_code=204)


@router.get("/insights")
async def get_etf_insights(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    portfolio_id=Depends(get_portfolio_id_dep),
) -> dict:
    """Aggregate ETF insights: total value, allocation, performance, projections."""
    filters = [ETFHolding.user_id == session.user_id]
    if portfolio_id:
        filters.append(ETFHolding.portfolio_id == portfolio_id)

    stmt = select(ETFHolding).where(*filters)
    result = await db.execute(stmt)
    holdings = result.scalars().all()

    if not holdings:
        return {"has_data": False}

    # Fetch market data + returns in parallel
    market_tasks = [etf_service.get_etf_market_data(h.ticker, h.geo_id) for h in holdings]
    return_tasks = [etf_service.get_etf_returns(h.ticker, h.geo_id) for h in holdings]

    market_results = await asyncio.gather(*market_tasks, return_exceptions=True)
    return_results = await asyncio.gather(*return_tasks, return_exceptions=True)

    holdings_data = []
    total_value_inr = 0.0
    total_value_usd = 0.0
    best_performer = None
    worst_performer = None

    for h, mkt, rets in zip(holdings, market_results, return_results):
        if isinstance(mkt, Exception) or mkt is None:
            mkt = {}
        if isinstance(rets, Exception) or rets is None:
            rets = {}

        current_price = float(mkt.get("current_price", 0))
        current_value = current_price * float(h.quantity)
        invested_value = float(h.buy_price) * float(h.quantity)
        gain_loss_pct = ((current_value - invested_value) / invested_value * 100) if invested_value > 0 else 0

        if h.currency == "INR":
            total_value_inr += current_value
        else:
            total_value_usd += current_value

        entry = {
            "ticker": h.ticker,
            "geo_id": h.geo_id,
            "currency": h.currency,
            "current_value": current_value,
            "gain_loss_pct": gain_loss_pct,
            "category": mkt.get("category", ""),
            "return_1y": rets.get("return_1y"),
            "return_3y": rets.get("return_3y"),
            "return_5y": rets.get("return_5y"),
        }
        holdings_data.append(entry)

        if best_performer is None or gain_loss_pct > best_performer["gain_loss_pct"]:
            best_performer = {"ticker": h.ticker, "gain_loss_pct": round(gain_loss_pct, 2)}
        if worst_performer is None or gain_loss_pct < worst_performer["gain_loss_pct"]:
            worst_performer = {"ticker": h.ticker, "gain_loss_pct": round(gain_loss_pct, 2)}

    allocation = etf_service.get_category_allocation(holdings_data)
    projections = etf_service.compute_projections(holdings_data)

    return {
        "has_data": True,
        "total_value_inr": round(total_value_inr, 2),
        "total_value_usd": round(total_value_usd, 2),
        "holdings_count": len(holdings),
        "allocation": allocation,
        "best_performer": best_performer,
        "worst_performer": worst_performer,
        "projections": projections,
    }


@router.get("/{holding_id}/details")
async def get_etf_detail(
    holding_id: UUID,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Detailed ETF info card: category, expense ratio, returns, top holdings."""
    stmt = select(ETFHolding).where(
        ETFHolding.id == holding_id,
        ETFHolding.user_id == session.user_id,
    )
    holding = (await db.execute(stmt)).scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=404, detail="ETF holding not found")

    details = await etf_service.get_etf_details(holding.ticker, holding.geo_id)
    if not details:
        raise HTTPException(status_code=502, detail="Failed to fetch ETF details from market data provider")

    return {
        "id": str(holding.id),
        "ticker": holding.ticker,
        "name": details.get("name", holding.name or ""),
        "geo_id": holding.geo_id,
        "currency": holding.currency,
        "quantity": float(holding.quantity),
        "buy_price": float(holding.buy_price),
        "buy_date": holding.buy_date.isoformat() if holding.buy_date else None,
        **details,
    }


@router.get("/comparison")
async def get_etf_comparison(
    mock_ticker: Optional[str] = None,
    mock_geo_id: Optional[str] = None,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    portfolio_id=Depends(get_portfolio_id_dep),
) -> dict:
    """Historical performance comparison of user's ETFs + optional mock ETF.

    Returns normalized price series (base=100 at earliest buy_date) for each ETF.
    If mock_ticker is provided, adds its series for the same period.
    """
    filters = [ETFHolding.user_id == session.user_id]
    if portfolio_id:
        filters.append(ETFHolding.portfolio_id == portfolio_id)

    stmt = select(ETFHolding).where(*filters)
    result = await db.execute(stmt)
    holdings = result.scalars().all()

    if not holdings:
        return {"has_data": False, "series": [], "tickers": []}

    # Find earliest buy_date across all holdings
    buy_dates = [h.buy_date for h in holdings if h.buy_date]
    if not buy_dates:
        # Default to 1 year ago
        from datetime import date, timedelta
        earliest = date.today() - timedelta(days=365)
    else:
        earliest = min(buy_dates)

    # Gather tickers to fetch
    ticker_configs = [(h.ticker, h.geo_id) for h in holdings]
    if mock_ticker and mock_geo_id:
        ticker_configs.append((mock_ticker.upper(), mock_geo_id))

    # Fetch historical series sequentially (yfinance has thread-safety issues)
    results = []
    for t, g in ticker_configs:
        try:
            hist = await etf_service.get_etf_history(t, g, str(earliest))
            results.append(hist)
        except Exception as e:
            results.append(None)

    series = []
    tickers = []
    for (ticker, geo_id), hist in zip(ticker_configs, results):
        if hist is None or len(hist) == 0:
            continue
        tickers.append({
            "ticker": ticker,
            "geo_id": geo_id,
            "is_mock": bool(mock_ticker and ticker == mock_ticker.upper() and geo_id == mock_geo_id),
        })
        series.append(hist)

    # Build unified time series with normalized values (base=100)
    if not series:
        return {"has_data": False, "series": [], "tickers": []}

    # Find common dates across all series
    all_dates = set()
    for s in series:
        all_dates.update(s.keys())
    sorted_dates = sorted(all_dates)

    # Normalize each series to base 100
    chart_data = []
    for d in sorted_dates:
        point = {"date": d}
        for i, s in enumerate(series):
            if d in s:
                # Normalize: first available value = 100
                first_val = next(iter(s.values()))
                point[tickers[i]["ticker"]] = round(s[d] / first_val * 100, 2) if first_val > 0 else 0
        chart_data.append(point)

    return {
        "has_data": True,
        "tickers": tickers,
        "chart_data": chart_data,
        "start_date": str(earliest),
    }
