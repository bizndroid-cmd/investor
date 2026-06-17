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

    async def capture_snapshot_from_market(self, user_id: UUID) -> bool:
        """Capture a daily snapshot using yfinance market prices.

        Uses tickers from holdings_cache (last known holdings from Groww).
        Does NOT require a live Groww connection — only needs ticker + quantity + avg_price.
        
        Returns True if snapshot was captured successfully.
        """
        from zoneinfo import ZoneInfo
        from backend.models.orm import HoldingCache
        import asyncio

        IST = ZoneInfo("Asia/Kolkata")
        today = datetime.now(IST).date()

        # Check if already captured today
        existing = await self._db.execute(
            select(PortfolioDailySummary).where(
                PortfolioDailySummary.user_id == user_id,
                PortfolioDailySummary.snapshot_date == today,
            )
        )
        if existing.scalar_one_or_none():
            logger.debug("Snapshot already exists for today, updating prices...")
            # Delete existing to re-create with fresh prices
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

        # Get holdings from cache
        stmt = select(HoldingCache).where(HoldingCache.user_id == user_id)
        result = await self._db.execute(stmt)
        holdings = result.scalars().all()

        if not holdings:
            logger.warning("No holdings in cache for user %s, cannot snapshot", user_id)
            return False

        # Fetch current prices via yfinance
        tickers = [h.ticker for h in holdings]
        prices = await self._fetch_yfinance_prices(tickers)

        total_value = Decimal("0")
        total_invested = Decimal("0")

        for holding in holdings:
            current_price = prices.get(holding.ticker, Decimal("0"))
            if current_price <= 0:
                current_price = holding.avg_buy_price  # fallback

            qty = holding.quantity
            avg_price = holding.avg_buy_price
            current_value = qty * current_price
            gain_loss = current_value - (qty * avg_price)
            gain_loss_pct = (gain_loss / (qty * avg_price) * 100) if (qty * avg_price) > 0 else Decimal("0")

            total_value += current_value
            total_invested += qty * avg_price

            snapshot = PortfolioSnapshot(
                user_id=user_id,
                snapshot_date=today,
                ticker=holding.ticker,
                broker_id=holding.broker_id,
                quantity=qty,
                avg_buy_price=avg_price,
                current_price=current_price,
                current_value=current_value,
                gain_loss=gain_loss,
                gain_loss_percent=gain_loss_pct,
                currency=holding.currency,
            )
            self._db.add(snapshot)

        # Daily summary
        total_gl = total_value - total_invested
        total_gl_pct = (total_gl / total_invested * 100) if total_invested > 0 else Decimal("0")

        summary = PortfolioDailySummary(
            user_id=user_id,
            snapshot_date=today,
            total_value=total_value,
            total_invested=total_invested,
            total_gain_loss=total_gl,
            total_gain_loss_percent=total_gl_pct,
            day_change=Decimal("0"),
            day_change_percent=Decimal("0"),
            holdings_count=len(holdings),
        )
        self._db.add(summary)

        try:
            await self._db.commit()
            logger.info(
                "Market snapshot captured for user %s: %d tickers, value=%.2f, invested=%.2f",
                user_id, len(holdings), float(total_value), float(total_invested),
            )

            # Auto-score pending predictions
            try:
                await self._auto_score_predictions(user_id, today)
            except Exception as e:
                logger.debug("Auto-score skipped: %s", str(e))

            return True
        except Exception as e:
            await self._db.rollback()
            logger.error("Market snapshot failed: %s", str(e))
            return False

    async def _fetch_yfinance_prices(self, tickers: list[str]) -> dict[str, Decimal]:
        """Fetch current prices for multiple tickers via yfinance (NSE)."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._yfinance_batch_sync, tickers)

    @staticmethod
    def _yfinance_batch_sync(tickers: list[str]) -> dict[str, Decimal]:
        """Synchronous batch yfinance price fetch."""
        import yfinance

        prices: dict[str, Decimal] = {}
        for ticker in tickers:
            try:
                yf_ticker = f"{ticker}.NS"
                stock = yfinance.Ticker(yf_ticker)
                info = stock.fast_info
                price = getattr(info, "last_price", 0) or 0
                if price > 0:
                    prices[ticker] = Decimal(str(round(price, 2)))
            except Exception:
                pass
        return prices

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

            # Auto-score any pending predictions from previous days
            try:
                await self._auto_score_predictions(user_id, today)
            except Exception as score_err:
                logger.debug("Auto-score skipped: %s", str(score_err))

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

    async def _auto_score_predictions(self, user_id: UUID, today: date) -> None:
        """Auto-score any unscored predictions that now have enough data."""
        from backend.services.prediction_service import PredictionService
        from backend.models.orm import PredictionRecord
        from datetime import timedelta

        # Find unscored predictions from the last 7 days
        cutoff = today - timedelta(days=7)
        stmt = select(PredictionRecord).where(
            PredictionRecord.user_id == user_id,
            PredictionRecord.prediction_date >= cutoff,
            PredictionRecord.confidence_score.is_(None),
        )
        result = await self._db.execute(stmt)
        unscored = result.scalars().all()

        if not unscored:
            return

        svc = PredictionService(db=self._db)
        for prediction in unscored:
            try:
                await svc.compute_confidence_score(user_id, prediction.prediction_date)
                logger.info("Auto-scored prediction for %s", prediction.prediction_date)
            except Exception:
                pass  # Not enough data yet — will try again next time

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
