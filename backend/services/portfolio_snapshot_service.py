"""Portfolio Snapshot Service.

Captures daily snapshots of portfolio holdings and aggregate values.
These snapshots enable:
- Historical portfolio value tracking
- Correlation with news sentiment for predictions
- Performance metrics over time
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.domain import NormalizedHolding, Portfolio
from backend.models.orm import PortfolioDailySummary, PortfolioSnapshot

logger = logging.getLogger(__name__)


class PortfolioSnapshotService:
    """Captures and queries daily portfolio snapshots."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def capture_snapshot(self, user_id: UUID, portfolio: Portfolio) -> bool:
        """Capture a daily snapshot of the current portfolio state.

        Called after a portfolio refresh. Only stores one snapshot per ticker per day
        (upserts by unique constraint on user_id + snapshot_date + ticker).

        Returns True if new snapshot was stored, False if already existed for today.
        """
        from zoneinfo import ZoneInfo

        IST = ZoneInfo("Asia/Kolkata")
        today = datetime.now(IST).date()

        # Check if we already have a summary for today
        existing = await self._db.execute(
            select(PortfolioDailySummary).where(
                PortfolioDailySummary.user_id == user_id,
                PortfolioDailySummary.snapshot_date == today,
            )
        )
        if existing.scalar_one_or_none():
            # Already captured today — update it
            return await self._update_snapshot(user_id, today, portfolio)

        # Store per-holding snapshots
        for holding in portfolio.holdings:
            snapshot = PortfolioSnapshot(
                user_id=user_id,
                snapshot_date=today,
                ticker=holding.ticker,
                broker_id=holding.broker_id,
                quantity=holding.quantity,
                avg_buy_price=holding.avg_buy_price,
                current_price=holding.current_price,
                current_value=holding.current_value,
                gain_loss=holding.gain_loss,
                gain_loss_percent=holding.gain_loss_percent,
                day_change=Decimal("0"),  # Will be computed when we have previous day
                day_change_percent=Decimal("0"),
                currency=holding.currency,
            )
            self._db.add(snapshot)

        # Store daily aggregate summary
        summary = PortfolioDailySummary(
            user_id=user_id,
            snapshot_date=today,
            total_value=portfolio.total_value,
            total_invested=portfolio.total_invested,
            total_gain_loss=portfolio.total_gain_loss,
            total_gain_loss_percent=portfolio.total_gain_loss_percent,
            day_change=portfolio.day_change,
            day_change_percent=portfolio.day_change_percent,
            holdings_count=len(portfolio.holdings),
        )
        self._db.add(summary)

        try:
            await self._db.commit()
            logger.info(
                "Portfolio snapshot captured for user %s: %d holdings, total_value=%s",
                user_id, len(portfolio.holdings), portfolio.total_value,
            )
            return True
        except Exception as e:
            await self._db.rollback()
            # Likely a unique constraint violation (already captured today)
            logger.debug("Snapshot already exists for today: %s", str(e))
            return False

    async def _update_snapshot(self, user_id: UUID, today: date, portfolio: Portfolio) -> bool:
        """Update today's snapshot with latest values."""
        # Delete existing holding snapshots for today and re-insert
        await self._db.execute(
            delete(PortfolioSnapshot).where(
                PortfolioSnapshot.user_id == user_id,
                PortfolioSnapshot.snapshot_date == today,
            )
        )
        await self._db.execute(
            delete(PortfolioDailySummary).where(
                PortfolioDailySummary.user_id == user_id,
                PortfolioDailySummary.snapshot_date == today,
            )
        )

        for holding in portfolio.holdings:
            snapshot = PortfolioSnapshot(
                user_id=user_id,
                snapshot_date=today,
                ticker=holding.ticker,
                broker_id=holding.broker_id,
                quantity=holding.quantity,
                avg_buy_price=holding.avg_buy_price,
                current_price=holding.current_price,
                current_value=holding.current_value,
                gain_loss=holding.gain_loss,
                gain_loss_percent=holding.gain_loss_percent,
                day_change=Decimal("0"),
                day_change_percent=Decimal("0"),
                currency=holding.currency,
            )
            self._db.add(snapshot)

        summary = PortfolioDailySummary(
            user_id=user_id,
            snapshot_date=today,
            total_value=portfolio.total_value,
            total_invested=portfolio.total_invested,
            total_gain_loss=portfolio.total_gain_loss,
            total_gain_loss_percent=portfolio.total_gain_loss_percent,
            day_change=portfolio.day_change,
            day_change_percent=portfolio.day_change_percent,
            holdings_count=len(portfolio.holdings),
        )
        self._db.add(summary)

        await self._db.commit()
        return True

    async def get_daily_summaries(
        self, user_id: UUID, days: int = 90
    ) -> list[dict]:
        """Get daily portfolio value summaries for the past N days."""
        from datetime import timedelta

        cutoff = date.today() - timedelta(days=days)
        stmt = (
            select(PortfolioDailySummary)
            .where(
                PortfolioDailySummary.user_id == user_id,
                PortfolioDailySummary.snapshot_date >= cutoff,
            )
            .order_by(PortfolioDailySummary.snapshot_date.asc())
        )
        result = await self._db.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "date": row.snapshot_date.isoformat(),
                "total_value": float(row.total_value),
                "total_invested": float(row.total_invested),
                "total_gain_loss": float(row.total_gain_loss),
                "total_gain_loss_percent": float(row.total_gain_loss_percent),
                "day_change": float(row.day_change),
                "day_change_percent": float(row.day_change_percent),
                "holdings_count": row.holdings_count,
            }
            for row in rows
        ]

    async def get_ticker_history(
        self, user_id: UUID, ticker: str, days: int = 90
    ) -> list[dict]:
        """Get daily price/value history for a specific ticker."""
        from datetime import timedelta

        cutoff = date.today() - timedelta(days=days)
        stmt = (
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.user_id == user_id,
                PortfolioSnapshot.ticker == ticker,
                PortfolioSnapshot.snapshot_date >= cutoff,
            )
            .order_by(PortfolioSnapshot.snapshot_date.asc())
        )
        result = await self._db.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "date": row.snapshot_date.isoformat(),
                "current_price": float(row.current_price),
                "quantity": float(row.quantity),
                "current_value": float(row.current_value),
                "gain_loss": float(row.gain_loss),
                "gain_loss_percent": float(row.gain_loss_percent),
            }
            for row in rows
        ]
