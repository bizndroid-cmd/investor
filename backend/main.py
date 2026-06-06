"""FastAPI application entry point.

Creates the FastAPI app with lifespan context manager for startup/shutdown,
includes all routers, and configures middleware.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

from backend.config import settings
from backend.database import engine
from backend.dependencies import (
    create_llm_service,
    get_alert_service,
    get_market_data_service,
    get_news_service,
    get_order_service,
    get_ws_manager,
    set_redis_pool,
    set_ws_manager,
)
from backend.routers import alerts as alerts_router
from backend.routers import auth as auth_router
from backend.routers import brokers as brokers_router
from backend.routers import market_data as market_data_router
from backend.routers import news as news_router
from backend.routers import orders as orders_router
from backend.routers import portfolio as portfolio_router
from backend.routers import predictions as predictions_router
from backend.routers import telemetry as telemetry_router
from backend.routers import ws as ws_router
from backend.services.market_data_service import MarketDataService
from backend.services.news_aggregator import NewsAggregator
from backend.services.news_analyzer import NewsAnalyzer
from backend.services.telemetry_service import get_telemetry_service, reset_telemetry_service
from backend.services.websocket_manager import WebSocketManager
from backend.tasks.news_collector import start_news_collector
from backend.tasks.price_poller import start_price_poller

logger = logging.getLogger(__name__)

# Background task reference
_poller_task: asyncio.Task | None = None
_news_collector_task: asyncio.Task | None = None
_news_scheduler = None  # NewsCollectionScheduler instance for manual triggers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    global _poller_task
    global _news_collector_task
    global _news_scheduler

    # --- Startup ---
    logger.info("Starting application...")

    # Initialize telemetry service (tracks from app start)
    reset_telemetry_service()
    telemetry = get_telemetry_service()

    # Create Redis connection pool
    redis_pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    set_redis_pool(redis_pool)

    # Create WebSocket manager
    ws_manager = WebSocketManager()
    set_ws_manager(ws_manager)

    # Set the WebSocket manager in the ws router module
    ws_router.set_ws_manager(ws_manager)

    # Create market data service for the poller
    market_data_service = MarketDataService(
        redis=redis_pool, finnhub_api_key=settings.finnhub_api_key
    )

    # Create alert service for the poller (needs a DB session)
    # The poller will use a lightweight alert service that creates its own sessions
    from backend.database import AsyncSessionLocal
    from backend.services.alert_service import AlertService

    # Start background price poller
    class _PollerAlertService:
        """Lightweight alert service wrapper for the poller that creates its own DB sessions."""

        def __init__(self, redis: aioredis.Redis, ws_manager: WebSocketManager):
            self._redis = redis
            self._ws_manager = ws_manager

        async def evaluate_alerts(self, ticker: str, current_price: float):
            async with AsyncSessionLocal() as session:
                alert_svc = AlertService(
                    db=session, redis=self._redis, ws_manager=self._ws_manager
                )
                return await alert_svc.evaluate_alerts(ticker, current_price)

    poller_alert_service = _PollerAlertService(redis_pool, ws_manager)
    _poller_task = await start_price_poller(
        market_data_service=market_data_service,
        ws_manager=ws_manager,
        alert_service=poller_alert_service,
    )

    # Start background news collector (schedule-aware, 1-2x daily)
    llm_service = create_llm_service()
    news_aggregator = NewsAggregator()
    news_analyzer = NewsAnalyzer(llm_service=llm_service)
    _news_collector_task, _news_scheduler = await start_news_collector(
        aggregator=news_aggregator,
        analyzer=news_analyzer,
    )

    logger.info("Application started successfully")

    yield

    # --- Shutdown ---
    logger.info("Shutting down application...")

    # Stop price poller
    if _poller_task and not _poller_task.done():
        _poller_task.cancel()
        try:
            await _poller_task
        except asyncio.CancelledError:
            pass

    # Stop news collector
    if _news_collector_task and not _news_collector_task.done():
        _news_collector_task.cancel()
        try:
            await _news_collector_task
        except asyncio.CancelledError:
            pass

    # Close Redis pool
    await redis_pool.aclose()

    # Dispose database engine
    await engine.dispose()

    logger.info("Application shut down successfully")


# Create FastAPI app
app = FastAPI(
    title="Stock Investment Dashboard API",
    description="Aggregated multi-broker stock portfolio management with real-time updates",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTPS redirect (production only)
if settings.environment == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

# ---------------------------------------------------------------------------
# Dependency overrides (wire service factories into router placeholders)
# ---------------------------------------------------------------------------

app.dependency_overrides[market_data_router.get_market_data_service] = get_market_data_service
app.dependency_overrides[alerts_router.get_alert_service] = get_alert_service
app.dependency_overrides[orders_router.get_order_service] = get_order_service
app.dependency_overrides[news_router.get_news_service] = get_news_service

# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------

app.include_router(auth_router.router)
app.include_router(brokers_router.router)
app.include_router(portfolio_router.router)
app.include_router(market_data_router.router)
app.include_router(orders_router.router)
app.include_router(alerts_router.router)
app.include_router(news_router.router)
app.include_router(predictions_router.router)
app.include_router(telemetry_router.router)
app.include_router(ws_router.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {"status": "ok", "environment": settings.environment}
