# Financial Compass — Technical Architecture

## Architecture Overview

```
Browser ↔ Caddy (reverse proxy) ↔ FastAPI Backend ↔ PostgreSQL + Redis
                                  ↕
                          Telegram Bot API
                          yfinance / Market APIs
                          LLM (Gemini/Groq/OpenAI)
```

---

## Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Frontend** | React + TypeScript | React 18, TS 5.6 |
| **Build** | Vite | 5.4 |
| **Styling** | Tailwind CSS | 3.4 |
| **State** | TanStack Query + Zustand | v5 / v5 |
| **Charts** | Recharts | 2.13 |
| **Icons** | Lucide React | 0.453 |
| **Routing** | React Router | 6.28 |
| **Backend** | FastAPI (Python) | 0.115 |
| **ORM** | SQLAlchemy (async) | 2.0 |
| **Database** | PostgreSQL | 16 |
| **Cache/Sessions** | Redis | 7 |
| **Migrations** | Alembic | 1.13 |
| **Auth** | JWT (python-jose) + bcrypt | — |
| **MFA** | TOTP (pyotp) | — |
| **Market Data** | yfinance, Finnhub | — |
| **AI/LLM** | LangChain + Gemini/Groq/OpenAI | — |
| **Notifications** | Telegram Bot API | — |
| **Reverse Proxy** | Caddy | 2 (Alpine) |
| **Containers** | Docker + Docker Compose | — |
| **Hosting** | AWS EC2 (t3.small, us-east-2) | — |
| **CI/CD** | GitHub Actions (SSH deploy) | — |

---

## Codebase Size

| Metric | Count |
|--------|-------|
| Backend Python files | 97 |
| Frontend TS/TSX files | 73 |
| Backend lines of code | ~18,300 |
| Frontend lines of code | ~10,600 |
| API endpoints | 84 |
| Database models (tables) | 21 |
| Alembic migrations | 17 |
| Backend services | 20 |
| Frontend pages | 19 |
| Frontend components | 31 |

---

## Backend Structure

```
backend/
├── alembic/versions/        # 17 DB migrations
├── connectors/              # Broker integrations
│   ├── groww.py             # India (NSE/BSE)
│   ├── robinhood.py         # US (NYSE/NASDAQ)
│   ├── zerodha.py           # India
│   └── fidelity.py          # US
├── geo/                     # Multi-geography support
│   ├── registry.py          # IN/US config (exchanges, timezone, currency)
│   ├── ticker_resolver.py   # yfinance suffix resolution
│   ├── currency.py          # Format + conversion
│   └── market_hours.py      # Trading day/time detection
├── interfaces/              # Abstract contracts (dependency inversion)
├── models/
│   ├── orm.py               # 21 SQLAlchemy models
│   └── domain.py            # Pydantic domain objects
├── routers/                 # API endpoints
│   ├── auth.py              # Register, login, MFA, refresh
│   ├── portfolio.py         # Holdings, snapshots, refresh
│   ├── portfolios.py        # Multi-portfolio CRUD, net-worth
│   ├── earnings.py          # Dividends, yield, cost basis
│   ├── etfs.py              # ETF CRUD, insights, comparison
│   ├── goals.py             # Financial goals, wealth entries
│   ├── alerts.py            # Price alerts CRUD
│   ├── research.py          # Per-stock research card
│   ├── news.py              # News feed, briefing
│   ├── brokers.py           # Broker connections
│   ├── telegram.py          # Telegram sync, attachments, approval webhook
│   ├── market_data.py       # Real-time prices
│   └── orders.py            # Order placement
├── services/                # Business logic
│   ├── aggregator_service.py    # Multi-broker portfolio aggregation
│   ├── auth_service.py          # JWT, sessions, approval flow
│   ├── alert_service.py         # Price monitoring + Telegram notify
│   ├── etf_service.py           # yfinance ETF data + returns
│   ├── intelligence_service.py  # Pattern recognition
│   ├── llm_service.py           # Multi-provider LLM abstraction
│   ├── market_data_service.py   # Finnhub + yfinance prices
│   ├── news_aggregator.py       # RSS + NewsAPI.ai fetching
│   ├── news_analyzer.py         # LLM sentiment analysis
│   ├── news_service.py          # Briefing generation
│   ├── portfolio_snapshot_service.py  # Daily capture
│   ├── screener_service.py      # screener.in fundamentals
│   ├── technical_analysis_service.py  # RSI, MACD, Bollinger, ATR
│   ├── telegram_service.py      # Bot messaging + approval
│   ├── telemetry_service.py     # LLM usage tracking
│   ├── trade_report_parser.py   # XLSX/CSV import
│   └── websocket_manager.py     # Real-time price broadcast
├── tasks/
│   └── news_collector.py    # Scheduled news collection
├── prompts/                 # LLM prompt templates
├── config.py                # Settings (env vars)
├── database.py              # Async engine + session factory
├── dependencies.py          # FastAPI DI (portfolio_id, geo, services)
└── main.py                  # App entry, lifespan, middleware
```

---

## Frontend Structure

```
frontend/src/
├── api/                     # API client layer
│   ├── client.ts            # apiFetch, auth header, 401 handling
│   ├── portfolio.ts         # Portfolio/holdings/fundamentals
│   ├── alerts.ts            # Alerts CRUD
│   ├── etfs.ts              # ETF endpoints
│   ├── goals.ts             # Goals + wealth entries
│   ├── news.ts              # News + briefing
│   ├── brokers.ts           # Broker connections
│   └── types.ts             # Shared TypeScript interfaces
├── components/
│   ├── layout/              # Sidebar, TopBar, DashboardLayout
│   ├── portfolio/           # HoldingsTable, TopPerformers, NetWorthCard, FundamentalsPanel
│   ├── brokers/             # BrokerConnectionCard, BrokerComparisonTable
│   ├── alerts/              # AlertNotification
│   └── common/              # Toast
├── contexts/
│   ├── PortfolioContext.tsx  # Active portfolio state
│   └── GeoContext.tsx        # Currency/locale
├── hooks/
│   ├── usePortfolio.ts      # Portfolio query + refresh
│   ├── useAlerts.ts         # Alert CRUD mutations
│   ├── useNews.ts           # Briefing + news queries
│   └── usePriceSocket.ts   # WebSocket live prices
├── stores/
│   └── socketStore.ts       # Zustand WebSocket state
└── pages/                   # 19 page components
```

---

## Database Schema (21 tables)

| Table | Purpose |
|-------|---------|
| users | Auth, email, password hash, MFA, is_approved |
| sessions | JWT session tracking |
| broker_tokens | Encrypted broker access tokens |
| holdings_cache | Cached broker holdings |
| portfolio_snapshots | Daily per-ticker snapshots |
| portfolio_daily_summary | Daily aggregate values |
| portfolios | Multi-portfolio definitions |
| orders | Trade orders |
| alerts | Price alert rules |
| news_articles | Collected news items |
| collection_runs | News collection metadata |
| briefing_cache | LLM-generated briefings |
| stock_fundamentals | Screener.in data cache |
| prediction_records | AI prediction tracking |
| trade_history | Parsed broker trade reports |
| attachments | Telegram document uploads |
| user_preferences | Geography, broker defaults |
| etf_holdings | Manual ETF entries |
| goals | Financial targets |
| wealth_entries | Manual wealth deposits |

---

## Security

- JWT access tokens (15 min) + refresh tokens (7 days)
- bcrypt password hashing (12 rounds)
- Session inactivity timeout (30 min via Redis)
- TOTP MFA support
- Registration approval via Telegram (admin must approve)
- Disposable email domain blocklist
- Broker tokens encrypted at rest (AES)
- CORS restricted to app domain
- No exposed DB/Redis ports (internal Docker network only)

---

## Key Features by Page

| Page | Features |
|------|----------|
| **Blueprint** | Multi-goal tracking, wealth overview, progress rings, time-to-goal projection |
| **The Market** | Live portfolio from broker, sector allocation, fundamentals, net-worth card |
| **Earnings** | Dividend yield, cost basis, income projection, trade history import |
| **ETFs** | Multi-lot management, comparison chart with mock simulator, allocation insights |
| **AI Copilot** | Daily briefing (LLM), AI predictions with accuracy scoring, smart insights, news feed |
| **Research** | Per-stock technicals (RSI, MACD, Bollinger, S/R), fundamentals, AI verdict |
| **Alerts** | Price target alerts, Telegram notifications, proximity monitoring, smart suggestions |

---

## External API Dependencies

| Service | Used For | Cost |
|---------|----------|------|
| yfinance | Stock/ETF prices, history, fundamentals | Free |
| Finnhub | Real-time quotes | Free tier (60 calls/min) |
| Groww API | Indian broker holdings | Free (user token) |
| Robinhood (robin_stocks) | US broker holdings | Free (user creds) |
| NewsAPI.ai / EventRegistry | News articles | Free tier |
| Telegram Bot API | Notifications, approval, file sync | Free |
| Google Gemini / Groq | LLM briefings, analysis | Free tier / pay-per-use |

---

## Deployment

| Component | Config |
|-----------|--------|
| EC2 instance | t3.small, 2 vCPU, 2GB RAM, 20GB disk, us-east-2 |
| Docker Compose | 4 containers (backend, postgres, redis, caddy) + ephemeral frontend-builder |
| Caddy | Reverse proxy, SPA routing, API pass-through |
| CI/CD | GitHub Actions SSH on push to main |

---

## Local Development

```bash
# Backend
cd investor
cp .env.example .env  # fill values
pip install -e backend[dev]
PYTHONPATH=. alembic -c backend/alembic.ini upgrade head
uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

---

## Key Architecture Patterns

- **FastAPI Dependency Injection** — `get_portfolio_id`, `get_portfolio_geo` resolve context per-request
- **Multi-portfolio scoping** — all data queries include `portfolio_id` filter (with NULL fallback for legacy data)
- **yfinance in thread pool** — `run_in_executor(None, sync_fn)` for blocking I/O
- **TanStack Query cache segmentation** — query keys include `portfolioId` for automatic invalidation on switch
- **PortfolioContext** — React context provides active portfolio ID to all pages/hooks
- **Telegram polling** — background task every 10s checks for approval callbacks (no HTTPS webhook needed)
- **Circuit breaker** — LLM calls tracked, auto-paused on rate limit
