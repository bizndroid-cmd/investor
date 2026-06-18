"""Scheduled news collection task.

Replaces the old 30-minute polling model with a schedule-aware daily
collection system. Fetches news at configured IST times (default 07:00, 18:00),
stores with collection_date, and records CollectionRun metadata.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import uuid4
from zoneinfo import ZoneInfo

from backend.config import settings

if TYPE_CHECKING:
    from backend.services.news_aggregator import NewsAggregator
    from backend.services.news_analyzer import NewsAnalyzer

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


def parse_collection_times(times_str: str) -> list[tuple[int, int]]:
    """Parse NEWS_COLLECTION_TIMES string into list of (hour, minute) tuples.

    Validates format: comma-separated HH:MM values (24-hour IST).
    Returns sorted list of (hour, minute) tuples.
    """
    times = []
    for entry in times_str.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) != 2:
            logger.warning("Invalid time entry '%s', skipping", entry)
            continue
        try:
            hour, minute = int(parts[0]), int(parts[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                times.append((hour, minute))
            else:
                logger.warning("Time out of range '%s', skipping", entry)
        except ValueError:
            logger.warning("Invalid time format '%s', skipping", entry)

    if not times:
        # Fallback to defaults
        times = [(7, 0), (18, 0)]

    return sorted(times)


class NewsCollectionScheduler:
    """Schedule-aware news collection task.

    Calculates time until next configured IST run time,
    sleeps until then, executes collection, repeats.
    """

    def __init__(
        self,
        aggregator: "NewsAggregator",
        analyzer: "NewsAnalyzer",
    ) -> None:
        self._aggregator = aggregator
        self._analyzer = analyzer
        self._times = parse_collection_times(settings.news_collection_times)
        self._first_run_done = False
        logger.info(
            "News collector initialized with schedule: %s IST",
            ", ".join(f"{h:02d}:{m:02d}" for h, m in self._times),
        )

    async def run(self) -> None:
        """Main loop: check for catch-up, then enter schedule loop."""
        await self._maybe_catch_up()

        # Auto-refresh Groww token on startup (in case it expired overnight)
        await self._auto_refresh_groww_token()

        while True:
            seconds_until_next = self._seconds_until_next_run()
            next_time = datetime.now(IST) + timedelta(seconds=seconds_until_next)
            logger.info(
                "News collector sleeping until %s IST (%.0f seconds)",
                next_time.strftime("%Y-%m-%d %H:%M"),
                seconds_until_next,
            )

            # Check if we need to refresh Groww token before the next run
            # (tokens expire at 6 AM IST, refresh at 5:30 AM)
            await self._schedule_token_refresh(seconds_until_next)

            await asyncio.sleep(seconds_until_next)

            try:
                await self._execute_collection(source="scheduled")
            except Exception as e:
                logger.error("Scheduled collection failed: %s", str(e))

            # Post-collection: auto-generate briefings and score predictions
            try:
                await self._post_collection_tasks()
            except Exception as e:
                logger.error("Post-collection tasks failed: %s", str(e))

            # Run cleanup after first scheduled run of the day
            if not self._first_run_done:
                self._first_run_done = True
                try:
                    await self._cleanup_old_data()
                except Exception as e:
                    logger.error("Daily cleanup failed: %s", str(e))

    async def execute_immediate(self) -> dict:
        """Execute an immediate collection run (manual trigger).

        Returns collection run metadata.
        """
        return await self._execute_collection(source="manual")

    async def _execute_collection(self, source: str) -> dict:
        """Single collection cycle with retry logic.

        Creates a CollectionRun record, fetches/stores articles for all users,
        retries up to 3 times on failure.
        """
        from backend.database import AsyncSessionLocal
        from backend.models.orm import CollectionRun

        start_time = time.time()
        today_ist = datetime.now(IST).date()

        # Create CollectionRun record
        run_id = uuid4()
        async with AsyncSessionLocal() as db:
            run = CollectionRun(
                id=run_id,
                started_at=datetime.now(timezone.utc),
                status="started",
                source=source,
            )
            db.add(run)
            await db.commit()

        total_fetched = 0
        total_stored = 0
        last_error = None

        for attempt in range(4):  # 1 initial + 3 retries
            try:
                fetched, stored = await self._collect_for_all_users(
                    run_id=run_id, collection_date=today_ist
                )
                total_fetched = fetched
                total_stored = stored
                last_error = None
                break
            except Exception as e:
                last_error = str(e)
                logger.error(
                    "Collection attempt %d/4 failed: %s", attempt + 1, last_error
                )
                if attempt < 3:
                    delay = min(60 * (2 ** attempt), 240)
                    await asyncio.sleep(delay)

        # Update CollectionRun with results
        duration = time.time() - start_time
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select

            stmt = select(CollectionRun).where(CollectionRun.id == run_id)
            result = await db.execute(stmt)
            run = result.scalar_one()

            if last_error:
                run.status = "failed"
                run.error_message = last_error[:500]
            else:
                run.status = "completed"

            run.completed_at = datetime.now(timezone.utc)
            run.articles_fetched = total_fetched
            run.articles_stored = total_stored
            run.duration_seconds = round(duration, 1)
            await db.commit()

        # Log results
        status = "completed" if not last_error else "failed"
        logger.info(
            "Collection run %s [%s]: fetched=%d, stored=%d, duration=%.1fs",
            status, source, total_fetched, total_stored, duration,
        )

        if duration > 300:  # 5 minutes
            logger.warning("Collection run exceeded 5 minutes (%.1fs)", duration)

        return {
            "run_id": str(run_id),
            "status": status,
            "source": source,
            "articles_fetched": total_fetched,
            "articles_stored": total_stored,
            "duration_seconds": round(duration, 1),
        }

    async def _collect_for_all_users(
        self, run_id, collection_date: date
    ) -> tuple[int, int]:
        """Fetch and store articles for all users. Returns (fetched, stored) counts."""
        from backend.database import AsyncSessionLocal
        from backend.models.orm import HoldingCache, NewsArticle, User
        from sqlalchemy import select, func

        total_fetched = 0
        total_stored = 0

        # Get all user IDs
        async with AsyncSessionLocal() as db:
            stmt = select(User.id)
            result = await db.execute(stmt)
            user_ids = [row[0] for row in result.all()]

        if not user_ids:
            logger.debug("No users found, skipping collection")
            return 0, 0

        for user_id in user_ids:
            try:
                fetched, stored = await self._collect_for_user(
                    user_id=user_id,
                    run_id=run_id,
                    collection_date=collection_date,
                )
                total_fetched += fetched
                total_stored += stored
            except Exception as exc:
                logger.error("Collection failed for user %s: %s", user_id, str(exc))

        return total_fetched, total_stored

    async def _collect_for_user(
        self, user_id, run_id, collection_date: date
    ) -> tuple[int, int]:
        """Fetch, deduplicate, store, and analyze articles for a single user."""
        from backend.database import AsyncSessionLocal
        from backend.models.orm import HoldingCache, NewsArticle
        from sqlalchemy import select, func

        # Get user's portfolio tickers
        async with AsyncSessionLocal() as db:
            stmt = select(HoldingCache.ticker).where(HoldingCache.user_id == user_id)
            result = await db.execute(stmt)
            portfolio_tickers = [row[0] for row in result.all()]

        if not portfolio_tickers:
            return 0, 0

        # Fetch articles from RSS feeds
        raw_articles = await self._aggregator.fetch_articles(portfolio_tickers)
        if not raw_articles:
            return 0, 0

        fetched = len(raw_articles)
        stored = 0

        # Store with deduplication (case-insensitive title + source_name + collection_date)
        async with AsyncSessionLocal() as db:
            for article in raw_articles:
                # Check for duplicate
                stmt = select(func.count()).select_from(NewsArticle).where(
                    NewsArticle.user_id == user_id,
                    NewsArticle.collection_date == collection_date,
                    func.lower(NewsArticle.title) == article.title.strip().lower(),
                    func.lower(NewsArticle.source_name) == article.source_name.strip().lower(),
                )
                result = await db.execute(stmt)
                if result.scalar() > 0:
                    continue

                # Identify related tickers from content
                content_upper = f"{article.title} {article.raw_content}".upper()
                related_tickers = [
                    t for t in portfolio_tickers if t.upper() in content_upper
                ]

                news_record = NewsArticle(
                    user_id=user_id,
                    title=article.title,
                    source_name=article.source_name,
                    source_url=article.source_url,
                    published_at=article.published_at,
                    raw_content=article.raw_content,
                    related_tickers=related_tickers if related_tickers else None,
                    collection_date=collection_date,
                    collection_run_id=run_id,
                    is_analyzed=False,
                )
                db.add(news_record)
                stored += 1

            if stored > 0:
                await db.commit()

        # Analyze articles (batched, with circuit breaker)
        if stored > 0:
            analyzed_items = await self._analyzer.analyze_batch(
                raw_articles, portfolio_tickers
            )
            if analyzed_items:
                async with AsyncSessionLocal() as db:
                    for item in analyzed_items:
                        stmt = select(NewsArticle).where(
                            NewsArticle.user_id == user_id,
                            NewsArticle.title == item.title,
                            NewsArticle.collection_date == collection_date,
                        )
                        result = await db.execute(stmt)
                        record = result.scalar_one_or_none()
                        if record:
                            record.summary = item.summary
                            record.sentiment_score = item.sentiment_score.value
                            record.impact_level = item.impact_level.value
                            record.related_tickers = item.related_tickers
                            record.relevance_score = item.relevance_score
                            record.is_analyzed = True
                            record.is_stub = item.is_stub
                            record.analyzed_at = item.analyzed_at
                    await db.commit()

        return fetched, stored

    def _seconds_until_next_run(self) -> float:
        """Calculate seconds from now until the next scheduled IST time."""
        now_ist = datetime.now(IST)
        today = now_ist.date()

        # Find next scheduled time today or tomorrow
        for hour, minute in self._times:
            scheduled = datetime(
                today.year, today.month, today.day, hour, minute, tzinfo=IST
            )
            if scheduled > now_ist:
                return (scheduled - now_ist).total_seconds()

        # All today's times have passed — schedule for first time tomorrow
        tomorrow = today + timedelta(days=1)
        hour, minute = self._times[0]
        scheduled = datetime(
            tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, tzinfo=IST
        )
        return (scheduled - now_ist).total_seconds()

    async def _maybe_catch_up(self) -> None:
        """If last successful run was >12h ago, execute a catch-up fetch."""
        from backend.database import AsyncSessionLocal
        from backend.models.orm import CollectionRun
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            stmt = (
                select(CollectionRun)
                .where(CollectionRun.status == "completed")
                .order_by(desc(CollectionRun.started_at))
                .limit(1)
            )
            result = await db.execute(stmt)
            last_run = result.scalar_one_or_none()

        if last_run is None:
            # No previous run — do a catch-up
            logger.info("No previous collection run found. Executing catch-up fetch.")
            await asyncio.sleep(5)  # Brief delay on startup
            await self._execute_collection(source="catch_up")
            return

        hours_since = (
            datetime.now(timezone.utc) - last_run.started_at
        ).total_seconds() / 3600

        if hours_since > 12:
            logger.info(
                "Last collection run was %.1f hours ago. Executing catch-up fetch.",
                hours_since,
            )
            await asyncio.sleep(5)
            await self._execute_collection(source="catch_up")

    async def _cleanup_old_data(self) -> None:
        """Delete articles older than retention window and old collection_run records."""
        from backend.database import AsyncSessionLocal
        from backend.models.orm import CollectionRun, NewsArticle
        from sqlalchemy import delete, select, func

        cutoff_date = date.today() - timedelta(days=settings.news_retention_days)

        async with AsyncSessionLocal() as db:
            # Delete old articles
            stmt = delete(NewsArticle).where(
                NewsArticle.collection_date < cutoff_date
            )
            result = await db.execute(stmt)
            deleted_articles = result.rowcount

            # Delete old collection runs
            cutoff_ts = datetime.now(timezone.utc) - timedelta(
                days=settings.news_retention_days
            )
            stmt = delete(CollectionRun).where(CollectionRun.started_at < cutoff_ts)
            result = await db.execute(stmt)
            deleted_runs = result.rowcount

            await db.commit()

        if deleted_articles > 0 or deleted_runs > 0:
            logger.info(
                "Cleanup: deleted %d old articles and %d old collection runs",
                deleted_articles,
                deleted_runs,
            )

        # Enforce per-user article cap
        await self._enforce_article_cap()

    async def _post_collection_tasks(self) -> None:
        """Run after news collection: generate briefing, snapshot portfolio, score predictions.

        This runs for all users after each scheduled news collection.
        """
        from backend.database import AsyncSessionLocal
        from backend.models.orm import User
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            stmt = select(User.id)
            result = await db.execute(stmt)
            user_ids = [row[0] for row in result.all()]

        if not user_ids:
            return

        for user_id in user_ids:
            try:
                await self._run_daily_tasks_for_user(user_id)
            except Exception as e:
                logger.error("Post-collection tasks failed for user %s: %s", user_id, str(e))

    async def _run_daily_tasks_for_user(self, user_id) -> None:
        """Run daily automated tasks for a single user."""
        from backend.database import AsyncSessionLocal
        from backend.dependencies import create_llm_service
        from backend.services.news_aggregator import NewsAggregator
        from backend.services.news_analyzer import NewsAnalyzer
        from backend.services.news_service import NewsService
        from backend.services.portfolio_snapshot_service import PortfolioSnapshotService
        from backend.services.prediction_service import PredictionService
        from backend.config import settings
        import redis.asyncio as aioredis
        from datetime import date
        from zoneinfo import ZoneInfo

        IST = ZoneInfo("Asia/Kolkata")
        today = datetime.now(IST).date()

        redis = aioredis.from_url(settings.redis_url, decode_responses=True)

        try:
            # 1. Capture portfolio snapshot from market prices (yfinance, no Groww needed)
            async with AsyncSessionLocal() as db:
                snapshot_svc = PortfolioSnapshotService(db=db)
                captured = await snapshot_svc.capture_snapshot_from_market(user_id=user_id)
                if captured:
                    logger.info("Daily market snapshot captured for user %s", user_id)

            # 1b. Refresh stock fundamentals weekly (screener.in)
            try:
                from backend.services.screener_service import ScreenerService
                from backend.models.orm import HoldingCache
                from sqlalchemy import select as sa_select
                async with AsyncSessionLocal() as db:
                    stmt = sa_select(HoldingCache.ticker).where(HoldingCache.user_id == user_id)
                    result = await db.execute(stmt)
                    tickers = [r[0] for r in result.all()]
                    if tickers:
                        screener_svc = ScreenerService(db=db)
                        await screener_svc.fetch_all_portfolio(tickers)
            except Exception as e:
                logger.warning("Fundamentals refresh skipped: %s", str(e))

            # 2. Auto-generate portfolio briefing (stores prediction)
            async with AsyncSessionLocal() as db:
                llm_service = create_llm_service()
                aggregator = NewsAggregator()
                analyzer = NewsAnalyzer(llm_service=llm_service)
                news_svc = NewsService(db=db, redis=redis, aggregator=aggregator, analyzer=analyzer)

                briefing = await news_svc.generate_briefing(user_id=user_id)
                is_cached = briefing.get("is_cached", False)
                is_stub = briefing.get("is_stub", False)

                if not is_cached and not is_stub:
                    logger.info("Auto-briefing generated for user %s", user_id)
                elif is_cached:
                    logger.debug("Briefing served from cache for user %s (no new news)", user_id)

            # 3. Auto-score pending predictions (already triggered in snapshot capture above)
            # Additional pass for any missed ones
            async with AsyncSessionLocal() as db:
                pred_svc = PredictionService(db=db)
                for days_back in range(1, 8):
                    check_date = today - timedelta(days=days_back)
                    try:
                        result = await pred_svc.compute_confidence_score(user_id, check_date)
                        if result:
                            logger.info(
                                "Auto-scored prediction for user %s, date %s: %.1f%%",
                                user_id, check_date, result["confidence_score"],
                            )
                    except Exception:
                        pass

        finally:
            await redis.aclose()

    async def _schedule_token_refresh(self, sleep_seconds: float) -> None:
        """If the next collection is after 6 AM IST, schedule a token refresh at 5:30 AM.

        Runs the refresh in the background while sleeping for the main schedule.
        """
        now_ist = datetime.now(IST)
        today = now_ist.date()

        # Calculate 5:30 AM IST today (or tomorrow if already past)
        refresh_time = datetime(today.year, today.month, today.day, 5, 30, tzinfo=IST)
        if refresh_time <= now_ist:
            # Already past 5:30 AM today — check tomorrow
            tomorrow = today + timedelta(days=1)
            refresh_time = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 5, 30, tzinfo=IST)

        seconds_until_refresh = (refresh_time - now_ist).total_seconds()

        # Only schedule if the refresh time falls within our sleep window
        if 0 < seconds_until_refresh < sleep_seconds:
            logger.info(
                "Groww token refresh scheduled in %.0f seconds (5:30 AM IST)",
                seconds_until_refresh,
            )
            # Sleep until refresh time, refresh, then the outer loop handles the rest
            await asyncio.sleep(seconds_until_refresh)
            await self._auto_refresh_groww_token()
            # Remaining sleep is handled by the outer loop recalculation

    async def _auto_refresh_groww_token(self) -> None:
        """Auto-refresh Groww access token for all users using API Key + Secret.

        Uses the checksum flow: SHA256(secret + timestamp) to generate a new token.
        This runs daily before the old token expires (6 AM IST).
        """
        if not settings.groww_api_key or not settings.groww_api_secret:
            logger.debug("Groww auto-refresh skipped: no API key/secret configured")
            return

        from backend.database import AsyncSessionLocal
        from backend.models.orm import User, BrokerToken
        from backend.connectors.groww import GrowwConnector
        from sqlalchemy import select

        connector = GrowwConnector()

        # Find all users with a Groww connection
        async with AsyncSessionLocal() as db:
            stmt = select(BrokerToken.user_id).where(BrokerToken.broker_id == "groww")
            result = await db.execute(stmt)
            user_ids = [row[0] for row in result.all()]

        if not user_ids:
            logger.debug("No users with Groww connection, skipping token refresh")
            return

        for user_id in user_ids:
            try:
                # This calls the checksum auth flow and stores the new token
                await connector.refresh_tokens(user_id)
                logger.info("Groww token auto-refreshed for user %s", user_id)
            except Exception as e:
                logger.warning("Groww token refresh failed for user %s: %s", user_id, str(e))

    async def _enforce_article_cap(self) -> None:
        """Delete oldest articles if user exceeds the per-user cap."""
        from backend.database import AsyncSessionLocal
        from backend.models.orm import NewsArticle, User
        from sqlalchemy import select, func, delete

        max_articles = settings.news_max_articles_per_user

        async with AsyncSessionLocal() as db:
            # Find users over the cap
            stmt = (
                select(NewsArticle.user_id, func.count(NewsArticle.id).label("cnt"))
                .group_by(NewsArticle.user_id)
                .having(func.count(NewsArticle.id) > max_articles)
            )
            result = await db.execute(stmt)
            over_cap = result.all()

            for user_id, count in over_cap:
                excess = count - max_articles
                # Get IDs of oldest articles to delete
                oldest_stmt = (
                    select(NewsArticle.id)
                    .where(NewsArticle.user_id == user_id)
                    .order_by(NewsArticle.collection_date.asc())
                    .limit(excess)
                )
                oldest_result = await db.execute(oldest_stmt)
                ids_to_delete = [row[0] for row in oldest_result.all()]

                if ids_to_delete:
                    del_stmt = delete(NewsArticle).where(
                        NewsArticle.id.in_(ids_to_delete)
                    )
                    await db.execute(del_stmt)
                    logger.info(
                        "Enforced article cap: deleted %d articles for user %s",
                        len(ids_to_delete),
                        user_id,
                    )

            await db.commit()


async def start_news_collector(
    aggregator: "NewsAggregator",
    analyzer: "NewsAnalyzer",
) -> tuple[asyncio.Task, NewsCollectionScheduler]:
    """Start the background news collection scheduler.

    Returns both the task and the scheduler instance (for manual triggers).
    """
    scheduler = NewsCollectionScheduler(aggregator=aggregator, analyzer=analyzer)
    task = asyncio.create_task(scheduler.run())
    return task, scheduler
