"""Financial Goals API — targets, progress tracking, wealth entries.

Endpoints:
- GET /goals — list all goals with progress
- POST /goals — create goal
- PUT /goals/{id} — update goal
- DELETE /goals/{id} — remove goal
- GET /goals/{id}/entries — list wealth entries for a goal
- POST /goals/entries — add wealth entry
- DELETE /goals/entries/{id} — remove entry
- GET /goals/summary — total wealth summary across all sources
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.domain import Session
from backend.models.orm import Goal, WealthEntry, PortfolioDailySummary, ETFHolding
from backend.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/goals", tags=["goals"])

# Approximate exchange rate — will be updated from market data
USD_TO_INR = 83.5
INR_TO_USD = 1 / USD_TO_INR


class CreateGoalRequest(BaseModel):
    name: str = Field(..., max_length=100)
    target_amount: Decimal = Field(..., gt=0)
    target_currency: str = Field(..., pattern="^(INR|USD)$")
    deadline: date | None = None
    icon: str = "target"
    color: str = "blue"


class UpdateGoalRequest(BaseModel):
    name: str | None = None
    target_amount: Decimal | None = Field(None, gt=0)
    deadline: date | None = None
    icon: str | None = None
    color: str | None = None
    is_active: bool | None = None


class AddEntryRequest(BaseModel):
    goal_id: str | None = None
    category: str = Field(..., pattern="^(savings|fd|real_estate|crypto|gold_physical|ppf|nps|other)$")
    label: str = Field(..., max_length=100)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., pattern="^(INR|USD)$")
    entry_date: date
    notes: str | None = None


def _convert_to(amount: float, from_currency: str, to_currency: str) -> float:
    """Convert amount between INR and USD."""
    if from_currency == to_currency:
        return amount
    if from_currency == "USD" and to_currency == "INR":
        return amount * USD_TO_INR
    if from_currency == "INR" and to_currency == "USD":
        return amount * INR_TO_USD
    return amount


@router.get("")
async def list_goals(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all goals with current progress."""
    stmt = select(Goal).where(Goal.user_id == session.user_id).order_by(Goal.created_at)
    result = await db.execute(stmt)
    goals = result.scalars().all()

    if not goals:
        return []

    # Get total wealth per goal
    enriched = []
    for goal in goals:
        progress = await _compute_goal_progress(db, session.user_id, goal)
        enriched.append(progress)

    return enriched


@router.post("", status_code=201)
async def create_goal(
    body: CreateGoalRequest,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new financial goal."""
    goal = Goal(
        id=uuid4(),
        user_id=session.user_id,
        name=body.name,
        target_amount=body.target_amount,
        target_currency=body.target_currency,
        deadline=body.deadline,
        icon=body.icon,
        color=body.color,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)

    return {
        "id": str(goal.id),
        "name": goal.name,
        "target_amount": float(goal.target_amount),
        "target_currency": goal.target_currency,
        "deadline": goal.deadline.isoformat() if goal.deadline else None,
        "icon": goal.icon,
        "color": goal.color,
    }


@router.put("/{goal_id}")
async def update_goal(
    goal_id: UUID,
    body: UpdateGoalRequest,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a goal."""
    stmt = select(Goal).where(Goal.id == goal_id, Goal.user_id == session.user_id)
    goal = (await db.execute(stmt)).scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    if body.name is not None:
        goal.name = body.name
    if body.target_amount is not None:
        goal.target_amount = body.target_amount
    if body.deadline is not None:
        goal.deadline = body.deadline
    if body.icon is not None:
        goal.icon = body.icon
    if body.color is not None:
        goal.color = body.color
    if body.is_active is not None:
        goal.is_active = body.is_active

    await db.commit()
    return {"status": "updated"}


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: UUID,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a goal and its entries."""
    stmt = select(Goal).where(Goal.id == goal_id, Goal.user_id == session.user_id)
    goal = (await db.execute(stmt)).scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.delete(goal)
    await db.commit()
    return Response(status_code=204)


@router.get("/{goal_id}/entries")
async def list_entries(
    goal_id: UUID,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all wealth entries for a goal."""
    stmt = (
        select(WealthEntry)
        .where(WealthEntry.user_id == session.user_id, WealthEntry.goal_id == goal_id)
        .order_by(desc(WealthEntry.entry_date))
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()

    return [
        {
            "id": str(e.id),
            "category": e.category,
            "label": e.label,
            "amount": float(e.amount),
            "currency": e.currency,
            "entry_date": e.entry_date.isoformat() if e.entry_date else None,
            "notes": e.notes,
        }
        for e in entries
    ]


@router.post("/entries", status_code=201)
async def add_entry(
    body: AddEntryRequest,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a wealth entry."""
    goal_id = UUID(body.goal_id) if body.goal_id else None

    # Verify goal ownership if specified
    if goal_id:
        stmt = select(Goal).where(Goal.id == goal_id, Goal.user_id == session.user_id)
        goal = (await db.execute(stmt)).scalar_one_or_none()
        if not goal:
            raise HTTPException(status_code=404, detail="Goal not found")

    entry = WealthEntry(
        id=uuid4(),
        user_id=session.user_id,
        goal_id=goal_id,
        category=body.category,
        label=body.label,
        amount=body.amount,
        currency=body.currency,
        entry_date=body.entry_date,
        notes=body.notes,
    )
    db.add(entry)
    await db.commit()

    return {"id": str(entry.id), "status": "created"}


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: UUID,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a wealth entry."""
    stmt = select(WealthEntry).where(WealthEntry.id == entry_id, WealthEntry.user_id == session.user_id)
    entry = (await db.execute(stmt)).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    await db.delete(entry)
    await db.commit()
    return Response(status_code=204)


@router.get("/summary")
async def get_wealth_summary(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Total wealth summary across all sources: stocks, ETFs, manual entries."""

    # 1. Portfolio value (latest snapshot)
    portfolio_stmt = (
        select(PortfolioDailySummary)
        .where(PortfolioDailySummary.user_id == session.user_id)
        .order_by(desc(PortfolioDailySummary.snapshot_date))
        .limit(1)
    )
    portfolio_result = await db.execute(portfolio_stmt)
    portfolio_summary = portfolio_result.scalar_one_or_none()

    stocks_inr = float(portfolio_summary.total_value) if portfolio_summary else 0

    # 2. ETF value
    etf_stmt = select(ETFHolding).where(ETFHolding.user_id == session.user_id)
    etf_result = await db.execute(etf_stmt)
    etf_holdings = etf_result.scalars().all()

    etf_inr = sum(float(e.buy_price * e.quantity) for e in etf_holdings if e.currency == "INR")
    etf_usd = sum(float(e.buy_price * e.quantity) for e in etf_holdings if e.currency == "USD")

    # 3. Manual wealth entries (sum by category)
    entry_stmt = select(WealthEntry).where(WealthEntry.user_id == session.user_id)
    entry_result = await db.execute(entry_stmt)
    entries = entry_result.scalars().all()

    # Aggregate entries by category, convert to INR for total
    categories: dict[str, float] = {}
    manual_total_inr = 0.0
    for e in entries:
        val_inr = _convert_to(float(e.amount), e.currency, "INR")
        categories[e.category] = categories.get(e.category, 0) + val_inr
        manual_total_inr += val_inr

    # Total in INR
    total_inr = stocks_inr + etf_inr + _convert_to(etf_usd, "USD", "INR") + manual_total_inr

    return {
        "total_wealth_inr": round(total_inr, 2),
        "total_wealth_usd": round(total_inr * INR_TO_USD, 2),
        "breakdown": {
            "stocks_inr": round(stocks_inr, 2),
            "etf_inr": round(etf_inr + _convert_to(etf_usd, "USD", "INR"), 2),
            "manual_inr": round(manual_total_inr, 2),
        },
        "categories": {k: round(v, 2) for k, v in sorted(categories.items(), key=lambda x: -x[1])},
    }


async def _compute_goal_progress(db: AsyncSession, user_id: UUID, goal: Goal) -> dict:
    """Compute progress for a single goal."""

    # Get entries for this goal
    stmt = select(WealthEntry).where(
        WealthEntry.user_id == user_id,
        WealthEntry.goal_id == goal.id,
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()

    # Sum entries in goal's target currency
    entries_total = 0.0
    for e in entries:
        entries_total += _convert_to(float(e.amount), e.currency, goal.target_currency)

    # Auto-include stocks + ETFs value (converted to goal currency)
    # Portfolio value
    portfolio_stmt = (
        select(PortfolioDailySummary)
        .where(PortfolioDailySummary.user_id == user_id)
        .order_by(desc(PortfolioDailySummary.snapshot_date))
        .limit(1)
    )
    portfolio_result = await db.execute(portfolio_stmt)
    portfolio_summary = portfolio_result.scalar_one_or_none()
    stocks_val = _convert_to(
        float(portfolio_summary.total_value) if portfolio_summary else 0,
        "INR", goal.target_currency
    )

    # ETF value
    etf_stmt = select(ETFHolding).where(ETFHolding.user_id == user_id)
    etf_result = await db.execute(etf_stmt)
    etfs = etf_result.scalars().all()
    etf_val = sum(
        _convert_to(float(e.buy_price * e.quantity), e.currency, goal.target_currency)
        for e in etfs
    )

    current_total = entries_total + stocks_val + etf_val
    target = float(goal.target_amount)
    progress_pct = min(100, (current_total / target * 100)) if target > 0 else 0

    # Estimate time to goal (simple: based on monthly average contribution from entries)
    months_to_goal = None
    if entries and current_total < target:
        # Average monthly contribution from entries
        dates = [e.entry_date for e in entries if e.entry_date]
        if len(dates) >= 2:
            from datetime import timedelta
            span_days = (max(dates) - min(dates)).days or 30
            monthly_rate = entries_total / (span_days / 30)
            if monthly_rate > 0:
                remaining = target - current_total
                months_to_goal = round(remaining / monthly_rate, 1)

    return {
        "id": str(goal.id),
        "name": goal.name,
        "target_amount": target,
        "target_currency": goal.target_currency,
        "deadline": goal.deadline.isoformat() if goal.deadline else None,
        "icon": goal.icon,
        "color": goal.color,
        "is_active": goal.is_active,
        "current_total": round(current_total, 2),
        "progress_pct": round(progress_pct, 1),
        "entries_total": round(entries_total, 2),
        "stocks_value": round(stocks_val, 2),
        "etf_value": round(etf_val, 2),
        "entries_count": len(entries),
        "months_to_goal": months_to_goal,
    }
