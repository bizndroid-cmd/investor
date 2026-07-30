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
BATCH_SIZE = 15

# Delay between batched LLM calls (seconds) to respect RPM limits
RATE_LIMIT_DELAY = 8.0


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

        Pipeline:
        1. Deduplicate similar articles (title similarity)
        2. Classify obvious articles with keyword rules (skip LLM)
        3. Send remaining ambiguous articles to LLM in batches
        4. Merge results

        Args:
            articles: List of raw articles to analyze.
            portfolio_tickers: User's portfolio ticker symbols.

        Returns:
            List of successfully analyzed items.
        """
        if not articles:
            return []

        # Step 1: Deduplicate
        unique_articles = self._deduplicate(articles)
        dedup_count = len(articles) - len(unique_articles)
        if dedup_count > 0:
            logger.info("Deduplication removed %d similar articles (%d remaining)", dedup_count, len(unique_articles))

        # Step 2: Keyword-based classification for obvious articles
        keyword_results, ambiguous_articles = self._classify_by_keywords(unique_articles, portfolio_tickers)
        if keyword_results:
            logger.info("Keyword classifier handled %d articles, %d need LLM", len(keyword_results), len(ambiguous_articles))

        # Check if we're in stub mode
        from backend.config import settings
        if settings.llm_provider == "stub":
            llm_results = await self._analyze_batch_simple(ambiguous_articles, portfolio_tickers)
            return keyword_results + llm_results

        # Check circuit breaker
        from backend.services.telemetry_service import get_telemetry_service
        telemetry = get_telemetry_service()
        if telemetry.is_circuit_open():
            remaining = telemetry.get_circuit_remaining_seconds()
            logger.info(
                "Circuit breaker OPEN — skipping LLM for %d articles. Retry in %.0f seconds.",
                len(ambiguous_articles), remaining,
            )
            return keyword_results + self._stub_batch_results(ambiguous_articles, portfolio_tickers)

        # Step 3: Send ambiguous articles to LLM in batches
        batches = [
            ambiguous_articles[i:i + BATCH_SIZE]
            for i in range(0, len(ambiguous_articles), BATCH_SIZE)
        ]

        llm_results: list[AnalyzedNewsItem] = []
        total_batches = len(batches)

        for batch_idx, batch in enumerate(batches):
            if telemetry.is_circuit_open():
                logger.info("Circuit breaker tripped mid-batch at %d/%d", batch_idx + 1, total_batches)
                remaining_articles = [a for b in batches[batch_idx:] for a in b]
                llm_results.extend(self._stub_batch_results(remaining_articles, portfolio_tickers))
                break

            logger.debug("Analyzing batch %d/%d (%d articles)", batch_idx + 1, total_batches, len(batch))
            batch_results = await self._analyze_article_batch(batch, portfolio_tickers)
            llm_results.extend(batch_results)

            if batch_idx < total_batches - 1:
                await asyncio.sleep(RATE_LIMIT_DELAY)

        all_results = keyword_results + llm_results
        logger.info(
            "Analysis complete: %d input, %d deduped, %d keyword-classified, %d LLM-analyzed (%d calls)",
            len(articles), dedup_count, len(keyword_results), len(llm_results), total_batches,
        )
        return all_results

    def _deduplicate(self, articles: list[RawNewsArticle]) -> list[RawNewsArticle]:
        """Remove near-duplicate articles based on title similarity.

        Uses normalized title comparison. Two articles are duplicates if
        their normalized titles share >80% of words.
        """
        seen_titles: list[set[str]] = []
        unique: list[RawNewsArticle] = []

        for article in articles:
            title_words = set(article.title.lower().split())
            # Remove very short words and numbers
            title_words = {w for w in title_words if len(w) > 2 and not w.isdigit()}

            if not title_words:
                unique.append(article)
                seen_titles.append(title_words)
                continue

            is_dup = False
            for seen in seen_titles:
                if not seen:
                    continue
                overlap = len(title_words & seen) / max(len(title_words), len(seen))
                if overlap > 0.8:
                    is_dup = True
                    break

            if not is_dup:
                unique.append(article)
                seen_titles.append(title_words)

        return unique

    def _classify_by_keywords(
        self, articles: list[RawNewsArticle], portfolio_tickers: list[str]
    ) -> tuple[list[AnalyzedNewsItem], list[RawNewsArticle]]:
        """Classify articles with strong keyword signals without LLM.

        Returns (classified_results, remaining_ambiguous_articles).
        Articles are classified only if they have strong unambiguous signals.
        """
        BULLISH_KEYWORDS = {
            "surge", "surges", "rally", "rallies", "soars", "jumps", "gains",
            "profit", "profits", "beats", "exceeds", "upgrade", "upgraded",
            "bullish", "record high", "all-time high", "outperform", "buy",
            "dividend", "bonus", "buyback", "strong results", "beat estimates",
        }
        BEARISH_KEYWORDS = {
            "crash", "crashes", "plunge", "plunges", "falls", "drops", "slumps",
            "loss", "losses", "misses", "disappoints", "downgrade", "downgraded",
            "bearish", "sell", "warning", "fraud", "scam", "default", "debt crisis",
            "cuts dividend", "profit warning", "layoffs", "shutdown",
        }
        HIGH_IMPACT_KEYWORDS = {
            "rbi", "sebi", "government", "budget", "policy", "regulation",
            "merger", "acquisition", "ipo", "fpo", "split", "delisting",
            "rate hike", "rate cut", "inflation", "gdp",
        }

        classified: list[AnalyzedNewsItem] = []
        ambiguous: list[RawNewsArticle] = []

        tickers_upper = {t.upper() for t in portfolio_tickers}

        for article in articles:
            text = f"{article.title} {article.raw_content[:300]}".lower()
            words = set(text.split())

            # Find related tickers by simple string match
            content_upper = f"{article.title} {article.raw_content}".upper()
            related_tickers = [t for t in portfolio_tickers if t.upper() in content_upper]

            bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
            bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text)
            high_impact = any(kw in text for kw in HIGH_IMPACT_KEYWORDS)

            # Only classify if signal is strong and unambiguous
            if bullish_count >= 2 and bearish_count == 0:
                sentiment = SentimentScore.BULLISH
            elif bearish_count >= 2 and bullish_count == 0:
                sentiment = SentimentScore.BEARISH
            elif bullish_count == 0 and bearish_count == 0 and not related_tickers:
                # Clearly irrelevant neutral article
                sentiment = SentimentScore.NEUTRAL
            else:
                # Ambiguous — needs LLM
                ambiguous.append(article)
                continue

            impact = ImpactLevel.HIGH if high_impact else ImpactLevel.MEDIUM if related_tickers else ImpactLevel.LOW
            relevance = 0.8 if related_tickers else 0.4

            classified.append(
                AnalyzedNewsItem(
                    id=uuid4(),
                    title=article.title,
                    source_name=article.source_name,
                    source_url=article.source_url,
                    published_at=article.published_at,
                    summary=article.title[:200],
                    sentiment_score=sentiment,
                    impact_level=impact,
                    related_tickers=related_tickers,
                    relevance_score=relevance,
                    is_stub=False,
                    analyzed_at=datetime.now(timezone.utc),
                )
            )

        return classified, ambiguous

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
