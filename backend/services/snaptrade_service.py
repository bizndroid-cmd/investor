"""SnapTrade integration — unified US broker connection via OAuth.

Uses SnapTrade REST API with proper HMAC-SHA256 request signing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from base64 import b64encode
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx

from backend.config import settings
from backend.models.domain import RawHolding

logger = logging.getLogger(__name__)

BASE_URL = "https://api.snaptrade.com/api/v1"


def _compute_signature(consumer_key: str, path: str, query_string: str, body: Any = None) -> str:
    """Compute SnapTrade request signature.

    1. Build payload: {content, path, query} with sorted keys
    2. Canonical JSON (sorted, no whitespace)
    3. HMAC-SHA256 with consumerKey
    4. Base64 encode
    """
    content = body if body is not None else None

    payload = {
        "content": content,
        "path": path,
        "query": query_string,
    }

    # Canonical JSON: sorted keys, no whitespace
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    # HMAC-SHA256
    sig = hmac.new(
        consumer_key.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return b64encode(sig).decode("utf-8")


class SnapTradeService:
    """SnapTrade API client with proper request signing."""

    def __init__(self):
        self.client_id = settings.snaptrade_client_id
        self.consumer_key = settings.snaptrade_consumer_key

    async def _request(self, method: str, path: str, params: dict = None, body: dict = None) -> Any:
        """Make signed request to SnapTrade API."""
        if params is None:
            params = {}

        # Add required auth params
        params["clientId"] = self.client_id
        params["timestamp"] = str(int(time.time()))

        # Build query string (exact order matters for signature)
        query_string = urlencode(params)
        full_path = f"/api/v1{path}"

        # Compute signature
        signature = _compute_signature(
            self.consumer_key,
            full_path,
            query_string,
            body,
        )

        url = f"{BASE_URL}{path}?{query_string}"
        headers = {
            "Signature": signature,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                elif method == "POST":
                    resp = await client.post(url, headers=headers, json=body)
                elif method == "DELETE":
                    resp = await client.delete(url, headers=headers)
                else:
                    return None

                if resp.status_code >= 400:
                    logger.warning("SnapTrade %s %s -> %d: %s", method, path, resp.status_code, resp.text[:300])
                    return None

                return resp.json() if resp.text.strip() else None
            except Exception as e:
                logger.error("SnapTrade request error: %s", str(e))
                return None

    async def register_user(self, user_id: UUID) -> dict | None:
        """Register a RuDo user with SnapTrade."""
        return await self._request("POST", "/snapTrade/registerUser", body={
            "userId": str(user_id),
        })

    async def get_login_url(self, user_id: UUID, user_secret: str, broker: str = None) -> str | None:
        """Get Connection Portal URL for broker OAuth (Commercial key)."""
        body = {}
        if broker:
            body["broker"] = broker

        result = await self._request(
            "POST",
            "/snapTrade/login",
            params={"userId": str(user_id), "userSecret": user_secret},
            body=body if body else None,
        )
        if result:
            return result.get("redirectURI") or result.get("loginLink")
        return None

    async def get_personal_login_url(self, broker: str = None) -> str | None:
        """Get Connection Portal URL for Personal key (no userId/userSecret)."""
        body = {}
        if broker:
            body["broker"] = broker

        result = await self._request(
            "POST",
            "/snapTrade/login",
            body=body if body else None,
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
