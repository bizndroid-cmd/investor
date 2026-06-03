"""LLM service implementing ILLMService.

Provider-agnostic LLM service backed by LangChain.
Defaults to stub responses when LLM_PROVIDER is "stub" (the default).
Real providers (OpenAI, Anthropic, Ollama) are lazy-imported only when needed.
"""

from __future__ import annotations

import logging
import time
from uuid import UUID

from backend.interfaces.llm_service import (
    ILLMService,
    LLMAnalysisResponse,
    LLMProvider,
)
from backend.models.domain import (
    ImpactLevel,
    NewsAnalysisResponse,
    Portfolio,
    SentimentScore,
    TriggeredAlert,
)
from backend.services.telemetry_service import get_telemetry_service

logger = logging.getLogger(__name__)


class LLMService(ILLMService):
    """Concrete implementation of ILLMService.

    When provider is STUB, all methods return placeholder responses
    with is_stub=True and never raise exceptions.

    For real providers, LangChain is used as the abstraction layer.
    Provider-specific imports are lazy to avoid import errors when
    the corresponding packages are not installed.
    """

    def __init__(self, provider: LLMProvider, model_name: str) -> None:
        self._provider = provider
        self._model_name = model_name
        self._is_stub = provider == LLMProvider.STUB
        self._llm = None  # Lazy-initialized for real providers

    def _get_llm(self):
        """Lazy-initialize the LangChain LLM instance."""
        if self._llm is not None:
            return self._llm

        if self._is_stub:
            return None

        if self._provider == LLMProvider.OPENAI:
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(model=self._model_name)
        elif self._provider == LLMProvider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic
            self._llm = ChatAnthropic(model=self._model_name)
        elif self._provider == LLMProvider.OLLAMA:
            from langchain_ollama import ChatOllama
            self._llm = ChatOllama(model=self._model_name)
        elif self._provider == LLMProvider.GROQ:
            from langchain_openai import ChatOpenAI
            from backend.config import settings
            self._llm = ChatOpenAI(
                model=self._model_name,
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )
        elif self._provider == LLMProvider.GEMINI:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from backend.config import settings
            self._llm = ChatGoogleGenerativeAI(
                model=self._model_name,
                google_api_key=settings.gemini_api_key,
            )

        return self._llm

    def _record_llm_telemetry(
        self,
        *,
        purpose: str,
        success: bool,
        latency_ms: float,
        response=None,
        error: str | None = None,
    ) -> None:
        """Record LLM call telemetry."""
        telemetry = get_telemetry_service()
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        if response and hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            prompt_tokens = getattr(usage, "input_tokens", 0) or 0
            completion_tokens = getattr(usage, "output_tokens", 0) or 0
            total_tokens = prompt_tokens + completion_tokens

        telemetry.record_llm_call(
            provider=self._provider.value,
            model=self._model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            purpose=purpose,
            success=success,
            error=error,
        )

    async def analyze_portfolio(
        self,
        user_id: UUID,
        portfolio: Portfolio,
    ) -> LLMAnalysisResponse:
        """Generate a natural-language summary and insight for a user's portfolio."""
        if self._is_stub:
            return LLMAnalysisResponse(
                content="Portfolio analysis is not yet available. Configure an LLM provider to enable this feature.",
                provider=self._provider,
                model=self._model_name,
                is_stub=True,
            )

        llm = self._get_llm()
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content="You are a financial portfolio analyst. Provide concise, actionable insights."),
                HumanMessage(content=f"Analyze this portfolio for user {user_id}:\n"
                            f"Total value: {portfolio.total_value}\n"
                            f"Total gain/loss: {portfolio.total_gain_loss} ({portfolio.total_gain_loss_percent}%)\n"
                            f"Holdings: {len(portfolio.holdings)} positions"),
            ]
            start = time.time()
            response = await llm.ainvoke(messages)
            latency = (time.time() - start) * 1000
            self._record_llm_telemetry(purpose="portfolio_analysis", success=True, latency_ms=latency, response=response)
            return LLMAnalysisResponse(
                content=response.content,
                provider=self._provider,
                model=self._model_name,
                is_stub=False,
            )
        except Exception as e:
            logger.error("LLM analyze_portfolio failed: %s", str(e))
            self._record_llm_telemetry(purpose="portfolio_analysis", success=False, latency_ms=0, error=str(e))
            return LLMAnalysisResponse(
                content="Portfolio analysis temporarily unavailable.",
                provider=self._provider,
                model=self._model_name,
                is_stub=True,
            )

    async def answer_natural_language_query(
        self,
        user_id: UUID,
        query: str,
        portfolio: Portfolio,
    ) -> LLMAnalysisResponse:
        """Answer a free-text question about the user's portfolio."""
        if self._is_stub:
            return LLMAnalysisResponse(
                content="Natural language queries are not yet available. Configure an LLM provider to enable this feature.",
                provider=self._provider,
                model=self._model_name,
                is_stub=True,
            )

        llm = self._get_llm()
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content="You are a financial assistant. Answer questions about the user's portfolio concisely."),
                HumanMessage(content=f"Portfolio context: {len(portfolio.holdings)} holdings, "
                            f"total value: {portfolio.total_value}\n\nQuestion: {query}"),
            ]
            start = time.time()
            response = await llm.ainvoke(messages)
            latency = (time.time() - start) * 1000
            self._record_llm_telemetry(purpose="nl_query", success=True, latency_ms=latency, response=response)
            return LLMAnalysisResponse(
                content=response.content,
                provider=self._provider,
                model=self._model_name,
                is_stub=False,
            )
        except Exception as e:
            logger.error("LLM answer_query failed: %s", str(e))
            self._record_llm_telemetry(purpose="nl_query", success=False, latency_ms=0, error=str(e))
            return LLMAnalysisResponse(
                content="Query processing temporarily unavailable.",
                provider=self._provider,
                model=self._model_name,
                is_stub=True,
            )

    async def generate_trade_recommendation(
        self,
        user_id: UUID,
        ticker: str,
        portfolio: Portfolio,
    ) -> LLMAnalysisResponse:
        """Generate a contextual trade recommendation for a given ticker."""
        if self._is_stub:
            return LLMAnalysisResponse(
                content=f"Trade recommendations for {ticker} are not yet available. Configure an LLM provider to enable this feature.",
                provider=self._provider,
                model=self._model_name,
                is_stub=True,
            )

        llm = self._get_llm()
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content="You are a financial advisor. Provide informational trade recommendations. "
                             "NOTE: This is not financial advice."),
                HumanMessage(content=f"Generate a trade recommendation for {ticker}.\n"
                            f"Portfolio context: {len(portfolio.holdings)} holdings, "
                            f"total value: {portfolio.total_value}"),
            ]
            start = time.time()
            response = await llm.ainvoke(messages)
            latency = (time.time() - start) * 1000
            self._record_llm_telemetry(purpose="trade_recommendation", success=True, latency_ms=latency, response=response)
            return LLMAnalysisResponse(
                content=response.content,
                provider=self._provider,
                model=self._model_name,
                is_stub=False,
            )
        except Exception as e:
            logger.error("LLM trade_recommendation failed: %s", str(e))
            self._record_llm_telemetry(purpose="trade_recommendation", success=False, latency_ms=0, error=str(e))
            return LLMAnalysisResponse(
                content=f"Trade recommendation for {ticker} temporarily unavailable.",
                provider=self._provider,
                model=self._model_name,
                is_stub=True,
            )

    async def summarize_alerts(
        self,
        user_id: UUID,
        triggered_alerts: list[TriggeredAlert],
    ) -> LLMAnalysisResponse:
        """Produce a concise natural-language digest of triggered price alerts."""
        if self._is_stub:
            alert_count = len(triggered_alerts)
            return LLMAnalysisResponse(
                content=f"Alert summarization is not yet available. You have {alert_count} triggered alert(s). Configure an LLM provider to enable this feature.",
                provider=self._provider,
                model=self._model_name,
                is_stub=True,
            )

        llm = self._get_llm()
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            alerts_text = "\n".join(
                f"- {a.ticker}: price {a.triggered_price} crossed {a.condition} target {a.target_price}"
                for a in triggered_alerts
            )
            messages = [
                SystemMessage(content="You are a financial notification assistant. Summarize triggered alerts concisely."),
                HumanMessage(content=f"Summarize these triggered alerts:\n{alerts_text}"),
            ]
            start = time.time()
            response = await llm.ainvoke(messages)
            latency = (time.time() - start) * 1000
            self._record_llm_telemetry(purpose="alert_summary", success=True, latency_ms=latency, response=response)
            return LLMAnalysisResponse(
                content=response.content,
                provider=self._provider,
                model=self._model_name,
                is_stub=False,
            )
        except Exception as e:
            logger.error("LLM summarize_alerts failed: %s", str(e))
            self._record_llm_telemetry(purpose="alert_summary", success=False, latency_ms=0, error=str(e))
            return LLMAnalysisResponse(
                content="Alert summarization temporarily unavailable.",
                provider=self._provider,
                model=self._model_name,
                is_stub=True,
            )

    async def analyze_news_article(
        self,
        article_content: str,
        portfolio_tickers: list[str],
    ) -> NewsAnalysisResponse:
        """Analyze a news article for sentiment, impact, and portfolio relevance."""
        if self._is_stub:
            # Deterministic stub: neutral sentiment, medium impact,
            # summary = first 200 chars, related_tickers = portfolio tickers found in content.
            summary = article_content[:200]
            content_upper = article_content.upper()
            related_tickers = [
                t for t in portfolio_tickers if t.upper() in content_upper
            ]
            return NewsAnalysisResponse(
                summary=summary,
                sentiment_score=SentimentScore.NEUTRAL,
                impact_level=ImpactLevel.MEDIUM,
                related_tickers=related_tickers,
                is_stub=True,
            )

        llm = self._get_llm()
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            tickers_str = ", ".join(portfolio_tickers) if portfolio_tickers else "none"
            messages = [
                SystemMessage(
                    content=(
                        "You are a financial news analyst specializing in Indian equity markets.\n\n"
                        "Here is the user's watchlist: " + tickers_str + "\n\n"
                        "For the provided news article, decide if it's relevant to the watchlist. "
                        "If NOT relevant, return: {\"relevant\": false}\n\n"
                        "If relevant, return a JSON object with exactly these fields:\n"
                        '- "relevant": true\n'
                        '- "summary": one-liner summary of the article (max 200 characters)\n'
                        '- "related_tickers": which ticker(s) from the watchlist it impacts\n'
                        '- "sentiment_score": one of "bullish", "bearish", or "neutral"\n'
                        '- "impact_level": one of "high", "medium", or "low"\n\n'
                        "Return ONLY valid JSON, no additional text."
                    )
                ),
                HumanMessage(
                    content=(
                        f"News article:\n{article_content}"
                    )
                ),
            ]
            start = time.time()
            response = await llm.ainvoke(messages)
            latency = (time.time() - start) * 1000
            self._record_llm_telemetry(purpose="news_analysis", success=True, latency_ms=latency, response=response)

            import json
            # Handle potential markdown code fences in response
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                content = content.rsplit("```", 1)[0].strip()
            result = json.loads(content)

            # If LLM says article is not relevant, return None to filter it out
            if not result.get("relevant", True):
                return NewsAnalysisResponse(
                    summary="",
                    sentiment_score=SentimentScore.NEUTRAL,
                    impact_level=ImpactLevel.LOW,
                    related_tickers=[],
                    is_stub=False,
                )

            # Validate and normalize the LLM response
            sentiment = result.get("sentiment_score", "neutral").lower()
            if sentiment not in ("bullish", "bearish", "neutral"):
                sentiment = "neutral"

            impact = result.get("impact_level", "medium").lower()
            if impact not in ("high", "medium", "low"):
                impact = "medium"

            summary = result.get("summary", article_content[:200])[:200]

            related = result.get("related_tickers", [])
            # Only keep tickers that are in the user's portfolio
            valid_tickers_upper = {t.upper() for t in portfolio_tickers}
            related_tickers = [
                t for t in related if t.upper() in valid_tickers_upper
            ]

            return NewsAnalysisResponse(
                summary=summary,
                sentiment_score=SentimentScore(sentiment),
                impact_level=ImpactLevel(impact),
                related_tickers=related_tickers,
                is_stub=False,
            )
        except Exception as e:
            logger.error("LLM analyze_news_article failed: %s", str(e))
            self._record_llm_telemetry(purpose="news_analysis", success=False, latency_ms=0, error=str(e))
            raise
