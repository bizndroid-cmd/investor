"""Analytics API — track user interactions, serve usage dashboard.

Endpoints:
- POST /analytics/events — batch record events (page views, clicks)
- GET /analytics/summary — usage summary for admin
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.domain import Session
from backend.models.orm import AnalyticsEvent
from backend.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


class EventItem(BaseModel):
    event_type: str = Field(..., pattern="^(page_view|click|session_end)$")
    page: str | None = None
    target: str | None = None
    duration_ms: int | None = None
    metadata: dict | None = None


class BatchEventsRequest(BaseModel):
    events: list[EventItem] = Field(..., max_length=50)


@router.post("/events", status_code=202)
async def record_events(
    body: BatchEventsRequest,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record a batch of analytics events. Fire-and-forget from client."""
    for event in body.events:
        db.add(AnalyticsEvent(
            id=uuid4(),
            user_id=session.user_id,
            event_type=event.event_type,
            page=event.page[:50] if event.page else None,
            target=event.target[:100] if event.target else None,
            duration_ms=event.duration_ms,
            extra_data=json.dumps(event.metadata) if event.metadata else None,
        ))
    await db.commit()
    return {"recorded": len(body.events)}


@router.get("/summary")
async def get_analytics_summary(
    days: int = Query(7, ge=1, le=90),
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Usage summary: page views, top pages, session time, active days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Total events
    total_stmt = select(func.count()).where(
        AnalyticsEvent.user_id == session.user_id,
        AnalyticsEvent.created_at >= cutoff,
    )
    total = (await db.execute(total_stmt)).scalar() or 0

    # Page views by page
    pages_stmt = (
        select(AnalyticsEvent.page, func.count().label("views"))
        .where(
            AnalyticsEvent.user_id == session.user_id,
            AnalyticsEvent.event_type == "page_view",
            AnalyticsEvent.created_at >= cutoff,
        )
        .group_by(AnalyticsEvent.page)
        .order_by(desc("views"))
        .limit(10)
    )
    pages_result = await db.execute(pages_stmt)
    top_pages = [{"page": r[0], "views": r[1]} for r in pages_result.all()]

    # Top clicked targets
    clicks_stmt = (
        select(AnalyticsEvent.target, func.count().label("clicks"))
        .where(
            AnalyticsEvent.user_id == session.user_id,
            AnalyticsEvent.event_type == "click",
            AnalyticsEvent.created_at >= cutoff,
            AnalyticsEvent.target.isnot(None),
        )
        .group_by(AnalyticsEvent.target)
        .order_by(desc("clicks"))
        .limit(10)
    )
    clicks_result = await db.execute(clicks_stmt)
    top_clicks = [{"target": r[0], "clicks": r[1]} for r in clicks_result.all()]

    # Average session duration
    avg_duration_stmt = select(func.avg(AnalyticsEvent.duration_ms)).where(
        AnalyticsEvent.user_id == session.user_id,
        AnalyticsEvent.event_type == "session_end",
        AnalyticsEvent.created_at >= cutoff,
    )
    avg_duration = (await db.execute(avg_duration_stmt)).scalar()

    # Active days
    active_days_stmt = (
        select(func.count(func.distinct(func.date_trunc("day", AnalyticsEvent.created_at))))
        .where(
            AnalyticsEvent.user_id == session.user_id,
            AnalyticsEvent.created_at >= cutoff,
        )
    )
    active_days = (await db.execute(active_days_stmt)).scalar() or 0

    return {
        "period_days": days,
        "total_events": total,
        "top_pages": top_pages,
        "top_clicks": top_clicks,
        "avg_session_ms": round(avg_duration) if avg_duration else None,
        "active_days": active_days,
    }
