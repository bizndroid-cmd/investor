"""News Analyzer service for LLM-powered article analysis.

Uses batched prompts (multiple articles per LLM call) and rate limiting
to stay within free tier API limits.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from backend.interfaces.llm_service import ILLMService
from backend.models.domain import (
    AnalyzedNewsItem,
    ImpactLevel,
    NewsAnalysisResponse,
    RawNewsArticle,
    SentimentScore,
)

logger = logging.getLogger(__name__)

# Batch size: how many articles to send per LLM call
BATCH_SIZE = 5

# Delay between batched LLM calls (seconds) to respect RPM limits
# With 10 RPM limit and batches of 5, we process 50 articles/min at max
RATE_LIMIT_DELAY = 8.0  # ~7-8 calls/min leaves headroom


class NewsAnalyzer:
    """Processes raw news articles through the LLM to extract analysis metadata.
    
    Uses batching (multiple articles per prompt) and rate limiting to stay
    within Gemini free tier limits (10-15 RPM, 250-1000 RPD).
    """

    def __init__(self, llm_service: ILLMService) -> None:
        self._llm_service = llm_service

    async def analyze_article(
        self, article: RawNewsArticle, portfolio_tickers: list[str]
    ) -> AnalyzedNewsItem | None:
        """Analyze a single article using the LLM service.

        Args:
            article: Raw news article to analyze.
            portfolio_tickers: User's portfolio ticker symbols.

        Returns:
            AnalyzedNewsItem with LLM-derived metadata, or None on failure.
        """
        try:
            analysis: NewsAnalysisResponse = await self._llm_service.analyze_news_article(
                article_content=article.raw_content,
                portfolio_tickers=portfolio_tickers,
            )
        except Exception as exc:
            logger.error(
                "LLM analysis failed for article '%s': %s",
                article.title,
                str(exc),
            )
            return None

        relevance_score = self._calculate_relevance(
            article, analysis, portfolio_tickers
        )

        return AnalyzedNewsItem(
            id=uuid4(),
            title=article.title,
            source_name=article.source_name,
            source_url=article.source_url,
            published_at=article.published_at,
            summary=analysis.summary,
            sentiment_score=analysis.sentiment_score,
            impact_level=analysis.impact_level,
            related_tickers=analysis.related_tickers,
            relevance_score=relevance_score,
            is_stub=analysis.is_stub,
            analyzed_at=datetime.now(timezone.utc),
        )

    async def analyze_batch(
        self, articles: list[RawNewsArticle], portfolio_tickers: list[str]
    ) -> list[AnalyzedNewsItem]:
        """Analyze a batch of articles using batched LLM calls with rate limiting.

        Groups articles into batches of BATCH_SIZE and sends one LLM prompt
        per batch. Adds a delay between batches to respect API rate limits.
        Checks circuit breaker before attempting any calls.

        Args:
            articles: List of raw articles to analyze.
            portfolio_tickers: User's portfolio ticker symbols.

        Returns:
            List of successfully analyzed items.
        """
        if not articles:
            return []

        # Check if we're in stub mode — if so, use fast single-article analysis
        from backend.config import settings
        if settings.llm_provider == "stub":
            return await self._analyze_batch_simple(articles, portfolio_tickers)

        # Check circuit breaker — if open, skip LLM entirely and return stub results
        from backend.services.telemetry_service import get_telemetry_service
        telemetry = get_telemetry_service()
        if telemetry.is_circuit_open():
            remaining = telemetry.get_circuit_remaining_seconds()
            logger.info(
                "Circuit breaker OPEN — skipping LLM analysis for %d articles. "
                "Will retry in %.0f seconds.",
                len(articles), remaining,
            )
            return self._stub_batch_results(articles, portfolio_tickers)

        # Batch articles into groups
        batches = [
            articles[i:i + BATCH_SIZE]
            for i in range(0, len(articles), BATCH_SIZE)
        ]

        results: list[AnalyzedNewsItem] = []
        total_batches = len(batches)

        for batch_idx, batch in enumerate(batches):
            # Re-check circuit breaker before each batch
            if telemetry.is_circuit_open():
                logger.info(
                    "Circuit breaker tripped mid-batch — stopping at batch %d/%d",
                    batch_idx + 1, total_batches,
                )
                # Return stub results for remaining articles
                remaining_articles = [a for b in batches[batch_idx:] for a in b]
                results.extend(self._stub_batch_results(remaining_articles, portfolio_tickers))
                break

            logger.debug(
                "Analyzing batch %d/%d (%d articles)",
                batch_idx + 1, total_batches, len(batch),
            )

            batch_results = await self._analyze_article_batch(batch, portfolio_tickers)
            results.extend(batch_results)

            # Rate limit: wait between batches (skip after last batch)
            if batch_idx < total_batches - 1:
                await asyncio.sleep(RATE_LIMIT_DELAY)

        logger.info(
            "Batch analysis complete: %d articles → %d results (%d LLM calls)",
            len(articles), len(results), total_batches,
        )
        return results

    async def _analyze_batch_simple(
        self, articles: list[RawNewsArticle], portfolio_tickers: list[str]
    ) -> list[AnalyzedNewsItem]:
        """Simple one-by-one analysis (used in stub mode where there's no rate limit)."""
        results: list[AnalyzedNewsItem] = []
        for article in articles:
            item = await self.analyze_article(article, portfolio_tickers)
            if item is not None:
                results.append(item)
        return results

    async def _analyze_article_batch(
        self, articles: list[RawNewsArticle], portfolio_tickers: list[str]
    ) -> list[AnalyzedNewsItem]:
        """Send multiple articles in one LLM prompt and parse batch response.

        Falls back to individual analysis if batch parsing fails.
        """
        import time
        from backend.services.telemetry_service import get_telemetry_service
        from backend.config import settings

        tickers_str = ", ".join(portfolio_tickers) if portfolio_tickers else "none"

        # Build batch prompt
        articles_section = ""
        for i, article in enumerate(articles, 1):
            # Truncate content to keep prompt manageable
            content = article.raw_content[:500] if article.raw_content else article.title
            articles_section += f"\n---ARTICLE {i}---\nTitle: {article.title}\nContent: {content}\n"

        system_prompt = (
            "You are a financial news analyst specializing in Indian equity markets.\n\n"
            f"User's watchlist: {tickers_str}\n\n"
            f"You will receive {len(articles)} news articles. For EACH article, decide if it's relevant to the watchlist.\n\n"
            "Return a JSON array with one object per article, in order. Each object must have:\n"
            '- "relevant": true/false\n'
            '- "summary": one-liner summary (max 150 chars, empty string if not relevant)\n'
            '- "related_tickers": array of affected tickers from watchlist (empty if not relevant)\n'
            '- "sentiment_score": "bullish", "bearish", or "neutral"\n'
            '- "impact_level": "high", "medium", or "low"\n\n'
            "Return ONLY a valid JSON array, no other text."
        )

        try:
            llm = self._llm_service._get_llm()
            if llm is None:
                raise ValueError("LLM not initialized")

            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=articles_section),
            ]

            start = time.time()
            response = await llm.ainvoke(messages)
            latency = (time.time() - start) * 1000

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
                purpose=f"news_analysis_batch_{len(articles)}",
                success=True,
            )

            # Parse response
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                content = content.rsplit("```", 1)[0].strip()

            parsed = json.loads(content)
            if not isinstance(parsed, list):
                raise ValueError("Expected JSON array")

            # Map results back to articles
            results: list[AnalyzedNewsItem] = []
            for i, article in enumerate(articles):
                if i >= len(parsed):
                    break

                item_data = parsed[i]
                if not isinstance(item_data, dict):
                    continue

                # Normalize fields
                sentiment = item_data.get("sentiment_score", "neutral").lower()
                if sentiment not in ("bullish", "bearish", "neutral"):
                    sentiment = "neutral"

                impact = item_data.get("impact_level", "medium").lower()
                if impact not in ("high", "medium", "low"):
                    impact = "medium"

                summary = item_data.get("summary", "")[:200] or article.title[:200]

                related = item_data.get("related_tickers", [])
                valid_tickers_upper = {t.upper() for t in portfolio_tickers}
                related_tickers = [
                    t for t in related if t.upper() in valid_tickers_upper
                ]

                relevance_score = 0.5
                if related_tickers:
                    relevance_score = 0.8
                if item_data.get("relevant", False) and not related_tickers:
                    relevance_score = 0.6

                results.append(
                    AnalyzedNewsItem(
                        id=uuid4(),
                        title=article.title,
                        source_name=article.source_name,
                        source_url=article.source_url,
                        published_at=article.published_at,
                        summary=summary,
                        sentiment_score=SentimentScore(sentiment),
                        impact_level=ImpactLevel(impact),
                        related_tickers=related_tickers,
                        relevance_score=relevance_score,
                        is_stub=False,
                        analyzed_at=datetime.now(timezone.utc),
                    )
                )

            return results

        except Exception as exc:
            logger.error("Batch LLM analysis failed: %s", str(exc))
            # Record failure telemetry
            try:
                telemetry = get_telemetry_service()
                telemetry.record_llm_call(
                    provider=settings.llm_provider,
                    model=getattr(settings, f"{settings.llm_provider}_model", "unknown"),
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    latency_ms=0,
                    purpose=f"news_analysis_batch_{len(articles)}",
                    success=False,
                    error=str(exc),
                )
            except Exception:
                pass

            # Fallback: return articles with stub analysis
            results = []
            for article in articles:
                content_upper = f"{article.title} {article.raw_content}".upper()
                related_tickers = [
                    t for t in portfolio_tickers if t.upper() in content_upper
                ]
                results.append(
                    AnalyzedNewsItem(
                        id=uuid4(),
                        title=article.title,
                        source_name=article.source_name,
                        source_url=article.source_url,
                        published_at=article.published_at,
                        summary=article.title[:200],
                        sentiment_score=SentimentScore.NEUTRAL,
                        impact_level=ImpactLevel.MEDIUM,
                        related_tickers=related_tickers,
                        relevance_score=0.5,
                        is_stub=True,
                        analyzed_at=datetime.now(timezone.utc),
                    )
                )
            return results

    def _calculate_relevance(
        self,
        article: RawNewsArticle,
        analysis: NewsAnalysisResponse,
        portfolio_tickers: list[str],
    ) -> float:
        """Calculate a relevance score for the article."""
        base_score = 0.5
        content_upper = f"{article.title} {article.raw_content}".upper()

        mentioned_tickers = [
            t for t in portfolio_tickers if t.upper() in content_upper
        ]

        if not mentioned_tickers:
            return base_score

        score = base_score + 0.3
        additional = min(len(mentioned_tickers) - 1, 2)
        score += additional * 0.1

        return min(score, 1.0)

    @staticmethod
    def _stub_batch_results(
        articles: list[RawNewsArticle], portfolio_tickers: list[str]
    ) -> list[AnalyzedNewsItem]:
        """Return stub/fallback analysis results when LLM is unavailable."""
        results = []
        for article in articles:
            content_upper = f"{article.title} {article.raw_content}".upper()
            related_tickers = [
                t for t in portfolio_tickers if t.upper() in content_upper
            ]
            results.append(
                AnalyzedNewsItem(
                    id=uuid4(),
                    title=article.title,
                    source_name=article.source_name,
                    source_url=article.source_url,
                    published_at=article.published_at,
                    summary=article.title[:200],
                    sentiment_score=SentimentScore.NEUTRAL,
                    impact_level=ImpactLevel.MEDIUM,
                    related_tickers=related_tickers,
                    relevance_score=0.5 + (0.3 if related_tickers else 0.0),
                    is_stub=True,
                    analyzed_at=datetime.now(timezone.utc),
                )
            )
        return results
