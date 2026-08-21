"""SnapTrade integration router — connect US brokers via OAuth.

Endpoints:
- POST /snaptrade/register — register user with SnapTrade (first time)
- GET /snaptrade/connect-url — get Connection Portal URL (opens broker login)
- GET /snaptrade/accounts — list connected brokerage accounts
- GET /snaptrade/holdings — fetch holdings from all connected US accounts
- GET /snaptrade/connections — list active connections
- DELETE /snaptrade/disconnect — remove all connections
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.domain import Session
from backend.models.orm import UserPreferences
from backend.routers.auth import get_current_user
from backend.services.snaptrade_service import SnapTradeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/snaptrade", tags=["snaptrade"])


async def _get_user_secret(db: AsyncSession, user_id: UUID) -> str | None:
    """Get stored SnapTrade user secret from preferences."""
    # Store in user_preferences.timezone field temporarily (hack)
    # TODO: Add dedicated snaptrade_user_secret column
    stmt = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()
    if prefs and prefs.currency_code and prefs.currency_code.startswith("ST:"):
        return prefs.currency_code[3:]  # Strip "ST:" prefix
    return None


async def _store_user_secret(db: AsyncSession, user_id: UUID, secret: str) -> None:
    """Store SnapTrade user secret."""
    from uuid import uuid4

    stmt = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = UserPreferences(id=uuid4(), user_id=user_id, geography="US")
        db.add(prefs)

    # Store with prefix to distinguish from actual currency codes
    prefs.currency_code = f"ST:{secret}"
    await db.commit()


@router.post("/register")
async def register_snaptrade_user(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register user with SnapTrade. Only needed once."""
    # Check if already registered
    existing_secret = await _get_user_secret(db, session.user_id)
    if existing_secret:
        return {"status": "already_registered", "message": "User already connected to SnapTrade"}

    svc = SnapTradeService()
    result = await svc.register_user(session.user_id)

    if not result:
        raise HTTPException(status_code=502, detail="Failed to register with SnapTrade")

    user_secret = result.get("userSecret")
    if not user_secret:
        raise HTTPException(status_code=502, detail="SnapTrade did not return userSecret")

    # Store the secret
    await _store_user_secret(db, session.user_id, user_secret)

    return {"status": "registered", "message": "Ready to connect broker"}


@router.get("/connect-url")
async def get_connect_url(
    broker: str | None = None,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get Connection Portal URL. User opens this to connect their broker via OAuth.

    Optional broker param: ROBINHOOD, FIDELITY, ETRADE, SCHWAB, etc.
    If omitted, user picks from SnapTrade's broker list.
    """
    user_secret = await _get_user_secret(db, session.user_id)
    if not user_secret:
        raise HTTPException(status_code=400, detail="Register with SnapTrade first (POST /snaptrade/register)")

    svc = SnapTradeService()
    url = await svc.get_login_url(session.user_id, user_secret, broker=broker)

    if not url:
        raise HTTPException(status_code=502, detail="Failed to get connection URL from SnapTrade")

    return {"connect_url": url, "broker": broker}


@router.get("/accounts")
async def list_accounts(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all connected brokerage accounts."""
    user_secret = await _get_user_secret(db, session.user_id)
    if not user_secret:
        return {"accounts": [], "message": "Not registered with SnapTrade"}

    svc = SnapTradeService()
    accounts = await svc.list_accounts(session.user_id, user_secret)

    return {
        "accounts": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "number": a.get("number"),
                "institution_name": a.get("institutionName"),
                "type": a.get("type"),
                "balance": a.get("balance"),
            }
            for a in accounts
        ],
        "count": len(accounts),
    }


@router.get("/holdings")
async def get_holdings(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fetch holdings from all connected US broker accounts."""
    user_secret = await _get_user_secret(db, session.user_id)
    if not user_secret:
        return {"holdings": [], "message": "Not registered with SnapTrade"}

    svc = SnapTradeService()
    holdings = await svc.get_holdings(session.user_id, user_secret)

    return {
        "holdings": [
            {
                "ticker": h.ticker,
                "company_name": h.company_name,
                "quantity": float(h.quantity),
                "avg_buy_price": float(h.avg_buy_price),
                "currency": h.currency,
                "broker_id": "snaptrade",
            }
            for h in holdings
        ],
        "count": len(holdings),
    }


@router.get("/connections")
async def list_connections(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List active brokerage connections."""
    user_secret = await _get_user_secret(db, session.user_id)
    if not user_secret:
        return {"connections": []}

    svc = SnapTradeService()
    connections = await svc.list_connections(session.user_id, user_secret)

    return {
        "connections": [
            {
                "id": c.get("id"),
                "brokerage": c.get("brokerage", {}).get("name"),
                "status": c.get("status"),
                "created_at": c.get("createdDate"),
            }
            for c in connections
        ],
    }


@router.delete("/disconnect")
async def disconnect(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove SnapTrade registration and all connections."""
    svc = SnapTradeService()
    await svc.delete_user(session.user_id)

    # Clear stored secret
    stmt = select(UserPreferences).where(UserPreferences.user_id == session.user_id)
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()
    if prefs and prefs.currency_code and prefs.currency_code.startswith("ST:"):
        prefs.currency_code = None
        await db.commit()

    return {"status": "disconnected"}
