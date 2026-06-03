"""FastAPI orders router for order placement and history.

Endpoints:
- POST /orders — place a new order
- GET /orders — list order history with optional filters
- GET /orders/{order_id} — get a single order by ID
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from backend.models.domain import (
    BrokerId,
    Order,
    OrderFilters,
    OrderRequest,
    Session,
)
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])


def get_order_service():
    """Dependency placeholder — overridden in main.py via app.dependency_overrides."""
    raise NotImplementedError("OrderService not wired. Use dependency overrides.")


@router.post("", response_model=Order, status_code=201)
async def place_order(
    body: OrderRequest,
    session: Session = Depends(get_current_user),
    order_service=Depends(get_order_service),
) -> Order:
    """Place a new buy or sell order."""
    return await order_service.place_order(user_id=session.user_id, request=body)


@router.get("", response_model=list[Order])
async def list_orders(
    broker_id: Optional[BrokerId] = Query(default=None),
    ticker: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_current_user),
    order_service=Depends(get_order_service),
) -> list[Order]:
    """Return order history for the current user with optional filters."""
    filters = OrderFilters(
        broker_id=broker_id,
        ticker=ticker,
        status=status,
        limit=limit,
    )
    return await order_service.get_order_history(
        user_id=session.user_id, filters=filters
    )


@router.get("/{order_id}", response_model=Order)
async def get_order(
    order_id: UUID,
    session: Session = Depends(get_current_user),
    order_service=Depends(get_order_service),
) -> Order:
    """Return a single order by its ID."""
    return await order_service.get_order_status(
        user_id=session.user_id, order_id=order_id
    )
