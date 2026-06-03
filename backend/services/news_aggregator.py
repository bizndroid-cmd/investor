"""News Aggregator service for fetching and storing market news articles.

Sources: Indian financial RSS feeds (Economic Times, LiveMint, Moneycontrol).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.domain import RawNewsArticle
from backend.models.orm import NewsArticle
from backend.services.telemetry_service import get_telemetry_service

logger = logging.getLogger(__name__)

# Indian financial RSS feeds
RSS_FEEDS = [
    # Economic Times - Markets
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    # Economic Times - Stocks News
    "https://economictimes.indiatimes.com/markets/stocks/news/rssfeeds/2146842.cms",
    # LiveMint - Markets
    "https://www.livemint.com/rss/markets",
    # Moneycontrol - Market Reports
    "https://www.moneycontrol.com/rss/marketreports.xml",
    # Moneycontrol - Business News
    "https://www.moneycontrol.com/rss/business.xml",
]


class NewsAggregator:
    """Fetches and stores market news articles from Indian financial RSS feeds."""

    def __init__(self) -> None:
        self._max_retries = 2
        self._base_delay = 1.0  # seconds

    async def fetch_articles(self, portfolio_tickers: list[str]) -> list[RawNewsArticle]:
        """Fetch articles from Indian financial RSS feeds.

        Args:
            portfolio_tickers: List of ticker symbols from the user's portfolio.

        Returns:
            List of raw news articles from Indian financial sources.
        """
        raw_articles = await self._fetch_from_rss(portfolio_tickers)
        filtered = self._filter_by_time(raw_articles)
        return filtered

    async def store_articles(
        self, db: AsyncSession, user_id: UUID, articles: list[RawNewsArticle]
    ) -> int:
        """Persist raw articles to the news_articles table.

        Args:
            db: Async database session.
            user_id: The user who owns these articles.
            articles: List of raw articles to store.

        Returns:
            Number of articles successfully stored.
        """
        stored_count = 0
        for article in articles:
            # Check for duplicate by title + user to avoid re-inserting
            stmt = select(NewsArticle).where(
                NewsArticle.user_id == user_id,
                NewsArticle.title == article.title,
                NewsArticle.published_at == article.published_at,
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                continue

            news_record = NewsArticle(
                user_id=user_id,
                title=article.title,
                source_name=article.source_name,
                source_url=article.source_url,
                published_at=article.published_at,
                raw_content=article.raw_content,
                is_analyzed=False,
            )
            db.add(news_record)
            stored_count += 1

        if stored_count > 0:
            await db.commit()

        return stored_count

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_from_rss(self, portfolio_tickers: list[str]) -> list[RawNewsArticle]:
        """Fetch articles from Indian financial RSS feeds concurrently."""
        all_articles: list[RawNewsArticle] = []

        async with httpx.AsyncClient(timeout=20.0) as client:
            tasks = [self._fetch_rss(client, url) for url in RSS_FEEDS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning("RSS feed %s failed: %s", RSS_FEEDS[i], str(result))
                else:
                    all_articles.extend(result)

        # Deduplicate by title
        seen_titles: set[str] = set()
        unique: list[RawNewsArticle] = []
        for article in all_articles:
            title_key = article.title.strip().lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique.append(article)

        logger.info("Fetched %d unique articles from %d RSS feeds", len(unique), len(RSS_FEEDS))
        return unique

    async def _fetch_rss(self, client: httpx.AsyncClient, url: str) -> list[RawNewsArticle]:
        """Parse a single RSS feed URL into RawNewsArticle objects."""
        telemetry = get_telemetry_service()
        start = time.time()
        try:
            response = await client.get(url)
            response.raise_for_status()
            latency = (time.time() - start) * 1000
            telemetry.record_api_call(
                service=self._get_source_name(url, ""),
                endpoint=url,
                method="GET",
                status_code=response.status_code,
                latency_ms=latency,
                success=True,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            telemetry.record_api_call(
                service=self._get_source_name(url, ""),
                endpoint=url,
                method="GET",
                status_code=None,
                latency_ms=latency,
                success=False,
                error=str(e),
            )
            raise

        articles: list[RawNewsArticle] = []
        root = ET.fromstring(response.text)

        # Determine source name from feed title
        channel = root.find("channel")
        feed_title = ""
        if channel is not None:
            title_el = channel.find("title")
            if title_el is not None and title_el.text:
                feed_title = title_el.text.strip()

        # Map known feed URLs to clean source names
        source_name = self._get_source_name(url, feed_title)

        items = root.findall(".//item")
        for item in items:
            try:
                title_el = item.find("title")
                title = ""
                if title_el is not None:
                    title = (title_el.text or "").strip()
                if not title:
                    continue

                # Parse publication date
                pubdate_el = item.find("pubDate")
                if pubdate_el is None or not pubdate_el.text:
                    continue
                published_at = parsedate_to_datetime(pubdate_el.text.strip())

                # Get description/content
                desc_el = item.find("description")
                content = ""
                if desc_el is not None and desc_el.text:
                    content = re.sub(r"<[^>]+>", "", desc_el.text).strip()

                # Get link
                link_el = item.find("link")
                source_url = link_el.text.strip() if link_el is not None and link_el.text else None

                if not content:
                    content = title

                articles.append(
                    RawNewsArticle(
                        title=title,
                        source_name=source_name,
                        source_url=source_url,
                        published_at=published_at,
                        raw_content=content,
                    )
                )
            except Exception as exc:
                logger.debug("Skipping RSS item: %s", exc)
                continue

        return articles

    def _get_source_name(self, url: str, feed_title: str) -> str:
        """Map RSS feed URL to a clean source name."""
        if "economictimes" in url:
            return "Economic Times"
        if "livemint" in url:
            return "LiveMint"
        if "moneycontrol" in url:
            return "Moneycontrol"
        return feed_title or "Unknown"

    def _filter_by_time(self, articles: list[RawNewsArticle]) -> list[RawNewsArticle]:
        """Filter articles to only those published within the last 48 hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        return [
            article
            for article in articles
            if article.published_at >= cutoff
        ]
