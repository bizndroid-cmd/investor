# Requirements: Multi-Portfolio Support

## Introduction

Enable users to maintain multiple portfolios across different geographies and brokers simultaneously. A user with stocks in both Groww (India) and Robinhood (US) sees them as separate portfolios with geo-appropriate analysis, while still viewing combined net worth.

## Glossary

- **Portfolio**: A named collection of holdings tied to one geography and one broker. Each user can have multiple portfolios.
- **Active Portfolio**: The currently selected portfolio in the frontend — all page content filters by this.
- **Combined View**: Aggregated metrics (total net worth) across all user portfolios, converted to a display currency.

## Requirements

### Requirement 1: Portfolio Entity

**User Story:** As a user with investments in multiple countries, I want to organize my holdings into separate portfolios per broker/geography.

#### Acceptance Criteria

1. THE system SHALL support a `portfolios` table with: id, user_id, name, geo_id, broker_id, is_default, created_at.
2. WHEN a user registers, THE system SHALL create one default portfolio with geo_id="IN" and name="My Portfolio".
3. A user SHALL be able to create additional portfolios with different geo_id values.
4. EACH portfolio SHALL be associated with exactly one geography and one primary broker.
5. THE system SHALL enforce that broker_id is compatible with the portfolio's geo_id (e.g., no Groww portfolio with geo="US").

### Requirement 2: Holdings Linked to Portfolio

**User Story:** As a user, I want each stock position to belong to a specific portfolio so analysis is geography-correct.

#### Acceptance Criteria

1. THE portfolio_snapshots table SHALL include a portfolio_id column linking each snapshot to a portfolio.
2. THE portfolio_daily_summary table SHALL include a portfolio_id column.
3. THE trade_history table SHALL include a portfolio_id column.
4. EXISTING data (no portfolio_id) SHALL default to the user's first/default portfolio during migration.
5. ALL portfolio-dependent queries SHALL filter by portfolio_id when an active portfolio is selected.

### Requirement 3: Portfolio Switching

**User Story:** As a user, I want to quickly switch between my portfolios without logging out.

#### Acceptance Criteria

1. THE frontend SHALL display a portfolio selector in the top bar showing the active portfolio name.
2. WHEN the user switches portfolios, THE frontend SHALL update all page data to reflect the selected portfolio's holdings, geography, and currency.
3. THE backend SHALL accept an optional `portfolio_id` query parameter on portfolio-dependent endpoints.
4. IF no portfolio_id is provided, THE system SHALL use the user's default portfolio.

### Requirement 4: Combined Net Worth

**User Story:** As a user with multiple portfolios, I want to see my total net worth across all portfolios.

#### Acceptance Criteria

1. THE portfolio page SHALL display a combined net worth card showing total value across all portfolios.
2. THE combined value SHALL convert each portfolio's value to the user's preferred display currency using approximate exchange rates.
3. THE combined view SHALL show portfolio count and per-portfolio breakdown.

### Requirement 5: Portfolio CRUD API

**User Story:** As a user, I want to create, rename, and delete portfolios.

#### Acceptance Criteria

1. THE system SHALL provide POST /portfolios to create a new portfolio (name, geo_id, broker_id).
2. THE system SHALL provide GET /portfolios to list all user portfolios.
3. THE system SHALL provide PUT /portfolios/{id} to rename or update a portfolio.
4. THE system SHALL provide DELETE /portfolios/{id} to delete a portfolio (with confirmation).
5. THE system SHALL NOT allow deletion of the last remaining portfolio.

### Requirement 6: Backward Compatibility

**User Story:** As an existing user, my current data and experience must not change.

#### Acceptance Criteria

1. EXISTING users SHALL have a default portfolio auto-created from their current data.
2. THE migration SHALL link all existing holdings/snapshots to this default portfolio.
3. SINGLE-portfolio users SHALL see no UI change (portfolio switcher hidden when only one portfolio exists).
4. ALL existing API endpoints SHALL continue working without portfolio_id parameter (uses default).
