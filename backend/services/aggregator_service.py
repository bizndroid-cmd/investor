"""Aggregator service implementing IAggregatorService.

Responsible for fetching holdings from all connected broker connectors,
normalizing them to the common schema, enriching with market data,
and computing portfolio summaries.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.interfaces.aggregator_service import IAggregatorService
from backend.interfaces.broker_connector import IBrokerConnector
from backend.interfaces.market_data_service import IMarketDataService
from backend.models.domain import (
    BrokerId,
    BrokerStatus,
    NormalizedHolding,
    Portfolio,
    PriceQuote,
    RawHolding,
    RefreshResult,
)

logger = logging.getLogger(__name__)

# Redis cache TTL for holdings (5 minutes)
HOLDINGS_CACHE_TTL_SECONDS = 5 * 60


def compute_portfolio_summary(holdings: list[NormalizedHolding]) -> dict:
    """Compute portfolio summary math invariants from a list of normalized holdings.

    Returns a dict with:
    - total_value: sum of current_values
    - total_invested: sum of qty * avg_buy_price
    - total_gain_loss: total_value - total_invested
    - total_gain_loss_percent: (total_gain_loss / total_invested) * 100 when total_invested > 0
    - day_change: sum of (current_price - previous_close) * quantity for each holding
    - day_change_percent: (day_change / (total_value - day_change)) * 100 when denominator > 0
    """
    total_value = Decimal("0")
    total_invested = Decimal("0")
    day_change = Decimal("0")

    for h in holdings:
        total_value += h.current_value
        total_invested += h.quantity * h.avg_buy_price

    total_gain_loss = total_value - total_invested
    total_gain_loss_percent = (
        (total_gain_loss / total_invested * Decimal("100"))
        if total_invested > 0
        else Decimal("0")
    )

    # day_change is computed externally and passed via holdings' current_price vs previous_close
    # We approximate day_change as total_gain_loss for the summary since we don't store
    # previous_close on NormalizedHolding. The caller should set day_change explicitly.
    # For now, day_change will be set to 0 and overridden by the caller.

    return {
        "total_value": total_value,
        "total_invested": total_invested,
        "total_gain_loss": total_gain_loss,
        "total_gain_loss_percent": total_gain_loss_percent,
        "day_change": day_change,
        "day_change_percent": Decimal("0"),
    }


class AggregatorService(IAggregatorService):
    """Concrete implementation of IAggregatorService.

    Fetches holdings from all connected broker connectors concurrently,
    normalizes them, enriches with current market prices, computes
    portfolio summaries, and caches results in Redis.
    """

    def __init__(
        self,
        db: AsyncSession,
        redis: aioredis.Redis,
        connectors: dict[BrokerId, IBrokerConnector],
        market_data_service: IMarketDataService,
    ) -> None:
        self._db = db
        self._redis = redis
        self._connectors = connectors
        self._market_data_service = market_data_service

    def normalize_holding(
        self,
        raw: RawHolding,
        current_price: Decimal,
        previous_close: Decimal,
    ) -> NormalizedHolding:
        """Map a raw holding to normalized form with computed fields.

        Computes:
        - current_value = quantity * current_price
        - gain_loss = current_value - (quantity * avg_buy_price)
        - gain_loss_percent = (gain_loss / (quantity * avg_buy_price)) * 100
        """
        current_value = raw.quantity * current_price
        cost_basis = raw.quantity * raw.avg_buy_price
        gain_loss = current_value - cost_basis
        gain_loss_percent = (
            (gain_loss / cost_basis * Decimal("100"))
            if cost_basis > 0
            else Decimal("0")
        )

        return NormalizedHolding(
            ticker=raw.ticker,
            company_name=raw.company_name or raw.ticker,
            broker_id=raw.broker_id,
            quantity=raw.quantity,
            avg_buy_price=raw.avg_buy_price,
            current_price=current_price,
            current_value=current_value,
            gain_loss=gain_loss,
            gain_loss_percent=gain_loss_percent,
            currency=raw.currency,
            last_updated=datetime.now(timezone.utc),
            is_stale=False,
        )

    async def get_portfolio(self, user_id: UUID) -> Portfolio:
        """Return the aggregated portfolio for the given user.

        - Check Redis cache first for each broker
        - If cache miss, fetch from all connected connectors concurrently
        - On connector failure: return last cached holdings with is_stale=True
        - Normalize all holdings, enrich with current prices
        - Compute portfolio summary
        - Cache results in Redis
        - Return Portfolio object
        """
        all_holdings: list[NormalizedHolding] = []
        broker_statuses: list[BrokerStatus] = []
        day_change = Decimal("0")

        # Determine which brokers are connected
        connected_brokers: list[BrokerId] = []
        for broker_id, connector in self._connectors.items():
            try:
                if await connector.is_connected(user_id):
                    connected_brokers.append(broker_id)
                else:
                    broker_statuses.append(
                        BrokerStatus(broker_id=broker_id, status="disconnected")
                    )
            except Exception:
                broker_statuses.append(
                    BrokerStatus(broker_id=broker_id, status="disconnected")
                )

        # Try cache first for each connected broker
        brokers_needing_fetch: list[BrokerId] = []
        for broker_id in connected_brokers:
            cache_key = f"holdings:{user_id}:{broker_id}"
            cached = await self._redis.get(cache_key)
            if cached:
                try:
                    cached_holdings = [
                        NormalizedHolding.model_validate(h)
                        for h in json.loads(cached)
                    ]
                    all_holdings.extend(cached_holdings)
                    broker_statuses.append(
                        BrokerStatus(
                            broker_id=broker_id,
                            status="connected",
                            last_successful_fetch=datetime.now(timezone.utc),
                        )
                    )
                    continue
                except Exception:
                    pass
            brokers_needing_fetch.append(broker_id)

        # Fetch from brokers that had cache misses
        if brokers_needing_fetch:
            fetch_tasks = [
                self._connectors[bid].get_holdings(user_id)
                for bid in brokers_needing_fetch
            ]
            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            # Collect all tickers for batch price fetch
            all_raw_holdings: dict[BrokerId, list[RawHolding]] = {}
            failed_brokers: list[BrokerId] = []

            for broker_id, result in zip(brokers_needing_fetch, results):
                if isinstance(result, Exception):
                    logger.error(
                        "Failed to fetch holdings from %s for user %s: %s",
                        broker_id,
                        user_id,
                        str(result),
                    )
                    failed_brokers.append(broker_id)
                else:
                    all_raw_holdings[broker_id] = result

            # Handle failed brokers: try to use cached data with is_stale=True
            for broker_id in failed_brokers:
                cache_key = f"holdings:{user_id}:{broker_id}"
                cached = await self._redis.get(cache_key)
                if cached:
                    try:
                        cached_holdings = [
                            NormalizedHolding.model_validate(h)
                            for h in json.loads(cached)
                        ]
                        # Mark as stale
                        for h in cached_holdings:
                            h.is_stale = True
                        all_holdings.extend(cached_holdings)
                    except Exception:
                        pass
                broker_statuses.append(
                    BrokerStatus(
                        broker_id=broker_id,
                        status="error",
                        error_message="Failed to fetch holdings",
                    )
                )

            # Get all unique tickers from successful fetches
            tickers_needed: set[str] = set()
            for raw_list in all_raw_holdings.values():
                for raw in raw_list:
                    tickers_needed.add(raw.ticker)

            # Fetch current prices in batch
            price_quotes: dict[str, PriceQuote] = {}
            if tickers_needed:
                try:
                    price_quotes = await self._market_data_service.get_batch_prices(
                        list(tickers_needed)
                    )
                except Exception as e:
                    logger.error("Failed to fetch batch prices: %s", str(e))

            # Normalize holdings from successful fetches
            for broker_id, raw_list in all_raw_holdings.items():
                normalized_for_broker: list[NormalizedHolding] = []
                for raw in raw_list:
                    quote = price_quotes.get(raw.ticker)
                    current_price = quote.price if quote else raw.avg_buy_price
                    previous_close = quote.previous_close if quote else current_price

                    normalized = self.normalize_holding(raw, current_price, previous_close)
                    normalized_for_broker.append(normalized)

                    # Accumulate day change
                    day_change += (current_price - previous_close) * raw.quantity

                all_holdings.extend(normalized_for_broker)

                # Cache the normalized holdings for this broker
                cache_key = f"holdings:{user_id}:{broker_id}"
                cache_data = json.dumps(
                    [h.model_dump(mode="json") for h in normalized_for_broker]
                )
                await self._redis.set(cache_key, cache_data, ex=HOLDINGS_CACHE_TTL_SECONDS)

                broker_statuses.append(
                    BrokerStatus(
                        broker_id=broker_id,
                        status="connected",
                        last_successful_fetch=datetime.now(timezone.utc),
                    )
                )

        # Compute portfolio summary
        summary = compute_portfolio_summary(all_holdings)

        # Override day_change with the computed value
        summary["day_change"] = day_change
        previous_total = summary["total_value"] - day_change
        summary["day_change_percent"] = (
            (day_change / previous_total * Decimal("100"))
            if previous_total > 0
            else Decimal("0")
        )

        return Portfolio(
            user_id=user_id,
            holdings=all_holdings,
            total_value=summary["total_value"],
            total_invested=summary["total_invested"],
            total_gain_loss=summary["total_gain_loss"],
            total_gain_loss_percent=summary["total_gain_loss_percent"],
            day_change=summary["day_change"],
            day_change_percent=summary["day_change_percent"],
            broker_statuses=broker_statuses,
            last_refreshed=datetime.now(timezone.utc),
        )

    async def get_holdings_by_broker(
        self,
        user_id: UUID,
        broker_id: BrokerId,
    ) -> list[NormalizedHolding]:
        """Return normalized holdings for a single broker."""
        connector = self._connectors.get(broker_id)
        if connector is None:
            return []

        # Check cache first
        cache_key = f"holdings:{user_id}:{broker_id}"
        cached = await self._redis.get(cache_key)
        if cached:
            try:
                return [
                    NormalizedHolding.model_validate(h) for h in json.loads(cached)
                ]
            except Exception:
                pass

        # Fetch from connector
        try:
            raw_holdings = await connector.get_holdings(user_id)
        except Exception as e:
            logger.error(
                "Failed to fetch holdings from %s for user %s: %s",
                broker_id,
                user_id,
                str(e),
            )
            return []

        # Get prices
        tickers = [raw.ticker for raw in raw_holdings]
        price_quotes: dict[str, PriceQuote] = {}
        if tickers:
            try:
                price_quotes = await self._market_data_service.get_batch_prices(tickers)
            except Exception:
                pass

        # Normalize
        normalized: list[NormalizedHolding] = []
        for raw in raw_holdings:
            quote = price_quotes.get(raw.ticker)
            current_price = quote.price if quote else raw.avg_buy_price
            previous_close = quote.previous_close if quote else current_price
            normalized.append(self.normalize_holding(raw, current_price, previous_close))

        # Cache
        cache_data = json.dumps([h.model_dump(mode="json") for h in normalized])
        await self._redis.set(cache_key, cache_data, ex=HOLDINGS_CACHE_TTL_SECONDS)

        return normalized

    async def refresh_all(self, user_id: UUID) -> list[RefreshResult]:
        """Force-refresh from all brokers (bypass cache), return list of RefreshResult."""
        results: list[RefreshResult] = []

        # Determine connected brokers
        connected_brokers: list[BrokerId] = []
        for broker_id, connector in self._connectors.items():
            try:
                if await connector.is_connected(user_id):
                    connected_brokers.append(broker_id)
            except Exception:
                results.append(
                    RefreshResult(
                        broker_id=broker_id,
                        success=False,
                        holdings_count=0,
                        error_message="Failed to check connection status",
                        fetched_at=datetime.now(timezone.utc),
                    )
                )

        if not connected_brokers:
            return results

        # Fetch from all connected brokers concurrently
        fetch_tasks = [
            self._connectors[bid].get_holdings(user_id)
            for bid in connected_brokers
        ]
        fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        # Collect tickers for batch price fetch
        all_raw: dict[BrokerId, list[RawHolding]] = {}
        for broker_id, result in zip(connected_brokers, fetch_results):
            if isinstance(result, Exception):
                results.append(
                    RefreshResult(
                        broker_id=broker_id,
                        success=False,
                        holdings_count=0,
                        error_message=str(result),
                        fetched_at=datetime.now(timezone.utc),
                    )
                )
            else:
                all_raw[broker_id] = result

        # Get prices for all tickers
        tickers_needed: set[str] = set()
        for raw_list in all_raw.values():
            for raw in raw_list:
                tickers_needed.add(raw.ticker)

        price_quotes: dict[str, PriceQuote] = {}
        if tickers_needed:
            try:
                price_quotes = await self._market_data_service.get_batch_prices(
                    list(tickers_needed)
                )
            except Exception as e:
                logger.error("Failed to fetch batch prices during refresh: %s", str(e))

        # Normalize and cache for each successful broker
        for broker_id, raw_list in all_raw.items():
            normalized: list[NormalizedHolding] = []
            for raw in raw_list:
                quote = price_quotes.get(raw.ticker)
                current_price = quote.price if quote else raw.avg_buy_price
                previous_close = quote.previous_close if quote else current_price
                normalized.append(
                    self.normalize_holding(raw, current_price, previous_close)
                )

            # Cache (overwrite existing)
            cache_key = f"holdings:{user_id}:{broker_id}"
            cache_data = json.dumps([h.model_dump(mode="json") for h in normalized])
            await self._redis.set(cache_key, cache_data, ex=HOLDINGS_CACHE_TTL_SECONDS)

            results.append(
                RefreshResult(
                    broker_id=broker_id,
                    success=True,
                    holdings_count=len(normalized),
                    fetched_at=datetime.now(timezone.utc),
                )
            )

        return results
