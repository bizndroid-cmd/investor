"""WebSocket connection manager for real-time price and order updates.

Manages a registry of connected WebSocket clients keyed by user_id,
with subscription tracking for ticker-based price broadcasts.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import WebSocket

from backend.models.domain import Order, PriceQuote

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and ticker subscriptions.

    Connection registry: dict[UUID, list[WebSocket]]
    Subscription registry: dict[str, set[UUID]] — ticker -> set of user_ids
    User subscriptions: dict[UUID, set[str]] — user_id -> set of tickers
    """

    def __init__(self) -> None:
        # user_id -> list of active WebSocket connections
        self._connections: dict[UUID, list[WebSocket]] = {}
        # ticker -> set of user_ids subscribed to that ticker
        self._ticker_subscribers: dict[str, set[UUID]] = {}
        # user_id -> set of tickers they're subscribed to
        self._user_subscriptions: dict[UUID, set[str]] = {}

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
        """Register a new WebSocket connection for a user."""
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        logger.info("WebSocket connected for user %s", user_id)

    async def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        """Remove a WebSocket connection and clean up subscriptions."""
        if user_id in self._connections:
            try:
                self._connections[user_id].remove(websocket)
            except ValueError:
                pass
            if not self._connections[user_id]:
                del self._connections[user_id]
                # Clean up subscriptions for this user
                self._cleanup_user_subscriptions(user_id)

        logger.info("WebSocket disconnected for user %s", user_id)

    def subscribe(self, user_id: UUID, tickers: list[str]) -> None:
        """Subscribe a user to price updates for the given tickers."""
        if user_id not in self._user_subscriptions:
            self._user_subscriptions[user_id] = set()

        for ticker in tickers:
            ticker_upper = ticker.upper()
            self._user_subscriptions[user_id].add(ticker_upper)
            if ticker_upper not in self._ticker_subscribers:
                self._ticker_subscribers[ticker_upper] = set()
            self._ticker_subscribers[ticker_upper].add(user_id)

        logger.debug("User %s subscribed to %s", user_id, tickers)

    def unsubscribe(self, user_id: UUID, tickers: list[str]) -> None:
        """Unsubscribe a user from price updates for the given tickers."""
        if user_id not in self._user_subscriptions:
            return

        for ticker in tickers:
            ticker_upper = ticker.upper()
            self._user_subscriptions[user_id].discard(ticker_upper)
            if ticker_upper in self._ticker_subscribers:
                self._ticker_subscribers[ticker_upper].discard(user_id)
                if not self._ticker_subscribers[ticker_upper]:
                    del self._ticker_subscribers[ticker_upper]

        logger.debug("User %s unsubscribed from %s", user_id, tickers)

    async def broadcast_price_update(self, ticker: str, quote: PriceQuote) -> None:
        """Send a price update to all users subscribed to the given ticker."""
        ticker_upper = ticker.upper()
        subscribers = self._ticker_subscribers.get(ticker_upper, set())

        if not subscribers:
            return

        message = json.dumps({
            "type": "price_update",
            "data": json.loads(quote.model_dump_json()),
        })

        for user_id in list(subscribers):
            await self._send_to_user(user_id, message)

    async def broadcast_order_update(self, user_id: UUID, order: Order) -> None:
        """Send an order status update to a specific user."""
        message = json.dumps({
            "type": "order_update",
            "data": json.loads(order.model_dump_json()),
        })
        await self._send_to_user(user_id, message)

    def get_all_subscribed_tickers(self) -> set[str]:
        """Return all tickers that have at least one subscriber."""
        return set(self._ticker_subscribers.keys())

    def get_connected_user_ids(self) -> set[UUID]:
        """Return all currently connected user IDs."""
        return set(self._connections.keys())

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    async def _send_to_user(self, user_id: UUID, message: str) -> None:
        """Send a message to all WebSocket connections for a user."""
        connections = self._connections.get(user_id, [])
        disconnected: list[WebSocket] = []

        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)

        # Clean up disconnected sockets
        for ws in disconnected:
            try:
                self._connections[user_id].remove(ws)
            except (ValueError, KeyError):
                pass

        if user_id in self._connections and not self._connections[user_id]:
            del self._connections[user_id]
            self._cleanup_user_subscriptions(user_id)

    def _cleanup_user_subscriptions(self, user_id: UUID) -> None:
        """Remove all ticker subscriptions for a disconnected user."""
        tickers = self._user_subscriptions.pop(user_id, set())
        for ticker in tickers:
            if ticker in self._ticker_subscribers:
                self._ticker_subscribers[ticker].discard(user_id)
                if not self._ticker_subscribers[ticker]:
                    del self._ticker_subscribers[ticker]
