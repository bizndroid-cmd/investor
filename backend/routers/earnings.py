"""Portfolio Earnings API — passive income, dividends, yield analysis.

Endpoints:
- GET /portfolio/earnings — full earnings breakdown
"""

from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select, desc, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.domain import Session
from backend.models.orm import PortfolioSnapshot, StockFundamentals
from backend.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio/earnings", tags=["earnings"])


@router.get("")
async def get_earnings(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Full earnings breakdown: dividends, yield, cost basis, projections."""

    # Get latest portfolio snapshot
    stmt = (
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == session.user_id)
        .order_by(desc(PortfolioSnapshot.snapshot_date))
    )
    result = await db.execute(stmt)
    all_snapshots = result.scalars().all()

    if not all_snapshots:
        return {"has_data": False}

    # Get latest date's holdings
    latest_date = all_snapshots[0].snapshot_date
    holdings = [s for s in all_snapshots if s.snapshot_date == latest_date]

    # Get fundamentals for dividend data
    tickers = [h.ticker for h in holdings]
    fund_stmt = select(StockFundamentals).where(StockFundamentals.ticker.in_(tickers))
    fund_result = await db.execute(fund_stmt)
    fundamentals = {f.ticker: f for f in fund_result.scalars().all()}

    # --- Dividend Earnings ---
    dividend_stocks = []
    total_annual_dividends = Decimal("0")
    total_portfolio_value = Decimal("0")
    total_invested = Decimal("0")

    for h in holdings:
        fund = fundamentals.get(h.ticker)
        div_yield = Decimal(str(fund.dividend_yield or "0")) if fund else Decimal("0")
        current_value = h.current_value or Decimal("0")
        invested = (h.avg_buy_price or Decimal("0")) * (h.quantity or Decimal("0"))

        total_portfolio_value += current_value
        total_invested += invested

        # Annual dividend = current_value * yield / 100
        annual_dividend = current_value * div_yield / Decimal("100")
        total_annual_dividends += annual_dividend

        # Yield on cost (dividend relative to what you paid)
        yield_on_cost = (annual_dividend / invested * Decimal("100")) if invested > 0 else Decimal("0")

        dividend_stocks.append({
            "ticker": h.ticker,
            "quantity": float(h.quantity),
            "current_value": float(current_value),
            "invested_value": float(invested),
            "dividend_yield_pct": float(div_yield),
            "annual_dividend": round(float(annual_dividend), 2),
            "monthly_dividend": round(float(annual_dividend / 12), 2),
            "yield_on_cost_pct": round(float(yield_on_cost), 2),
            "payout_frequency": _estimate_payout_frequency(h.ticker),
        })

    # Sort by annual dividend descending
    dividend_stocks.sort(key=lambda x: x["annual_dividend"], reverse=True)

    # --- Estimate historical dividends earned per stock ---
    # Uses yfinance dividend history + user's holding quantity
    import asyncio
    historical_dividends = await _estimate_historical_dividends(holdings)

    # Get purchase dates for display
    from backend.models.orm import PortfolioSnapshot as PS2
    from sqlalchemy import func as sa_func
    pd_stmt = (
        select(PS2.ticker, sa_func.min(PS2.snapshot_date).label("first_date"))
        .where(PS2.user_id == session.user_id)
        .group_by(PS2.ticker)
    )
    pd_result = await db.execute(pd_stmt)
    purchase_date_map = {row[0]: row[1].isoformat() for row in pd_result.all()}

    for stock in dividend_stocks:
        stock["total_earned_est"] = historical_dividends.get(stock["ticker"], 0)
        stock["purchase_date"] = purchase_date_map.get(stock["ticker"])

    # --- Cost Basis Breakdown ---
    total_gain = total_portfolio_value - total_invested
    gain_pct = (total_gain / total_invested * 100) if total_invested > 0 else Decimal("0")
    house_money_pct = (total_gain / total_portfolio_value * 100) if total_portfolio_value > 0 else Decimal("0")

    # --- Yield vs Benchmarks ---
    effective_yield = (total_annual_dividends / total_portfolio_value * 100) if total_portfolio_value > 0 else Decimal("0")

    # --- Income Projection ---
    # Project at current rate for 1, 3, 5 years (assuming 8% dividend growth)
    growth_rate = Decimal("1.08")
    projected_1y = total_annual_dividends
    projected_3y = total_annual_dividends * growth_rate ** 3
    projected_5y = total_annual_dividends * growth_rate ** 5

    # --- Top Dividend Earners ---
    paying_stocks = [s for s in dividend_stocks if s["annual_dividend"] > 0]
    non_paying = [s for s in dividend_stocks if s["annual_dividend"] == 0]

    return {
        "has_data": True,
        "snapshot_date": latest_date.isoformat(),

        # Summary
        "summary": {
            "total_portfolio_value": round(float(total_portfolio_value), 2),
            "total_invested": round(float(total_invested), 2),
            "total_annual_dividends": round(float(total_annual_dividends), 2),
            "total_monthly_dividends": round(float(total_annual_dividends / 12), 2),
            "effective_yield_pct": round(float(effective_yield), 2),
            "stocks_paying_dividends": len(paying_stocks),
            "stocks_not_paying": len(non_paying),
        },

        # Cost Basis
        "cost_basis": {
            "total_invested": round(float(total_invested), 2),
            "current_value": round(float(total_portfolio_value), 2),
            "unrealized_gain": round(float(total_gain), 2),
            "gain_pct": round(float(gain_pct), 2),
            "house_money_pct": round(float(house_money_pct), 2),
            "original_capital_pct": round(float(100 - house_money_pct), 2),
        },

        # Yield Comparison
        "yield_comparison": {
            "portfolio_yield": round(float(effective_yield), 2),
            "fd_rate": 7.0,  # Approximate SBI FD rate
            "savings_rate": 3.5,
            "nifty_dividend_yield": 1.3,  # Approximate Nifty 50 div yield
            "ppf_rate": 7.1,
        },

        # Income Projection
        "projection": {
            "annual_now": round(float(projected_1y), 2),
            "annual_3y": round(float(projected_3y), 2),
            "annual_5y": round(float(projected_5y), 2),
            "growth_assumption_pct": 8,
        },

        # Per-stock dividends
        "dividend_stocks": paying_stocks,
        "non_paying_stocks": non_paying,
    }


def _estimate_payout_frequency(ticker: str) -> str:
    """Estimate dividend payout frequency for Indian stocks.

    Most Indian companies pay annually or semi-annually.
    Large-caps with consistent dividends tend to pay interim + final.
    """
    # Companies known for frequent payouts
    quarterly_payers = {"TCS", "INFY", "COALINDIA", "VEDL"}
    semi_annual = {"HDFCBANK", "ITC", "RELIANCE", "ONGC", "LT", "WIPRO"}

    if ticker in quarterly_payers:
        return "Quarterly"
    elif ticker in semi_annual:
        return "Semi-Annual"
    else:
        return "Annual"


async def _estimate_historical_dividends(holdings) -> dict[str, float]:
    """Estimate total dividends earned per stock since purchase.

    Uses the earliest portfolio_snapshot date as a proxy for purchase date.
    Fetches dividend history from yfinance, sums payouts from purchase date onwards.
    Multiplies each payout by user's quantity.
    """
    import asyncio

    # Get earliest snapshot date per ticker from DB
    from backend.database import AsyncSessionLocal
    from backend.models.orm import PortfolioSnapshot
    from sqlalchemy import select, func

    purchase_dates: dict[str, str] = {}
    user_id = holdings[0].user_id if holdings else None

    if user_id:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(
                    PortfolioSnapshot.ticker,
                    func.min(PortfolioSnapshot.snapshot_date).label("first_date"),
                )
                .where(PortfolioSnapshot.user_id == user_id)
                .group_by(PortfolioSnapshot.ticker)
            )
            result = await db.execute(stmt)
            for row in result.all():
                purchase_dates[row[0]] = row[1].isoformat()

    results: dict[str, float] = {}

    def _fetch_dividends(ticker: str, quantity: float, purchase_date_str: str | None) -> tuple[str, float]:
        try:
            import yfinance
            from datetime import datetime, timedelta, timezone as tz

            stock = yfinance.Ticker(f"{ticker}.NS")
            dividends = stock.dividends

            if dividends is None or dividends.empty:
                return ticker, 0.0

            # Use purchase date if available, otherwise 3 years back
            if purchase_date_str:
                import pandas as pd
                cutoff = pd.Timestamp(purchase_date_str, tz="Asia/Kolkata")
            else:
                cutoff = dividends.index[-1] - timedelta(days=3 * 365)

            # Ensure timezone compatibility
            if dividends.index.tz is None:
                dividends.index = dividends.index.tz_localize("Asia/Kolkata")

            recent = dividends[dividends.index >= cutoff]
            total = float(recent.sum()) * quantity
            return ticker, round(total, 2)
        except Exception:
            return ticker, 0.0

    # Run in thread pool
    loop = asyncio.get_event_loop()
    tasks = []
    for h in holdings:
        qty = float(h.quantity or 0)
        if qty > 0:
            pd_str = purchase_dates.get(h.ticker)
            tasks.append(loop.run_in_executor(
                None, _fetch_dividends, h.ticker, qty, pd_str
            ))

    if tasks:
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        for result in completed:
            if isinstance(result, tuple):
                ticker, total = result
                results[ticker] = total

    return results
