"""Remittance Tracker API — cross-border transfer management.

Endpoints:
- GET /remittances — list all transfers with stats
- POST /remittances — record new transfer
- DELETE /remittances/{id} — remove transfer
- GET /remittances/summary — YTD totals, avg rate, best/worst rate
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.domain import Session
from backend.models.orm import Remittance
from backend.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remittances", tags=["remittances"])


class AddRemittanceRequest(BaseModel):
    direction: str = Field(..., pattern="^(inr_to_usd|usd_to_inr)$")
    source_amount: Decimal = Field(..., gt=0)
    exchange_rate: Decimal = Field(..., gt=0)
    provider: str | None = None
    purpose: str | None = None
    transfer_date: date
    notes: str | None = None


@router.get("")
async def list_remittances(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all remittances with computed target amounts."""
    stmt = (
        select(Remittance)
        .where(Remittance.user_id == session.user_id)
        .order_by(desc(Remittance.transfer_date))
    )
    result = await db.execute(stmt)
    transfers = result.scalars().all()

    return {
        "transfers": [
            {
                "id": str(t.id),
                "direction": t.direction,
                "source_amount": float(t.source_amount),
                "source_currency": t.source_currency,
                "target_amount": float(t.target_amount),
                "target_currency": t.target_currency,
                "exchange_rate": float(t.exchange_rate),
                "provider": t.provider,
                "purpose": t.purpose,
                "transfer_date": t.transfer_date.isoformat() if t.transfer_date else None,
                "notes": t.notes,
            }
            for t in transfers
        ],
        "count": len(transfers),
    }


@router.post("", status_code=201)
async def add_remittance(
    body: AddRemittanceRequest,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record a new cross-border transfer."""
    if body.direction == "inr_to_usd":
        source_currency = "INR"
        target_currency = "USD"
        target_amount = body.source_amount / body.exchange_rate
    else:
        source_currency = "USD"
        target_currency = "INR"
        target_amount = body.source_amount * body.exchange_rate

    remittance = Remittance(
        id=uuid4(),
        user_id=session.user_id,
        direction=body.direction,
        source_amount=body.source_amount,
        source_currency=source_currency,
        target_amount=target_amount,
        target_currency=target_currency,
        exchange_rate=body.exchange_rate,
        provider=body.provider,
        purpose=body.purpose,
        transfer_date=body.transfer_date,
        notes=body.notes,
    )
    db.add(remittance)
    await db.commit()

    return {"id": str(remittance.id), "target_amount": float(target_amount)}


@router.delete("/{remittance_id}", status_code=204)
async def delete_remittance(
    remittance_id: UUID,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a remittance record."""
    stmt = select(Remittance).where(Remittance.id == remittance_id, Remittance.user_id == session.user_id)
    r = (await db.execute(stmt)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Remittance not found")
    await db.delete(r)
    await db.commit()
    return Response(status_code=204)


@router.get("/summary")
async def get_remittance_summary(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """YTD summary: total moved, avg rate, best/worst rates."""
    from datetime import datetime, timezone

    ytd_start = date(datetime.now(timezone.utc).year, 1, 1)

    stmt = select(Remittance).where(
        Remittance.user_id == session.user_id,
        Remittance.transfer_date >= ytd_start,
    )
    result = await db.execute(stmt)
    transfers = result.scalars().all()

    if not transfers:
        return {"has_data": False}

    inr_to_usd = [t for t in transfers if t.direction == "inr_to_usd"]
    usd_to_inr = [t for t in transfers if t.direction == "usd_to_inr"]

    # INR sent out
    total_inr_sent = sum(float(t.source_amount) for t in inr_to_usd)
    total_usd_received = sum(float(t.target_amount) for t in inr_to_usd)
    avg_rate_out = (total_inr_sent / total_usd_received) if total_usd_received else 0

    # USD sent to India
    total_usd_sent = sum(float(t.source_amount) for t in usd_to_inr)
    total_inr_received = sum(float(t.target_amount) for t in usd_to_inr)
    avg_rate_in = (total_inr_received / total_usd_sent) if total_usd_sent else 0

    # Best/worst rates
    all_rates = [float(t.exchange_rate) for t in transfers]
    best_rate = max(all_rates) if all_rates else 0
    worst_rate = min(all_rates) if all_rates else 0

    # Live rate for comparison
    from backend.services.forex_service import get_usdinr_rate
    live = await get_usdinr_rate()
    spot_rate = live.get("rate", 83.5)

    return {
        "has_data": True,
        "ytd": {
            "total_transfers": len(transfers),
            "inr_to_usd": {
                "count": len(inr_to_usd),
                "total_inr_sent": round(total_inr_sent, 2),
                "total_usd_received": round(total_usd_received, 2),
                "avg_rate": round(avg_rate_out, 2),
            },
            "usd_to_inr": {
                "count": len(usd_to_inr),
                "total_usd_sent": round(total_usd_sent, 2),
                "total_inr_received": round(total_inr_received, 2),
                "avg_rate": round(avg_rate_in, 2),
            },
        },
        "rates": {
            "best": round(best_rate, 2),
            "worst": round(worst_rate, 2),
            "current_spot": round(spot_rate, 2),
        },
        "providers_used": list({t.provider for t in transfers if t.provider}),
    }
