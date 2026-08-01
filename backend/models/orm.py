from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    mfa_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )

    broker_tokens: Mapped[list["BrokerToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    holdings_cache: Mapped[list["HoldingCache"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    news_articles: Mapped[list["NewsArticle"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class BrokerToken(Base):
    __tablename__ = "broker_tokens"
    __table_args__ = (UniqueConstraint("user_id", "broker_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    broker_id: Mapped[str] = mapped_column(String(20), nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_iv: Mapped[str] = mapped_column(Text, nullable=False)
    token_tag: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    connected_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    last_refreshed: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="connected")

    user: Mapped["User"] = relationship(back_populates="broker_tokens")


class HoldingCache(Base):
    __tablename__ = "holdings_cache"
    __table_args__ = (UniqueConstraint("user_id", "broker_id", "ticker"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    broker_id: Mapped[str] = mapped_column(String(20), nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    avg_buy_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    fetched_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    user: Mapped["User"] = relationship(back_populates="holdings_cache")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    broker_id: Mapped[str] = mapped_column(String(20), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    execution_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    placed_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )

    user: Mapped["User"] = relationship(back_populates="orders")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    target_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    condition: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    triggered_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )

    user: Mapped["User"] = relationship(back_populates="alerts")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    last_active: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    user: Mapped["User"] = relationship(back_populates="sessions")


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        sa.Index("idx_news_articles_user_id", "user_id"),
        sa.Index("idx_news_articles_published_at", "published_at"),
        sa.Index("idx_news_articles_sentiment", "sentiment_score"),
        sa.Index("idx_news_articles_impact", "impact_level"),
        sa.Index("idx_news_articles_analyzed", "is_analyzed"),
        sa.Index("idx_news_collection_date", "collection_date"),
        sa.Index("idx_news_user_collection_date", "user_id", "collection_date"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False
    )
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sentiment_score: Mapped[str | None] = mapped_column(String(10), nullable=True)
    impact_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    related_tickers: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    relevance_score: Mapped[float] = mapped_column(sa.Float, default=0.0)
    is_analyzed: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    is_stub: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    analyzed_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    # New columns for daily collection model
    collection_date: Mapped[datetime | None] = mapped_column(
        sa.Date, nullable=True
    )
    collection_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("collection_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(20), default="rss", server_default=sa.text("'rss'")
    )  # "rss" or "newsapi_ai"

    user: Mapped["User"] = relationship(back_populates="news_articles")
    collection_run: Mapped["CollectionRun | None"] = relationship(back_populates="articles")


class CollectionRun(Base):
    """Tracks metadata for each news collection execution."""

    __tablename__ = "collection_runs"
    __table_args__ = (
        sa.Index("idx_collection_runs_status", "status"),
        sa.Index("idx_collection_runs_started_at", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    started_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="started")
    source: Mapped[str] = mapped_column(String(20), default="scheduled")
    articles_fetched: Mapped[int] = mapped_column(sa.Integer, default=0)
    articles_stored: Mapped[int] = mapped_column(sa.Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    articles: Mapped[list["NewsArticle"]] = relationship(back_populates="collection_run")


class BriefingCache(Base):
    """Stores generated portfolio briefings for reuse."""

    __tablename__ = "briefing_cache"
    __table_args__ = (
        sa.Index("idx_briefing_cache_user_date", "user_id", "collection_date"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    collection_date: Mapped[datetime] = mapped_column(sa.Date, nullable=False)
    briefing_text: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    articles_used: Mapped[int] = mapped_column(sa.Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    news_last_fetched_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )


class PortfolioSnapshot(Base):
    """Daily snapshot of portfolio state for historical tracking and prediction."""

    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        sa.Index("idx_portfolio_snapshots_user_date", "user_id", "snapshot_date"),
        UniqueConstraint("user_id", "snapshot_date", "ticker", name="uq_portfolio_snapshot"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[datetime] = mapped_column(sa.Date, nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    broker_id: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    avg_buy_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gain_loss: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gain_loss_percent: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    day_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    day_change_percent: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )


class PortfolioDailySummary(Base):
    """Daily aggregate portfolio value for trend tracking."""

    __tablename__ = "portfolio_daily_summary"
    __table_args__ = (
        sa.Index("idx_portfolio_daily_summary_user_date", "user_id", "snapshot_date"),
        UniqueConstraint("user_id", "snapshot_date", name="uq_portfolio_daily_summary"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[datetime] = mapped_column(sa.Date, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    total_invested: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    total_gain_loss: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    total_gain_loss_percent: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    day_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    day_change_percent: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    holdings_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )


class StockFundamentals(Base):
    """Cached stock fundamentals from screener.in."""

    __tablename__ = "stock_fundamentals"
    __table_args__ = (
        sa.Index("idx_stock_fundamentals_ticker", "ticker"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    market_cap: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_price: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pe_ratio: Mapped[str | None] = mapped_column(String(20), nullable=True)
    book_value: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dividend_yield: Mapped[str | None] = mapped_column(String(20), nullable=True)
    roce: Mapped[str | None] = mapped_column(String(20), nullable=True)
    roe: Mapped[str | None] = mapped_column(String(20), nullable=True)
    face_value: Mapped[str | None] = mapped_column(String(20), nullable=True)
    high_low: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pros: Mapped[str | None] = mapped_column(Text, nullable=True)
    cons: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )


class PredictionRecord(Base):
    """Stores LLM predictions from briefings for accuracy tracking."""

    __tablename__ = "prediction_records"
    __table_args__ = (
        sa.Index("idx_prediction_records_user_date", "user_id", "prediction_date"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    prediction_date: Mapped[datetime] = mapped_column(sa.Date, nullable=False)
    # Overall market mood prediction
    market_mood: Mapped[str] = mapped_column(String(10), nullable=False)  # bullish/bearish/neutral
    market_mood_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Per-ticker predictions stored as JSON
    ticker_predictions: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    # Full briefing text
    briefing_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Confidence score (computed after market data comes in)
    confidence_score: Mapped[float | None] = mapped_column(sa.Float, nullable=True)  # 0-100
    score_computed_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    # Score breakdown
    mood_accuracy: Mapped[float | None] = mapped_column(sa.Float, nullable=True)  # 0-100
    ticker_accuracy: Mapped[float | None] = mapped_column(sa.Float, nullable=True)  # 0-100
    # Metadata
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )


class TradeHistory(Base):
    """Parsed trade history from uploaded broker reports."""

    __tablename__ = "trade_history"
    __table_args__ = (
        sa.Index("idx_trade_history_user_ticker", "user_id", "ticker"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(30), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    trade_type: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY or SELL
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(10), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    broker: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )


class Attachment(Base):
    """Documents received via Telegram for processing."""

    __tablename__ = "attachments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_id: Mapped[str] = mapped_column(String(200), nullable=False)
    file_size: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    processed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    records_imported: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    received_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())


class UserPreferences(Base):
    """Per-user geography and display preferences."""

    __tablename__ = "user_preferences"
    __table_args__ = (sa.UniqueConstraint("user_id", name="uq_user_preferences_user"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    geography: Mapped[str] = mapped_column(String(5), default="IN", nullable=False)
    default_broker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )


class Portfolio(Base):
    """A named portfolio tied to one geography and broker."""

    __tablename__ = "portfolios"
    __table_args__ = (sa.Index("idx_portfolios_user", "user_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    geo_id: Mapped[str] = mapped_column(String(5), default="IN", nullable=False)
    broker_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_default: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )
