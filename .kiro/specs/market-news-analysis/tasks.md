# Implementation Plan: Market News Analysis

## Overview

This plan implements an LLM-powered news aggregation and analysis pipeline for the Stock Investment Dashboard. It follows the existing project patterns (FastAPI backend with SQLAlchemy ORM, React + TypeScript frontend) and builds incrementally: data models → backend services → API layer → background task → frontend components.

## Tasks

- [x] 1. Create database models and migration
  - [x] 1.1 Add news domain models and enums to `backend/models/domain.py`
    - Add `SentimentScore` enum (bullish, bearish, neutral)
    - Add `ImpactLevel` enum (high, medium, low)
    - Add `RawNewsArticle`, `AnalyzedNewsItem`, `NewsAnalysisResponse`, `PaginatedNewsResponse`, `RefreshStatus` Pydantic models
    - _Requirements: 2.1, 2.2, 2.3, 3.2, 3.3, 6.3_

  - [x] 1.2 Add `NewsArticle` ORM model to `backend/models/orm.py`
    - Define the `news_articles` table with all columns (id, user_id, title, source_name, source_url, published_at, raw_content, summary, sentiment_score, impact_level, related_tickers, relevance_score, is_analyzed, is_stub, analyzed_at, fetched_at, created_at)
    - Add indexes on user_id, published_at, sentiment_score, impact_level, is_analyzed
    - Add relationship to User model
    - _Requirements: 1.4, 6.3_

  - [x] 1.3 Create Alembic migration for `news_articles` table
    - Generate migration in `backend/alembic/versions/`
    - Include all columns, indexes, and foreign key constraint
    - _Requirements: 1.4_

- [x] 2. Extend LLM service interface and implementation
  - [x] 2.1 Add `analyze_news_article` method to `ILLMService` interface in `backend/interfaces/llm_service.py`
    - Define abstract method accepting article content and portfolio tickers, returning `NewsAnalysisResponse`
    - _Requirements: 7.2_

  - [x] 2.2 Implement `analyze_news_article` in `backend/services/llm_service.py`
    - Add stub implementation returning deterministic placeholder (sentiment=neutral, impact=medium, summary from first 200 chars, is_stub=True)
    - Add real LLM implementation using LangChain with structured prompt for JSON output (sentiment_score, impact_level, summary, related_tickers)
    - Handle LLM errors gracefully (log and return None)
    - _Requirements: 2.1, 2.3, 2.5, 7.1, 7.3, 7.4_

  - [ ]* 2.3 Write property test for stub determinism (Property 14)
    - **Property 14: Stub determinism**
    - Verify that calling `analyze_news_article` twice with same input in stub mode produces identical output
    - **Validates: Requirements 7.3**

  - [ ]* 2.4 Write property test for summary length invariant (Property 4)
    - **Property 4: Summary length invariant**
    - Verify that for any analyzed article the summary length is ≤ 200 characters
    - **Validates: Requirements 2.3**

  - [ ]* 2.5 Write property test for sentiment and impact domain constraints (Property 6)
    - **Property 6: Sentiment and impact domain constraints**
    - Verify that sentiment_score is always one of {bullish, bearish, neutral} and impact_level is always one of {high, medium, low}
    - **Validates: Requirements 3.2, 3.3**

- [x] 3. Implement News Aggregator service
  - [x] 3.1 Create `backend/services/news_aggregator.py`
    - Implement `NewsAggregator` class with `fetch_articles(portfolio_tickers)` and `store_articles(articles)` methods
    - Fetch from configured News Source API (NewsAPI or equivalent) with Indian market focus
    - Filter articles for relevance: must mention NSE/BSE ticker, Indian market keyword, or portfolio sector
    - Filter articles to only those published within last 24 hours
    - Handle API errors with exponential backoff (1s, 2s, 4s, max 3 retries)
    - Log failures and continue with partial results
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 3.2 Add `news_api_key` and `news_api_url` to `backend/config.py` Settings
    - Add configuration fields for the news source API
    - Add `news_poll_interval` setting (default: 1800 seconds / 30 minutes)
    - _Requirements: 5.4_

  - [ ]* 3.3 Write property test for article relevance filtering (Property 1)
    - **Property 1: Article relevance filtering**
    - Verify that only articles containing NSE/BSE ticker references, Indian market keywords, or matching portfolio sectors pass the filter
    - **Validates: Requirements 1.2**

  - [ ]* 3.4 Write property test for time window filtering (Property 3)
    - **Property 3: Time window filtering**
    - Verify that articles are included if and only if published within the last 24 hours
    - **Validates: Requirements 1.5**

  - [ ]* 3.5 Write property test for article storage round-trip (Property 2)
    - **Property 2: Article storage round-trip**
    - Verify that storing and retrieving an article preserves title, source_name, published_at, and raw_content
    - **Validates: Requirements 1.4**

- [x] 4. Implement News Analyzer service
  - [x] 4.1 Create `backend/services/news_analyzer.py`
    - Implement `NewsAnalyzer` class with `analyze_article(article, portfolio_tickers)` and `analyze_batch(articles, portfolio_tickers)` methods
    - Call `ILLMService.analyze_news_article` for each article
    - Assign relevance_score: articles mentioning portfolio tickers get higher scores
    - Handle LLM errors by marking article as unanalyzed (is_analyzed=false)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.4_

  - [ ]* 4.2 Write property test for portfolio relevance scoring (Property 5)
    - **Property 5: Portfolio relevance scoring**
    - Verify that articles mentioning portfolio tickers receive strictly higher relevance scores than those mentioning none
    - **Validates: Requirements 3.1**

  - [ ]* 4.3 Write property test for multi-ticker association (Property 7)
    - **Property 7: Multi-ticker association**
    - Verify that when an article mentions N distinct portfolio tickers, all N appear in related_tickers
    - **Validates: Requirements 3.4, 2.2**

- [ ] 5. Checkpoint - Ensure backend services work correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement News Service (orchestration layer)
  - [x] 6.1 Create `backend/interfaces/news_service.py`
    - Define `INewsService` abstract class with `get_news_feed` and `trigger_refresh` methods
    - _Requirements: 6.1, 6.2_

  - [x] 6.2 Create `backend/services/news_service.py`
    - Implement `NewsService` class orchestrating NewsAggregator and NewsAnalyzer
    - Implement `get_news_feed` with pagination, filtering (sentiment, impact, ticker), and sorting by ranking
    - Implement ranking: high-impact portfolio-relevant articles first
    - Implement `trigger_refresh` with status tracking via Redis
    - Cache paginated results in Redis (5 min TTL), invalidate on refresh
    - Fall back to direct DB queries if Redis unavailable
    - _Requirements: 3.5, 5.1, 5.2, 5.4, 6.1, 6.2, 6.5_

  - [ ]* 6.3 Write property test for ranking invariant (Property 8)
    - **Property 8: Ranking invariant**
    - Verify that high-impact portfolio-relevant articles always appear before low-impact or zero-relevance articles
    - **Validates: Requirements 3.5**

  - [ ]* 6.4 Write property test for pagination correctness (Property 11)
    - **Property 11: Pagination correctness**
    - Verify correct slicing, page size limits, and has_next flag accuracy
    - **Validates: Requirements 6.1**

  - [ ]* 6.5 Write property test for API filter correctness (Property 12)
    - **Property 12: API filter correctness**
    - Verify that filtering by sentiment, impact, or ticker returns only matching articles
    - **Validates: Requirements 6.2**

- [x] 7. Implement News Router (API endpoints)
  - [x] 7.1 Create `backend/routers/news.py`
    - Implement `GET /news` endpoint with query params: sentiment, impact_level, ticker, page, page_size
    - Implement `POST /news/refresh` endpoint triggering a manual refresh cycle
    - Add authentication dependency (require logged-in user)
    - Return 401 for unauthenticated requests, 422 for invalid params, 200 with empty list when no news available
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 7.2 Register news router in `backend/main.py`
    - Import and include the news router
    - Wire dependency overrides for NewsService
    - _Requirements: 6.1_

  - [x] 7.3 Add `get_news_service` dependency to `backend/dependencies.py`
    - Create factory function wiring NewsAggregator, NewsAnalyzer, and NewsService with DB session, Redis, and LLM service
    - _Requirements: 7.1, 7.2_

  - [ ]* 7.4 Write property test for response schema completeness (Property 13)
    - **Property 13: Response schema completeness**
    - Verify that every news item returned by GET /news contains all required fields (id, title, source_name, published_at, summary, sentiment_score, impact_level, related_tickers, analyzed_at) with no nulls
    - **Validates: Requirements 6.3**

- [x] 8. Implement News Poller background task
  - [x] 8.1 Create `backend/tasks/news_poller.py`
    - Follow `price_poller.py` pattern: async loop with configurable interval (default 30 min)
    - Each cycle: fetch articles via NewsAggregator, then analyze via NewsAnalyzer
    - Handle cancellation gracefully
    - Log errors and continue on failure
    - _Requirements: 5.4, 1.3_

  - [x] 8.2 Wire news poller into app lifespan in `backend/main.py`
    - Start news poller task during startup
    - Cancel task during shutdown
    - _Requirements: 5.4_

- [ ] 9. Checkpoint - Ensure full backend integration works
  - Ensure all tests pass, ask the user if questions arise.

- [-] 10. Implement frontend API client and hook
  - [x] 10.1 Create `frontend/src/api/news.ts`
    - Add `getNewsFeed(params)` function calling `GET /news` with filter/pagination params
    - Add `triggerRefresh()` function calling `POST /news/refresh`
    - Define TypeScript types for `NewsItem`, `PaginatedNewsResponse`, `RefreshStatus`
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 10.2 Create `frontend/src/hooks/useNews.ts`
    - Implement React Query hook for fetching news feed with filters
    - Implement mutation hook for triggering refresh
    - Handle loading, error, and stale data states
    - _Requirements: 5.1, 5.3, 5.5_

- [-] 11. Implement frontend News Feed components
  - [x] 11.1 Create `frontend/src/components/news/NewsItem.tsx`
    - Display title, source name, publication time, summary
    - Show sentiment indicator (green=bullish, red=bearish, gray=neutral)
    - Show impact level badge
    - Implement expand/collapse to show full summary and related tickers
    - _Requirements: 4.2, 4.3, 4.4_

  - [x] 11.2 Create `frontend/src/components/news/NewsFilters.tsx`
    - Filter controls for sentiment (bullish/bearish/neutral), impact level (high/medium/low), and ticker selection
    - _Requirements: 4.5_

  - [x] 11.3 Create `frontend/src/components/news/NewsFeed.tsx`
    - Main container: scrollable list of NewsItem components sorted by relevance
    - Include NewsFilters component
    - Manual refresh button with loading state indicator
    - Loading skeleton while data is being fetched
    - Empty state message when no news available
    - Stale data indicator with last refresh time on failure
    - _Requirements: 4.1, 4.2, 4.5, 4.6, 5.1, 5.3, 5.5_

  - [x] 11.4 Create `frontend/src/pages/NewsPage.tsx` and add route to `App.tsx`
    - Create the News page component wrapping NewsFeed
    - Add `/news` route to the router in App.tsx
    - Add navigation link in the dashboard layout sidebar
    - _Requirements: 4.1_

- [ ] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using Hypothesis (Python backend) 
- The backend uses the existing `price_poller` pattern for the news background task
- Stub mode provides deterministic responses for development without LLM credentials
- Frontend properties (9, 10 from design) are covered implicitly by the component implementation and can be tested with fast-check if desired
