"""SnapTrade integration — unified US broker connection (Robinhood, Fidelity, etc).

Flow:
1. Register RuDo user as SnapTrade user (once)
2. Generate Connection Portal URL (opens broker OAuth)
3. After auth, fetch holdings via SnapTrade API
4. Normalize to RuDo's NormalizedHolding format
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


def _sign_request(path: str, method: str = "GET", body: str = "") -> dict[str, str]:
    """Generate SnapTrade request signature headers."""
    consumer_key = settings.snaptrade_consumer_key
    client_id = settings.snaptrade_client_id
    timestamp = str(int(time.time()))

    # Signature: HMAC-SHA256(consumerKey, requestPath + timestamp + body)
    sig_content = f"/api/v1{path}{timestamp}{body}"
    signature = hmac.new(
        consumer_key.encode(),
        sig_content.encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        "clientId": client_id,
        "Signature": signature,
        "Timestamp": timestamp,
        "Content-Type": "application/json",
    }


class SnapTradeService:
    """Manages SnapTrade API interactions."""

    def __init__(self):
        self.client_id = settings.snaptrade_client_id
        self.consumer_key = settings.snaptrade_consumer_key

    def _get_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, params: dict = None, body: dict = None) -> Any:
        """Make signed request to SnapTrade API."""
        url = f"{BASE_URL}{path}"

        # Add clientId to params
        if params is None:
            params = {}

        # Build signature
        timestamp = str(int(time.time()))
        body_str = json.dumps(body) if body else ""

        sig_content = f"/api/v1{path}"
        # SnapTrade uses: path + clientId + timestamp for signature
        sig_data = f"{sig_content}&clientId={self.client_id}&timestamp={timestamp}"
        signature = hmac.new(
            self.consumer_key.encode(),
            sig_data.encode(),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "Signature": signature,
            "timestamp": timestamp,
        }

        params["clientId"] = self.client_id
        params["timestamp"] = timestamp
        params["Signature"] = signature

        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(url, params=params, headers=headers)
            elif method == "POST":
                resp = await client.post(url, params=params, json=body, headers=headers)
            elif method == "DELETE":
                resp = await client.delete(url, params=params, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if resp.status_code >= 400:
                logger.error("SnapTrade API error %d: %s", resp.status_code, resp.text[:200])
                return None

            return resp.json() if resp.text else None

    async def register_user(self, user_id: UUID) -> dict | None:
        """Register a RuDo user with SnapTrade. Returns userId and userSecret."""
        result = await self._request("POST", "/snapTrade/registerUser", body={
            "userId": str(user_id),
        })
        return result

    async def get_login_url(self, user_id: UUID, user_secret: str, broker: str = None) -> str | None:
        """Generate Connection Portal URL for user to connect their broker.

        Returns URL to redirect user to (opens broker OAuth flow).
        """
        body = {}
        if broker:
            body["broker"] = broker  # e.g., "ROBINHOOD", "FIDELITY"

        result = await self._request(
            "POST",
            "/snapTrade/login",
            params={"userId": str(user_id), "userSecret": user_secret},
            body=body,
        )
        if result and "redirectURI" in result:
            return result["redirectURI"]
        if result and "loginLink" in result:
            return result["loginLink"]
        return None

    async def list_accounts(self, user_id: UUID, user_secret: str) -> list[dict]:
        """List all connected brokerage accounts for a user."""
        result = await self._request(
            "GET",
            "/accounts",
            params={"userId": str(user_id), "userSecret": user_secret},
        )
        return result if isinstance(result, list) else []

    async def get_holdings(self, user_id: UUID, user_secret: str, account_id: str = None) -> list[RawHolding]:
        """Fetch holdings from all connected accounts (or specific account)."""
        if account_id:
            path = f"/accounts/{account_id}/positions"
        else:
            path = "/holdings"

        result = await self._request(
            "GET",
            path,
            params={"userId": str(user_id), "userSecret": user_secret},
        )

        if not result:
            return []

        holdings = []
        positions = result if isinstance(result, list) else result.get("positions", [])

        for pos in positions:
            symbol = pos.get("symbol", {})
            ticker = symbol.get("symbol") or symbol.get("rawSymbol", "")
            if not ticker:
                continue

            units = Decimal(str(pos.get("units", 0)))
            avg_price = Decimal(str(pos.get("averageEntryPrice") or pos.get("price", 0)))
            currency = symbol.get("currency", {}).get("code", "USD")

            holdings.append(RawHolding(
                broker_id="snaptrade",
                ticker=ticker,
                company_name=symbol.get("description") or symbol.get("name"),
                quantity=units,
                avg_buy_price=avg_price,
                currency=currency,
                extra={"account_id": account_id, "symbol_id": symbol.get("id")},
            ))

        return holdings

    async def list_connections(self, user_id: UUID, user_secret: str) -> list[dict]:
        """List all brokerage connections (authorizations) for a user."""
        result = await self._request(
            "GET",
            "/authorizations",
            params={"userId": str(user_id), "userSecret": user_secret},
        )
        return result if isinstance(result, list) else []

    async def delete_user(self, user_id: UUID) -> bool:
        """Deregister user from SnapTrade (cleanup)."""
        result = await self._request("DELETE", "/snapTrade/deleteUser", params={
            "userId": str(user_id),
        })
        return result is not None
