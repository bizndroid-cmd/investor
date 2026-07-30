"""FastAPI news router for market news feed and refresh endpoints.

Endpoints:
- GET /news — paginated, filterable list of analyzed news items
- POST /news/refresh — manual refresh trigger
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.models.domain import PaginatedNewsResponse, RefreshStatus, Session
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/news", tags=["news"])


def get_news_service():
    """Dependency placeholder — overridden in main.py via app.dependency_overrides."""
    raise NotImplementedError("NewsService not wired. Use dependency overrides.")


@router.get("", response_model=PaginatedNewsResponse)
async def get_news_feed(
    sentiment: str | None = Query(None, description="Filter by sentiment: bullish, bearish, neutral"),
    impact_level: str | None = Query(None, description="Filter by impact: high, medium, low"),
    ticker: str | None = Query(None, description="Filter by ticker symbol"),
    source_type: str | None = Query(None, description="Filter by source: rss, newsapi_ai"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    session: Session = Depends(get_current_user),
    news_service=Depends(get_news_service),
) -> PaginatedNewsResponse:
    """Return a paginated, optionally filtered news feed for the current user."""
    return await news_service.get_news_feed(
        user_id=session.user_id,
        sentiment=sentiment,
        impact_level=impact_level,
        ticker=ticker,
        source_type=source_type,
        page=page,
        page_size=page_size,
    )


@router.post("/refresh", response_model=RefreshStatus)
async def trigger_refresh(
    source: str | None = Query(None, description="Source to fetch from: rss, newsapi_ai, or all (default)"),
    session: Session = Depends(get_current_user),
    news_service=Depends(get_news_service),
) -> RefreshStatus:
    """Trigger a manual news refresh for the current user.
    
    Optionally specify source: 'rss', 'newsapi_ai', or 'all' (default).
    """
    return await news_service.trigger_refresh(user_id=session.user_id, source=source)


@router.get("/briefing")
async def get_portfolio_briefing(
    session: Session = Depends(get_current_user),
    news_service=Depends(get_news_service),
) -> dict:
    """Generate a daily portfolio briefing combining holdings + news."""
    return await news_service.generate_briefing(user_id=session.user_id)


@router.get("/briefing/history")
async def get_briefing_history(
    days: int = Query(30, ge=1, le=90),
    session: Session = Depends(get_current_user),
) -> list[dict]:
    """Return past briefings stored in the cache."""
    from backend.database import AsyncSessionLocal
    from backend.models.orm import BriefingCache
    from sqlalchemy import select, desc
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        stmt = (
            select(BriefingCache)
            .where(
                BriefingCache.user_id == session.user_id,
                BriefingCache.collection_date >= cutoff,
            )
            .order_by(desc(BriefingCache.collection_date))
        )
        result = await db.execute(stmt)
        records = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "collection_date": r.collection_date.isoformat() if hasattr(r.collection_date, 'isoformat') else str(r.collection_date),
            "briefing_text": r.briefing_text,
            "provider": r.provider,
            "model": r.model,
            "articles_used": r.articles_used,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        }
        for r in records
    ]


@router.get("/collection-status")
async def get_collection_status(
    session: Session = Depends(get_current_user),
) -> dict:
    """Return status of the most recent news collection run."""
    from backend.database import AsyncSessionLocal
    from backend.models.orm import CollectionRun
    from sqlalchemy import select, desc
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")

    async with AsyncSessionLocal() as db:
        stmt = (
            select(CollectionRun)
            .order_by(desc(CollectionRun.started_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        last_run = result.scalar_one_or_none()

    # Calculate staleness
    is_stale = True
    last_run_data = None

    if last_run:
        hours_since = (
            datetime.now(timezone.utc) - last_run.started_at
        ).total_seconds() / 3600
        is_stale = last_run.status != "completed" or hours_since > 24

        last_run_data = {
            "id": str(last_run.id),
            "started_at": last_run.started_at.isoformat(),
            "completed_at": last_run.completed_at.isoformat() if last_run.completed_at else None,
            "status": last_run.status,
            "source": last_run.source,
            "articles_fetched": last_run.articles_fetched,
            "articles_stored": last_run.articles_stored,
            "duration_seconds": last_run.duration_seconds,
        }

    # Calculate next scheduled time
    from backend.tasks.news_collector import parse_collection_times
    from backend.config import settings

    times = parse_collection_times(settings.news_collection_times)
    now_ist = datetime.now(IST)
    next_scheduled = None
    for hour, minute in times:
        scheduled = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled > now_ist:
            next_scheduled = scheduled.isoformat()
            break
    if not next_scheduled:
        tomorrow = now_ist.date() + timedelta(days=1)
        hour, minute = times[0]
        next_scheduled = datetime(
            tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, tzinfo=IST
        ).isoformat()

    return {
        "last_run": last_run_data,
        "is_stale": is_stale,
        "next_scheduled": next_scheduled,
        "collection_date": datetime.now(IST).date().isoformat(),
    }
