# Requirements Document

## Introduction

Multi-geography and multi-broker support for the stock investment dashboard. Currently hardcoded to Indian market (Groww broker, INR, NSE, screener.in, Indian RSS feeds, IST market hours). This feature abstracts geography-specific behavior behind provider interfaces so users from any country can use their local broker, currency, exchange, fundamentals source, and news feeds — while preserving full backward compatibility for existing Indian/Groww users.

## Glossary

- **Geography_Registry**: Backend registry that maps a geography identifier (e.g., "IN", "US") to its associated configuration: currency, exchanges, market hours, ticker suffix, fundamentals source, news feeds, sector map, and dividend norms.
- **User_Profile_Service**: Service responsible for storing and retrieving per-user preferences including geography, default broker, timezone, and currency.
- **Ticker_Resolver**: Component that converts a raw ticker symbol into the correct provider-specific format (e.g., appending ".NS" for NSE, ".L" for London, or no suffix for US exchanges).
- **Currency_Formatter**: Component that formats monetary values with the correct symbol, locale, decimal places, and number grouping for a given currency.
- **Fundamentals_Provider**: Abstract interface for fetching stock fundamentals (P/E, ROE, ROCE, market cap, etc.) from geography-specific sources.
- **News_Feed_Provider**: Abstract interface for fetching market news from geography-appropriate RSS feeds or news APIs.
- **Market_Hours_Service**: Component that determines whether a given exchange is currently open based on its timezone and trading schedule.
- **Sector_Classification_Provider**: Component that maps tickers to sector names based on geography-specific classification schemes.
- **Dashboard_Frontend**: The React-based frontend application that displays portfolio, prices, news, and analytics.
- **Aggregator_Service**: Backend service that orchestrates portfolio data across connected brokers for a user.

## Requirements

### Requirement 1: Geography Registry Configuration

**User Story:** As a developer, I want a centralized registry of geography configurations, so that adding a new geography requires only adding a new registry entry without modifying core logic.

#### Acceptance Criteria

1. THE Geography_Registry SHALL provide configuration for each supported geography including: currency code, currency symbol, currency locale, decimal places, supported exchanges, ticker suffix for yfinance, market open time, market close time, market timezone, trading days, fundamentals source identifier, news feed URLs, and sector classification map.
2. WHEN the application starts, THE Geography_Registry SHALL load configurations for "IN" (India) and "US" (United States) as built-in geographies.
3. THE Geography_Registry SHALL provide a lookup method that accepts a geography identifier and returns the full configuration object for that geography.
4. IF a lookup is requested for an unsupported geography identifier, THEN THE Geography_Registry SHALL raise a descriptive error indicating the geography is not registered.
5. THE Geography_Registry SHALL define the "IN" geography with: currency_code="INR", currency_symbol="₹", exchanges=["NSE", "BSE"], yfinance_suffix=".NS", market_open="09:15", market_close="15:30", timezone="Asia/Kolkata", trading_days=[Monday-Friday], fundamentals_source="screener", dividend_frequency="annual".
6. THE Geography_Registry SHALL define the "US" geography with: currency_code="USD", currency_symbol="$", exchanges=["NYSE", "NASDAQ"], yfinance_suffix="", market_open="09:30", market_close="16:00", timezone="America/New_York", trading_days=[Monday-Friday], fundamentals_source="yfinance", dividend_frequency="quarterly".

### Requirement 2: User Geography Preferences

**User Story:** As a user, I want to configure my preferred geography and broker, so that the dashboard displays market data relevant to my region.

#### Acceptance Criteria

1. THE User_Profile_Service SHALL store per-user preferences including: geography identifier, default broker identifier, timezone, and preferred currency code.
2. WHEN a new user registers without specifying a geography, THE User_Profile_Service SHALL default the geography to "IN" to maintain backward compatibility.
3. WHEN a user updates their geography preference, THE User_Profile_Service SHALL persist the change and invalidate any cached data that depends on geography (price cache, fundamentals cache, news cache).
4. THE User_Profile_Service SHALL expose an API endpoint (PUT /api/user/preferences) that accepts geography, default_broker, timezone, and currency fields.
5. THE User_Profile_Service SHALL expose an API endpoint (GET /api/user/preferences) that returns the current user preferences.
6. IF a user sets a geography that does not exist in the Geography_Registry, THEN THE User_Profile_Service SHALL reject the request with a 400 status code and a descriptive error message.

### Requirement 3: Ticker Resolution

**User Story:** As a developer, I want tickers automatically resolved to their exchange-specific format, so that price fetching works correctly across geographies without manual suffix management.

#### Acceptance Criteria

1. WHEN the Ticker_Resolver receives a raw ticker and a geography identifier, THE Ticker_Resolver SHALL append the appropriate yfinance suffix from the Geography_Registry for that geography.
2. WHEN the Ticker_Resolver resolves a ticker for geography "IN", THE Ticker_Resolver SHALL append ".NS" to produce the yfinance symbol.
3. WHEN the Ticker_Resolver resolves a ticker for geography "US", THE Ticker_Resolver SHALL return the ticker unchanged (empty suffix).
4. THE Ticker_Resolver SHALL accept an optional explicit exchange parameter that overrides the default suffix (e.g., ".BO" for BSE instead of ".NS" for NSE).
5. FOR ALL valid ticker-geography pairs, resolving a ticker then stripping the suffix SHALL produce the original ticker (round-trip property).

### Requirement 4: Currency Formatting

**User Story:** As a user, I want all monetary values displayed in my local currency format, so that I can read portfolio values naturally.

#### Acceptance Criteria

1. THE Currency_Formatter SHALL format monetary values using the currency symbol, decimal places, and thousands separator appropriate for the specified currency code.
2. WHEN formatting for currency "INR", THE Currency_Formatter SHALL use symbol "₹", 2 decimal places, and Indian numbering system grouping (lakh/crore: 1,00,000).
3. WHEN formatting for currency "USD", THE Currency_Formatter SHALL use symbol "$", 2 decimal places, and Western numbering system grouping (1,000,000).
4. THE Dashboard_Frontend SHALL read the user's preferred currency from the User_Profile_Service and use it for all monetary value displays.
5. THE Dashboard_Frontend SHALL render currency formatting on the client side using the Intl.NumberFormat API with the appropriate locale and currency parameters.
6. FOR ALL non-negative numeric values and valid currency codes, formatting then parsing the formatted string SHALL produce a value equal to the original within rounding tolerance (round-trip property).

### Requirement 5: Market Hours Awareness

**User Story:** As a user, I want the system to know when my market is open, so that price caching and refresh intervals are optimized for my exchange.

#### Acceptance Criteria

1. WHEN determining cache TTL for price data, THE Market_Hours_Service SHALL use the market hours and timezone from the Geography_Registry for the user's configured geography.
2. WHILE the user's configured exchange is within trading hours, THE Market_Hours_Service SHALL report the market as open and use a short cache TTL (30 seconds).
3. WHILE the user's configured exchange is outside trading hours, THE Market_Hours_Service SHALL report the market as closed and use a long cache TTL (5 minutes).
4. THE Market_Hours_Service SHALL account for the exchange's timezone when determining open/closed status, converting current UTC time to the exchange's local time.
5. THE Market_Hours_Service SHALL exclude non-trading days (weekends per the geography's configured trading_days) from open-market calculations.

### Requirement 6: Fundamentals Data Provider Abstraction

**User Story:** As a user, I want to view stock fundamentals regardless of which market I invest in, so that I can make informed decisions.

#### Acceptance Criteria

1. THE Fundamentals_Provider interface SHALL define methods: fetch_fundamentals(ticker, geography) returning a standardized fundamentals dictionary, and get_cached_fundamentals(ticker) returning stored data.
2. WHEN the user's geography is "IN", THE system SHALL use the screener.in scraper (existing ScreenerService) as the Fundamentals_Provider implementation.
3. WHEN the user's geography is "US", THE system SHALL use yfinance info data as the Fundamentals_Provider implementation, extracting P/E ratio, book value, dividend yield, ROE, and market cap from the Ticker.info dictionary.
4. THE Fundamentals_Provider SHALL return a common schema regardless of source: ticker, market_cap, pe_ratio, book_value, dividend_yield, roe, roce (null if unavailable), and fetched_at timestamp.
5. IF a fundamentals field is not available from the geography's data source, THEN THE Fundamentals_Provider SHALL set that field to null rather than omitting it.

### Requirement 7: News Feed Provider Abstraction

**User Story:** As a user, I want market news from sources relevant to my geography, so that the news feed shows actionable information for my portfolio.

#### Acceptance Criteria

1. THE News_Feed_Provider interface SHALL define a method: fetch_articles(geography, portfolio_tickers) returning a list of RawNewsArticle objects.
2. WHEN the user's geography is "IN", THE News_Feed_Provider SHALL fetch from Indian financial RSS feeds (Economic Times, LiveMint, Moneycontrol) matching the current implementation.
3. WHEN the user's geography is "US", THE News_Feed_Provider SHALL fetch from US financial news sources appropriate for NYSE/NASDAQ stocks.
4. THE News_Feed_Provider SHALL tag each article with the geography it was sourced from.
5. THE NewsAggregator SHALL select the News_Feed_Provider implementation based on the requesting user's configured geography.

### Requirement 8: Sector Classification per Geography

**User Story:** As a user, I want my portfolio's sector analysis to use the correct sector classifications for my market, so that concentration risk analysis is accurate.

#### Acceptance Criteria

1. THE Sector_Classification_Provider SHALL maintain separate sector maps per geography.
2. WHEN determining the sector for a ticker, THE Sector_Classification_Provider SHALL use the sector map corresponding to the user's geography.
3. THE Sector_Classification_Provider SHALL return "other" for tickers not found in the geography's sector map.
4. THE "IN" sector map SHALL contain Indian stock sector mappings (matching the existing SECTOR_MAP in intelligence_service.py).
5. THE "US" sector map SHALL contain US stock sector mappings for major S&P 500 constituents.
6. WHEN a ticker is not found in the primary sector map, THE Sector_Classification_Provider SHALL attempt to look up the sector from the fundamentals data source as a fallback.

### Requirement 9: Broker Connector Geography Binding

**User Story:** As a developer, I want each broker connector to declare its supported geographies, so that the system only offers users brokers valid for their region.

#### Acceptance Criteria

1. THE IBrokerConnector interface SHALL include a supported_geographies attribute listing the geography identifiers where that broker operates.
2. THE Groww connector SHALL declare supported_geographies=["IN"].
3. THE Robinhood connector SHALL declare supported_geographies=["US"].
4. WHEN listing available brokers for a user, THE Aggregator_Service SHALL filter broker connectors to those whose supported_geographies include the user's configured geography.
5. IF a user attempts to connect a broker that does not support their configured geography, THEN THE system SHALL reject the connection request with a descriptive error.

### Requirement 10: Market Data Service Geography Awareness

**User Story:** As a developer, I want the market data service to resolve tickers and determine market hours based on the user's geography, so that price fetching works correctly for any supported market.

#### Acceptance Criteria

1. WHEN fetching a current price via yfinance fallback, THE MarketDataService SHALL use the Ticker_Resolver to produce the correct yfinance symbol based on the user's geography rather than hardcoding the ".NS" suffix.
2. WHEN determining cache TTL, THE MarketDataService SHALL delegate to the Market_Hours_Service with the user's geography rather than using the hardcoded US market hours check.
3. WHEN fetching batch prices via the Groww LTP API, THE MarketDataService SHALL only use the Groww LTP path for users whose geography is "IN" and fall back to Finnhub/yfinance for other geographies.
4. WHEN fetching historical data, THE MarketDataService SHALL pass the geography-resolved ticker (via Ticker_Resolver) to yfinance download.

### Requirement 11: Technical Analysis Geography Awareness

**User Story:** As a user, I want technical analysis indicators computed for my stocks regardless of geography, so that I get the same analytical quality on any exchange.

#### Acceptance Criteria

1. WHEN computing technical indicators, THE TechnicalAnalysisService SHALL use the Ticker_Resolver to produce the correct yfinance symbol rather than hardcoding the ".NS" suffix.
2. THE TechnicalAnalysisService SHALL accept a geography parameter (or resolve it from user context) to determine the correct ticker format.
3. THE technical analysis computation logic (SMA, RSI, MACD, Bollinger Bands, ATR, Support/Resistance) SHALL remain unchanged regardless of geography — only the ticker resolution differs.

### Requirement 12: Backward Compatibility

**User Story:** As an existing Indian/Groww user, I want my dashboard to continue working exactly as before without any action on my part, so that this upgrade does not disrupt my workflow.

#### Acceptance Criteria

1. WHEN a user has no explicit geography preference stored, THE system SHALL default all geography-dependent behavior to "IN" (India).
2. THE existing Groww connector, ScreenerService, Indian RSS feeds, IST market hours, and INR currency formatting SHALL continue to function identically for users with geography "IN".
3. THE database migration for user preferences SHALL add a geography column with default value "IN" so existing users require no data migration action.
4. THE existing API endpoints SHALL continue to return the same response structure — geography-specific data SHALL be additive, not breaking.
5. WHEN the system starts with no geography-related environment variables configured, THE system SHALL operate in India-only mode matching current behavior.

### Requirement 13: Frontend Geography-Aware Display

**User Story:** As a user, I want the frontend to adapt its display based on my geography, so that currency symbols, number formatting, and market status reflect my local context.

#### Acceptance Criteria

1. WHEN rendering monetary values, THE Dashboard_Frontend SHALL use the Currency_Formatter with the user's preferred currency rather than hardcoding "₹".
2. WHEN displaying market status (open/closed), THE Dashboard_Frontend SHALL show the status for the user's configured exchange based on Market_Hours_Service.
3. WHEN displaying sector analysis, THE Dashboard_Frontend SHALL label sectors according to the user's geography's sector classification.
4. THE Dashboard_Frontend SHALL fetch user preferences on login and store the geography context in application state for use by all display components.
5. THE Dashboard_Frontend SHALL provide a settings UI where users can select their geography from the list of supported geographies in the Geography_Registry.

### Requirement 14: Dividend Frequency Norms

**User Story:** As a user, I want dividend yield calculations and projections to account for my market's typical dividend frequency, so that income estimates are accurate.

#### Acceptance Criteria

1. THE Geography_Registry SHALL include a dividend_frequency field for each geography specifying the typical distribution schedule ("annual" for India, "quarterly" for US).
2. WHEN projecting annual dividend income, THE system SHALL use the geography's dividend_frequency to annualize the reported yield correctly.
3. WHEN displaying dividend information in the briefing or fundamentals view, THE system SHALL indicate the expected payment frequency based on the user's geography.
