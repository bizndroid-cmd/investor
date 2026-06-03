from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from backend.models.domain import NewsAnalysisResponse, Portfolio, TriggeredAlert


class LLMProvider(str, Enum):
    """Supported LLM backend providers.

    The default is ``STUB``, which returns placeholder responses without
    making any external API calls. Activate a real provider by setting the
    ``LLM_PROVIDER`` environment variable.
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    GROQ = "groq"
    GEMINI = "gemini"
    STUB = "stub"  # default — returns placeholder responses


@dataclass
class LLMAnalysisRequest:
    """Input payload for an LLM analysis call."""

    prompt: str
    context: dict  # structured data passed as context (e.g., portfolio snapshot)
    max_tokens: int = 512


@dataclass
class LLMAnalysisResponse:
    """Output from an LLM analysis call."""

    content: str
    provider: LLMProvider
    model: str
    is_stub: bool = False  # True when the stub implementation is active


class ILLMService(ABC):
    """Provider-agnostic LLM service interface.

    Backed by LangChain; the active provider is selected via the
    ``LLM_PROVIDER`` environment variable (default: ``stub``).

    All methods are scaffolded from day one and return stub responses until
    a real provider is configured — no LLM calls are made in the initial
    release.
    """

    @abstractmethod
    async def analyze_portfolio(
        self,
        user_id: UUID,
        portfolio: Portfolio,
    ) -> LLMAnalysisResponse:
        """Generate a natural-language summary and insight for a user's portfolio.

        Future use case: portfolio health analysis, concentration risk commentary.
        """
        ...

    @abstractmethod
    async def answer_natural_language_query(
        self,
        user_id: UUID,
        query: str,
        portfolio: Portfolio,
    ) -> LLMAnalysisResponse:
        """Answer a free-text question about the user's portfolio.

        Future use case: "Which of my stocks has the highest volatility this month?"
        """
        ...

    @abstractmethod
    async def generate_trade_recommendation(
        self,
        user_id: UUID,
        ticker: str,
        portfolio: Portfolio,
    ) -> LLMAnalysisResponse:
        """Generate a contextual trade recommendation for a given ticker.

        Future use case: rebalancing suggestions, risk-adjusted position sizing.

        NOTE: Recommendations are informational only and not financial advice.
        """
        ...

    @abstractmethod
    async def summarize_alerts(
        self,
        user_id: UUID,
        triggered_alerts: list[TriggeredAlert],
    ) -> LLMAnalysisResponse:
        """Produce a concise natural-language digest of triggered price alerts.

        Future use case: daily alert summary email / push notification.
        """
        ...

    @abstractmethod
    async def analyze_news_article(
        self,
        article_content: str,
        portfolio_tickers: list[str],
    ) -> NewsAnalysisResponse:
        """Analyze a news article for sentiment, impact, and portfolio relevance.

        Returns a structured analysis including sentiment score, impact level,
        a concise summary (≤200 chars), and related tickers from the portfolio.
        """
        ...
