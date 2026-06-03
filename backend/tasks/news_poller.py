"""Background news polling task.

Runs periodically (default every 30 minutes), fetches news articles for all
users via the NewsAggregator, then analyzes them via the NewsAnalyzer.
Follows the same pattern as price_poller.py.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from backend.config import settings

if TYPE_CHECKING:
    from backend.services.news_aggregator import NewsAggregator
    from backend.services.news_analyzer import NewsAnalyzer

logger = logging.getLogger(__name__)


async def start_news_poller(
    aggregator: "NewsAggregator",
    analyzer: "NewsAnalyzer",
) -> asyncio.Task:
    """Start the background news polling task.

    Returns the asyncio.Task so it can be cancelled on shutdown.

    Each cycle:
    1. Get all users from the database
    2. For each user, get their portfolio tickers
    3. Fetch news articles via NewsAggregator
    4. Store raw articles
    5. Analyze articles via NewsAnalyzer
    6. Update DB with analysis results
    """
    poll_interval = settings.news_poll_interval

    async def _poll_loop() -> None:
        logger.info("News poller started (interval: %ds)", poll_interval)
        while True:
            try:
                await _poll_once(aggregator, analyzer)
            except asyncio.CancelledError:
                logger.info("News poller cancelled")
                break
            except Exception as e:
                logger.error("News poller error: %s", str(e))

            await asyncio.sleep(poll_interval)

    task = asyncio.create_task(_poll_loop())
    return task


async def _poll_once(
    aggregator: "NewsAggregator",
    analyzer: "NewsAnalyzer",
) -> None:
    """Execute a single news polling cycle for all users."""
    from backend.database import AsyncSessionLocal
    from backend.models.orm import HoldingCache, NewsArticle, User

    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # Get all users
        stmt = select(User.id)
        result = await db.execute(stmt)
        user_ids = [row[0] for row in result.all()]

    if not user_ids:
        logger.debug("No users found, skipping news poll cycle")
        return

    logger.debug("News poller: processing %d users", len(user_ids))

    for user_id in user_ids:
        try:
            await _poll_for_user(user_id, aggregator, analyzer)
        except Exception as exc:
            logger.error(
                "News poller failed for user %s: %s", user_id, str(exc)
            )


async def _poll_for_user(
    user_id,
    aggregator: "NewsAggregator",
    analyzer: "NewsAnalyzer",
) -> None:
    """Fetch and analyze news for a single user."""
    from backend.database import AsyncSessionLocal
    from backend.models.orm import HoldingCache, NewsArticle

    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # Get user's portfolio tickers from holdings cache
        stmt = select(HoldingCache.ticker).where(HoldingCache.user_id == user_id)
        result = await db.execute(stmt)
        portfolio_tickers = [row[0] for row in result.all()]

    if not portfolio_tickers:
        logger.debug("User %s has no holdings, skipping", user_id)
        return

    # Fetch articles
    raw_articles = await aggregator.fetch_articles(portfolio_tickers)
    if not raw_articles:
        return

    # Store raw articles
    async with AsyncSessionLocal() as db:
        await aggregator.store_articles(db, user_id, raw_articles)

    # Analyze articles
    analyzed_items = await analyzer.analyze_batch(raw_articles, portfolio_tickers)

    if not analyzed_items:
        return

    # Update DB with analysis results
    async with AsyncSessionLocal() as db:
        for item in analyzed_items:
            stmt = select(NewsArticle).where(
                NewsArticle.user_id == user_id,
                NewsArticle.title == item.title,
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

    logger.debug(
        "News poller: user %s — fetched %d, analyzed %d",
        user_id,
        len(raw_articles),
        len(analyzed_items),
    )
