"""Background price polling task.

Runs every 30 seconds, fetches batch prices for all tickers held by
connected/subscribed users, broadcasts updates via WebSocketManager,
and evaluates price alerts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.interfaces.alert_service import IAlertService
    from backend.interfaces.market_data_service import IMarketDataService
    from backend.services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

# Polling interval in seconds
POLL_INTERVAL = 30


async def start_price_poller(
    market_data_service: "IMarketDataService",
    ws_manager: "WebSocketManager",
    alert_service: "IAlertService",
) -> asyncio.Task:
    """Start the background price polling task.

    Returns the asyncio.Task so it can be cancelled on shutdown.

    The poller:
    1. Collects all tickers from subscribed users via WebSocketManager
    2. Fetches batch prices from MarketDataService
    3. Broadcasts price updates to subscribed clients
    4. Evaluates alerts for each ticker via AlertService
    """

    async def _poll_loop() -> None:
        logger.info("Price poller started (interval: %ds)", POLL_INTERVAL)
        while True:
            try:
                await _poll_once(market_data_service, ws_manager, alert_service)
            except asyncio.CancelledError:
                logger.info("Price poller cancelled")
                break
            except Exception as e:
                logger.error("Price poller error: %s", str(e))

            await asyncio.sleep(POLL_INTERVAL)

    task = asyncio.create_task(_poll_loop())
    return task


async def _poll_once(
    market_data_service: "IMarketDataService",
    ws_manager: "WebSocketManager",
    alert_service: "IAlertService",
) -> None:
    """Execute a single polling cycle."""
    # Collect all tickers that have subscribers
    tickers = ws_manager.get_all_subscribed_tickers()

    if not tickers:
        return

    logger.debug("Polling prices for %d tickers: %s", len(tickers), tickers)

    # Fetch batch prices
    quotes = await market_data_service.get_batch_prices(list(tickers))

    # Broadcast updates and evaluate alerts
    for ticker, quote in quotes.items():
        # Broadcast to subscribed WebSocket clients
        await ws_manager.broadcast_price_update(ticker, quote)

        # Evaluate alerts for this ticker
        try:
            await alert_service.evaluate_alerts(ticker, float(quote.price))
        except Exception as e:
            logger.error("Alert evaluation failed for %s: %s", ticker, str(e))
