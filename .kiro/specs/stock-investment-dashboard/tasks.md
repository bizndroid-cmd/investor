# Implementation Plan: Stock Investment Dashboard

## Overview

Incremental implementation of the full-stack Stock Investment Dashboard. The backend is Python 3.11+ / FastAPI (async) with PostgreSQL + Redis; the frontend is React 18 + TypeScript + Vite + shadcn/ui + Recharts. Tasks are ordered so each step produces runnable, integrated code before the next step begins. Property-based tests (Hypothesis) are placed immediately after the logic they validate.

---

## Tasks

- [x] 1. Project scaffolding and shared configuration
  - Create the monorepo directory layout: `backend/`, `frontend/`, `infra/`
  - Add `backend/pyproject.toml` with pinned dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `alembic`, `asyncpg`, `redis[hiredis]`, `pydantic[email]`, `python-jose[cryptography]`, `passlib[bcrypt]`, `pyotp`, `cryptography`, `httpx`, `finnhub-python`, `yfinance`, `robin_stocks`, `kiteconnect`, `snaptrade`, `langchain-core`, `langchain-openai`, `langchain-anthropic`, `langchain-ollama`, `hypothesis`, `pytest`, `pytest-asyncio`, `testcontainers[postgres,redis]`
  - Add `frontend/package.json` with pinned dependencies: `react@18`, `typescript`, `vite`, `@tanstack/react-query@5`, `zustand`, `recharts`, `@playwright/test`, `axe-playwright`; initialise shadcn/ui
  - Add root `docker-compose.yml` spinning up `postgres:16` and `redis:7`
  - Add `.env.example` documenting all required environment variables (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, `LLM_PROVIDER`, broker API keys, `FINNHUB_API_KEY`)
  - _Requirements: 8.1, 8.2_

- [x] 2. Database schema and migrations
  - [x] 2.1 Write SQLAlchemy 2.0 async ORM models for `users`, `broker_tokens`, `holdings_cache`, `orders`, `alerts`, `sessions` tables matching the schema in the design document
    - Place models in `backend/models/`; use `mapped_column` / `Mapped` typed annotations
    - _Requirements: 1.2, 2.2, 5.6, 7.1, 8.1_
  - [x] 2.2 Create Alembic initial migration from the ORM models
    - Configure `alembic.ini` and `env.py` for async engine
    - _Requirements: 1.2, 5.6_

- [x] 3. Core domain types and interfaces
  - [x] 3.1 Implement all Pydantic v2 domain models (`NormalizedHolding`, `Portfolio`, `PriceQuote`, `HistoricalDataPoint`, `OrderRequest`, `Order`, `Alert`, `BrokerStatus`, `AuthTokens`, `Session`, `MFASetupData`, `RawHolding`, `RawOrder`, `OrderResult`, `RefreshResult`, `TriggeredAlert`) in `backend/models/domain.py`
    - _Requirements: 2.2, 2.4, 5.1, 7.1_
  - [x] 3.2 Implement all service ABCs (`IBrokerConnector`, `IAuthService`, `IAggregatorService`, `IMarketDataService`, `IOrderService`, `IAlertService`, `ILLMService`) in `backend/interfaces/`
    - _Requirements: 1.1, 2.1, 3.1, 5.3, 7.2_

- [x] 4. Token encryption utility
  - [x] 4.1 Implement `backend/utils/encryption.py` with `encrypt_token(plaintext: str) -> tuple[str, str, str]` and `decrypt_token(ciphertext: str, iv: str, tag: str) -> str` using AES-256-GCM via the `cryptography` library
    - _Requirements: 8.1_
  - [ ]* 4.2 Write property test for token encryption round-trip
    - **Property 9: Token encryption round-trip is lossless**
    - Generate arbitrary token strings with `st.text()` (Unicode, special chars, empty, long)
    - Assert `decrypt_token(*encrypt_token(token)) == token` byte-for-byte
    - **Validates: Requirements 8.1**

- [x] 5. Authentication service
  - [x] 5.1 Implement `backend/services/auth_service.py` (`AuthService` implementing `IAuthService`): `register`, `login`, `logout`, `refresh_session`, `setup_mfa`, `verify_mfa`, `get_session`
    - Use `passlib[bcrypt]` for password hashing, `python-jose` for JWT (access token 15 min, refresh token 7 days), `pyotp` for TOTP
    - Persist sessions in `sessions` table; track inactivity via `session:active:{sessionId}` Redis key (TTL 30 min)
    - _Requirements: 1.1, 8.3, 8.4, 8.6_
  - [x] 5.2 Implement FastAPI auth router (`backend/routers/auth.py`): `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/refresh`, `POST /auth/mfa/setup`, `POST /auth/mfa/verify`
    - _Requirements: 1.1, 8.6_
  - [ ]* 5.3 Write property test for session expiry logic
    - **Property 10: Session expiry is determined solely by inactivity duration**
    - Generate arbitrary `(last_active, now)` datetime pairs with `st.datetimes()`
    - Assert `is_session_expired(last_active, now) == ((now - last_active) > timedelta(minutes=30))`
    - **Validates: Requirements 8.3**

- [x] 6. Checkpoint — auth layer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Broker connector infrastructure
  - [x] 7.1 Implement `backend/utils/broker_token_store.py`: async helpers to read/write/delete encrypted broker tokens from `broker_tokens` table using the encryption utility from task 4
    - _Requirements: 1.2, 1.3, 8.1_
  - [x] 7.2 Implement the Groww connector (`backend/connectors/groww.py`) implementing `IBrokerConnector`
    - Auth: API Key + TOTP via `api.groww.in/v1`; implement `get_authorization_url`, `exchange_code_for_tokens`, `refresh_tokens`, `revoke_tokens`, `is_connected`, `get_holdings`, `get_orders`, `place_order`, `cancel_order`
    - _Requirements: 1.1, 1.2, 1.3, 2.2, 5.3_
  - [x] 7.3 Implement the Zerodha connector (`backend/connectors/zerodha.py`) implementing `IBrokerConnector`
    - Auth: Kite Connect v3 OAuth 2.0 (`request_token` → `access_token`); use `kiteconnect` library
    - _Requirements: 1.1, 1.2, 1.3, 2.2, 5.3_
  - [x] 7.4 Implement the Fidelity connector (`backend/connectors/fidelity.py`) implementing `IBrokerConnector`
    - Auth: SnapTrade OAuth 2.0; use `snaptrade` SDK
    - _Requirements: 1.1, 1.2, 1.3, 2.2, 5.3_
  - [x] 7.5 Implement the Robinhood connector (`backend/connectors/robinhood.py`) implementing `IBrokerConnector`
    - Auth: `robin_stocks` username + password + TOTP MFA; runs in-process (no sidecar)
    - _Requirements: 1.1, 1.2, 1.3, 2.2, 5.3_
  - [x] 7.6 Implement broker router (`backend/routers/brokers.py`): `GET /brokers`, `POST /brokers/{broker_id}/connect`, `GET /brokers/{broker_id}/callback`, `DELETE /brokers/{broker_id}`
    - _Requirements: 1.1, 1.4, 1.5, 1.6_

- [x] 8. Holdings aggregation and normalization
  - [x] 8.1 Implement `backend/services/aggregator_service.py` (`AggregatorService` implementing `IAggregatorService`)
    - `normalize_holding(raw: RawHolding, broker_id: BrokerId) -> NormalizedHolding`: maps each broker's raw schema to the common domain model
    - `get_portfolio`: fetches from all connected connectors concurrently (`asyncio.gather`), normalizes, enriches with current prices, computes portfolio summary math, caches in Redis (`holdings:{userId}:{brokerId}`, TTL 5 min)
    - On connector failure: return last cached holdings with `is_stale=True` and update `broker_tokens.status` to `'error'`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
  - [ ]* 8.2 Write property test for holdings normalization
    - **Property 1: Holdings normalization preserves all required fields**
    - Generate `RawHolding` instances for each broker schema with `st.builds()`
    - Assert all required fields present and `quantity` / `avg_buy_price` numerically equal to raw values
    - **Validates: Requirements 2.2**
  - [ ]* 8.3 Write property test for portfolio summary math invariants
    - **Property 2: Portfolio summary math invariants**
    - Generate arbitrary `list[NormalizedHolding]` with `st.lists(st.builds(NormalizedHolding, ...), min_size=1)`
    - Assert `total_value`, `total_invested`, `total_gain_loss`, `total_gain_loss_percent` satisfy all four invariants simultaneously
    - **Validates: Requirements 2.4**
  - [ ]* 8.4 Write property test for combined position aggregation
    - **Property 3: Combined position aggregation is correct**
    - Generate holdings for the same ticker across multiple brokers
    - Assert combined quantity equals sum of individual quantities; combined avg cost basis equals quantity-weighted average
    - **Validates: Requirements 2.3, 6.2**
  - [ ]* 8.5 Write property test for stale data timestamp invariant
    - **Property 4: Stale data indicator never shows a future timestamp**
    - Generate arbitrary `(last_fetched_at, now)` pairs with `st.datetimes()`
    - Assert staleness duration `>= 0` and displayed timestamp `<= now`
    - **Validates: Requirements 2.5, 3.4**
  - [x] 8.6 Implement aggregator router (`backend/routers/portfolio.py`): `GET /portfolio`, `GET /portfolio/holdings`, `POST /portfolio/refresh`
    - _Requirements: 2.1, 2.3, 2.4, 2.6_

- [x] 9. Checkpoint — aggregation layer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Market data service
  - [x] 10.1 Implement `backend/services/market_data_service.py` (`MarketDataService` implementing `IMarketDataService`)
    - `get_current_price`: check Redis cache (`price:{ticker}`, TTL 30 s market hours / 5 min off-hours); on miss, call Finnhub REST; on Finnhub error/429, return last cached value with `is_stale=True`
    - `get_batch_prices`: fan-out to `get_current_price` concurrently; respect Finnhub 60 req/min rate limit via Redis counter (`ratelimit:finnhub:{minute}`)
    - `get_historical_data`: call yfinance for ranges `1d`–`5y`; surface empty list on failure
    - _Requirements: 3.1, 3.4, 3.5_
  - [x] 10.2 Implement market data router (`backend/routers/market_data.py`): `GET /market/price/{ticker}`, `POST /market/prices/batch`, `GET /market/history/{ticker}?range=`
    - _Requirements: 3.1, 3.5_

- [x] 11. WebSocket price broadcast
  - [x] 11.1 Implement `backend/services/websocket_manager.py`: connection registry keyed by `user_id`; `subscribe(user_id, tickers)`, `broadcast_price_update(ticker, quote)`, `broadcast_order_update(user_id, order)`
    - _Requirements: 3.2, 5.7_
  - [x] 11.2 Implement FastAPI WebSocket endpoint (`backend/routers/ws.py`): `WS /ws` — authenticate via token query param, register connection, handle subscribe/unsubscribe messages
    - _Requirements: 3.2, 3.3_
  - [x] 11.3 Implement background price polling task (`backend/tasks/price_poller.py`): runs every 30 seconds via `asyncio` background task; fetches batch prices for all tickers held by connected users; fans out updates via `WebSocketManager`; updates Redis cache
    - _Requirements: 3.1, 3.2_

- [x] 12. Alert service
  - [x] 12.1 Implement `backend/services/alert_service.py` (`AlertService` implementing `IAlertService`)
    - `create_alert`, `update_alert`, `delete_alert`, `get_alerts`: CRUD against `alerts` table; maintain `alerts:active:{ticker}` Redis set
    - `evaluate_alerts(ticker, current_price)`: load active alert IDs from Redis set; for each, check condition; if triggered, update `alerts.status` to `'triggered'`, set `triggered_at`, remove from Redis set, emit notification
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [ ]* 12.2 Write property test for alert condition evaluation
    - **Property 5: Alert condition evaluation is consistent**
    - Generate arbitrary `(price, target_price, condition)` triples with `st.decimals()` and `st.sampled_from(["above", "below"])`
    - Assert `should_trigger(price, target_price, "above") == (price > target_price)` and `should_trigger(price, target_price, "below") == (price < target_price)`
    - **Validates: Requirements 7.1, 7.2**
  - [ ]* 12.3 Write property test for triggered alert idempotency
    - **Property 6: Triggered alert is not re-triggered without reset**
    - Generate an alert and a sequence of arbitrary price updates with `st.lists(st.decimals())`
    - Assert that after the first trigger, no subsequent evaluation produces a trigger until the alert is explicitly reset
    - **Validates: Requirements 7.3**
  - [x] 12.4 Integrate `evaluate_alerts` into the price polling task (task 11.3) so alerts are checked on every price tick
    - _Requirements: 7.2_
  - [x] 12.5 Implement alerts router (`backend/routers/alerts.py`): `GET /alerts`, `POST /alerts`, `PATCH /alerts/{alert_id}`, `DELETE /alerts/{alert_id}`
    - _Requirements: 7.1, 7.4_

- [x] 13. Order service
  - [x] 13.1 Implement `backend/services/order_service.py` (`OrderService` implementing `IOrderService`)
    - `place_order`: idempotency check (duplicate pending order within 10 s); delegate to broker connector; persist to `orders` table; emit WebSocket order update; retry once on network error (500 ms then 1000 ms backoff)
    - `get_order_history`: query `orders` table with optional filters
    - `get_order_status`: fetch single order by ID
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 5.7_
  - [ ]* 13.2 Write property test for order history round-trip
    - **Property 7: Order history round-trip preserves all fields**
    - Generate arbitrary `OrderRequest` objects with `st.builds(OrderRequest, ...)`
    - Persist via `OrderService` (mock async DB session) and retrieve by ID
    - Assert `broker_id`, `ticker`, `side`, `order_type`, `quantity`, `limit_price` are identical
    - **Validates: Requirements 5.6**
  - [ ]* 13.3 Write property test for order notification completeness
    - **Property 8: Order notification contains all required fields**
    - Generate arbitrary confirmed and rejected order objects
    - Assert confirmed notifications contain `order_type`, `ticker`, `quantity`, `execution_price`; rejected notifications contain `rejection_reason`
    - **Validates: Requirements 5.4, 5.5**
  - [x] 13.4 Implement orders router (`backend/routers/orders.py`): `POST /orders`, `GET /orders`, `GET /orders/{order_id}`
    - _Requirements: 5.1, 5.2, 5.6, 5.7_

- [x] 14. Checkpoint — backend services
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. LLM service stub
  - [x] 15.1 Implement `backend/services/llm_service.py` (`LLMService` implementing `ILLMService`) with stub responses for all four methods (`analyze_portfolio`, `answer_natural_language_query`, `generate_trade_recommendation`, `summarize_alerts`)
    - Wire provider selection via `LLM_PROVIDER` env var using LangChain (`ChatOpenAI`, `ChatAnthropic`, `ChatOllama`, `StubLLM`)
    - Stub always returns `is_stub=True` and never raises exceptions
    - _Requirements: (future LLM integration — scaffolded per design)_
  - [ ]* 15.2 Write unit tests for LLM stub
    - Assert `is_stub=True` on all four methods
    - Assert no exceptions raised for arbitrary inputs
    - _Requirements: (LLM stub correctness)_

- [x] 16. FastAPI application wiring and dependency injection
  - [x] 16.1 Implement `backend/dependencies.py`: factory functions for all services; wire concrete implementations into FastAPI's DI graph using `Depends`
    - Include `create_llm_service()` provider-selection logic
    - _Requirements: 1.1, 2.1, 3.1, 5.3, 7.1_
  - [x] 16.2 Implement `backend/main.py`: create `FastAPI` app; include all routers; register startup/shutdown lifespan hooks (DB engine, Redis pool, background price poller); enforce HTTPS redirect middleware
    - _Requirements: 8.2_
  - [ ]* 16.3 Write integration tests for auth flow
    - Register → login → refresh → logout cycle against real PostgreSQL + Redis via `testcontainers-python`
    - _Requirements: 1.1, 8.3, 8.4_
  - [ ]* 16.4 Write integration tests for broker connection and holdings aggregation
    - Mock broker OAuth callback → token storage → token retrieval → aggregated portfolio shape
    - _Requirements: 1.2, 2.1, 2.2_
  - [ ]* 16.5 Write integration tests for order placement and alert triggering
    - Mock broker order API → order persisted in DB → status update via WebSocket
    - Create alert → simulate price update → verify notification emitted
    - _Requirements: 5.3, 7.2_

- [x] 17. Checkpoint — full backend integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 18. Frontend project setup and API client
  - [x] 18.1 Initialise Vite + React 18 + TypeScript project in `frontend/`; configure shadcn/ui, TanStack Query v5 provider, Zustand stores (`uiStore.ts` for time range / broker filter, `socketStore.ts` for WebSocket state)
    - _Requirements: 9.1, 9.2_
  - [x] 18.2 Implement typed API client modules (`frontend/src/api/portfolio.ts`, `orders.ts`, `alerts.ts`, `brokers.ts`) using `fetch` with base URL from env; include request/response types matching backend Pydantic models
    - _Requirements: 2.1, 5.1, 7.1_
  - [x] 18.3 Implement `frontend/src/hooks/usePriceSocket.ts`: WebSocket client with exponential-backoff reconnection (max 30 s); subscribe/unsubscribe to tickers; expose price updates via Zustand; show "Reconnecting…" banner while disconnected; fall back to REST polling every 60 s
    - _Requirements: 3.2, 3.3_

- [x] 19. Layout and navigation shell
  - [x] 19.1 Implement `DashboardLayout.tsx`, `Sidebar.tsx`, `TopBar.tsx` using shadcn/ui; responsive breakpoints (stacked below 768 px); keyboard-navigable navigation
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 20. Portfolio summary and holdings table
  - [x] 20.1 Implement `PortfolioSummary.tsx`: display total value, total invested, total gain/loss (currency + %), day change; wire to `usePortfolio` TanStack Query hook (`GET /portfolio`)
    - _Requirements: 2.4, 9.5_
  - [x] 20.2 Implement `HoldingsTable.tsx` and `HoldingRow.tsx`: sortable table of all holdings with ticker, company name, quantity, avg buy price, current price, current value, gain/loss %; show per-broker breakdown and combined position for duplicate tickers; `BrokerStatusBadge.tsx` for connection state
    - _Requirements: 2.2, 2.3, 1.6_
  - [x] 20.3 Implement `PriceChange.tsx` (up/down animated indicator, visible ≥ 3 s) and `StaleDataIndicator.tsx` (last-updated timestamp, never future); wire live price updates from `usePriceSocket`
    - _Requirements: 3.3, 3.4, 2.5_
  - [x] 20.4 Implement `TimeRangeSelector.tsx` (1d / 1w / 1m / 3m / 1y / 5y); connect to `uiStore` so all charts and metrics update on selection
    - _Requirements: 4.2, 6.5_

- [x] 21. Chart engine
  - [x] 21.1 Implement `AllocationChart.tsx` (Recharts `PieChart`/`RadialBarChart`): allocation by stock and by broker; tooltip on hover/tap; toggle between pie and bar
    - _Requirements: 4.1, 4.5, 4.6_
  - [ ]* 21.2 Write property test for portfolio allocation percentages
    - **Property 11: Portfolio allocation percentages sum to 100**
    - Generate arbitrary non-empty holdings lists with `st.lists(..., min_size=1)`
    - Assert by-stock and by-broker percentage sets each sum to 100 within ±0.01%
    - **Validates: Requirements 4.1**
  - [x] 21.3 Implement `PortfolioTrendChart.tsx` (Recharts `LineChart`): total portfolio value over selected time range; tooltip; wire to `GET /market/history` via `useMarketData` hook
    - _Requirements: 4.2, 4.5_
  - [x] 21.4 Implement `PriceHistoryChart.tsx` (Recharts `LineChart`): per-stock price history for selected holding and time range; empty state with retry button on data failure
    - _Requirements: 4.3, 4.5_
  - [x] 21.5 Implement `GainLossChart.tsx` (Recharts `BarChart`): unrealized gain/loss per stock and per broker; tooltip
    - _Requirements: 4.4, 4.5_

- [x] 22. Multi-broker comparison and insights
  - [x] 22.1 Implement `BrokerComparisonTable.tsx`: side-by-side total value, total gain/loss, number of holdings per broker; highlight duplicate positions with combined quantity and avg cost basis
    - _Requirements: 6.1, 6.2_
  - [x] 22.2 Implement top-5 / bottom-5 performers panel: compute and display rankings by gain/loss % for selected time range
    - _Requirements: 6.4, 6.5_
  - [ ]* 22.3 Write property test for top/bottom performer ranking invariant
    - **Property 12: Top/bottom performer ranking invariant**
    - Generate arbitrary lists of holdings with random gain/loss percentages using `st.lists(st.decimals(), min_size=1)`
    - Assert top-N performers each have gain/loss % >= all non-top-N; bottom-N performers each have gain/loss % <= all non-bottom-N
    - **Validates: Requirements 6.4**
  - [x] 22.4 Implement diversification score display: calculate and render sector/asset allocation score in the comparison view
    - _Requirements: 6.3_

- [x] 23. Order placement UI
  - [x] 23.1 Implement `OrderForm.tsx`: pre-populated with ticker and broker; supports market and limit orders for buy/sell; submit calls `POST /orders`; accessible form with keyboard navigation
    - _Requirements: 5.1, 5.2, 9.2_
  - [x] 23.2 Implement `TransactionHistory.tsx` and `OrderStatusBadge.tsx`: display all orders with status, timestamp, broker, ticker, type, quantity, price; auto-update pending orders via WebSocket order updates
    - _Requirements: 5.6, 5.7_
  - [x] 23.3 Wire success/error notifications: on order confirmation show toast with order type, ticker, quantity, execution price; on rejection show toast with rejection reason
    - _Requirements: 5.4, 5.5_

- [x] 24. Alerts UI
  - [x] 24.1 Implement `CreateAlertForm.tsx`: ticker, target price, condition (above/below); submit calls `POST /alerts`; accessible
    - _Requirements: 7.1, 9.2_
  - [x] 24.2 Implement `AlertList.tsx`: display active and triggered alerts; edit and delete actions; wire to `useAlerts` TanStack Query hook
    - _Requirements: 7.4_
  - [x] 24.3 Implement in-app notification delivery for triggered alerts (toast/banner within 60 s of trigger); wire browser push notification opt-in via `Notification` API
    - _Requirements: 7.2, 7.5_

- [x] 25. Broker connection management UI
  - [x] 25.1 Implement `BrokerConnectionCard.tsx`: per-broker connect/disconnect button; display connection status badge (connected / disconnected / error) and last successful fetch time; initiate OAuth redirect via `POST /brokers/{broker_id}/connect`
    - _Requirements: 1.1, 1.4, 1.5, 1.6_

- [x] 26. Checkpoint — frontend feature complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 27. Accessibility and responsive polish
  - [x] 27.1 Audit all interactive components for WCAG 2.1 AA: sufficient colour contrast, ARIA labels on icon-only buttons, focus rings, `role` and `aria-live` on dynamic price regions
    - _Requirements: 9.2_
  - [x] 27.2 Verify mobile layout (320 px – 767 px): stacked vertical layout, touch-friendly chart interactions, touch-friendly form controls
    - _Requirements: 9.1, 9.3, 9.4_

- [x] 28. End-to-end and performance tests
  - [ ]* 28.1 Write Playwright E2E test: connect broker (mocked OAuth), view portfolio summary and holdings table
    - _Requirements: 1.1, 2.1, 2.4_
  - [ ]* 28.2 Write Playwright E2E test: place a buy order and verify confirmation notification
    - _Requirements: 5.1, 5.4_
  - [ ]* 28.3 Write Playwright E2E test: create a price alert and verify it appears in the alert list
    - _Requirements: 7.1, 7.4_
  - [ ]* 28.4 Write Playwright E2E test: verify responsive layout at 375 px (mobile) and 1440 px (desktop)
    - _Requirements: 9.1, 9.3_
  - [ ]* 28.5 Integrate `axe-playwright` into E2E tests to catch WCAG 2.1 AA violations automatically
    - _Requirements: 9.2_
  - [ ]* 28.6 Add Lighthouse CI configuration to enforce 3-second initial load budget on each PR
    - _Requirements: 9.5_

- [x] 29. Final checkpoint — all tests pass
  - Ensure all unit, property, integration, and E2E tests pass. Ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP.
- Each task references specific requirements for traceability.
- Property tests (Hypothesis) are placed immediately after the logic they validate to catch regressions early.
- Unit tests and property tests are complementary — property tests cover universal invariants, unit tests cover specific examples and edge cases.
- Checkpoints at tasks 6, 9, 14, 17, 26, and 29 ensure incremental validation throughout the build.
- The LLM service (task 15) is scaffolded as a stub; activating a real provider requires only setting `LLM_PROVIDER` and the corresponding API key environment variable.
