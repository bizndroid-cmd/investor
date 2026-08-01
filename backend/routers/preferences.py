"""User Preferences API — geography and display settings.

Endpoints:
- GET /user/preferences — get current user preferences
- PUT /user/preferences — update preferences
- GET /user/geographies — list available geographies
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.geo.registry import get_geo, list_geos
from backend.models.domain import Session
from backend.models.orm import UserPreferences
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/user", tags=["user"])


class UserPreferencesResponse(BaseModel):
    geography: str = "IN"
    default_broker: str | None = None
    timezone: str | None = None
    currency_code: str | None = None
    # Resolved from registry
    currency_symbol: str = "₹"
    locale: str = "en-IN"
    display_name: str = "India"
    exchanges: list[str] = []
    dividend_frequency: str = "annual"


class UpdatePreferencesRequest(BaseModel):
    geography: str | None = None
    default_broker: str | None = None
    timezone: str | None = None
    currency_code: str | None = None


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_preferences(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesResponse:
    """Get current user preferences with resolved geography config."""
    stmt = select(UserPreferences).where(UserPreferences.user_id == session.user_id)
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()

    geo_id = prefs.geography if prefs else "IN"
    geo = get_geo(geo_id)

    return UserPreferencesResponse(
        geography=geo_id,
        default_broker=prefs.default_broker if prefs else None,
        timezone=prefs.timezone if prefs else geo.timezone,
        currency_code=prefs.currency_code if prefs else geo.currency_code,
        currency_symbol=geo.currency_symbol,
        locale=geo.currency_locale,
        display_name=geo.display_name,
        exchanges=list(geo.exchanges),
        dividend_frequency=geo.dividend_frequency,
    )


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_preferences(
    body: UpdatePreferencesRequest,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesResponse:
    """Update user preferences. Validates geography against registry."""
    # Validate geography if provided
    if body.geography:
        try:
            get_geo(body.geography)
        except ValueError:
            available = ", ".join(list_geos())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Geography '{body.geography}' is not supported. Available: {available}",
            )

    # Get or create preferences row
    stmt = select(UserPreferences).where(UserPreferences.user_id == session.user_id)
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = UserPreferences(id=uuid4(), user_id=session.user_id, geography="IN")
        db.add(prefs)

    # Apply updates
    if body.geography is not None:
        prefs.geography = body.geography
    if body.default_broker is not None:
        prefs.default_broker = body.default_broker
    if body.timezone is not None:
        prefs.timezone = body.timezone
    if body.currency_code is not None:
        prefs.currency_code = body.currency_code

    await db.commit()
    await db.refresh(prefs)

    # Invalidate caches on geography change
    if body.geography:
        try:
            from backend.dependencies import get_redis_pool
            redis = get_redis_pool()
            if redis:
                # Clear user-specific caches
                keys = await redis.keys(f"*{session.user_id}*")
                if keys:
                    await redis.delete(*keys)
        except Exception:
            pass  # Non-fatal

    # Return resolved response
    geo = get_geo(prefs.geography)
    return UserPreferencesResponse(
        geography=prefs.geography,
        default_broker=prefs.default_broker,
        timezone=prefs.timezone or geo.timezone,
        currency_code=prefs.currency_code or geo.currency_code,
        currency_symbol=geo.currency_symbol,
        locale=geo.currency_locale,
        display_name=geo.display_name,
        exchanges=list(geo.exchanges),
        dividend_frequency=geo.dividend_frequency,
    )


@router.get("/geographies")
async def list_available_geographies() -> list[dict]:
    """List all supported geographies with display info."""
    result = []
    for geo_id in list_geos():
        geo = get_geo(geo_id)
        result.append({
            "geo_id": geo_id,
            "display_name": geo.display_name,
            "currency_code": geo.currency_code,
            "currency_symbol": geo.currency_symbol,
            "exchanges": list(geo.exchanges),
        })
    return result
