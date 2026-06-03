# Implementation Plan: News Data Store

## Overview

Transition the news system from a 30-minute polling model to a scheduled daily collection model. This involves creating a `collection_runs` table, adding `collection_date` to `news_articles`, building a schedule-aware collector task, updating the briefing generator to read from stored data, and adding a collection status endpoint.

## Tasks

- [ ] 1. Database schema changes and migration
  - [ ] 1.1 Add `CollectionRun` ORM model and update `NewsArticle` model
    - Add `CollectionRun` class to `backend/models/orm.py` with columns: id, started_at, completed_at, status, source, articles_fetched, articles_stored, duration_seconds, error_message, created_at
    - Add `collection_date` (Date, NOT NULL) and `collection_run_id` (UUID FK to collection_runs, nullable) columns to existing `NewsArticle` model
    - Add relationship from `NewsArticle` to `CollectionRun`
    - _Requirements: 2.1, 2.2, 4.5_

  - [ ] 1.2 Create Alembic migration `0003_add_collection_runs`
    - Create `collection_runs` table
    - Add `collection_date` and `collection_run_id` columns to `news_articles`
    - Backfill `collection_date` from `fetched_at` converted to IST date for existing rows
    - Set `collection_date` as NOT NULL after backfill
    - Add indexes: `idx_news_collection_date`, `idx_news_collection_date_tickers` (GIN on related_tickers), `idx_news_user_collection_date`
    - Add unique deduplication index: `idx_news_dedup` on (user_id, collection_date, lower(title), lower(source_name))
    - Add indexes on `collection_runs`: `idx_collection_runs_status`, `idx_collection_runs_started_at`
    - _Requirements: 2.1, 2.3, 2.5, 4.5_

- [ ] 2. Configuration updates
  - [ ] 2.1 Add new settings to `backend/config.py`
    - Add `news_collection_times: str = "07:00,18:00"` (IST, comma-separated HH:MM)
    - Add `news_retention_days: int = 90`
    - Add `news_max_articles_per_user: int = 10000`
    - Keep existing `news_poll_interval` for backward compatibility but mark as deprecated in comment
    - _Requirements: 1.3, 2.4, 6.5_

  - [ ] 2.2 Update `.env.example` with new environment variables
    - Add `NEWS_COLLECTION_TIMES=07:00,18:00`
    - Add `NEWS_RETENTION_DAYS=90`
    - _Requirements: 1.3_

- [ ] 3. Implement scheduled news collector
  - [ ] 3.1 Create `backend/tasks/news_collector.py` with `NewsCollectionScheduler` class
    - Implement `__init__` accepting aggregator, analyzer, and parsed collection times
    - Implement `_seconds_until_next_run()` calculating time to next IST scheduled run
    - Implement `_maybe_catch_up()` checking if last successful run was >12h ago on startup, triggering catch-up fetch within 5 minutes
    - Implement main `run()` loop: catch-up check → calculate sleep until next run → execute → repeat
    - Implement `execute_immediate()` for manual trigger (source="manual")
    - _Requirements: 1.1, 1.2, 1.4, 5.5, 6.1_

  - [ ] 3.2 Implement `_execute_collection()` with retry logic
    - Create a `CollectionRun` record with status "started"
    - Iterate all users, resolve portfolio tickers, fetch articles via aggregator
    - Store articles with `collection_date` (IST date) and `collection_run_id`, applying deduplication (skip if title+source already exists for that user+date)
    - Kick off analysis via analyzer
    - On success: update run with status "completed", articles_fetched, articles_stored, duration_seconds
    - On failure: retry up to 3 times with exponential backoff (60s, 120s, 240s), then mark run as "failed" with error_message
    - _Requirements: 1.5, 2.1, 2.2, 2.3, 2.6, 5.1, 5.2, 6.2, 6.3_

  - [ ] 3.3 Implement daily cleanup within the collector
    - After first scheduled run each day, delete articles where `collection_date` < today - `news_retention_days`
    - Delete old `collection_runs` records beyond retention window
    - Enforce per-user article cap (`news_max_articles_per_user`)
    - _Requirements: 2.4_

  - [ ]* 3.4 Write unit tests for `NewsCollectionScheduler`
    - Test `_seconds_until_next_run()` correctly calculates IST times
    - Test catch-up logic triggers when last run was >12h ago
    - Test retry logic with exponential backoff
    - Test deduplication skips duplicate articles within same collection_date
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 2.3_

- [ ] 4. Checkpoint - Ensure migration and collector tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Update briefing generator to use stored data
  - [ ] 5.1 Modify `generate_briefing()` in `backend/services/news_service.py`
    - Query articles by `collection_date` matching today's IST date instead of last-24h time window
    - Filter articles to only those matching user's portfolio tickers (via `related_tickers` column)
    - If no articles for today's `collection_date`, fall back to most recent `collection_date` that has data (search up to 7 days back)
    - Include `collection_date` timestamp in the briefing response dict
    - Preserve stub-mode behavior: return placeholder briefing using stored article titles/summaries
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 5.2 Write unit tests for updated briefing generator
    - Test articles are filtered by collection_date
    - Test fallback to most recent date when today has no data
    - Test only user's portfolio tickers are included
    - Test collection_date is present in response
    - Test stub mode returns placeholder without LLM calls
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 6. Add collection status endpoint and pattern analysis queries
  - [ ] 6.1 Add `GET /news/collection-status` endpoint to `backend/routers/news.py`
    - Query most recent `CollectionRun` from DB
    - Return: last run details (status, started_at, completed_at, articles_fetched, articles_stored, duration_seconds)
    - Calculate `is_stale` flag: True if no successful run in past 24 hours
    - Calculate `next_scheduled` ISO timestamp of next run based on configured times
    - Include today's `collection_date` (IST) in response
    - _Requirements: 5.3, 5.4_

  - [ ] 6.2 Add pattern analysis query methods to `backend/services/news_service.py`
    - Implement `get_ticker_sentiment_trend(ticker, start_date, end_date)` returning sentiment distribution per collection_date (bullish/bearish/neutral counts)
    - Implement `get_ticker_news_timeline(ticker, days=90)` returning chronological article sequence ordered by collection_date
    - Both methods query using `collection_date` and `related_tickers` indexes
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 6.3 Write unit tests for collection status and pattern analysis
    - Test stale detection when no run in 24h
    - Test sentiment trend aggregation returns correct counts
    - Test timeline query returns articles in chronological order
    - _Requirements: 4.3, 4.4, 5.3, 5.4_

- [ ] 7. Wire new collector into application lifecycle
  - [ ] 7.1 Update `backend/main.py` to use `NewsCollectionScheduler`
    - Import and instantiate `NewsCollectionScheduler` with parsed collection times from settings
    - Replace `start_news_poller` call with new scheduler's `run()` as background task
    - Store scheduler instance on app state for access by manual refresh endpoint
    - Remove/deprecate old `start_news_poller` import
    - _Requirements: 6.1, 6.4_

  - [ ] 7.2 Update `POST /news/refresh` to trigger immediate collection run
    - Modify the refresh endpoint to call `scheduler.execute_immediate()` instead of the per-user live fetch
    - Return `CollectionRun` metadata (articles_fetched, articles_stored, status) in response
    - _Requirements: 5.5_

  - [ ]* 7.3 Write integration tests for the full collection flow
    - Test scheduled collection stores articles with correct collection_date
    - Test manual refresh triggers immediate collection run
    - Test collection status reflects latest run
    - Test briefing reads from stored data without live API calls
    - _Requirements: 1.1, 5.5, 3.1_

- [ ] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The design uses Python with SQLAlchemy async ORM, FastAPI, and Alembic migrations
- India Standard Time (IST = UTC+5:30) is used for all schedule calculations; India does not observe DST
- The existing `news_poller.py` is replaced by the new `news_collector.py` but kept for backward compatibility initially
- Unit tests and integration tests validate specific examples and edge cases

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "2.2"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["3.1", "3.2", "3.3"] },
    { "id": 3, "tasks": ["3.4", "5.1", "6.1", "6.2"] },
    { "id": 4, "tasks": ["5.2", "6.3", "7.1"] },
    { "id": 5, "tasks": ["7.2"] },
    { "id": 6, "tasks": ["7.3"] }
  ]
}
```
