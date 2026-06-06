"""Prediction Service — tracks LLM prediction accuracy.

Stores predictions from briefings, then computes confidence scores
by comparing predictions against actual market movements from
portfolio_snapshots data.

Confidence Score (0-100):
- 100 = Perfect prediction (mood + all ticker directions matched)
- 0 = Completely wrong (every prediction was opposite)

Components:
- Mood Accuracy (40% weight): Did overall market mood match portfolio direction?
- Ticker Accuracy (60% weight): Per-ticker direction predictions vs actual price changes
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import (
    PredictionRecord,
    PortfolioDailySummary,
    PortfolioSnapshot,
)

logger = logging.getLogger(__name__)


class PredictionService:
    """Manages prediction storage and confidence scoring."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def store_prediction(
        self,
        *,
        user_id: UUID,
        prediction_date: date,
        market_mood: str,
        market_mood_reason: str | None,
        ticker_predictions: list[dict],
        suggestions: list[str],
        briefing_text: str,
        provider: str,
        model: str,
    ) -> PredictionRecord:
        """Store a prediction from a briefing for later accuracy evaluation."""
        record = PredictionRecord(
            user_id=user_id,
            prediction_date=prediction_date,
            market_mood=market_mood,
            market_mood_reason=market_mood_reason,
            ticker_predictions=json.dumps(ticker_predictions),
            suggestions=json.dumps(suggestions),
            briefing_text=briefing_text,
            provider=provider,
            model=model,
        )
        self._db.add(record)
        await self._db.commit()
        await self._db.refresh(record)
        return record

    async def compute_confidence_score(
        self, user_id: UUID, prediction_date: date
    ) -> dict | None:
        """Compute confidence score for a prediction by comparing with actual price data.

        Requires portfolio snapshot data from the day AFTER the prediction.
        Returns None if insufficient data.
        """
        # Get the prediction record
        stmt = select(PredictionRecord).where(
            PredictionRecord.user_id == user_id,
            PredictionRecord.prediction_date == prediction_date,
        )
        result = await self._db.execute(stmt)
        prediction = result.scalar_one_or_none()

        if not prediction:
            return None

        # Get snapshot for the prediction day and the next trading day
        next_day = prediction_date + timedelta(days=1)
        # Check up to 3 days forward (skip weekends)
        snapshot_today = await self._get_snapshot(user_id, prediction_date)
        snapshot_next = None
        for days_ahead in range(1, 4):
            check_date = prediction_date + timedelta(days=days_ahead)
            snapshot_next = await self._get_snapshot(user_id, check_date)
            if snapshot_next:
                break

        if not snapshot_today or not snapshot_next:
            return None  # Not enough data yet

        # Compute mood accuracy (40% weight)
        mood_score = self._compute_mood_accuracy(
            prediction.market_mood, snapshot_today, snapshot_next
        )

        # Compute ticker accuracy (60% weight)
        ticker_score = await self._compute_ticker_accuracy(
            user_id, prediction, prediction_date, snapshot_next.snapshot_date
        )

        # Weighted confidence score
        confidence_score = round(mood_score * 0.4 + ticker_score * 0.6, 1)

        # Update the prediction record
        prediction.confidence_score = confidence_score
        prediction.mood_accuracy = mood_score
        prediction.ticker_accuracy = ticker_score
        prediction.score_computed_at = datetime.now(timezone.utc)
        await self._db.commit()

        return {
            "prediction_date": prediction_date.isoformat(),
            "confidence_score": confidence_score,
            "mood_accuracy": mood_score,
            "ticker_accuracy": ticker_score,
            "market_mood_predicted": prediction.market_mood,
            "actual_portfolio_change": float(
                snapshot_next.total_gain_loss_percent - snapshot_today.total_gain_loss_percent
            ),
        }

    def _compute_mood_accuracy(
        self, predicted_mood: str, snapshot_today, snapshot_next
    ) -> float:
        """Compare predicted mood with actual portfolio direction.

        Returns 0-100 score.
        """
        # Actual direction: compare total values
        actual_change = snapshot_next.total_value - snapshot_today.total_value

        if actual_change > 0:
            actual_mood = "bullish"
        elif actual_change < 0:
            actual_mood = "bearish"
        else:
            actual_mood = "neutral"

        # Scoring
        if predicted_mood == actual_mood:
            return 100.0
        elif predicted_mood == "neutral" or actual_mood == "neutral":
            return 50.0  # Partial credit for neutral
        else:
            return 0.0  # Completely wrong direction

    async def _compute_ticker_accuracy(
        self, user_id: UUID, prediction: PredictionRecord,
        prediction_date: date, next_date: date,
    ) -> float:
        """Compare per-ticker predictions with actual price changes.

        Returns 0-100 score.
        """
        if not prediction.ticker_predictions:
            return 50.0  # No predictions = neutral

        try:
            ticker_preds = json.loads(prediction.ticker_predictions)
        except (json.JSONDecodeError, TypeError):
            return 50.0

        if not ticker_preds:
            return 50.0

        # Get snapshots for both days
        stmt_today = select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.snapshot_date == prediction_date,
        )
        stmt_next = select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.snapshot_date == next_date,
        )

        result_today = await self._db.execute(stmt_today)
        result_next = await self._db.execute(stmt_next)

        today_by_ticker = {s.ticker: s for s in result_today.scalars().all()}
        next_by_ticker = {s.ticker: s for s in result_next.scalars().all()}

        correct = 0
        total = 0

        for pred in ticker_preds:
            ticker = pred.get("ticker", "")
            expected = pred.get("expected_direction", "flat")

            if ticker not in today_by_ticker or ticker not in next_by_ticker:
                continue

            today_price = today_by_ticker[ticker].current_price
            next_price = next_by_ticker[ticker].current_price

            # Determine actual direction
            if next_price > today_price:
                actual = "up"
            elif next_price < today_price:
                actual = "down"
            else:
                actual = "flat"

            total += 1
            if expected == actual:
                correct += 1
            elif expected == "flat" or actual == "flat":
                correct += 0.5  # Partial credit

        if total == 0:
            return 50.0

        return round((correct / total) * 100, 1)

    async def _get_snapshot(self, user_id: UUID, snapshot_date: date):
        """Get portfolio daily summary for a date."""
        stmt = select(PortfolioDailySummary).where(
            PortfolioDailySummary.user_id == user_id,
            PortfolioDailySummary.snapshot_date == snapshot_date,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_prediction_history(
        self, user_id: UUID, days: int = 30
    ) -> list[dict]:
        """Get prediction history with confidence scores for the dashboard."""
        cutoff = date.today() - timedelta(days=days)
        stmt = (
            select(PredictionRecord)
            .where(
                PredictionRecord.user_id == user_id,
                PredictionRecord.prediction_date >= cutoff,
            )
            .order_by(desc(PredictionRecord.prediction_date))
        )
        result = await self._db.execute(stmt)
        records = result.scalars().all()

        return [
            {
                "prediction_date": r.prediction_date.isoformat(),
                "market_mood": r.market_mood,
                "confidence_score": r.confidence_score,
                "mood_accuracy": r.mood_accuracy,
                "ticker_accuracy": r.ticker_accuracy,
                "provider": r.provider,
                "model": r.model,
                "scored": r.confidence_score is not None,
            }
            for r in records
        ]

    async def get_average_confidence(self, user_id: UUID, days: int = 30) -> dict:
        """Get average confidence score over a period."""
        cutoff = date.today() - timedelta(days=days)
        stmt = select(PredictionRecord).where(
            PredictionRecord.user_id == user_id,
            PredictionRecord.prediction_date >= cutoff,
            PredictionRecord.confidence_score.isnot(None),
        )
        result = await self._db.execute(stmt)
        scored = result.scalars().all()

        if not scored:
            return {
                "average_score": None,
                "total_predictions": 0,
                "scored_predictions": 0,
                "days": days,
            }

        avg = sum(r.confidence_score for r in scored) / len(scored)
        return {
            "average_score": round(avg, 1),
            "total_predictions": len(scored),
            "scored_predictions": len([r for r in scored if r.confidence_score is not None]),
            "highest_score": max(r.confidence_score for r in scored),
            "lowest_score": min(r.confidence_score for r in scored),
            "days": days,
        }
