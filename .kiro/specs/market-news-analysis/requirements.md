# Requirements Document

## Introduction

The Market News Analysis feature adds an LLM-powered section to the Stock Investment Dashboard that aggregates and analyzes market news from Indian news sources. The system identifies news articles with potential impact on NSE/BSE stock prices — particularly those held in the user's portfolio — and classifies each item by its likely directional impact (bullish or bearish). This enables investors to stay informed about events that may affect their holdings without manually scanning multiple news sources.

## Glossary

- **News_Aggregator**: The backend service responsible for fetching raw news articles from configured news source APIs
- **News_Analyzer**: The LLM-powered service that processes raw news articles and determines their relevance and market impact
- **Impact_Classifier**: The component within News_Analyzer that assigns a directional sentiment (bullish, bearish, or neutral) and an impact magnitude (high, medium, low) to each news article
- **News_Feed**: The frontend UI section that displays analyzed news items to the user
- **Portfolio_Ticker**: A stock ticker symbol (e.g., RELIANCE, HDFCBANK, TCS) present in the user's current portfolio holdings
- **Sentiment_Score**: A classification indicating the expected directional market impact — one of bullish, bearish, or neutral
- **Impact_Level**: A classification indicating the magnitude of expected price impact — one of high, medium, or low
- **News_Item**: A structured representation of a news article containing title, source, publication date, summary, related tickers, sentiment score, and impact level
- **News_Source_API**: An external API providing market and financial news (e.g., NewsAPI, Google News, or similar services providing Indian market coverage)

## Requirements

### Requirement 1: Fetch Market News from External Sources

**User Story:** As an investor, I want the system to aggregate news from financial news sources, so that I have a centralized view of market-moving information.

#### Acceptance Criteria

1. WHEN a news fetch is triggered, THE News_Aggregator SHALL retrieve articles from at least one configured News_Source_API
2. THE News_Aggregator SHALL filter retrieved articles to include only those related to Indian equity markets (NSE/BSE), macroeconomic events impacting India, or sectors represented in the user's portfolio
3. IF a News_Source_API is unreachable or returns an error, THEN THE News_Aggregator SHALL log the failure and continue operating with remaining available sources
4. THE News_Aggregator SHALL store each retrieved article with its title, source name, publication timestamp, and raw content
5. WHEN fetching articles, THE News_Aggregator SHALL retrieve only articles published within the last 24 hours

### Requirement 2: Analyze News for Market Impact Using LLM

**User Story:** As an investor, I want news articles analyzed for their potential impact on stock prices, so that I can quickly understand which news matters to my investments.

#### Acceptance Criteria

1. WHEN new articles are available, THE News_Analyzer SHALL process each article through the configured LLM provider to determine its Sentiment_Score and Impact_Level
2. THE News_Analyzer SHALL extract and associate relevant stock ticker symbols (Portfolio_Tickers) mentioned or implied in each article
3. THE News_Analyzer SHALL generate a concise summary (maximum 200 characters) for each analyzed article explaining the potential market impact
4. IF the LLM provider is unavailable or returns an error, THEN THE News_Analyzer SHALL mark the article as unanalyzed and retry on the next analysis cycle
5. WHILE the LLM provider is configured as "stub", THE News_Analyzer SHALL return placeholder analysis responses with is_stub set to true

### Requirement 3: Classify News by Portfolio Relevance

**User Story:** As an investor, I want news prioritized by relevance to my holdings, so that I see the most important information first.

#### Acceptance Criteria

1. WHEN analyzed articles are available, THE Impact_Classifier SHALL assign a higher relevance score to articles that mention or relate to the user's Portfolio_Tickers
2. THE Impact_Classifier SHALL categorize each article into one of the following Sentiment_Scores: bullish, bearish, or neutral
3. THE Impact_Classifier SHALL assign one of the following Impact_Levels: high, medium, or low
4. WHEN an article relates to multiple Portfolio_Tickers, THE Impact_Classifier SHALL associate the article with each relevant ticker
5. THE Impact_Classifier SHALL rank articles by a combination of Impact_Level and portfolio relevance, placing high-impact portfolio-relevant articles first

### Requirement 4: Display News Feed in Dashboard

**User Story:** As an investor, I want a dedicated news section in my dashboard, so that I can browse analyzed market news alongside my portfolio.

#### Acceptance Criteria

1. THE News_Feed SHALL display analyzed news items in a scrollable list sorted by relevance ranking
2. THE News_Feed SHALL show for each News_Item: the title, source name, publication time, LLM-generated summary, Sentiment_Score indicator, and Impact_Level indicator
3. THE News_Feed SHALL visually distinguish bullish articles (green indicator), bearish articles (red indicator), and neutral articles (gray indicator)
4. WHEN a user clicks on a News_Item, THE News_Feed SHALL expand the item to show the full summary and list of related Portfolio_Tickers
5. THE News_Feed SHALL provide filter controls allowing the user to filter by Sentiment_Score, Impact_Level, or specific Portfolio_Ticker
6. WHILE news data is loading, THE News_Feed SHALL display a loading skeleton placeholder

### Requirement 5: Refresh News On Demand and Periodically

**User Story:** As an investor, I want news refreshed regularly and on demand, so that I always see the latest market-moving information.

#### Acceptance Criteria

1. THE News_Feed SHALL provide a manual refresh button that triggers a new news fetch and analysis cycle
2. WHEN the user triggers a manual refresh, THE News_Aggregator SHALL fetch and analyze new articles and update the News_Feed within 30 seconds
3. WHILE a refresh operation is in progress, THE News_Feed SHALL display a loading indicator on the refresh button
4. THE News_Aggregator SHALL automatically refresh news at a configurable interval (default: 30 minutes)
5. IF a refresh operation fails, THEN THE News_Feed SHALL display the last successfully loaded news with a stale data indicator showing the time of last successful refresh

### Requirement 6: News Analysis API Endpoint

**User Story:** As a frontend developer, I want a well-defined API endpoint for news data, so that I can integrate the news section into the dashboard.

#### Acceptance Criteria

1. THE News_Aggregator SHALL expose a GET endpoint that returns a paginated list of analyzed News_Items for the authenticated user
2. THE News_Aggregator SHALL accept optional query parameters for filtering by Sentiment_Score, Impact_Level, and ticker symbol
3. THE News_Aggregator SHALL return each News_Item with fields: id, title, source, published_at, summary, sentiment_score, impact_level, related_tickers, and analyzed_at
4. IF the user is not authenticated, THEN THE News_Aggregator SHALL return a 401 Unauthorized response
5. WHEN no analyzed news is available, THE News_Aggregator SHALL return an empty list with a 200 status code

### Requirement 7: Handle LLM Provider Configuration

**User Story:** As a system administrator, I want the news analysis to work with the existing LLM provider configuration, so that no additional setup is needed beyond the current LLM settings.

#### Acceptance Criteria

1. THE News_Analyzer SHALL use the same LLM provider and model configured via the existing LLM_PROVIDER environment variable
2. THE News_Analyzer SHALL integrate with the existing ILLMService interface pattern used by the application
3. WHILE the LLM provider is set to "stub", THE News_Analyzer SHALL return deterministic placeholder responses suitable for development and testing
4. WHEN switching between LLM providers, THE News_Analyzer SHALL function correctly without requiring news-specific configuration changes
