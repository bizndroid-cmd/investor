# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-08

### Added
- NewsAPI.ai integration with India location filter
- AI Predictions dashboard with confidence scoring
- Portfolio daily snapshots for historical tracking
- Source filtering (RSS / NewsAPI.ai / All) in news feed
- External prompt files for LLM briefing customization
- yfinance fallback for live NSE stock prices
- Groww token input via frontend (daily access token)
- Prediction accuracy tracking (mood + ticker direction)

### Changed
- News collection schedule: 8:00 AM + 8:00 PM IST (was 7:00 + 18:00)
- Portfolio shows "Current Market Value" (was "Total Value")
- Briefing auto-loads on page visit (was manual trigger only)
- News sorted by latest first (was by relevance score)
- NewsAPI.ai: 100 articles per pull (was 50)

### Fixed
- Portfolio showing invested = market value (no live prices)
- Groww disconnect not showing token input
- Batch price fetch failing silently when Finnhub key empty
- NewsAPI.ai keyword limit (10 tickers, free tier max 15)
- Briefing not persisting between page navigations

## [1.0.0] - 2026-06-03

### Added
- Initial release: Stock Investment Dashboard
- Multi-broker portfolio aggregation (Groww)
- Real-time price updates via WebSocket
- News collection from Indian RSS feeds
- LLM-powered portfolio briefings (Groq/Gemini)
- Circuit breaker for API rate limit protection
- Telemetry/Nerd Stats dashboard
- Docker production deployment with Caddy reverse proxy
- Zero-downtime deploy script
- GitHub Actions CI/CD workflow

## [0.1.0] - 2026-05-28

### Added
- Project scaffolding
- FastAPI backend with auth (JWT + MFA)
- React frontend with Tailwind CSS
- PostgreSQL + Redis infrastructure
- Groww broker connector
- Basic portfolio display
