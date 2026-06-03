from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

BrokerId = Literal["groww", "zerodha", "fidelity", "robinhood"]
TimeRange = Literal["1d", "1w", "1m", "3m", "1y", "5y"]

# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------


class NormalizedHolding(BaseModel):
    """A single stock position normalized to the common schema."""

    ticker: str
    company_name: str
    broker_id: BrokerId
    quantity: Decimal
    avg_buy_price: Decimal
    current_price: Decimal
    current_value: Decimal
    gain_loss: Decimal
    gain_loss_percent: Decimal
    currency: str = "USD"
    last_updated: datetime
    is_stale: bool = False


class BrokerStatus(BaseModel):
    """Connection status for a single broker."""

    broker_id: BrokerId
    status: Literal["connected", "disconnected", "error"]
    last_successful_fetch: datetime | None = None
    error_message: str | None = None


class Portfolio(BaseModel):
    """Aggregated portfolio across all connected brokers for a user."""

    user_id: UUID
    holdings: list[NormalizedHolding]
    total_value: Decimal
    total_invested: Decimal
    total_gain_loss: Decimal
    total_gain_loss_percent: Decimal
    day_change: Decimal
    day_change_percent: Decimal
    broker_statuses: list[BrokerStatus]
    last_refreshed: datetime


class PriceQuote(BaseModel):
    """Current price quote from the market data provider."""

    ticker: str
    price: Decimal
    previous_close: Decimal
    change: Decimal
    change_percent: Decimal
    timestamp: datetime
    is_stale: bool = False


class HistoricalDataPoint(BaseModel):
    """A single OHLCV data point in a price history series."""

    date: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class OrderRequest(BaseModel):
    """Request payload for placing a buy or sell order."""

    broker_id: BrokerId
    ticker: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"]
    quantity: Decimal
    limit_price: Decimal | None = None


class Order(BaseModel):
    """A persisted order record with full lifecycle state."""

    id: UUID
    user_id: UUID
    broker_id: BrokerId
    broker_order_id: str | None = None
    ticker: str
    order_type: Literal["market", "limit"]
    side: Literal["buy", "sell"]
    quantity: Decimal
    limit_price: Decimal | None = None
    execution_price: Decimal | None = None
    status: Literal["pending", "filled", "rejected", "cancelled"]
    rejection_reason: str | None = None
    placed_at: datetime
    updated_at: datetime


class Alert(BaseModel):
    """A price alert set by the user for a specific ticker."""

    id: UUID
    user_id: UUID
    ticker: str
    target_price: Decimal
    condition: Literal["above", "below"]
    status: Literal["active", "triggered"] = "active"
    triggered_at: datetime | None = None
    created_at: datetime


class AuthTokens(BaseModel):
    """JWT access/refresh token pair returned after successful login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expiry


class Session(BaseModel):
    """An active user session tracked in the database."""

    id: UUID
    user_id: UUID
    expires_at: datetime
    last_active: datetime


class MFASetupData(BaseModel):
    """Data returned when a user initiates MFA setup."""

    secret: str
    provisioning_uri: str
    qr_code_base64: str


# ---------------------------------------------------------------------------
# Raw broker data models (connector output before normalization)
# ---------------------------------------------------------------------------


class RawHolding(BaseModel):
    """Flexible model for raw holding data returned by a broker connector."""

    broker_id: BrokerId
    ticker: str
    company_name: str | None = None
    quantity: Decimal
    avg_buy_price: Decimal
    currency: str = "USD"
    extra: dict = Field(default_factory=dict)  # broker-specific extra fields


class RawOrder(BaseModel):
    """Raw order data returned by a broker connector."""

    broker_id: BrokerId
    broker_order_id: str
    ticker: str
    order_type: Literal["market", "limit"]
    side: Literal["buy", "sell"]
    quantity: Decimal
    limit_price: Decimal | None = None
    execution_price: Decimal | None = None
    status: Literal["pending", "filled", "rejected", "cancelled"]
    placed_at: datetime


class OrderResult(BaseModel):
    """Result returned by a broker connector after placing an order."""

    broker_order_id: str
    status: str
    execution_price: Decimal | None = None
    rejection_reason: str | None = None


class RefreshResult(BaseModel):
    """Result of a holdings refresh attempt for a single broker."""

    broker_id: BrokerId
    success: bool
    holdings_count: int
    error_message: str | None = None
    fetched_at: datetime


class TriggeredAlert(BaseModel):
    """Emitted when an alert condition is satisfied."""

    alert_id: UUID
    user_id: UUID
    ticker: str
    target_price: Decimal
    condition: Literal["above", "below"]
    triggered_price: Decimal
    triggered_at: datetime


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateAlertRequest(BaseModel):
    """Payload for creating a new price alert."""

    ticker: str
    target_price: Decimal
    condition: Literal["above", "below"]


class UpdateAlertRequest(BaseModel):
    """Payload for partially updating an existing alert."""

    target_price: Decimal | None = None
    condition: Literal["above", "below"] | None = None
    status: Literal["active", "triggered"] | None = None


class OrderFilters(BaseModel):
    """Optional filters for querying order history."""

    broker_id: BrokerId | None = None
    ticker: str | None = None
    status: str | None = None
    limit: int = 50


# ---------------------------------------------------------------------------
# News analysis models
# ---------------------------------------------------------------------------


class SentimentScore(str, Enum):
    """Directional market impact classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ImpactLevel(str, Enum):
    """Magnitude of expected price impact."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RawNewsArticle(BaseModel):
    """Raw article fetched from a news source before LLM analysis."""

    title: str
    source_name: str
    source_url: str | None = None
    published_at: datetime
    raw_content: str


class AnalyzedNewsItem(BaseModel):
    """A fully analyzed news article with LLM-derived metadata."""

    id: UUID
    title: str
    source_name: str
    source_url: str | None = None
    published_at: datetime
    summary: str  # max 200 chars
    sentiment_score: SentimentScore
    impact_level: ImpactLevel
    related_tickers: list[str]
    relevance_score: float
    is_stub: bool = False
    analyzed_at: datetime


class NewsAnalysisResponse(BaseModel):
    """LLM output for a single article analysis."""

    summary: str
    sentiment_score: SentimentScore
    impact_level: ImpactLevel
    related_tickers: list[str]
    is_stub: bool = False


class PaginatedNewsResponse(BaseModel):
    """Paginated response for the news feed endpoint."""

    items: list[AnalyzedNewsItem]
    total: int
    page: int
    page_size: int
    has_next: bool


class RefreshStatus(BaseModel):
    """Status of a news refresh operation."""

    status: Literal["started", "in_progress", "completed", "failed"]
    articles_fetched: int = 0
    articles_analyzed: int = 0
    last_refresh_at: datetime | None = None
