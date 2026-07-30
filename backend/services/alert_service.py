"""Alert service implementing IAlertService.

Manages CRUD operations for user-defined price alerts and evaluates
alert conditions against incoming price ticks.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.interfaces.alert_service import IAlertService
from backend.models.domain import (
    Alert,
    CreateAlertRequest,
    TriggeredAlert,
    UpdateAlertRequest,
)
from backend.models.orm import Alert as AlertORM
from backend.services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


def should_trigger(price: Decimal, target_price: Decimal, condition: str) -> bool:
    """Pure function to evaluate whether an alert condition is met.

    Returns True if:
    - condition == "above" and price > target_price
    - condition == "below" and price < target_price

    Returns False when price == target_price (boundary case).
    """
    if condition == "above":
        return price > target_price
    elif condition == "below":
        return price < target_price
    return False


class AlertService(IAlertService):
    """Concrete implementation of IAlertService.

    Uses PostgreSQL for persistence and Redis for fast alert lookups
    during price evaluation.
    """

    def __init__(
        self,
        db: AsyncSession,
        redis: aioredis.Redis,
        ws_manager: WebSocketManager,
    ) -> None:
        self._db = db
        self._redis = redis
        self._ws_manager = ws_manager

    async def create_alert(self, user_id: UUID, alert: CreateAlertRequest) -> Alert:
        """Create a new price alert for the given user."""
        alert_id = uuid4()
        now = datetime.now(timezone.utc)

        # Insert into DB
        alert_orm = AlertORM(
            id=alert_id,
            user_id=user_id,
            ticker=alert.ticker.upper(),
            target_price=alert.target_price,
            condition=alert.condition,
            status="active",
            created_at=now,
        )
        self._db.add(alert_orm)
        await self._db.commit()
        await self._db.refresh(alert_orm)

        # Add to Redis active alerts set
        redis_key = f"alerts:active:{alert.ticker.upper()}"
        await self._redis.sadd(redis_key, str(alert_id))

        return Alert(
            id=alert_id,
            user_id=user_id,
            ticker=alert.ticker.upper(),
            target_price=alert.target_price,
            condition=alert.condition,
            status="active",
            triggered_at=None,
            created_at=now,
        )

    async def update_alert(
        self,
        user_id: UUID,
        alert_id: UUID,
        update: UpdateAlertRequest,
    ) -> Alert:
        """Partially update an existing alert."""
        result = await self._db.execute(
            select(AlertORM).where(
                AlertORM.id == alert_id,
                AlertORM.user_id == user_id,
            )
        )
        alert_orm = result.scalar_one_or_none()
        if alert_orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found.",
            )

        old_ticker = alert_orm.ticker

        # Apply updates
        if update.target_price is not None:
            alert_orm.target_price = update.target_price
        if update.condition is not None:
            alert_orm.condition = update.condition
        if update.status is not None:
            alert_orm.status = update.status
            if update.status == "active":
                # Re-add to Redis set
                redis_key = f"alerts:active:{alert_orm.ticker}"
                await self._redis.sadd(redis_key, str(alert_id))
            elif update.status == "triggered":
                # Remove from Redis set
                redis_key = f"alerts:active:{alert_orm.ticker}"
                await self._redis.srem(redis_key, str(alert_id))

        await self._db.commit()
        await self._db.refresh(alert_orm)

        return Alert(
            id=alert_orm.id,
            user_id=alert_orm.user_id,
            ticker=alert_orm.ticker,
            target_price=alert_orm.target_price,
            condition=alert_orm.condition,
            status=alert_orm.status,
            triggered_at=alert_orm.triggered_at,
            created_at=alert_orm.created_at,
        )

    async def delete_alert(self, user_id: UUID, alert_id: UUID) -> None:
        """Delete an alert by ID."""
        result = await self._db.execute(
            select(AlertORM).where(
                AlertORM.id == alert_id,
                AlertORM.user_id == user_id,
            )
        )
        alert_orm = result.scalar_one_or_none()
        if alert_orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found.",
            )

        # Remove from Redis set
        redis_key = f"alerts:active:{alert_orm.ticker}"
        await self._redis.srem(redis_key, str(alert_id))

        # Delete from DB
        await self._db.delete(alert_orm)
        await self._db.commit()

    async def get_alerts(self, user_id: UUID) -> list[Alert]:
        """Return all alerts (active and triggered) for the given user."""
        result = await self._db.execute(
            select(AlertORM).where(AlertORM.user_id == user_id)
        )
        alert_orms = result.scalars().all()

        return [
            Alert(
                id=a.id,
                user_id=a.user_id,
                ticker=a.ticker,
                target_price=a.target_price,
                condition=a.condition,
                status=a.status,
                triggered_at=a.triggered_at,
                created_at=a.created_at,
            )
            for a in alert_orms
        ]

    async def evaluate_alerts(
        self,
        ticker: str,
        current_price: float,
    ) -> list[TriggeredAlert]:
        """Evaluate all active alerts for the given ticker against the current price.

        For each alert whose condition is satisfied:
        1. Update status to "triggered" in DB
        2. Set triggered_at timestamp
        3. Remove from Redis active set
        4. Broadcast notification via WebSocketManager
        """
        ticker_upper = ticker.upper()
        redis_key = f"alerts:active:{ticker_upper}"

        # Get all active alert IDs for this ticker from Redis
        alert_ids_raw = await self._redis.smembers(redis_key)
        if not alert_ids_raw:
            return []

        triggered_alerts: list[TriggeredAlert] = []
        price = Decimal(str(current_price))
        now = datetime.now(timezone.utc)

        for alert_id_str in alert_ids_raw:
            try:
                alert_id = UUID(alert_id_str)
            except ValueError:
                continue

            # Fetch alert from DB
            result = await self._db.execute(
                select(AlertORM).where(AlertORM.id == alert_id)
            )
            alert_orm = result.scalar_one_or_none()
            if alert_orm is None:
                # Stale Redis entry — remove it
                await self._redis.srem(redis_key, alert_id_str)
                continue

            # Skip already triggered alerts
            if alert_orm.status != "active":
                await self._redis.srem(redis_key, alert_id_str)
                continue

            # Evaluate condition
            if should_trigger(price, alert_orm.target_price, alert_orm.condition):
                # Trigger the alert
                alert_orm.status = "triggered"
                alert_orm.triggered_at = now
                await self._db.commit()

                # Remove from Redis set
                await self._redis.srem(redis_key, alert_id_str)

                triggered = TriggeredAlert(
                    alert_id=alert_orm.id,
                    user_id=alert_orm.user_id,
                    ticker=alert_orm.ticker,
                    target_price=alert_orm.target_price,
                    condition=alert_orm.condition,
                    triggered_price=price,
                    triggered_at=now,
                )
                triggered_alerts.append(triggered)

                # Broadcast notification via WebSocket
                await self._broadcast_alert_notification(triggered)

        return triggered_alerts

    async def _broadcast_alert_notification(self, triggered: TriggeredAlert) -> None:
        """Send an alert triggered notification to the user via WebSocket + Telegram."""
        message = json.dumps({
            "type": "alert_triggered",
            "data": json.loads(triggered.model_dump_json()),
        })
        connections = self._ws_manager._connections.get(triggered.user_id, [])
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                pass

        # Also send via Telegram
        try:
            from backend.services import telegram_service

            direction = "above" if triggered.condition == "above" else "below"
            emoji = "🚨" if triggered.condition == "above" else "🔻"

            tg_message = (
                f"{emoji} <b>Price Alert Triggered!</b>\n\n"
                f"<b>{triggered.ticker}</b> crossed your target\n\n"
                f"  🎯 Target: ₹{triggered.target_price:,.2f}\n"
                f"  📊 Current: ₹{triggered.triggered_price:,.2f}\n"
                f"  📋 Condition: Price went {direction}\n\n"
                f"━━━━━━━━━━━━━━━\n"
                f"<i>Review in app → Alerts section</i>"
            )
            await telegram_service.broadcast_to_all(tg_message)
        except Exception as e:
            logger.debug("Telegram alert notification failed: %s", str(e))
