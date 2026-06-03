"""Order service implementing IOrderService.

Handles order placement with idempotency checks, broker delegation,
persistence, WebSocket notifications, and retry logic.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.interfaces.broker_connector import IBrokerConnector
from backend.interfaces.order_service import IOrderService
from backend.models.domain import (
    BrokerId,
    Order,
    OrderFilters,
    OrderRequest,
    OrderResult,
)
from backend.models.orm import Order as OrderORM
from backend.services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

# Idempotency window: reject duplicate pending orders within this timeframe
IDEMPOTENCY_WINDOW_SECONDS = 10

# Retry backoff delays (in seconds)
RETRY_DELAYS = [0.5, 1.0]


def format_order_notification(order: Order) -> dict:
    """Format an order notification payload.

    For confirmed (filled) orders: includes order_type, ticker, quantity, execution_price.
    For rejected orders: includes rejection_reason.
    """
    if order.status == "filled":
        return {
            "type": "order_confirmed",
            "order_type": order.order_type,
            "ticker": order.ticker,
            "quantity": str(order.quantity),
            "execution_price": str(order.execution_price) if order.execution_price else None,
            "side": order.side,
            "order_id": str(order.id),
        }
    elif order.status == "rejected":
        return {
            "type": "order_rejected",
            "order_type": order.order_type,
            "ticker": order.ticker,
            "quantity": str(order.quantity),
            "side": order.side,
            "rejection_reason": order.rejection_reason,
            "order_id": str(order.id),
        }
    else:
        return {
            "type": "order_update",
            "order_type": order.order_type,
            "ticker": order.ticker,
            "quantity": str(order.quantity),
            "side": order.side,
            "status": order.status,
            "order_id": str(order.id),
        }


class OrderService(IOrderService):
    """Concrete implementation of IOrderService.

    Delegates order execution to broker connectors, persists orders,
    and emits WebSocket notifications.
    """

    def __init__(
        self,
        db: AsyncSession,
        connectors: dict[BrokerId, IBrokerConnector],
        ws_manager: WebSocketManager,
    ) -> None:
        self._db = db
        self._connectors = connectors
        self._ws_manager = ws_manager

    async def place_order(self, user_id: UUID, request: OrderRequest) -> Order:
        """Place an order via the appropriate broker connector.

        1. Idempotency check (duplicate pending order within 10s)
        2. Delegate to broker connector (with retry on network error)
        3. Persist to orders table
        4. Emit WebSocket order update
        """
        # Idempotency check
        await self._check_idempotency(user_id, request)

        # Get the appropriate connector
        connector = self._connectors.get(request.broker_id)
        if connector is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported broker: {request.broker_id}",
            )

        # Submit order to broker with retry logic
        order_result = await self._submit_with_retry(connector, user_id, request)

        # Persist order to database
        now = datetime.now(timezone.utc)
        order_id = uuid4()

        order_status = order_result.status
        # Map broker status to our status enum
        if order_status not in ("pending", "filled", "rejected", "cancelled"):
            order_status = "pending"

        order_orm = OrderORM(
            id=order_id,
            user_id=user_id,
            broker_id=request.broker_id,
            broker_order_id=order_result.broker_order_id,
            ticker=request.ticker.upper(),
            order_type=request.order_type,
            side=request.side,
            quantity=request.quantity,
            limit_price=request.limit_price,
            execution_price=order_result.execution_price,
            status=order_status,
            rejection_reason=order_result.rejection_reason,
            placed_at=now,
        )
        self._db.add(order_orm)
        await self._db.commit()
        await self._db.refresh(order_orm)

        order = self._orm_to_domain(order_orm)

        # Emit WebSocket update
        await self._ws_manager.broadcast_order_update(user_id, order)

        return order

    async def get_order_history(
        self,
        user_id: UUID,
        filters: OrderFilters | None = None,
    ) -> list[Order]:
        """Return the order history for the given user, with optional filters."""
        query = select(OrderORM).where(OrderORM.user_id == user_id)

        if filters:
            if filters.broker_id:
                query = query.where(OrderORM.broker_id == filters.broker_id)
            if filters.ticker:
                query = query.where(OrderORM.ticker == filters.ticker.upper())
            if filters.status:
                query = query.where(OrderORM.status == filters.status)
            query = query.limit(filters.limit)
        else:
            query = query.limit(50)

        query = query.order_by(OrderORM.placed_at.desc())

        result = await self._db.execute(query)
        order_orms = result.scalars().all()

        return [self._orm_to_domain(o) for o in order_orms]

    async def get_order_status(self, user_id: UUID, order_id: UUID) -> Order:
        """Return the current state of a single order by its ID."""
        result = await self._db.execute(
            select(OrderORM).where(
                OrderORM.id == order_id,
                OrderORM.user_id == user_id,
            )
        )
        order_orm = result.scalar_one_or_none()
        if order_orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found.",
            )
        return self._orm_to_domain(order_orm)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    async def _check_idempotency(self, user_id: UUID, request: OrderRequest) -> None:
        """Check for duplicate pending orders within the idempotency window."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=IDEMPOTENCY_WINDOW_SECONDS)

        result = await self._db.execute(
            select(OrderORM).where(
                and_(
                    OrderORM.user_id == user_id,
                    OrderORM.broker_id == request.broker_id,
                    OrderORM.ticker == request.ticker.upper(),
                    OrderORM.side == request.side,
                    OrderORM.quantity == request.quantity,
                    OrderORM.status == "pending",
                    OrderORM.placed_at >= cutoff,
                )
            )
        )
        duplicate = result.scalar_one_or_none()
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate order detected. A similar pending order was placed within the last 10 seconds.",
            )

    async def _submit_with_retry(
        self,
        connector: IBrokerConnector,
        user_id: UUID,
        request: OrderRequest,
    ) -> OrderResult:
        """Submit order to broker with retry on network errors."""
        last_error: Exception | None = None

        for attempt, delay in enumerate([0] + RETRY_DELAYS):
            if delay > 0:
                await asyncio.sleep(delay)

            try:
                result = await connector.place_order(user_id, request)
                return result
            except (ConnectionError, TimeoutError, OSError) as e:
                last_error = e
                logger.warning(
                    "Order submission attempt %d failed for %s: %s",
                    attempt + 1,
                    request.ticker,
                    str(e),
                )
                if attempt >= len(RETRY_DELAYS):
                    break
            except Exception as e:
                # Non-retryable error
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Broker error: {str(e)}",
                )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Order submission failed after retries: {str(last_error)}",
        )

    def _orm_to_domain(self, orm: OrderORM) -> Order:
        """Convert an ORM order to a domain Order model."""
        return Order(
            id=orm.id,
            user_id=orm.user_id,
            broker_id=orm.broker_id,
            broker_order_id=orm.broker_order_id,
            ticker=orm.ticker,
            order_type=orm.order_type,
            side=orm.side,
            quantity=orm.quantity,
            limit_price=orm.limit_price,
            execution_price=orm.execution_price,
            status=orm.status,
            rejection_reason=orm.rejection_reason,
            placed_at=orm.placed_at,
            updated_at=orm.updated_at,
        )
