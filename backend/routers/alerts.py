"""FastAPI alerts router for price alert CRUD operations.

Endpoints:
- GET /alerts — list all alerts for the current user
- POST /alerts — create a new alert
- PATCH /alerts/{alert_id} — update an existing alert
- DELETE /alerts/{alert_id} — delete an alert
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.domain import (
    Alert,
    CreateAlertRequest,
    Session,
    UpdateAlertRequest,
)
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


def get_alert_service():
    """Dependency placeholder — overridden in main.py via app.dependency_overrides."""
    raise NotImplementedError("AlertService not wired. Use dependency overrides.")


@router.get("", response_model=list[Alert])
async def list_alerts(
    session: Session = Depends(get_current_user),
    alert_service=Depends(get_alert_service),
) -> list[Alert]:
    """Return all alerts (active and triggered) for the current user."""
    return await alert_service.get_alerts(session.user_id)


@router.post("", response_model=Alert, status_code=status.HTTP_201_CREATED)
async def create_alert(
    body: CreateAlertRequest,
    session: Session = Depends(get_current_user),
    alert_service=Depends(get_alert_service),
) -> Alert:
    """Create a new price alert."""
    return await alert_service.create_alert(user_id=session.user_id, alert=body)


@router.patch("/{alert_id}", response_model=Alert)
async def update_alert(
    alert_id: UUID,
    body: UpdateAlertRequest,
    session: Session = Depends(get_current_user),
    alert_service=Depends(get_alert_service),
) -> Alert:
    """Partially update an existing alert."""
    return await alert_service.update_alert(
        user_id=session.user_id, alert_id=alert_id, update=body
    )


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: UUID,
    session: Session = Depends(get_current_user),
    alert_service=Depends(get_alert_service),
) -> Response:
    """Delete an alert by ID."""
    await alert_service.delete_alert(user_id=session.user_id, alert_id=alert_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/telegram-status")
async def get_telegram_status(
    session: Session = Depends(get_current_user),
) -> dict:
    """Check if Telegram notifications are configured and working."""
    from backend.services import telegram_service

    configured = telegram_service.is_configured()
    allowed_ids = telegram_service._get_allowed_chat_ids()

    return {
        "configured": configured,
        "chat_ids_count": len(allowed_ids),
        "active": configured and len(allowed_ids) > 0,
    }


@router.post("/telegram-test")
async def test_telegram(
    session: Session = Depends(get_current_user),
) -> dict:
    """Send a test message to verify Telegram connection."""
    from backend.services import telegram_service

    if not telegram_service.is_configured():
        return {"success": False, "message": "Telegram bot not configured"}

    count = await telegram_service.broadcast_to_all(
        "🔔 <b>Test Alert</b>\n\n"
        "If you see this, your alert notifications are working!\n"
        "Price alerts will be sent here when triggered."
    )
    return {
        "success": count > 0,
        "message": f"Sent to {count} chat(s)" if count > 0 else "No authorized chats found",
    }


@router.get("/suggestions")
async def get_alert_suggestions(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Generate smart alert suggestions based on portfolio technicals.

    Suggests:
    - Stop-loss at 2x ATR below current price for holdings without stop-loss alerts
    - Breakout target at resistance level for holdings without upside alerts
    """
    from backend.models.orm import PortfolioSnapshot, Alert as AlertORM
    from backend.services.technical_analysis_service import TechnicalAnalysisService
    from sqlalchemy import select, desc, distinct
    import asyncio

    # Get user's tickers
    stmt = select(distinct(PortfolioSnapshot.ticker)).where(
        PortfolioSnapshot.user_id == session.user_id
    )
    result = await db.execute(stmt)
    tickers = [r[0] for r in result.all()]

    if not tickers:
        return []

    # Get existing alerts to avoid duplicates
    alert_stmt = select(AlertORM).where(
        AlertORM.user_id == session.user_id,
        AlertORM.status == "active",
    )
    alert_result = await db.execute(alert_stmt)
    existing_alerts = alert_result.scalars().all()
    existing_below = {a.ticker for a in existing_alerts if a.condition == "below"}
    existing_above = {a.ticker for a in existing_alerts if a.condition == "above"}

    # Get technicals for portfolio tickers (limit to 8 to avoid timeout)
    ta_svc = TechnicalAnalysisService()
    suggestions = []

    for ticker in tickers[:8]:
        try:
            technicals = await ta_svc.get_technicals(ticker)
            if not technicals:
                continue

            price = technicals["current_price"]
            atr = technicals.get("atr")
            sr = technicals.get("support_resistance", {})

            # Stop-loss suggestion (2x ATR below current)
            if ticker not in existing_below and atr and price:
                stop_loss = round(price - (2 * atr), 2)
                if stop_loss > 0:
                    suggestions.append({
                        "ticker": ticker,
                        "type": "stop_loss",
                        "target_price": stop_loss,
                        "condition": "below",
                        "reason": f"2× ATR (₹{atr}) below current ₹{price:.0f}. Limits downside to ~{round(2*atr/price*100, 1)}%",
                        "urgency": "medium",
                    })

            # Breakout suggestion (resistance level)
            if ticker not in existing_above and sr.get("resistance"):
                resistance = sr["resistance"]
                if resistance > price:
                    suggestions.append({
                        "ticker": ticker,
                        "type": "breakout",
                        "target_price": round(resistance, 2),
                        "condition": "above",
                        "reason": f"Resistance at ₹{resistance:.0f} — breakout could signal momentum continuation",
                        "urgency": "low",
                    })

        except Exception:
            continue

    # Sort: stop losses first, then by urgency
    suggestions.sort(key=lambda s: (0 if s["type"] == "stop_loss" else 1, s["ticker"]))
    return suggestions[:12]


@router.get("/proximity")
async def get_alert_proximity(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Check how close active alerts are to triggering.

    Returns alerts sorted by proximity (closest to triggering first).
    Useful for daily digest: 'These alerts are almost hit'.
    """
    from backend.models.orm import Alert as AlertORM
    from backend.services.technical_analysis_service import TechnicalAnalysisService
    from sqlalchemy import select

    stmt = select(AlertORM).where(
        AlertORM.user_id == session.user_id,
        AlertORM.status == "active",
    )
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    if not alerts:
        return []

    # Get current prices for all alert tickers
    ta_svc = TechnicalAnalysisService()
    unique_tickers = list({a.ticker for a in alerts})
    prices: dict[str, float] = {}

    for ticker in unique_tickers[:10]:
        try:
            technicals = await ta_svc.get_technicals(ticker)
            if technicals:
                prices[ticker] = technicals["current_price"]
        except Exception:
            continue

    # Calculate proximity for each alert
    proximity_list = []
    for alert in alerts:
        current = prices.get(alert.ticker)
        if not current:
            continue

        target = float(alert.target_price)
        if alert.condition == "below":
            distance_pct = round((current - target) / current * 100, 2)
        else:
            distance_pct = round((target - current) / current * 100, 2)

        status_label = "safe"
        if distance_pct < 2:
            status_label = "imminent"
        elif distance_pct < 5:
            status_label = "close"

        proximity_list.append({
            "alert_id": str(alert.id),
            "ticker": alert.ticker,
            "condition": alert.condition,
            "target_price": float(alert.target_price),
            "current_price": current,
            "distance_pct": distance_pct,
            "status": status_label,
        })

    # Sort by distance (closest first)
    proximity_list.sort(key=lambda x: x["distance_pct"])
    return proximity_list
