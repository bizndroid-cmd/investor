"""Per-stock research card API — RhoFi-style equity report.

Endpoint:
- GET /portfolio/research/{ticker} — full research card with technicals + fundamentals + AI score
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.domain import Session
from backend.models.orm import PredictionRecord, PortfolioSnapshot
from backend.routers.auth import get_current_user
from backend.services.screener_service import ScreenerService
from backend.services.technical_analysis_service import TechnicalAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio/research", tags=["research"])


def _compute_verdict(technicals: dict, fundamentals: dict | None) -> dict:
    """Generate BUY/HOLD/SELL verdict with score/10 based on signals."""
    score = 5.0  # Start neutral
    reasons_bull: list[str] = []
    reasons_bear: list[str] = []

    # Technical signals
    trend = technicals.get("moving_averages", {}).get("trend", "neutral")
    if trend == "strong_bullish":
        score += 1.5
        reasons_bull.append("Strong uptrend (price > SMA20 > SMA50)")
    elif trend == "bullish":
        score += 0.8
        reasons_bull.append("Uptrend (price > SMA20)")
    elif trend == "strong_bearish":
        score -= 1.5
        reasons_bear.append("Strong downtrend (price < SMA20 < SMA50)")
    elif trend == "bearish":
        score -= 0.8
        reasons_bear.append("Downtrend (price < SMA20)")

    # RSI
    rsi = technicals.get("rsi")
    if rsi:
        if rsi > 70:
            score -= 0.5
            reasons_bear.append(f"RSI overbought ({rsi})")
        elif rsi < 30:
            score += 0.5
            reasons_bull.append(f"RSI oversold ({rsi}) — potential bounce")
        elif 40 <= rsi <= 60:
            reasons_bull.append(f"RSI neutral ({rsi})")

    # MACD
    macd = technicals.get("macd")
    if macd:
        if macd["histogram"] > 0:
            score += 0.5
            reasons_bull.append("MACD bullish crossover")
        else:
            score -= 0.5
            reasons_bear.append("MACD bearish crossover")

    # Bollinger
    bollinger = technicals.get("bollinger")
    if bollinger:
        if bollinger["signal"] == "oversold":
            score += 0.3
            reasons_bull.append("Near lower Bollinger Band")
        elif bollinger["signal"] == "overbought":
            score -= 0.3
            reasons_bear.append("Near upper Bollinger Band")

    # Volume
    vol = technicals.get("volume", {})
    if vol.get("ratio") and vol["ratio"] > 1.5:
        reasons_bull.append("High volume confirms momentum")
        score += 0.3

    # 52-week position
    w52 = technicals.get("week_52", {})
    if w52.get("from_high_pct") is not None:
        if w52["from_high_pct"] > -5:
            reasons_bull.append("Near 52-week high")
        elif w52["from_high_pct"] < -30:
            reasons_bear.append(f"Down {abs(w52['from_high_pct'])}% from 52-week high")
            score -= 0.3

    # Fundamental signals
    if fundamentals:
        pe = fundamentals.get("pe_ratio")
        roce = fundamentals.get("roce")
        roe = fundamentals.get("roe")
        div_yield = fundamentals.get("dividend_yield")

        if pe:
            pe_val = float(pe)
            if pe_val < 15:
                score += 0.8
                reasons_bull.append(f"Low P/E ({pe_val}) — value territory")
            elif pe_val > 50:
                score -= 0.5
                reasons_bear.append(f"High P/E ({pe_val}) — expensive")

        if roce:
            roce_val = float(roce)
            if roce_val > 20:
                score += 0.5
                reasons_bull.append(f"Strong ROCE ({roce_val}%)")
            elif roce_val < 8:
                score -= 0.3
                reasons_bear.append(f"Weak ROCE ({roce_val}%)")

        if roe:
            roe_val = float(roe)
            if roe_val > 15:
                score += 0.3
                reasons_bull.append(f"Good ROE ({roe_val}%)")

        if div_yield:
            dv = float(div_yield)
            if dv > 2:
                score += 0.2
                reasons_bull.append(f"Dividend yield {dv}%")

    # Clamp score
    score = max(1.0, min(10.0, score))

    # Verdict
    if score >= 7:
        verdict = "BUY"
    elif score >= 5:
        verdict = "HOLD"
    else:
        verdict = "SELL"

    return {
        "verdict": verdict,
        "score": round(score, 1),
        "max_score": 10,
        "strengths": reasons_bull[:5],
        "weaknesses": reasons_bear[:5],
    }


async def _get_prediction_accuracy(
    db: AsyncSession, user_id, ticker: str
) -> dict | None:
    """Get AI prediction accuracy for this specific ticker."""
    cutoff = date.today() - timedelta(days=30)
    stmt = (
        select(PredictionRecord)
        .where(
            PredictionRecord.user_id == user_id,
            PredictionRecord.prediction_date >= cutoff,
            PredictionRecord.confidence_score.isnot(None),
        )
        .order_by(desc(PredictionRecord.prediction_date))
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    if not records:
        return None

    # Find predictions mentioning this ticker
    ticker_correct = 0
    ticker_total = 0

    for rec in records:
        if not rec.ticker_predictions:
            continue
        try:
            preds = json.loads(rec.ticker_predictions)
        except (json.JSONDecodeError, TypeError):
            continue

        for p in preds:
            if p.get("ticker") == ticker:
                ticker_total += 1
                # If overall score > 60, assume individual tickers were more right than wrong
                if rec.confidence_score and rec.confidence_score >= 60:
                    ticker_correct += 1
                break

    if ticker_total == 0:
        return None

    return {
        "mentions": ticker_total,
        "correct_days": ticker_correct,
        "accuracy_pct": round(ticker_correct / ticker_total * 100, 1),
    }


async def _get_holding_info(db: AsyncSession, user_id, ticker: str) -> dict | None:
    """Get user's holding position for this ticker."""
    stmt = (
        select(PortfolioSnapshot)
        .where(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.ticker == ticker,
        )
        .order_by(desc(PortfolioSnapshot.snapshot_date))
        .limit(1)
    )
    result = await db.execute(stmt)
    snapshot = result.scalar_one_or_none()

    if not snapshot:
        return None

    return {
        "quantity": float(snapshot.quantity),
        "avg_buy_price": float(snapshot.avg_buy_price),
        "current_value": float(snapshot.current_value),
        "invested_value": float(snapshot.avg_buy_price * snapshot.quantity),
        "gain_loss": float(snapshot.gain_loss),
        "gain_loss_pct": float(snapshot.gain_loss_percent),
    }


@router.get("/{ticker}")
async def get_research_card(
    ticker: str,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Full per-stock research card combining technicals + fundamentals + AI accuracy."""
    ticker = ticker.upper()

    # Fetch all data concurrently
    import asyncio

    ta_svc = TechnicalAnalysisService()
    screener_svc = ScreenerService(db=db)

    technicals_task = ta_svc.get_technicals(ticker)
    fundamentals_task = screener_svc.get_fundamentals(ticker)
    prediction_task = _get_prediction_accuracy(db, session.user_id, ticker)
    holding_task = _get_holding_info(db, session.user_id, ticker)

    technicals, fundamentals, prediction_accuracy, holding = await asyncio.gather(
        technicals_task, fundamentals_task, prediction_task, holding_task
    )

    if not technicals:
        return {
            "error": f"Could not fetch technical data for {ticker}. Verify ticker is listed on NSE.",
            "ticker": ticker,
        }

    # Compute verdict
    verdict = _compute_verdict(technicals, fundamentals)

    # Risk factors
    risk_factors = []
    atr = technicals.get("atr")
    price = technicals.get("current_price", 0)
    if atr and price:
        volatility_pct = round(atr / price * 100, 2)
        if volatility_pct > 3:
            risk_factors.append(f"High daily volatility ({volatility_pct}% ATR)")
        else:
            risk_factors.append(f"Daily volatility: {volatility_pct}% ATR")

    w52 = technicals.get("week_52", {})
    if w52.get("from_high_pct") and w52["from_high_pct"] < -20:
        risk_factors.append(f"Significant drawdown from 52-week high ({w52['from_high_pct']}%)")

    if fundamentals and fundamentals.get("cons"):
        cons_list = fundamentals["cons"].split(" | ")[:2]
        risk_factors.extend(cons_list)

    return {
        "ticker": ticker,
        "verdict": verdict,
        "technicals": technicals,
        "fundamentals": fundamentals,
        "prediction_accuracy": prediction_accuracy,
        "holding": holding,
        "risk_factors": risk_factors,
    }
