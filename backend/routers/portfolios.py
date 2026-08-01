"""Portfolio management API — CRUD for multi-portfolio support.

Endpoints:
- GET /portfolios — list all user portfolios
- POST /portfolios — create new portfolio
- PUT /portfolios/{id} — update portfolio
- DELETE /portfolios/{id} — delete portfolio
- GET /portfolios/active — get active/default portfolio
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.geo.registry import get_geo, list_geos
from backend.models.domain import Session
from backend.models.orm import Portfolio
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


class CreatePortfolioRequest(BaseModel):
    name: str
    geo_id: str
    broker_id: str | None = None


class UpdatePortfolioRequest(BaseModel):
    name: str | None = None
    is_default: bool | None = None


class PortfolioResponse(BaseModel):
    id: str
    name: str
    geo_id: str
    broker_id: str | None
    is_default: bool
    currency_symbol: str
    currency_code: str
    display_name: str
    created_at: str


@router.get("")
async def list_portfolios(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PortfolioResponse]:
    """List all portfolios for current user."""
    stmt = select(Portfolio).where(Portfolio.user_id == session.user_id).order_by(Portfolio.created_at)
    result = await db.execute(stmt)
    portfolios = result.scalars().all()

    # If user has no portfolios, create default
    if not portfolios:
        default = Portfolio(
            id=uuid4(),
            user_id=session.user_id,
            name="My Portfolio",
            geo_id="IN",
            broker_id="groww",
            is_default=True,
        )
        db.add(default)
        await db.commit()
        await db.refresh(default)
        portfolios = [default]

    return [_to_response(p) for p in portfolios]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    body: CreatePortfolioRequest,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioResponse:
    """Create a new portfolio."""
    # Validate geography
    try:
        get_geo(body.geo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Geography '{body.geo_id}' not supported")

    # Validate broker-geo compatibility
    if body.broker_id:
        from backend.connectors.groww import GrowwConnector
        from backend.connectors.robinhood import RobinhoodConnector
        from backend.connectors.zerodha import ZerodhaConnector
        from backend.connectors.fidelity import FidelityConnector

        connectors = {
            "groww": GrowwConnector(),
            "zerodha": ZerodhaConnector(),
            "robinhood": RobinhoodConnector(),
            "fidelity": FidelityConnector(),
        }
        connector = connectors.get(body.broker_id)
        if connector and body.geo_id not in connector.supported_geographies:
            raise HTTPException(
                status_code=400,
                detail=f"Broker '{body.broker_id}' does not support geography '{body.geo_id}'"
            )

    portfolio = Portfolio(
        id=uuid4(),
        user_id=session.user_id,
        name=body.name,
        geo_id=body.geo_id,
        broker_id=body.broker_id,
        is_default=False,
    )
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)

    return _to_response(portfolio)


@router.put("/{portfolio_id}")
async def update_portfolio(
    portfolio_id: str,
    body: UpdatePortfolioRequest,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioResponse:
    """Update portfolio name or default status."""
    stmt = select(Portfolio).where(
        Portfolio.id == UUID(portfolio_id),
        Portfolio.user_id == session.user_id,
    )
    result = await db.execute(stmt)
    portfolio = result.scalar_one_or_none()

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if body.name is not None:
        portfolio.name = body.name

    if body.is_default is True:
        # Unset other defaults
        all_stmt = select(Portfolio).where(Portfolio.user_id == session.user_id)
        all_result = await db.execute(all_stmt)
        for p in all_result.scalars().all():
            p.is_default = False
        portfolio.is_default = True

    await db.commit()
    await db.refresh(portfolio)
    return _to_response(portfolio)


@router.delete("/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: str,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a portfolio. Cannot delete last remaining portfolio."""
    # Count user's portfolios
    count_stmt = select(func.count()).select_from(
        select(Portfolio).where(Portfolio.user_id == session.user_id).subquery()
    )
    count_result = await db.execute(count_stmt)
    count = count_result.scalar() or 0

    if count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete your only portfolio")

    stmt = select(Portfolio).where(
        Portfolio.id == UUID(portfolio_id),
        Portfolio.user_id == session.user_id,
    )
    result = await db.execute(stmt)
    portfolio = result.scalar_one_or_none()

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    await db.delete(portfolio)
    await db.commit()
    return {"status": "deleted"}


@router.get("/active")
async def get_active_portfolio(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioResponse:
    """Get the default/active portfolio."""
    stmt = select(Portfolio).where(
        Portfolio.user_id == session.user_id,
        Portfolio.is_default == True,
    )
    result = await db.execute(stmt)
    portfolio = result.scalar_one_or_none()

    if not portfolio:
        # Get first portfolio
        stmt = select(Portfolio).where(Portfolio.user_id == session.user_id).limit(1)
        result = await db.execute(stmt)
        portfolio = result.scalar_one_or_none()

    if not portfolio:
        # Create default
        portfolio = Portfolio(
            id=uuid4(),
            user_id=session.user_id,
            name="My Portfolio",
            geo_id="IN",
            broker_id="groww",
            is_default=True,
        )
        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)

    return _to_response(portfolio)


def _to_response(p: Portfolio) -> PortfolioResponse:
    geo = get_geo(p.geo_id)
    return PortfolioResponse(
        id=str(p.id),
        name=p.name,
        geo_id=p.geo_id,
        broker_id=p.broker_id,
        is_default=p.is_default,
        currency_symbol=geo.currency_symbol,
        currency_code=geo.currency_code,
        display_name=geo.display_name,
        created_at=p.created_at.isoformat() if p.created_at else "",
    )
