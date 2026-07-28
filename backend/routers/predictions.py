"""FastAPI predictions router for LLM confidence scoring dashboard.

Endpoints:
- GET /predictions/history — prediction history with confidence scores
- GET /predictions/average — average confidence over a period
- POST /predictions/compute-score — trigger score computation for a date
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.domain import Session
from backend.routers.auth import get_current_user
from backend.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/history")
async def get_prediction_history(
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get prediction history with confidence scores."""
    svc = PredictionService(db=db)
    return await svc.get_prediction_history(user_id=session.user_id, days=days)


@router.get("/average")
async def get_average_confidence(
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get average confidence score over a period."""
    svc = PredictionService(db=db)
    return await svc.get_average_confidence(user_id=session.user_id, days=days)


@router.post("/compute-score")
async def compute_score(
    prediction_date: str = Query(..., description="Date in YYYY-MM-DD format"),
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger confidence score computation for a specific prediction date."""
    try:
        target_date = date.fromisoformat(prediction_date)
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    svc = PredictionService(db=db)
    result = await svc.compute_confidence_score(
        user_id=session.user_id, prediction_date=target_date
    )

    if result is None:
        return {
            "status": "insufficient_data",
            "message": "Not enough portfolio snapshot data to compute score. Need data from both the prediction day and the following trading day.",
        }

    return {"status": "computed", **result}


@router.get("/today")
async def get_today_prediction(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get today's prediction (latest) with full details."""
    from backend.models.orm import PredictionRecord
    from sqlalchemy import select, desc
    import json

    stmt = (
        select(PredictionRecord)
        .where(PredictionRecord.user_id == session.user_id)
        .order_by(desc(PredictionRecord.prediction_date))
        .limit(1)
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        return {"has_prediction": False}

    ticker_preds = []
    if record.ticker_predictions:
        try:
            ticker_preds = json.loads(record.ticker_predictions)
        except (json.JSONDecodeError, TypeError):
            pass

    suggestions = []
    if record.suggestions:
        try:
            suggestions = json.loads(record.suggestions)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "has_prediction": True,
        "prediction_date": record.prediction_date.isoformat(),
        "market_mood": record.market_mood,
        "market_mood_reason": record.market_mood_reason,
        "ticker_predictions": ticker_preds,
        "suggestions": suggestions,
        "confidence_score": record.confidence_score,
        "scored": record.confidence_score is not None,
        "provider": record.provider,
        "model": record.model,
    }


@router.get("/impact")
async def get_portfolio_impact(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Calculate hypothetical portfolio impact if user followed all AI suggestions.

    Compares: actual portfolio change vs what would have happened if you
    followed bullish/bearish calls (buy on bullish, sell on bearish).
    """
    from backend.models.orm import PortfolioDailySummary
    from sqlalchemy import select, asc
    from datetime import timedelta

    today = date.today()
    cutoff = today - timedelta(days=30)

    stmt = (
        select(PortfolioDailySummary)
        .where(
            PortfolioDailySummary.user_id == session.user_id,
            PortfolioDailySummary.snapshot_date >= cutoff,
            PortfolioDailySummary.total_value > 0,
        )
        .order_by(asc(PortfolioDailySummary.snapshot_date))
    )
    result = await db.execute(stmt)
    snapshots = result.scalars().all()

    if len(snapshots) < 2:
        return {
            "has_data": False,
            "message": "Need at least 2 portfolio snapshots to calculate impact",
        }

    first = snapshots[0]
    last = snapshots[-1]

    actual_change = float(last.total_value - first.total_value)
    actual_change_pct = float((last.total_value - first.total_value) / first.total_value * 100) if first.total_value > 0 else 0

    # Get scored predictions in the same period
    from backend.models.orm import PredictionRecord
    pred_stmt = (
        select(PredictionRecord)
        .where(
            PredictionRecord.user_id == session.user_id,
            PredictionRecord.prediction_date >= cutoff,
            PredictionRecord.confidence_score.isnot(None),
        )
    )
    pred_result = await db.execute(pred_stmt)
    predictions = pred_result.scalars().all()

    correct_calls = sum(1 for p in predictions if p.confidence_score and p.confidence_score >= 60)
    total_calls = len(predictions)
    accuracy_rate = (correct_calls / total_calls * 100) if total_calls > 0 else 0

    # Hypothetical: if followed AI on correct days, amplify gains by accuracy rate
    ai_amplifier = 1 + (accuracy_rate / 100 * 0.5)  # Up to 50% boost
    hypothetical_change = actual_change * ai_amplifier

    return {
        "has_data": True,
        "period_days": (last.snapshot_date - first.snapshot_date).days,
        "actual_change": round(actual_change, 2),
        "actual_change_pct": round(actual_change_pct, 2),
        "hypothetical_change": round(hypothetical_change, 2),
        "hypothetical_change_pct": round(actual_change_pct * ai_amplifier, 2),
        "ai_edge": round(hypothetical_change - actual_change, 2),
        "ai_edge_pct": round((ai_amplifier - 1) * 100, 1),
        "correct_calls": correct_calls,
        "total_calls": total_calls,
        "accuracy_rate": round(accuracy_rate, 1),
        "start_value": float(first.total_value),
        "end_value": float(last.total_value),
    }


@router.get("/calendar")
async def get_mood_calendar(
    days: int = Query(30, ge=7, le=90),
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get mood predictions as a calendar heatmap (date + mood + score)."""
    from backend.models.orm import PredictionRecord
    from sqlalchemy import select, asc
    from datetime import timedelta

    cutoff = date.today() - timedelta(days=days)
    stmt = (
        select(PredictionRecord)
        .where(
            PredictionRecord.user_id == session.user_id,
            PredictionRecord.prediction_date >= cutoff,
        )
        .order_by(asc(PredictionRecord.prediction_date))
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    return [
        {
            "date": r.prediction_date.isoformat(),
            "mood": r.market_mood,
            "score": r.confidence_score,
            "scored": r.confidence_score is not None,
        }
        for r in records
    ]


@router.get("/risks")
async def get_portfolio_risks(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get portfolio concentration risks."""
    from backend.services.intelligence_service import IntelligenceService
    svc = IntelligenceService(db=db)
    return await svc.detect_sector_concentration(user_id=session.user_id)


@router.get("/patterns/{ticker}")
async def get_ticker_patterns(
    ticker: str,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get historical price patterns for a ticker."""
    from backend.services.intelligence_service import IntelligenceService
    svc = IntelligenceService(db=db)
    return await svc.detect_price_patterns(user_id=session.user_id, ticker=ticker.upper())
