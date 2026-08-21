"""SnapTrade integration — unified US broker connection via OAuth.

Uses SnapTrade REST API directly (no SDK dependency).
Auth: clientId + Signature (HMAC-SHA256 of consumerKey + request content).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

from backend.config import settings
from backend.models.domain import RawHolding

logger = logging.getLogger(__name__)

BASE_URL = "https://api.snaptrade.com/api/v1"


class SnapTradeService:
    """Manages SnapTrade API interactions using direct HTTP + HMAC signing."""

    def __init__(self):
        self.client_id = settings.snaptrade_client_id
        self.consumer_key = settings.snaptrade_consumer_key

    def _sign(self, path: str, data: str = "") -> tuple[str, str]:
        """Generate timestamp + signature for request."""
        timestamp = str(int(time.time()))
        sig_content = f"/api/v1{path}&clientId={self.client_id}&timestamp={timestamp}"
        if data:
            sig_content += f"&content={data}"
        signature = hmac.new(
            self.consumer_key.encode("utf-8"),
            sig_content.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return timestamp, signature

    async def _request(self, method: str, path: str, params: dict = None, body: dict = None) -> Any:
        """Make authenticated request to SnapTrade API."""
        url = f"{BASE_URL}{path}"

        if params is None:
            params = {}

        body_str = json.dumps(body) if body else ""
        timestamp, signature = self._sign(path, body_str)

        params["clientId"] = self.client_id
        params["timestamp"] = timestamp
        params["Signature"] = signature

        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if method == "GET":
                    resp = await client.get(url, params=params, headers=headers)
                elif method == "POST":
                    resp = await client.post(url, params=params, json=body, headers=headers)
                elif method == "DELETE":
                    resp = await client.delete(url, params=params, headers=headers)
                else:
                    return None

                if resp.status_code >= 400:
                    logger.warning("SnapTrade %s %s -> %d: %s", method, path, resp.status_code, resp.text[:200])
                    return None

                return resp.json() if resp.text.strip() else None
            except Exception as e:
                logger.error("SnapTrade request failed: %s", str(e))
                return None

    async def register_user(self, user_id: UUID) -> dict | None:
        """Register a RuDo user with SnapTrade."""
        return await self._request("POST", "/snapTrade/registerUser", body={
            "userId": str(user_id),
        })

    async def get_login_url(self, user_id: UUID, user_secret: str, broker: str = None) -> str | None:
        """Get Connection Portal URL for broker OAuth."""
        body = {}
        if broker:
            body["broker"] = broker

        result = await self._request(
            "POST",
            "/snapTrade/login",
            params={"userId": str(user_id), "userSecret": user_secret},
            body=body,
        )
        if result:
            return result.get("redirectURI") or result.get("loginLink")
        return None

    async def list_accounts(self, user_id: UUID, user_secret: str) -> list[dict]:
        """List connected brokerage accounts."""
        result = await self._request(
            "GET",
            "/accounts",
            params={"userId": str(user_id), "userSecret": user_secret},
        )
        return result if isinstance(result, list) else []

    async def get_holdings(self, user_id: UUID, user_secret: str) -> list[RawHolding]:
        """Fetch holdings from all connected accounts."""
        result = await self._request(
            "GET",
            "/holdings",
            params={"userId": str(user_id), "userSecret": user_secret},
        )

        if not result:
            return []

        holdings = []
        # SnapTrade returns list of account holdings
        accounts = result if isinstance(result, list) else [result]

        for account_data in accounts:
            positions = account_data.get("positions", []) if isinstance(account_data, dict) else []
            for pos in positions:
                symbol = pos.get("symbol", {})
                ticker = symbol.get("symbol") or symbol.get("rawSymbol", "")
                if not ticker:
                    continue

                units = Decimal(str(pos.get("units", 0)))
                avg_price = Decimal(str(pos.get("averageEntryPrice") or pos.get("price", 0)))
                currency = "USD"
                if isinstance(symbol.get("currency"), dict):
                    currency = symbol["currency"].get("code", "USD")

                holdings.append(RawHolding(
                    broker_id="snaptrade",
                    ticker=ticker,
                    company_name=symbol.get("description") or symbol.get("name"),
                    quantity=units,
                    avg_buy_price=avg_price,
                    currency=currency,
                ))

        return holdings

    async def list_connections(self, user_id: UUID, user_secret: str) -> list[dict]:
        """List brokerage connections."""
        result = await self._request(
            "GET",
            "/authorizations",
            params={"userId": str(user_id), "userSecret": user_secret},
        )
        return result if isinstance(result, list) else []

    async def delete_user(self, user_id: UUID) -> bool:
        """Deregister user from SnapTrade."""
        result = await self._request("DELETE", "/snapTrade/deleteUser", params={
            "userId": str(user_id),
        })
        return result is not None
