# Technical Design: News Data Store

## Overview

This design transitions the news system from a frequent polling model (every 30 minutes) to a scheduled daily collection model. It introduces a `collection_runs` table to track fetch metadata, adds a `collection_date` column to the existing `news_articles` table, rewrites the news poller as a schedule-aware task, and modifies the briefing generator to read exclusively from stored data.

The design preserves the existing `news_articles` table structure and adds to it (no destructive migrations), keeping the system backward-compatible during rollout.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI App                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────────┐    ┌────────────────┐ │
│  │ News Router  │───▶│  News Service    │───▶│ Briefing Gen   │ │
│  │ /news/*      │    │                  │    │ (reads from DB)│ │
│  └──────────────┘    └──────────────────┘    └────────────────┘ │
│                              │                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Scheduled News Collector (Background Task)    │   │
│  │  • Schedule-aware (07:00 IST, 18:00 IST default)         │   │
│  │  • Catch-up on startup                                    │   │
│  │  • Records CollectionRun metadata                         │   │
│  │  • Retry with exponential backoff                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│              │                         │                          │
│              ▼                         ▼                          │
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │ News Aggregator  │    │  News Analyzer   │                   │
│  │ (RSS feeds)      │    │  (LLM batched)   │                   │
│  └──────────────────┘    └──────────────────┘                   │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                        PostgreSQL                                 │
│  ┌───────────────────┐  ┌───────────────────────────────────┐   │
│  │  collection_runs  │  │  news_articles (existing + new cols)│  │
│  │  • id (PK)        │  │  • collection_date (DATE, new)      │  │
│  │  • started_at     │  │  • collection_run_id (FK, new)      │  │
│  │  • completed_at   │  │  • (all existing columns retained)  │  │
│  │  • status         │  │                                     │  │
│  │  • source         │  │  New indexes:                       │  │
│  │  • articles_fetch │  │  • idx_news_collection_date         │  │
│  │  • articles_stored│  │  • idx_news_collection_date_tickers │  │
│  │  • duration_secs  │  └───────────────────────────────────┘   │
│  └───────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Database Changes

### New Table: `collection_runs`

Tracks metadata for each news collection execution.

```sql
CREATE TABLE collection_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'started',  -- started, completed, failed
    source VARCHAR(20) NOT NULL DEFAULT 'scheduled', -- scheduled, manual, catch_up
    articles_fetched INTEGER DEFAULT 0,
    articles_stored INTEGER DEFAULT 0,
    duration_seconds FLOAT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX idx_collection_runs_status ON collection_runs(status);
CREATE INDEX idx_collection_runs_started_at ON collection_runs(started_at DESC);
```

### Alter Table: `news_articles` (add columns)

```sql
ALTER TABLE news_articles ADD COLUMN collection_date DATE;
ALTER TABLE news_articles ADD COLUMN collection_run_id UUID REFERENCES collection_runs(id) ON DELETE SET NULL;

-- Backfill: set collection_date from fetched_at for existing rows
UPDATE news_articles SET collection_date = (fetched_at AT TIME ZONE 'Asia/Kolkata')::date WHERE collection_date IS NULL;

-- Make collection_date NOT NULL after backfill
ALTER TABLE news_articles ALTER COLUMN collection_date SET NOT NULL;

-- New indexes for pattern analysis queries
CREATE INDEX idx_news_collection_date ON news_articles(collection_date);
CREATE INDEX idx_news_collection_date_tickers ON news_articles USING gin(related_tickers) WHERE related_tickers IS NOT NULL;
CREATE INDEX idx_news_user_collection_date ON news_articles(user_id, collection_date DESC);
```

### Deduplication Constraint

```sql
CREATE UNIQUE INDEX idx_news_dedup ON news_articles(user_id, collection_date, lower(title), lower(source_name));
```

## Configuration Changes

### New Settings (`backend/config.py`)

```python
# News Collection Schedule
news_collection_times: str = "07:00,18:00"  # IST, comma-separated HH:MM
news_retention_days: int = 90               # Historical window
news_max_articles_per_user: int = 10000     # Safety cap
```

### Environment Variables

```env
NEWS_COLLECTION_TIMES=07:00,18:00
NEWS_RETENTION_DAYS=90
```

The existing `news_poll_interval` setting remains in the config class (backward compat) but is ignored by the new scheduler.

## Component Design

### 1. Scheduled News Collector (`backend/tasks/news_collector.py`)

Replaces the current `news_poller.py` logic. New file that implements schedule-aware execution.

```python
class NewsCollectionScheduler:
    """Schedule-aware news collection task.
    
    Calculates time until next configured IST run time,
    sleeps until then, executes collection, repeats.
    """
    
    def __init__(self, aggregator, analyzer, collection_times: list[str]):
        self._aggregator = aggregator
        self._analyzer = analyzer
        self._times = collection_times  # ["07:00", "18:00"]
    
    async def run(self) -> None:
        """Main loop: check for catch-up, then enter schedule loop."""
        await self._maybe_catch_up()
        while True:
            seconds_until_next = self._seconds_until_next_run()
            await asyncio.sleep(seconds_until_next)
            await self._execute_collection(source="scheduled")
    
    async def execute_immediate(self) -> CollectionRunResult:
        """Execute an immediate collection (manual trigger)."""
        return await self._execute_collection(source="manual")
    
    async def _execute_collection(self, source: str) -> CollectionRunResult:
        """Single collection cycle with retry logic."""
        run = await self._create_run(source)
        for attempt in range(4):  # 1 + 3 retries
            try:
                result = await self._collect_for_all_users(run)
                await self._complete_run(run, result)
                return result
            except Exception as e:
                if attempt < 3:
                    delay = 60 * (2 ** attempt)  # 60s, 120s, 240s
                    await asyncio.sleep(min(delay, 240))
                else:
                    await self._fail_run(run, str(e))
                    raise
    
    def _seconds_until_next_run(self) -> float:
        """Calculate seconds from now until the next scheduled IST time."""
        ...
    
    async def _maybe_catch_up(self) -> None:
        """If last successful run was >12h ago and a scheduled time was missed, run once."""
        ...
```

### 2. Collection Run Model (`backend/models/orm.py`)

```python
class CollectionRun(Base):
    __tablename__ = "collection_runs"

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
```

### 3. News Articles Table Update

Add `collection_date` and `collection_run_id` to the existing `NewsArticle` model:

```python
class NewsArticle(Base):
    # ... existing columns ...
    collection_date: Mapped[datetime] = mapped_column(sa.Date, nullable=False)
    collection_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("collection_runs.id", ondelete="SET NULL"), nullable=True
    )
```

### 4. Updated Briefing Generator (within `news_service.py`)

```python
async def generate_briefing(self, user_id: UUID) -> dict:
    """Read from stored news_articles for today's collection_date."""
    today_ist = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    
    # Query articles for today's collection date
    articles = await self._get_articles_for_date(user_id, today_ist)
    
    # Fallback: search up to 7 days back
    if not articles:
        articles = await self._get_most_recent_articles(user_id, days_back=7)
    
    # Build briefing from stored data (no live fetch)
    ...
```

### 5. Collection Status Endpoint (`GET /news/collection-status`)

```python
@router.get("/collection-status")
async def get_collection_status(session: Session = Depends(get_current_user)):
    """Return status of most recent collection run + staleness indicator."""
    return {
        "last_run": { ... },  # Most recent CollectionRun
        "is_stale": bool,     # No successful run in 24h
        "next_scheduled": str, # ISO timestamp of next run
        "collection_date": str, # Today's IST date
    }
```

### 6. Daily Cleanup Task

Runs after the first scheduled collection each day:

```python
async def _cleanup_old_data(self) -> None:
    """Delete articles older than retention window and old collection_run records."""
    cutoff_date = date.today() - timedelta(days=settings.news_retention_days)
    # DELETE FROM news_articles WHERE collection_date < cutoff_date
    # DELETE FROM collection_runs WHERE started_at < cutoff_date
    # Enforce per-user article cap (10,000)
```

### 7. Pattern Analysis Query Support

The storage structure enables these queries for future LLM pattern analysis:

```python
# Sentiment distribution for a ticker over date range
async def get_ticker_sentiment_trend(ticker: str, start_date: date, end_date: date):
    """Returns: [{collection_date, bullish_count, bearish_count, neutral_count}, ...]"""
    
# Chronological article sequence for a ticker
async def get_ticker_news_timeline(ticker: str, days: int = 90):
    """Returns: [{collection_date, title, summary, sentiment, impact}, ...]"""
```

## Migration Strategy

1. **Alembic migration `0003`**: Add `collection_runs` table, add `collection_date` and `collection_run_id` columns to `news_articles`, backfill `collection_date` from `fetched_at`, add new indexes
2. **Code changes**: New `news_collector.py`, update `main.py` to use new scheduler, update `news_service.py` briefing to read from stored data
3. **Config update**: Add `NEWS_COLLECTION_TIMES` to `.env`, keep `news_poll_interval` as deprecated

## File Changes Summary

| File | Change |
|------|--------|
| `backend/models/orm.py` | Add `CollectionRun` model, add `collection_date` + `collection_run_id` to `NewsArticle` |
| `backend/alembic/versions/0003_add_collection_runs.py` | New migration |
| `backend/tasks/news_collector.py` | New file — schedule-aware collector |
| `backend/tasks/news_poller.py` | Deprecated (replaced by news_collector.py) |
| `backend/services/news_service.py` | Update `generate_briefing` to use stored data + `collection_date` |
| `backend/routers/news.py` | Add `GET /news/collection-status` endpoint |
| `backend/config.py` | Add `news_collection_times`, `news_retention_days`, `news_max_articles_per_user` |
| `backend/main.py` | Replace `start_news_poller` with new scheduler |
| `.env` / `.env.example` | Add `NEWS_COLLECTION_TIMES` |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| IST time calculation bugs (DST) | Runs at wrong time | India doesn't observe DST — IST is fixed UTC+5:30 |
| Rate limit hit during collection | Articles not analyzed | Circuit breaker already handles this; articles stored as stubs, re-analyzable later |
| App restart loses schedule state | Missed collection | Catch-up logic checks last successful run on startup |
| Large article count per collection | Slow DB writes | Batch inserts with dedup check, limit to 100 articles per feed |
| Old migration backfill on large table | Long lock | Use batched UPDATE with WHERE clause to avoid full table lock |
