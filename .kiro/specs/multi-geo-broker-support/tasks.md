# Implementation Plan: Multi-Geography Broker Support

## Overview

20 incremental tasks to make the application multi-geography and multi-broker compliant. Each task is independently deployable without breaking existing Indian/Groww functionality. Tasks are ordered by dependency — foundation first, services second, frontend last.

## Tasks

- [x] 1. Create Geography Registry module (`backend/geo/registry.py`) with frozen dataclass configs for "IN" and "US" geographies including currency, exchanges, yfinance suffix, market hours, timezone, fundamentals source, sector maps, dividend frequency. #requirement-1
- [x] 2. Create Ticker Resolver (`backend/geo/ticker_resolver.py`) with `resolve(ticker, geo_id)` and `strip_suffix(resolved, geo_id)` functions that use registry config to append/remove yfinance suffixes. #requirement-3
- [x] 3. Create Market Hours Service (`backend/geo/market_hours.py`) with `is_market_open(geo_id)` and `get_cache_ttl(geo_id)` replacing the hardcoded `_is_market_hours()` function. #requirement-5
- [x] 4. Create Currency Formatter — backend `backend/geo/currency.py` for Telegram messages and frontend `frontend/src/utils/currency.ts` using Intl.NumberFormat with geo-specific locale/currency. #requirement-4
- [x] 5. Create Sector Classification Provider (`backend/geo/sectors.py`) with `get_sector(ticker, geo_id)` using registry sector maps, returning "other" for unknown tickers. #requirement-8
- [x] 6. Create User Preferences DB migration (`0011_add_user_preferences.py`) and ORM model with geography (default "IN"), default_broker, timezone, currency_code columns. #requirement-2
- [x] 7. Create User Preferences API (`backend/routers/preferences.py`) with GET/PUT /user/preferences endpoints, geography validation against registry, Redis cache invalidation on change. #requirement-2
- [x] 8. Create `get_user_geo` FastAPI dependency in `backend/dependencies.py` that resolves user geography from preferences table, defaulting to "IN". #requirement-10 #requirement-12
- [x] 9. Update MarketDataService to accept `geo_id` parameter — use Ticker Resolver instead of hardcoded ".NS", use Market Hours Service instead of `_is_market_hours()`, restrict Groww LTP to geo="IN" only. #requirement-10
- [x] 10. Update TechnicalAnalysisService to accept `geo_id` parameter — replace hardcoded `f"{ticker}.NS"` with `ticker_resolver.resolve(ticker, geo_id)` in `_compute_technicals_sync`. #requirement-11
- [x] 11. Create Fundamentals Provider interface (`backend/interfaces/fundamentals_provider.py`) and US implementation (`backend/geo/fundamentals_yfinance.py`) extracting data from yfinance Ticker.info. #requirement-6
- [x] 12. Create News Feed Provider interface (`backend/interfaces/news_feed_provider.py`) and US implementation with Yahoo Finance/MarketWatch RSS, update NewsAggregator to select provider by geography. #requirement-7
- [x] 13. Add `supported_geographies` attribute to IBrokerConnector interface, set on all connectors (Groww/Zerodha=["IN"], Robinhood/Fidelity=["US"]), filter in AggregatorService. #requirement-9
- [x] 14. Update IntelligenceService to use `get_sector(ticker, geo_id)` from sectors provider instead of hardcoded SECTOR_MAP dictionary. #requirement-8
- [x] 15. Create Frontend GeoContext provider (`frontend/src/contexts/GeoContext.tsx`) fetching preferences on mount, exposing geography/currency/locale/formatCurrency to all components. #requirement-13
- [x] 16. Replace all hardcoded "₹" and "en-IN" formatting in frontend pages (Portfolio, Earnings, Alerts, Research) with GeoContext formatCurrency hook. #requirement-13
- [x] 17. Create Frontend Settings page (`frontend/src/pages/SettingsPage.tsx`) with geography selector, broker display, timezone — calls PUT /user/preferences, add to nav. #requirement-13
- [ ] 18. Update Telegram notification messages to use `format_currency(value, geo_id)` instead of hardcoded "₹" — pass user geo through all send functions. #requirement-4 #requirement-12
- [ ] 19. Update Earnings page yield comparison to show geo-appropriate benchmarks (FD/PPF for IN, T-Bills/S&P500 for US) and geo-appropriate dividend frequency assumptions. #requirement-14
- [ ] 20. Integration testing and backward compatibility verification — verify existing IN user unaffected, test US user end-to-end, deploy to AWS with zero regression. #requirement-12

## Task Dependency Graph

```json
{
  "waves": [
    { "tasks": [1], "description": "Foundation — Geography Registry (all other tasks depend on this)" },
    { "tasks": [2, 3, 4, 5, 6], "description": "Core utilities + DB migration (depend only on registry)" },
    { "tasks": [7], "description": "Preferences API (depends on migration)" },
    { "tasks": [8], "description": "FastAPI dependency (depends on preferences API)" },
    { "tasks": [9, 10, 11, 12, 13, 14], "description": "Service updates (depend on resolver, market hours, get_user_geo)" },
    { "tasks": [15], "description": "Frontend GeoContext (depends on preferences API)" },
    { "tasks": [16, 17, 18], "description": "Frontend currency + settings + Telegram (depend on GeoContext)" },
    { "tasks": [19], "description": "Earnings geo-specific benchmarks (depends on frontend context)" },
    { "tasks": [20], "description": "Integration testing + deployment verification" }
  ]
}
```

## Notes

- Tasks 1-5 are pure additions (new files only) — zero risk to existing code.
- Task 6-8 add DB + dependency — backward compatible via "IN" default.
- Tasks 9-14 modify existing services — each change is additive (new parameter with default).
- Tasks 15-19 are frontend — isolated from backend stability.
- Task 20 is verification — no code changes, only testing.
- Each task can be committed and deployed independently.
- If any task fails, revert just that task — prior tasks remain stable.
