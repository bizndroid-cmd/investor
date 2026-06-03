"""News Service orchestrating aggregation, analysis, and feed retrieval."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.interfaces.news_service import INewsService
from backend.models.domain import (
    AnalyzedNewsItem,
    PaginatedNewsResponse,
    RawNewsArticle,
    RefreshStatus,
)
from backend.models.orm import NewsArticle
from backend.services.news_aggregator import NewsAggregator
from backend.services.news_analyzer import NewsAnalyzer

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutes


class NewsService(INewsService):
    """Orchestrates news aggregation, analysis, caching, and feed delivery."""

    def __init__(
        self,
        db: AsyncSession,
        redis: aioredis.Redis,
        aggregator: NewsAggregator,
        analyzer: NewsAnalyzer,
    ) -> None:
        self._db = db
        self._redis = redis
        self._aggregator = aggregator
        self._analyzer = analyzer

    async def get_news_feed(
        self,
        user_id: UUID,
        sentiment: str | None = None,
        impact_level: str | None = None,
        ticker: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedNewsResponse:
        """Query news_articles table with filters, pagination, and caching."""
        # Try Redis cache first
        cache_key = self._build_cache_key(
            user_id, sentiment, impact_level, ticker, page, page_size
        )
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Build query with filters
        stmt = select(NewsArticle).where(
            NewsArticle.user_id == user_id,
        )

        if sentiment:
            stmt = stmt.where(NewsArticle.sentiment_score == sentiment)
        if impact_level:
            stmt = stmt.where(NewsArticle.impact_level == impact_level)
        if ticker:
            stmt = stmt.where(NewsArticle.related_tickers.any(ticker))

        # Count total matching records
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self._db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Sort by relevance_score DESC, then published_at DESC
        stmt = stmt.order_by(
            desc(NewsArticle.relevance_score),
            desc(NewsArticle.published_at),
        )

        # Paginate
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self._db.execute(stmt)
        rows = result.scalars().all()

        items = [self._orm_to_domain(row) for row in rows]

        response = PaginatedNewsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(offset + page_size) < total,
        )

        # Cache the response
        await self._set_cached(cache_key, response)

        return response

    async def trigger_refresh(self, user_id: UUID) -> RefreshStatus:
        """Fetch news articles and store them, then kick off background analysis.
        
        Returns immediately after fetching/storing. Analysis happens async.
        """
        try:
            # Get user's portfolio tickers from existing holdings
            portfolio_tickers = await self._get_user_tickers(user_id)

            # Fetch articles via aggregator (fast — just HTTP to RSS feeds)
            raw_articles = await self._aggregator.fetch_articles(portfolio_tickers)
            articles_fetched = len(raw_articles)

            # Store raw articles (fast — DB inserts)
            if raw_articles:
                await self._aggregator.store_articles(self._db, user_id, raw_articles)

            # Kick off analysis in the background (don't wait)
            import asyncio
            asyncio.create_task(
                self._background_analyze(user_id, raw_articles, portfolio_tickers)
            )

            # Invalidate cache
            await self._invalidate_cache(user_id)

            now = datetime.now(timezone.utc)
            try:
                await self._redis.set(f"news:last_refresh:{user_id}", now.isoformat())
            except Exception:
                pass

            return RefreshStatus(
                status="started",
                articles_fetched=articles_fetched,
                articles_analyzed=0,  # Analysis is happening in background
                last_refresh_at=now,
            )

        except Exception as exc:
            logger.error("News refresh failed for user %s: %s", user_id, str(exc))
            return RefreshStatus(
                status="failed",
                articles_fetched=0,
                articles_analyzed=0,
            )

    async def generate_briefing(self, user_id: UUID) -> dict:
        """Generate a daily portfolio briefing from stored news data.

        Logic:
        1. Check if a cached briefing exists for the current news data
        2. If news hasn't been updated since last briefing, serve cached version
        3. Otherwise, generate a new briefing via LLM and cache it
        """
        from backend.config import settings
        from backend.dependencies import create_llm_service
        from backend.models.orm import BriefingCache, CollectionRun
        from zoneinfo import ZoneInfo

        IST = ZoneInfo("Asia/Kolkata")
        is_stub = settings.llm_provider == "stub"
        now = datetime.now(timezone.utc)
        today_ist = datetime.now(IST).date()

        # 1. Get last live news pull time
        last_collection = await self._get_last_collection_run()
        last_fetched_at = last_collection.started_at if last_collection else None

        # 2. Get user's portfolio holdings
        holdings_data = await self._get_holdings_for_briefing(user_id)
        portfolio_tickers = [h["ticker"] for h in holdings_data]

        # 3. Get articles for today's collection_date (with fallback)
        articles = await self._get_articles_for_briefing(user_id, today_ist, portfolio_tickers)
        data_date = today_ist

        if not articles:
            for days_back in range(1, 8):
                fallback_date = today_ist - timedelta(days=days_back)
                articles = await self._get_articles_for_briefing(
                    user_id, fallback_date, portfolio_tickers
                )
                if articles:
                    data_date = fallback_date
                    break

        # 4. Check for cached briefing
        cached_briefing = await self._get_cached_briefing(user_id, data_date)

        if cached_briefing:
            # If news hasn't been updated since briefing was generated, serve cache
            news_unchanged = (
                last_fetched_at is None
                or cached_briefing.news_last_fetched_at is None
                or last_fetched_at <= cached_briefing.news_last_fetched_at
            )
            if news_unchanged:
                return {
                    "briefing": cached_briefing.briefing_text,
                    "generated_at": cached_briefing.generated_at.isoformat(),
                    "is_stub": False,
                    "is_cached": True,
                    "collection_date": data_date.isoformat(),
                    "last_news_pull": last_fetched_at.isoformat() if last_fetched_at else None,
                    "cache_message": (
                        f"Showing cached briefing from {cached_briefing.generated_at.strftime('%b %d, %I:%M %p')}. "
                        "No new news since then — regenerate will use tokens without new data."
                    ),
                    "error_reason": None,
                    "error_message": None,
                }

        # 5. If stub mode, return placeholder
        if is_stub:
            return {
                "briefing": self._stub_briefing(holdings_data, articles),
                "generated_at": now.isoformat(),
                "is_stub": True,
                "is_cached": False,
                "collection_date": data_date.isoformat(),
                "last_news_pull": last_fetched_at.isoformat() if last_fetched_at else None,
                "cache_message": None,
                "error_reason": "disabled",
                "error_message": "LLM provider is set to stub mode. Configure a real provider (gemini, groq, openai) in .env to enable AI briefings.",
            }

        # 6. If no articles at all
        if not articles:
            return {
                "briefing": self._stub_briefing(holdings_data, []),
                "generated_at": now.isoformat(),
                "is_stub": True,
                "is_cached": False,
                "collection_date": data_date.isoformat(),
                "last_news_pull": last_fetched_at.isoformat() if last_fetched_at else None,
                "cache_message": None,
                "error_reason": "no_data",
                "error_message": "No news data available. Pull fresh news first.",
            }

        # 7. Check circuit breaker before calling LLM
        from backend.services.telemetry_service import get_telemetry_service
        telemetry = get_telemetry_service()
        if telemetry.is_circuit_open():
            remaining = telemetry.get_circuit_remaining_seconds()
            # If we have a cached briefing (even if stale), serve it
            if cached_briefing:
                return {
                    "briefing": cached_briefing.briefing_text,
                    "generated_at": cached_briefing.generated_at.isoformat(),
                    "is_stub": False,
                    "is_cached": True,
                    "collection_date": data_date.isoformat(),
                    "last_news_pull": last_fetched_at.isoformat() if last_fetched_at else None,
                    "cache_message": f"Serving previous briefing. Rate limit cooldown active ({int(remaining)}s).",
                    "error_reason": "rate_limited",
                    "error_message": None,
                }
            return {
                "briefing": self._stub_briefing(holdings_data, articles),
                "generated_at": now.isoformat(),
                "is_stub": True,
                "is_cached": False,
                "collection_date": data_date.isoformat(),
                "last_news_pull": last_fetched_at.isoformat() if last_fetched_at else None,
                "cache_message": None,
                "error_reason": "rate_limited",
                "error_message": f"AI briefing paused — cooldown active ({int(remaining)}s remaining).",
            }

        # 8. Generate new briefing via LLM
        prompt = self._build_briefing_prompt(holdings_data, articles)

        try:
            llm_service = create_llm_service()
            llm = llm_service._get_llm()
            if llm is None:
                raise ValueError("LLM not configured")

            from langchain_core.messages import HumanMessage, SystemMessage
            import time as _time

            messages = [
                SystemMessage(content="You are a financial analyst creating daily portfolio briefings for Indian equity investors. Be concise and actionable."),
                HumanMessage(content=prompt),
            ]
            start = _time.time()
            response = await llm.ainvoke(messages)
            latency = (_time.time() - start) * 1000

            # Record telemetry
            telemetry = get_telemetry_service()
            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = getattr(response.usage_metadata, "input_tokens", 0) or 0
                completion_tokens = getattr(response.usage_metadata, "output_tokens", 0) or 0
            telemetry.record_llm_call(
                provider=settings.llm_provider,
                model=getattr(settings, f"{settings.llm_provider}_model", "unknown"),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=latency,
                purpose="portfolio_briefing",
                success=True,
            )

            briefing_text = response.content

            # 9. Cache the generated briefing
            await self._store_briefing_cache(
                user_id=user_id,
                collection_date=data_date,
                briefing_text=briefing_text,
                provider=settings.llm_provider,
                model=getattr(settings, f"{settings.llm_provider}_model", "unknown"),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                articles_used=len(articles),
                news_last_fetched_at=last_fetched_at,
            )

        except Exception as exc:
            logger.error("Briefing LLM call failed: %s", str(exc))

            telemetry = get_telemetry_service()
            error_str = str(exc)
            telemetry.record_llm_call(
                provider=settings.llm_provider,
                model=getattr(settings, f"{settings.llm_provider}_model", "unknown"),
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=0,
                purpose="portfolio_briefing",
                success=False,
                error=error_str,
            )

            error_lower = error_str.lower()
            if "429" in error_str or "rate" in error_lower or "quota" in error_lower or "resource_exhausted" in error_lower:
                error_reason = "rate_limited"
                error_message = "AI rate limit hit. Please try again later."
            else:
                error_reason = "error"
                error_message = f"AI briefing generation failed: {error_str[:150]}"

            # Serve cached briefing if available
            if cached_briefing:
                return {
                    "briefing": cached_briefing.briefing_text,
                    "generated_at": cached_briefing.generated_at.isoformat(),
                    "is_stub": False,
                    "is_cached": True,
                    "collection_date": data_date.isoformat(),
                    "last_news_pull": last_fetched_at.isoformat() if last_fetched_at else None,
                    "cache_message": f"Showing previous briefing. Error: {error_message}",
                    "error_reason": error_reason,
                    "error_message": error_message,
                }

            return {
                "briefing": self._stub_briefing(holdings_data, articles),
                "generated_at": now.isoformat(),
                "is_stub": True,
                "is_cached": False,
                "collection_date": data_date.isoformat(),
                "last_news_pull": last_fetched_at.isoformat() if last_fetched_at else None,
                "cache_message": None,
                "error_reason": error_reason,
                "error_message": error_message,
            }

        return {
            "briefing": briefing_text,
            "generated_at": now.isoformat(),
            "is_stub": False,
            "is_cached": False,
            "collection_date": data_date.isoformat(),
            "last_news_pull": last_fetched_at.isoformat() if last_fetched_at else None,
            "cache_message": None,
            "error_reason": None,
            "error_message": None,
        }

    async def _get_articles_for_briefing(
        self, user_id: UUID, collection_date, portfolio_tickers: list[str]
    ) -> list:
        """Get analyzed articles for a specific collection_date, filtered by tickers."""
        from sqlalchemy import or_, any_

        stmt = (
            select(NewsArticle)
            .where(
                NewsArticle.user_id == user_id,
                NewsArticle.collection_date == collection_date,
            )
            .order_by(desc(NewsArticle.relevance_score), desc(NewsArticle.published_at))
            .limit(50)
        )
        result = await self._db.execute(stmt)
        articles = result.scalars().all()

        # Filter to articles relevant to user's portfolio tickers
        if portfolio_tickers:
            relevant = []
            tickers_upper = {t.upper() for t in portfolio_tickers}
            for article in articles:
                if article.related_tickers:
                    if any(t.upper() in tickers_upper for t in article.related_tickers):
                        relevant.append(article)
                else:
                    # Include untagged articles too (they may be generally relevant)
                    relevant.append(article)
            return relevant

        return articles

    async def _get_last_collection_run(self):
        """Get the most recent successful collection run."""
        from backend.models.orm import CollectionRun

        stmt = (
            select(CollectionRun)
            .where(CollectionRun.status == "completed")
            .order_by(desc(CollectionRun.started_at))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_cached_briefing(self, user_id: UUID, collection_date):
        """Get the most recent cached briefing for a user and collection_date."""
        from backend.models.orm import BriefingCache

        stmt = (
            select(BriefingCache)
            .where(
                BriefingCache.user_id == user_id,
                BriefingCache.collection_date == collection_date,
            )
            .order_by(desc(BriefingCache.generated_at))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _store_briefing_cache(
        self,
        *,
        user_id: UUID,
        collection_date,
        briefing_text: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        articles_used: int,
        news_last_fetched_at,
    ) -> None:
        """Store a generated briefing in the cache."""
        from backend.models.orm import BriefingCache

        cache_entry = BriefingCache(
            user_id=user_id,
            collection_date=collection_date,
            briefing_text=briefing_text,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            articles_used=articles_used,
            news_last_fetched_at=news_last_fetched_at,
        )
        self._db.add(cache_entry)
        await self._db.commit()

    # ------------------------------------------------------------------
    # Pattern analysis queries (for future LLM trend prediction)
    # ------------------------------------------------------------------

    async def get_ticker_sentiment_trend(
        self, user_id: UUID, ticker: str, start_date, end_date
    ) -> list[dict]:
        """Get sentiment distribution for a ticker over a date range.

        Returns: [{collection_date, bullish, bearish, neutral}, ...]
        """
        from sqlalchemy import case, cast, Date

        stmt = (
            select(
                NewsArticle.collection_date,
                func.count(case((NewsArticle.sentiment_score == "bullish", 1))).label("bullish"),
                func.count(case((NewsArticle.sentiment_score == "bearish", 1))).label("bearish"),
                func.count(case((NewsArticle.sentiment_score == "neutral", 1))).label("neutral"),
            )
            .where(
                NewsArticle.user_id == user_id,
                NewsArticle.collection_date >= start_date,
                NewsArticle.collection_date <= end_date,
                NewsArticle.related_tickers.any(ticker),
                NewsArticle.is_analyzed == True,
            )
            .group_by(NewsArticle.collection_date)
            .order_by(NewsArticle.collection_date)
        )
        result = await self._db.execute(stmt)
        return [
            {
                "collection_date": row.collection_date.isoformat(),
                "bullish": row.bullish,
                "bearish": row.bearish,
                "neutral": row.neutral,
            }
            for row in result.all()
        ]

    async def get_ticker_news_timeline(
        self, user_id: UUID, ticker: str, days: int = 90
    ) -> list[dict]:
        """Get chronological article sequence for a ticker.

        Returns articles ordered by collection_date for time-series pattern input.
        """
        from datetime import date as date_type

        cutoff = date_type.today() - timedelta(days=days)
        stmt = (
            select(NewsArticle)
            .where(
                NewsArticle.user_id == user_id,
                NewsArticle.collection_date >= cutoff,
                NewsArticle.related_tickers.any(ticker),
                NewsArticle.is_analyzed == True,
            )
            .order_by(NewsArticle.collection_date.asc(), NewsArticle.published_at.asc())
        )
        result = await self._db.execute(stmt)
        articles = result.scalars().all()

        return [
            {
                "collection_date": a.collection_date.isoformat(),
                "title": a.title,
                "summary": a.summary or a.title[:200],
                "sentiment_score": a.sentiment_score,
                "impact_level": a.impact_level,
                "source_name": a.source_name,
            }
            for a in articles
        ]

    async def _get_holdings_for_briefing(self, user_id: UUID) -> list[dict]:
        """Get holdings data for the briefing prompt.

        Tries HoldingCache first, then Groww connector, then returns fallback tickers.
        """
        from backend.models.orm import HoldingCache

        # Try holdings cache
        stmt = select(HoldingCache).where(HoldingCache.user_id == user_id)
        result = await self._db.execute(stmt)
        cached = result.scalars().all()

        if cached:
            return [
                {
                    "ticker": h.ticker,
                    "quantity": float(h.quantity),
                    "avg_buy_price": float(h.avg_buy_price),
                    "current_price": None,  # not stored in cache
                    "gain_loss_percent": None,
                }
                for h in cached
            ]

        # Try Groww connector
        try:
            from backend.connectors.groww import GrowwConnector

            connector = GrowwConnector()
            holdings = await connector.get_holdings(user_id)
            if holdings:
                return [
                    {
                        "ticker": h.ticker,
                        "quantity": float(h.quantity),
                        "avg_buy_price": float(h.avg_buy_price),
                        "current_price": None,
                        "gain_loss_percent": None,
                    }
                    for h in holdings
                ]
        except Exception as exc:
            logger.warning("Failed to fetch holdings from Groww: %s", str(exc))

        # Fallback: return common tickers as watchlist
        fallback_tickers = ["RELIANCE", "HDFCBANK", "TCS", "ITC", "ADANIPORTS", "WIPRO"]
        return [{"ticker": t, "quantity": 0, "avg_buy_price": 0, "current_price": None, "gain_loss_percent": None} for t in fallback_tickers]

    def _build_briefing_prompt(self, holdings: list[dict], articles: list) -> str:
        """Build the LLM prompt for the daily briefing."""
        # Format holdings table
        holdings_lines = []
        for h in holdings:
            cp = h["current_price"] if h["current_price"] else "N/A"
            gl = f"{h['gain_loss_percent']:.1f}%" if h["gain_loss_percent"] is not None else "N/A"
            holdings_lines.append(
                f"  {h['ticker']} | qty: {h['quantity']} | avg_price: {h['avg_buy_price']} | current_price: {cp} | gain/loss: {gl}"
            )
        holdings_table = "\n".join(holdings_lines) if holdings_lines else "  (No holdings data available)"

        # Format articles
        article_lines = []
        for i, art in enumerate(articles[:30], 1):
            content_preview = (art.raw_content or "")[:200]
            article_lines.append(f"  {i}. {art.title}\n     {content_preview}")
        articles_text = "\n".join(article_lines) if article_lines else "  (No recent news articles)"

        prompt = f"""Here is the user's watchlist/portfolio:
{holdings_table}

Here are the latest news articles:
{articles_text}

Create a short daily briefing. For each article, decide if it's relevant to the watchlist. Only include relevant ones. For each relevant article, give:
- One liner summary
- Which ticker it impacts
- Sentiment: positive, negative, or neutral
- Potential Impact: high, medium, or low

End with:
- A list of tickers with no major news today
- A one-sentence overall market mood
- 1-2 actionable suggestions based on the portfolio's current state and today's news"""

        return prompt

    @staticmethod
    def _stub_briefing(holdings: list[dict], articles: list) -> str:
        """Return a placeholder briefing when LLM is not available."""
        tickers = [h["ticker"] for h in holdings] if holdings else ["N/A"]
        article_count = len(articles) if articles else 0
        return (
            f"📊 Daily Portfolio Briefing (Stub Mode)\n\n"
            f"**Portfolio:** {', '.join(tickers)}\n"
            f"**Articles Reviewed:** {article_count}\n\n"
            f"**Relevant News:**\n"
            f"- No LLM analysis available in stub mode.\n\n"
            f"**Tickers with no news:** {', '.join(tickers)}\n\n"
            f"**Market Mood:** Unable to determine (stub mode)\n\n"
            f"**Suggestions:**\n"
            f"- Configure a real LLM provider (e.g., Groq) for personalized briefings.\n"
            f"- Keep monitoring your portfolio for price movements.\n\n"
            f"*Powered by AI — not financial advice*"
        )

    async def _background_analyze(
        self, user_id: UUID, raw_articles: list[RawNewsArticle], portfolio_tickers: list[str]
    ) -> None:
        """Run article analysis in the background after refresh returns."""
        try:
            analyzed_items = await self._analyzer.analyze_batch(
                raw_articles, portfolio_tickers
            )

            # Need a fresh DB session for the background task
            from backend.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                for item in analyzed_items:
                    from backend.models.orm import NewsArticle as NewsArticleORM
                    stmt = select(NewsArticleORM).where(
                        NewsArticleORM.user_id == user_id,
                        NewsArticleORM.title == item.title,
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

            # Invalidate cache after analysis completes
            await self._invalidate_cache(user_id)
            logger.info(
                "Background analysis complete for user %s: %d articles analyzed",
                user_id, len(analyzed_items),
            )
        except Exception as exc:
            logger.error("Background analysis failed for user %s: %s", user_id, str(exc))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_user_tickers(self, user_id: UUID) -> list[str]:
        """Get the user's portfolio tickers.
        
        Tries holdings_cache first, then falls back to fetching from
        the Groww connector if cache is empty.
        """
        from backend.models.orm import HoldingCache

        stmt = select(HoldingCache.ticker).where(HoldingCache.user_id == user_id)
        result = await self._db.execute(stmt)
        tickers = [row[0] for row in result.all()]

        if tickers:
            return tickers

        # Fallback: fetch live from Groww connector
        try:
            from backend.connectors.groww import GrowwConnector
            connector = GrowwConnector()
            holdings = await connector.get_holdings(user_id)
            if holdings:
                return [h.ticker for h in holdings]
        except Exception:
            pass

        # Final fallback: common Indian market tickers
        return ["RELIANCE", "HDFCBANK", "TCS", "ITC", "ADANIPORTS", "WIPRO", "NIFTY", "SENSEX"]

    async def _update_analyzed_articles(
        self, user_id: UUID, items: list[AnalyzedNewsItem]
    ) -> None:
        """Update existing news_articles rows with analysis results."""
        for item in items:
            # Find the article by title and user to update it
            stmt = select(NewsArticle).where(
                NewsArticle.user_id == user_id,
                NewsArticle.title == item.title,
            )
            result = await self._db.execute(stmt)
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

        await self._db.commit()

    def _build_cache_key(
        self,
        user_id: UUID,
        sentiment: str | None,
        impact_level: str | None,
        ticker: str | None,
        page: int,
        page_size: int,
    ) -> str:
        """Build a Redis cache key for a paginated news feed query."""
        # Include filters in key so different filters get different cache entries
        parts = [f"news:feed:{user_id}:page:{page}"]
        if sentiment:
            parts.append(f"s:{sentiment}")
        if impact_level:
            parts.append(f"i:{impact_level}")
        if ticker:
            parts.append(f"t:{ticker}")
        parts.append(f"ps:{page_size}")
        return ":".join(parts)

    async def _get_cached(self, cache_key: str) -> PaginatedNewsResponse | None:
        """Try to get a cached response from Redis."""
        try:
            data = await self._redis.get(cache_key)
            if data:
                return PaginatedNewsResponse.model_validate_json(data)
        except Exception:
            # Redis unavailable — fall back to DB
            pass
        return None

    async def _set_cached(self, cache_key: str, response: PaginatedNewsResponse) -> None:
        """Cache a paginated response in Redis."""
        try:
            await self._redis.setex(
                cache_key,
                CACHE_TTL,
                response.model_dump_json(),
            )
        except Exception:
            # Redis unavailable — non-critical
            pass

    async def _invalidate_cache(self, user_id: UUID) -> None:
        """Invalidate all cached news feed pages for a user."""
        try:
            pattern = f"news:feed:{user_id}:*"
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            # Redis unavailable — non-critical
            pass

    @staticmethod
    def _orm_to_domain(row: NewsArticle) -> AnalyzedNewsItem:
        """Convert an ORM NewsArticle to a domain AnalyzedNewsItem."""
        from backend.models.domain import ImpactLevel, SentimentScore

        # Handle unanalyzed articles (sentiment/impact may be None)
        sentiment = SentimentScore.NEUTRAL
        if row.sentiment_score:
            try:
                sentiment = SentimentScore(row.sentiment_score)
            except ValueError:
                pass

        impact = ImpactLevel.LOW
        if row.impact_level:
            try:
                impact = ImpactLevel(row.impact_level)
            except ValueError:
                pass

        return AnalyzedNewsItem(
            id=row.id,
            title=row.title,
            source_name=row.source_name,
            source_url=row.source_url,
            published_at=row.published_at,
            summary=row.summary or row.title,
            sentiment_score=sentiment,
            impact_level=impact,
            related_tickers=row.related_tickers or [],
            relevance_score=row.relevance_score,
            is_stub=row.is_stub,
            analyzed_at=row.analyzed_at or row.created_at,
        )
