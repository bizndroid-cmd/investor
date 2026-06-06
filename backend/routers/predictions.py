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
