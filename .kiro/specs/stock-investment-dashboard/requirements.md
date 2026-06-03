# Requirements Document

## Introduction

The Stock Investment Dashboard is a centralized web application that aggregates investment holdings across multiple stock brokers — Groww, Fidelity Investments, Zerodha, and Robinhood — into a single, unified view. It provides investors with a real-time snapshot of their portfolio, supports buy/sell actions, and surfaces trends, charts, and analytics to support informed decision-making. The system integrates with each broker's API to fetch live data and presents it through a clean, elegant frontend.

## Glossary

- **Dashboard**: The central frontend application that displays aggregated investment data.
- **Broker**: A stock brokerage platform (Groww, Fidelity, Zerodha, or Robinhood) whose API the system integrates with.
- **Broker_Connector**: The per-broker integration module responsible for authenticating and fetching data from a specific broker's API.
- **Aggregator**: The backend service that collects, normalizes, and merges holdings data from all connected Broker_Connectors.
- **Portfolio**: The combined set of stock holdings across all connected brokers for a given user.
- **Holding**: A single stock position (ticker symbol, quantity, average buy price, current value) held at a specific broker.
- **Order**: A buy or sell instruction submitted by the user for a specific stock at a specific broker.
- **Market_Data_Provider**: The service responsible for fetching current stock prices and historical price data.
- **Auth_Service**: The component managing user authentication and per-broker OAuth token storage.
- **Chart_Engine**: The frontend component responsible for rendering graphs, charts, and trend visualizations.
- **Notification_Service**: The component that delivers alerts and status updates to the user.

---

## Requirements

### Requirement 1: Broker Authentication and Connection

**User Story:** As an investor, I want to connect my brokerage accounts securely, so that the dashboard can access my holdings without storing my broker credentials.

#### Acceptance Criteria

1. THE Auth_Service SHALL support OAuth 2.0 authorization flows for Groww, Fidelity Investments, Zerodha, and Robinhood.
2. WHEN a user initiates a broker connection, THE Auth_Service SHALL redirect the user to the broker's authorization page and store the resulting access token and refresh token securely.
3. WHEN an access token expires, THE Auth_Service SHALL automatically refresh it using the stored refresh token without requiring user re-authentication.
4. IF a broker's OAuth authorization fails, THEN THE Auth_Service SHALL display a descriptive error message identifying the broker and the reason for failure.
5. THE Auth_Service SHALL allow a user to disconnect a broker account, which SHALL result in the deletion of all stored tokens for that broker.
6. WHILE a broker is connected, THE Dashboard SHALL display the connection status (connected, disconnected, or error) for each broker.

---

### Requirement 2: Holdings Aggregation

**User Story:** As an investor, I want to see all my stock holdings from every connected broker in one place, so that I can understand my total portfolio at a glance.

#### Acceptance Criteria

1. WHEN a user opens the Dashboard, THE Aggregator SHALL fetch current holdings from all connected Broker_Connectors and present a unified Portfolio view within 5 seconds.
2. THE Aggregator SHALL normalize holdings data from each broker into a common schema containing: ticker symbol, company name, quantity, average buy price, current market price, current value, and gain/loss percentage.
3. WHEN the same stock is held at multiple brokers, THE Dashboard SHALL display both the per-broker breakdown and the combined total position for that stock.
4. THE Dashboard SHALL display the total Portfolio value, total invested amount, total unrealized gain/loss (in currency and percentage), and the day's change in value.
5. IF a Broker_Connector fails to retrieve holdings data, THEN THE Aggregator SHALL display the last successfully fetched data for that broker alongside a staleness indicator showing the time of the last successful fetch.
6. THE Dashboard SHALL support manual refresh, triggering THE Aggregator to re-fetch holdings from all connected brokers.

---

### Requirement 3: Real-Time Market Data

**User Story:** As an investor, I want to see up-to-date stock prices on my dashboard, so that my portfolio valuation reflects current market conditions.

#### Acceptance Criteria

1. THE Market_Data_Provider SHALL fetch current market prices for all stocks in the Portfolio at an interval not exceeding 60 seconds during market hours.
2. WHILE market hours are active, THE Dashboard SHALL automatically update displayed prices and portfolio valuations without requiring a manual page refresh.
3. WHEN a stock price changes, THE Dashboard SHALL visually indicate the direction of the change (up or down) for a minimum of 3 seconds.
4. IF the Market_Data_Provider is unable to fetch a price for a stock, THEN THE Dashboard SHALL display the last known price alongside a staleness indicator.
5. THE Market_Data_Provider SHALL provide historical price data for each stock for time ranges of 1 day, 1 week, 1 month, 3 months, 1 year, and 5 years.

---

### Requirement 4: Portfolio Visualization

**User Story:** As an investor, I want to see charts and trend graphs of my portfolio, so that I can quickly understand performance and allocation at a glance.

#### Acceptance Criteria

1. THE Chart_Engine SHALL render a portfolio allocation chart showing the percentage breakdown of holdings by stock and by broker.
2. THE Chart_Engine SHALL render a portfolio value trend line chart showing the total Portfolio value over time for user-selectable time ranges: 1 day, 1 week, 1 month, 3 months, 1 year, and 5 years.
3. WHEN a user selects a specific Holding, THE Chart_Engine SHALL render a price history chart for that stock for the selected time range.
4. THE Chart_Engine SHALL render a gain/loss breakdown chart showing unrealized gain or loss per stock and per broker.
5. WHEN a user hovers over or taps a data point on any chart, THE Chart_Engine SHALL display a tooltip showing the exact value and date for that data point.
6. THE Dashboard SHALL allow the user to toggle between chart types (line chart, bar chart, and pie chart) for applicable visualizations.

---

### Requirement 5: Buy and Sell Order Placement

**User Story:** As an investor, I want to place buy and sell orders directly from the dashboard, so that I can act on investment decisions without switching to individual broker apps.

#### Acceptance Criteria

1. WHEN a user initiates a buy or sell action for a Holding, THE Dashboard SHALL present an order form pre-populated with the stock's ticker symbol and the target broker.
2. THE Dashboard SHALL support market orders and limit orders for both buy and sell actions.
3. WHEN a user submits an Order, THE Broker_Connector for the selected broker SHALL transmit the order to the broker's API and return a confirmation or rejection response within 10 seconds.
4. WHEN an Order is confirmed by the broker, THE Notification_Service SHALL display a success notification containing the order type, ticker symbol, quantity, and execution price.
5. IF an Order is rejected by the broker, THEN THE Notification_Service SHALL display an error notification containing the broker's rejection reason.
6. THE Dashboard SHALL display a transaction history showing all orders placed through the Dashboard, including status (pending, filled, rejected), timestamp, broker, ticker symbol, order type, quantity, and price.
7. WHILE an Order is pending, THE Dashboard SHALL display the order's pending status in the transaction history and update it automatically when the broker reports a status change.

---

### Requirement 6: Multi-Broker Comparison and Insights

**User Story:** As an investor, I want to compare my holdings and performance across brokers, so that I can identify consolidation opportunities and optimize my portfolio.

#### Acceptance Criteria

1. THE Dashboard SHALL display a side-by-side comparison view showing total value, total gain/loss, and number of holdings per broker.
2. WHEN a stock is held at more than one broker, THE Dashboard SHALL highlight the duplicate position and display the combined quantity and average cost basis.
3. THE Dashboard SHALL calculate and display the overall portfolio diversification score based on sector and asset allocation.
4. THE Dashboard SHALL display the top 5 performing and bottom 5 performing holdings by percentage gain/loss for the selected time range.
5. WHEN a user selects a time range, THE Dashboard SHALL update all performance metrics, charts, and rankings to reflect data for that time range.

---

### Requirement 7: Alerts and Notifications

**User Story:** As an investor, I want to set price alerts for stocks, so that I am notified when a stock reaches a target price.

#### Acceptance Criteria

1. THE Dashboard SHALL allow a user to create a price alert by specifying a ticker symbol, a target price, and a condition (price rises above or price falls below the target).
2. WHEN a stock's current price satisfies an active alert condition, THE Notification_Service SHALL deliver an in-app notification to the user within 60 seconds of the condition being met.
3. WHEN an alert is triggered, THE Notification_Service SHALL mark the alert as triggered and stop re-notifying for the same condition unless the user resets or modifies the alert.
4. THE Dashboard SHALL display a list of all active and triggered alerts, allowing the user to edit or delete each alert.
5. WHERE browser push notifications are enabled by the user, THE Notification_Service SHALL also deliver price alerts as browser push notifications.

---

### Requirement 8: Security and Data Privacy

**User Story:** As an investor, I want my financial data and broker credentials to be handled securely, so that my accounts and personal information are protected.

#### Acceptance Criteria

1. THE Auth_Service SHALL store all OAuth tokens in encrypted form using AES-256 encryption at rest.
2. THE Dashboard SHALL enforce HTTPS for all client-server communication.
3. THE Auth_Service SHALL implement session expiry, invalidating user sessions after 30 minutes of inactivity.
4. IF a user's session expires, THEN THE Auth_Service SHALL redirect the user to the login page and discard all in-memory token data.
5. THE Dashboard SHALL not log or persist raw OAuth access tokens in application logs.
6. THE Auth_Service SHALL support multi-factor authentication for Dashboard login.

---

### Requirement 9: Responsive and Accessible UI

**User Story:** As an investor, I want the dashboard to work well on both desktop and mobile devices, so that I can monitor my portfolio from anywhere.

#### Acceptance Criteria

1. THE Dashboard SHALL render correctly and remain fully functional on screen widths from 320px to 2560px.
2. THE Dashboard SHALL meet WCAG 2.1 Level AA accessibility standards, including sufficient color contrast, keyboard navigability, and screen reader compatibility.
3. WHEN the Dashboard is loaded on a screen width below 768px, THE Dashboard SHALL switch to a mobile-optimized layout that stacks components vertically and uses touch-friendly controls.
4. THE Chart_Engine SHALL render charts that are legible and interactive on touch-screen devices.
5. THE Dashboard SHALL load the initial Portfolio view within 3 seconds on a standard broadband connection (25 Mbps download).
