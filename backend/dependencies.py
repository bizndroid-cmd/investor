"""FastAPI dependency injection factory functions.

Provides factory functions for all services, wiring concrete implementations
into FastAPI's DI graph using Depends.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.connectors.fidelity import FidelityConnector
from backend.connectors.groww import GrowwConnector
from backend.connectors.robinhood import RobinhoodConnector
from backend.connectors.zerodha import ZerodhaConnector
from backend.interfaces.broker_connector import IBrokerConnector
from backend.interfaces.llm_service import ILLMService, LLMProvider
from backend.models.domain import BrokerId
from backend.services.aggregator_service import AggregatorService
from backend.services.alert_service import AlertService
from backend.services.auth_service import AuthService
from backend.services.llm_service import LLMService
from backend.services.market_data_service import MarketDataService
from backend.services.news_aggregator import NewsAggregator
from backend.services.news_analyzer import NewsAnalyzer
from backend.services.news_service import NewsService
from backend.services.order_service import OrderService
from backend.services.websocket_manager import WebSocketManager

# ---------------------------------------------------------------------------
# Singleton instances (initialized during app lifespan)
# ---------------------------------------------------------------------------

_redis_pool: aioredis.Redis | None = None
_ws_manager: WebSocketManager | None = None

# Broker connectors registry
_CONNECTORS: dict[BrokerId, IBrokerConnector] = {
    "groww": GrowwConnector(),
    "zerodha": ZerodhaConnector(),
    "fidelity": FidelityConnector(),
    "robinhood": RobinhoodConnector(),
}


def set_redis_pool(pool: aioredis.Redis) -> None:
    """Set the global Redis pool (called during app startup)."""
    global _redis_pool
    _redis_pool = pool


def set_ws_manager(manager: WebSocketManager) -> None:
    """Set the global WebSocket manager (called during app startup)."""
    global _ws_manager
    _ws_manager = manager


def get_ws_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    if _ws_manager is None:
        raise RuntimeError("WebSocketManager not initialized")
    return _ws_manager


# ---------------------------------------------------------------------------
# Database dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session."""
    from backend.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Redis dependency
# ---------------------------------------------------------------------------


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Provide a Redis client from the connection pool."""
    if _redis_pool is not None:
        yield _redis_pool
    else:
        # Fallback: create a new connection (for testing or when pool not initialized)
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()


# ---------------------------------------------------------------------------
# Service dependencies
# ---------------------------------------------------------------------------


def get_auth_service(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> AuthService:
    """Provide an AuthService instance."""
    return AuthService(db=db, redis=redis)


def get_market_data_service(
    redis: aioredis.Redis = Depends(get_redis),
) -> MarketDataService:
    """Provide a MarketDataService instance."""
    return MarketDataService(redis=redis, finnhub_api_key=settings.finnhub_api_key)


def get_aggregator_service(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> AggregatorService:
    """Provide an AggregatorService instance."""
    return AggregatorService(
        db=db,
        redis=redis,
        connectors=_CONNECTORS,
        market_data_service=market_data_service,
    )


def get_alert_service(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> AlertService:
    """Provide an AlertService instance."""
    ws_manager = get_ws_manager()
    return AlertService(db=db, redis=redis, ws_manager=ws_manager)


def get_order_service(
    db: AsyncSession = Depends(get_db),
) -> OrderService:
    """Provide an OrderService instance."""
    ws_manager = get_ws_manager()
    return OrderService(db=db, connectors=_CONNECTORS, ws_manager=ws_manager)


# ---------------------------------------------------------------------------
# LLM Service factory
# ---------------------------------------------------------------------------


def create_llm_service() -> ILLMService:
    """Create an LLM service based on the configured provider.

    Provider selection is based on the LLM_PROVIDER setting.
    Real provider packages are only imported when actually needed.
    """
    provider = LLMProvider(settings.llm_provider)

    match provider:
        case LLMProvider.OPENAI:
            model_name = settings.openai_model
        case LLMProvider.ANTHROPIC:
            model_name = settings.anthropic_model
        case LLMProvider.OLLAMA:
            model_name = settings.ollama_model
        case LLMProvider.GROQ:
            model_name = settings.groq_model
        case LLMProvider.GEMINI:
            model_name = settings.gemini_model
        case _:
            model_name = "stub"

    return LLMService(provider=provider, model_name=model_name)


# ---------------------------------------------------------------------------
# News Service factory
# ---------------------------------------------------------------------------


def get_news_service(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> NewsService:
    """Provide a NewsService instance wired with aggregator, analyzer, and LLM."""
    llm_service = create_llm_service()
    aggregator = NewsAggregator()
    analyzer = NewsAnalyzer(llm_service=llm_service)
    return NewsService(db=db, redis=redis, aggregator=aggregator, analyzer=analyzer)
