"""Intelligence Service — Pattern detection, risk analysis, and self-improving predictions.

Uses accumulated historical data (news + prices + prediction scores) to provide
actionable insights beyond simple news sentiment.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import (
    NewsArticle,
    PortfolioDailySummary,
    PortfolioSnapshot,
    PredictionRecord,
    StockFundamentals,
)
from backend.geo.sectors import get_sector

logger = logging.getLogger(__name__)


class IntelligenceService:
    """Provides pattern-based intelligence and risk analysis."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_accuracy_context(self, user_id: UUID) -> str:
        """Build a text summary of past prediction accuracy for the LLM to learn from."""
        stmt = (
            select(PredictionRecord)
            .where(
                PredictionRecord.user_id == user_id,
                PredictionRecord.confidence_score.isnot(None),
            )
            .order_by(desc(PredictionRecord.prediction_date))
            .limit(10)
        )
        result = await self._db.execute(stmt)
        records = result.scalars().all()

        if not records:
            return "No prediction history yet. This is your first prediction — be thoughtful."

        avg_score = sum(r.confidence_score for r in records) / len(records)
        best = max(records, key=lambda r: r.confidence_score)
        worst = min(records, key=lambda r: r.confidence_score)

        # Analyze mood accuracy
        mood_correct = sum(1 for r in records if r.mood_accuracy and r.mood_accuracy >= 50)
        mood_total = len(records)

        lines = [
            f"Your prediction track record (last {len(records)} predictions):",
            f"  Average confidence score: {avg_score:.1f}%",
            f"  Mood direction correct: {mood_correct}/{mood_total} times",
            f"  Best day: {best.prediction_date} ({best.confidence_score}%)",
            f"  Worst day: {worst.prediction_date} ({worst.confidence_score}%)",
        ]

        # Identify patterns in failures
        wrong_moods = [r for r in records if r.mood_accuracy is not None and r.mood_accuracy == 0]
        if wrong_moods:
            lines.append(f"  Days you got mood WRONG: {', '.join(str(r.prediction_date) for r in wrong_moods)}")
            # Check if always bullish
            all_bullish = all(r.market_mood == "bullish" for r in records)
            if all_bullish:
                lines.append("  WARNING: You've predicted 'bullish' every single time. Consider being more nuanced.")

        return "\n".join(lines)

    async def detect_sector_concentration(self, user_id: UUID, geo_id: str = "IN") -> list[dict]:
        """Detect portfolio concentration risks by sector."""
        stmt = (
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == user_id)
            .order_by(desc(PortfolioSnapshot.snapshot_date))
            .limit(30)  # Latest snapshot day's holdings
        )
        result = await self._db.execute(stmt)
        snapshots = result.scalars().all()

        if not snapshots:
            return []

        # Get the most recent date's snapshots
        latest_date = snapshots[0].snapshot_date
        latest = [s for s in snapshots if s.snapshot_date == latest_date]

        total_value = sum(float(s.current_value) for s in latest)
        if total_value <= 0:
            return []

        # Group by sector
        sector_exposure: dict[str, float] = defaultdict(float)
        sector_tickers: dict[str, list[str]] = defaultdict(list)

        for s in latest:
            sector = get_sector(s.ticker, geo_id)
            sector_exposure[sector] += float(s.current_value)
            sector_tickers[sector].append(s.ticker)

        # Identify concentrated sectors (>20%)
        risks = []
        for sector, value in sector_exposure.items():
            pct = (value / total_value) * 100
            if pct > 20:
                risks.append({
                    "type": "sector_concentration",
                    "sector": sector,
                    "affected_tickers": sector_tickers[sector],
                    "exposure_pct": round(pct, 1),
                    "value": round(value, 0),
                    "risk": f"{sector.title()} sector makes up {pct:.0f}% of portfolio ({len(sector_tickers[sector])} stocks, ₹{value:,.0f})",
                    "severity": "high" if pct > 35 else "medium",
                })

        return sorted(risks, key=lambda r: r["exposure_pct"], reverse=True)

    async def detect_price_patterns(self, user_id: UUID, ticker: str) -> list[dict]:
        """Detect historical price patterns for a ticker based on news sentiment."""
        # Get last 30 days of news for this ticker
        cutoff = date.today() - timedelta(days=30)
        stmt = (
            select(NewsArticle)
            .where(
                NewsArticle.user_id == user_id,
                NewsArticle.related_tickers.any(ticker),
                NewsArticle.collection_date >= cutoff,
                NewsArticle.is_analyzed == True,
            )
            .order_by(desc(NewsArticle.collection_date))
        )
        result = await self._db.execute(stmt)
        articles = result.scalars().all()

        # Get price data for same period
        price_stmt = (
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.user_id == user_id,
                PortfolioSnapshot.ticker == ticker,
                PortfolioSnapshot.snapshot_date >= cutoff,
            )
            .order_by(PortfolioSnapshot.snapshot_date)
        )
        price_result = await self._db.execute(price_stmt)
        prices = price_result.scalars().all()

        if len(prices) < 2 or not articles:
            return []

        patterns = []

        # Detect: negative news → price drop pattern
        bearish_articles = [a for a in articles if a.sentiment_score == "bearish"]
        bullish_articles = [a for a in articles if a.sentiment_score == "bullish"]

        price_by_date = {p.snapshot_date: float(p.current_price) for p in prices}
        sorted_dates = sorted(price_by_date.keys())

        if bearish_articles and len(sorted_dates) >= 2:
            # Check if price dropped after bearish news
            first_price = price_by_date[sorted_dates[0]]
            last_price = price_by_date[sorted_dates[-1]]
            change_pct = ((last_price - first_price) / first_price) * 100

            if change_pct < -2 and bearish_articles:
                patterns.append({
                    "ticker": ticker,
                    "pattern": f"Bearish news ({len(bearish_articles)} articles) + price decline",
                    "historical_outcome": f"Stock dropped {abs(change_pct):.1f}% over {len(sorted_dates)} trading days",
                    "current_probability": "high" if len(bearish_articles) > 2 else "medium",
                    "suggested_action": "Consider reducing position or setting stop-loss",
                })

        if bullish_articles and len(sorted_dates) >= 2:
            first_price = price_by_date[sorted_dates[0]]
            last_price = price_by_date[sorted_dates[-1]]
            change_pct = ((last_price - first_price) / first_price) * 100

            if change_pct > 2 and bullish_articles:
                patterns.append({
                    "ticker": ticker,
                    "pattern": f"Bullish news ({len(bullish_articles)} articles) + price rise",
                    "historical_outcome": f"Stock gained {change_pct:.1f}% over {len(sorted_dates)} trading days",
                    "current_probability": "medium",
                    "suggested_action": "Momentum may continue — hold or add on dips",
                })

        return patterns

    async def get_full_analysis_context(self, user_id: UUID, portfolio_tickers: list[str]) -> dict:
        """Build complete intelligence context for the LLM."""
        accuracy_ctx = await self.get_accuracy_context(user_id)
        concentration_risks = await self.detect_sector_concentration(user_id)

        # Get patterns for top tickers (limit to avoid timeout)
        all_patterns = []
        for ticker in portfolio_tickers[:10]:
            patterns = await self.detect_price_patterns(user_id, ticker)
            all_patterns.extend(patterns)

        return {
            "accuracy_context": accuracy_ctx,
            "concentration_risks": concentration_risks,
            "patterns": all_patterns,
        }

    def format_for_prompt(self, analysis: dict) -> str:
        """Format the analysis context as text for the LLM prompt."""
        lines = []

        # Accuracy context
        lines.append(analysis.get("accuracy_context", ""))
        lines.append("")

        # Risk warnings
        risks = analysis.get("concentration_risks", [])
        if risks:
            lines.append("Portfolio Risk Warnings:")
            for r in risks:
                lines.append(f"  ⚠️ {r['risk']}")
            lines.append("")

        # Patterns
        patterns = analysis.get("patterns", [])
        if patterns:
            lines.append("Historical Patterns Detected:")
            for p in patterns:
                lines.append(f"  📊 {p['ticker']}: {p['pattern']}")
                lines.append(f"     Outcome: {p['historical_outcome']}")
                lines.append(f"     Suggestion: {p['suggested_action']}")
            lines.append("")

        return "\n".join(lines)
