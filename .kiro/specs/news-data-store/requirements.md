# Requirements Document

## Introduction

The News Data Store feature transitions the stock investment dashboard from frequent live API polling (every 30 minutes) to a scheduled daily collection model. News articles are fetched once or twice per day from Indian financial RSS feeds and persisted in the database with date-stamped historical records. The stored news powers the daily portfolio briefing via the LLM, replacing the current live-fetch approach. The historical news archive also lays the groundwork for future LLM-driven pattern detection and portfolio movement prediction.

## Glossary

- **News_Poller**: The background task responsible for scheduling and executing periodic news fetch cycles
- **News_Data_Store**: The persistent database layer that stores news articles with date stamps for historical retrieval
- **Daily_Collection_Schedule**: The configurable schedule defining when news fetches occur, defaulting to twice per day (morning and evening)
- **Collection_Date**: The calendar date associated with a batch of fetched news articles, enabling date-based historical queries
- **Briefing_Generator**: The service component that reads stored news from the News_Data_Store and passes it to the LLM for portfolio briefing generation
- **News_Aggregator**: The existing service that fetches raw news articles from Indian financial RSS feeds (Economic Times, LiveMint, Moneycontrol)
- **Portfolio_Ticker**: A stock ticker symbol present in the user's current portfolio holdings
- **Historical_News_Window**: A configurable duration (default 90 days) defining how far back historical news data is retained for pattern analysis
- **Collection_Run**: A single execution of the news fetching process, recording metadata about what was fetched and when

## Requirements

### Requirement 1: Reduce News Polling Frequency to Daily Schedule

**User Story:** As a system operator, I want news fetched only once or twice per day instead of every 30 minutes, so that external API usage is minimized and the system operates within free-tier rate limits.

#### Acceptance Criteria

1. THE News_Poller SHALL execute news fetch cycles according to the Daily_Collection_Schedule, defaulting to two runs per day
2. WHEN the Daily_Collection_Schedule specifies two runs, THE News_Poller SHALL execute the first run in the morning (default 07:00 IST) and the second run in the evening (default 18:00 IST)
3. THE News_Poller SHALL accept a configurable environment variable NEWS_COLLECTION_TIMES that defines the scheduled run times as a comma-separated list of HH:MM values in IST
4. WHEN the application starts after a missed scheduled run, THE News_Poller SHALL execute a catch-up fetch within 5 minutes of startup
5. IF a scheduled fetch fails, THEN THE News_Poller SHALL retry up to 3 times with exponential backoff starting at 60 seconds

### Requirement 2: Store News Articles with Date-Stamped Historical Records

**User Story:** As a system, I want all fetched news articles stored with their collection date, so that historical data accumulates for future analysis and briefing generation.

#### Acceptance Criteria

1. WHEN articles are fetched during a Collection_Run, THE News_Data_Store SHALL persist each article with a Collection_Date representing the calendar date of the fetch
2. THE News_Data_Store SHALL record metadata for each Collection_Run including: start time, end time, number of articles fetched, number of articles stored (deduplicated), and completion status
3. THE News_Data_Store SHALL deduplicate articles within the same Collection_Date by matching on title and source name, preventing duplicate storage from multiple runs on the same day
4. THE News_Data_Store SHALL retain historical news articles for at least the configured Historical_News_Window (default 90 days)
5. THE News_Data_Store SHALL support querying articles by Collection_Date, by date range, by ticker, and by source name
6. WHEN an article is stored, THE News_Data_Store SHALL associate the article with related Portfolio_Tickers identified from the article content

### Requirement 3: Power Daily Briefing from Stored News Data

**User Story:** As an investor, I want my daily portfolio briefing generated from stored news data rather than live fetches, so that briefings are fast, reliable, and not dependent on external API availability at request time.

#### Acceptance Criteria

1. WHEN a user requests a portfolio briefing, THE Briefing_Generator SHALL retrieve analyzed articles from the News_Data_Store for the current Collection_Date
2. THE Briefing_Generator SHALL pass only articles relevant to the user's Portfolio_Tickers to the LLM for briefing generation
3. IF no articles exist for the current Collection_Date, THEN THE Briefing_Generator SHALL fall back to articles from the most recent Collection_Date that has data
4. THE Briefing_Generator SHALL include the Collection_Date timestamp in the briefing response so the user knows the recency of the underlying data
5. WHILE the LLM provider is configured as "stub", THE Briefing_Generator SHALL return a placeholder briefing using stored article titles and summaries without making LLM calls

### Requirement 4: Design Storage for Future LLM Pattern Analysis

**User Story:** As a product owner, I want historical news stored in a structure that supports future LLM-based pattern detection, so that the system can eventually predict portfolio movement trends from accumulated news data.

#### Acceptance Criteria

1. THE News_Data_Store SHALL maintain a date-indexed archive of all articles associated with each Portfolio_Ticker across Collection_Dates
2. THE News_Data_Store SHALL store sentiment scores and impact levels alongside articles to enable trend queries without re-analysis
3. THE News_Data_Store SHALL support querying the sentiment distribution (count of bullish, bearish, neutral) for a given ticker over a specified date range
4. THE News_Data_Store SHALL support querying a chronological sequence of articles for a given ticker ordered by Collection_Date for time-series pattern input
5. THE News_Data_Store SHALL index articles by Collection_Date and related tickers to enable efficient historical range queries across 90 days of data

### Requirement 5: Manage Collection Run Lifecycle and Observability

**User Story:** As a system operator, I want visibility into when news was last collected and whether collections are succeeding, so that I can diagnose issues and trust the data freshness.

#### Acceptance Criteria

1. THE News_Poller SHALL record each Collection_Run with a status of "started", "completed", or "failed"
2. WHEN a Collection_Run completes, THE News_Poller SHALL log the count of articles fetched, the count stored after deduplication, and the total duration
3. THE News_Data_Store SHALL expose an API endpoint that returns the status of the most recent Collection_Run including its timestamp and article counts
4. IF no successful Collection_Run has occurred within the past 24 hours, THEN THE News_Data_Store SHALL mark the news data as stale in the collection status response
5. WHEN a manual refresh is triggered via the existing POST /news/refresh endpoint, THE News_Poller SHALL execute an immediate Collection_Run outside the Daily_Collection_Schedule

### Requirement 6: Migrate Existing Polling Infrastructure

**User Story:** As a developer, I want the existing 30-minute polling infrastructure updated to the new daily schedule, so that there is a single consistent news collection mechanism.

#### Acceptance Criteria

1. THE News_Poller SHALL replace the current 30-minute asyncio.sleep loop with a schedule-aware execution model that runs at configured times
2. THE News_Poller SHALL retain the existing per-user portfolio ticker resolution to fetch relevant news for each user's holdings
3. THE News_Poller SHALL continue using the existing NewsAggregator service for RSS feed fetching and the NewsAnalyzer service for LLM analysis
4. WHEN the NEWS_COLLECTION_TIMES environment variable is not set, THE News_Poller SHALL default to two daily runs at 07:00 and 18:00 IST
5. THE News_Poller SHALL update the existing news_poll_interval configuration to reflect the new scheduling approach, deprecating the interval-based setting
