"""Groww broker connector implementing IBrokerConnector.

Uses the official Groww Trading API (https://groww.in/trade-api/docs).
Base URL: https://api.groww.in/v1
Auth: Bearer access token + X-API-VERSION: 1.0 header.

The access token can be generated via:
  1. Access Token (from Groww settings page, expires daily at 6 AM)
  2. API Key + Secret (requires checksum, daily approval)
  3. API Key + TOTP (requires daily approval)

This connector uses the access token directly (stored in settings or broker_tokens table).
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import httpx

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.interfaces.broker_connector import IBrokerConnector
from backend.models.domain import (
    BrokerId,
    OrderRequest,
    OrderResult,
    RawHolding,
    RawOrder,
)
from backend.services.telemetry_service import get_telemetry_service
from backend.utils.broker_token_store import (
    delete_broker_tokens,
    get_broker_tokens,
    store_broker_tokens,
    update_broker_status,
)

logger = logging.getLogger(__name__)

GROWW_BASE_URL = "https://api.groww.in/v1"


def _generate_checksum(secret: str, timestamp: str) -> str:
    """Generate SHA256 checksum from API secret + timestamp (epoch seconds)."""
    raw = secret + timestamp
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_headers(access_token: str) -> dict[str, str]:
    """Standard headers for all Groww API requests."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "X-API-VERSION": "1.0",
    }


class GrowwConnector(IBrokerConnector):
    """Groww broker connector using the official Trading API.

    The access token from settings.groww_api_key is used directly.
    For users who connect via the dashboard, tokens are stored in broker_tokens table.
    """

    broker_id: BrokerId = "groww"
    supported_geographies: list[str] = ["IN"]

    async def _get_access_token(self, user_id: UUID) -> str | None:
        """Get the access token — first check broker_tokens table, then fall back to settings."""
        async with AsyncSessionLocal() as db:
            tokens = await get_broker_tokens(db, user_id, self.broker_id)
        if tokens is not None:
            return tokens[0]  # access_token
        # Fall back to the access token from settings
        if settings.groww_access_token:
            return settings.groww_access_token
        # Fall back to the API key (may be a valid access token in some setups)
        if settings.groww_api_key:
            return settings.groww_api_key
        return None

    async def get_authorization_url(self, user_id: UUID) -> str:
        """Generate an access token using API Key + Secret (checksum flow).

        Since Groww doesn't use traditional OAuth redirects, this method
        generates a token using the API key + secret checksum approach
        and stores it directly.
        """
        if not settings.groww_api_key or not settings.groww_api_secret:
            raise ValueError("Groww API key and secret are required")

        # Generate checksum: SHA256(secret + timestamp)
        timestamp = str(int(time.time()))
        checksum = _generate_checksum(settings.groww_api_secret, timestamp)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{GROWW_BASE_URL}/auth/token",
                    json={
                        "key_type": "approval",
                        "checksum": checksum,
                        "timestamp": timestamp,
                    },
                    headers={
                        "Authorization": settings.groww_api_key,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()

            access_token = data.get("token", "")
            expiry = data.get("expiry")
            expires_at = None
            if expiry:
                try:
                    expires_at = datetime.fromisoformat(expiry)
                except (ValueError, TypeError):
                    pass

            # Store the token
            async with AsyncSessionLocal() as db:
                await store_broker_tokens(
                    db=db,
                    user_id=user_id,
                    broker_id=self.broker_id,
                    access_token=access_token,
                    refresh_token=None,
                    expires_at=expires_at,
                )

            # Return empty string since there's no redirect URL
            return ""
        except httpx.HTTPStatusError as e:
            logger.error("Groww auth failed: %s - %s", e.response.status_code, e.response.text)
            # If token generation fails, store the API key directly as the access token
            # (it may already be a valid access token)
            async with AsyncSessionLocal() as db:
                await store_broker_tokens(
                    db=db,
                    user_id=user_id,
                    broker_id=self.broker_id,
                    access_token=settings.groww_api_key,
                    refresh_token=None,
                    expires_at=None,
                )
            return ""

    async def exchange_code_for_tokens(self, user_id: UUID, code: str) -> None:
        """Exchange TOTP code for access token (TOTP auth flow).

        For Groww, the 'code' parameter is the TOTP code.
        """
        if not settings.groww_api_key:
            raise ValueError("Groww API key is required")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{GROWW_BASE_URL}/auth/token",
                    json={
                        "key_type": "totp",
                        "totp": code,
                    },
                    headers={
                        "Authorization": settings.groww_api_key,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()

            access_token = data.get("token", "")
            expiry = data.get("expiry")
            expires_at = None
            if expiry:
                try:
                    expires_at = datetime.fromisoformat(expiry)
                except (ValueError, TypeError):
                    pass

            async with AsyncSessionLocal() as db:
                await store_broker_tokens(
                    db=db,
                    user_id=user_id,
                    broker_id=self.broker_id,
                    access_token=access_token,
                    refresh_token=None,
                    expires_at=expires_at,
                )
        except httpx.HTTPStatusError as e:
            logger.error("Groww TOTP exchange failed: %s", e.response.status_code)
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            raise

    async def refresh_tokens(self, user_id: UUID) -> None:
        """Refresh Groww token using API key + secret checksum flow.

        Groww tokens expire daily at 6 AM. This regenerates a new token.
        """
        if not settings.groww_api_key or not settings.groww_api_secret:
            return

        timestamp = str(int(time.time()))
        checksum = _generate_checksum(settings.groww_api_secret, timestamp)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{GROWW_BASE_URL}/auth/token",
                    json={
                        "key_type": "approval",
                        "checksum": checksum,
                        "timestamp": timestamp,
                    },
                    headers={
                        "Authorization": settings.groww_api_key,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()

            new_token = data.get("token", "")
            expiry = data.get("expiry")
            expires_at = None
            if expiry:
                try:
                    expires_at = datetime.fromisoformat(expiry)
                except (ValueError, TypeError):
                    pass

            async with AsyncSessionLocal() as db:
                await store_broker_tokens(
                    db=db,
                    user_id=user_id,
                    broker_id=self.broker_id,
                    access_token=new_token,
                    refresh_token=None,
                    expires_at=expires_at,
                )
        except Exception as e:
            logger.error("Groww token refresh failed for user %s: %s", user_id, str(e))
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")

    async def revoke_tokens(self, user_id: UUID) -> None:
        """Delete stored Groww tokens (Groww doesn't have a revoke endpoint)."""
        async with AsyncSessionLocal() as db:
            await delete_broker_tokens(db, user_id, self.broker_id)

    async def is_connected(self, user_id: UUID) -> bool:
        """Check if the user has a valid Groww connection.
        
        Only checks the user's stored token in the database (not env fallback).
        """
        async with AsyncSessionLocal() as db:
            tokens = await get_broker_tokens(db, user_id, self.broker_id)
        return tokens is not None

    async def get_holdings(self, user_id: UUID) -> list[RawHolding]:
        """Fetch holdings from GET /v1/holdings/user."""
        token = await self._get_access_token(user_id)
        if not token:
            logger.warning("No Groww access token for user %s", user_id)
            return []

        telemetry = get_telemetry_service()
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{GROWW_BASE_URL}/holdings/user",
                    headers=_get_headers(token),
                )
                response.raise_for_status()
                data = response.json()
            latency = (time.time() - start) * 1000
            telemetry.record_api_call(
                service="Groww",
                endpoint="/v1/holdings/user",
                method="GET",
                status_code=response.status_code,
                latency_ms=latency,
                success=True,
            )

            if data.get("status") != "SUCCESS":
                logger.error("Groww holdings API returned: %s", data.get("status"))
                return []

            holdings: list[RawHolding] = []
            for item in data.get("payload", {}).get("holdings", []):
                holdings.append(
                    RawHolding(
                        broker_id=self.broker_id,
                        ticker=item.get("trading_symbol", ""),
                        company_name=item.get("trading_symbol", ""),
                        quantity=Decimal(str(item.get("quantity", 0))),
                        avg_buy_price=Decimal(str(item.get("average_price", 0))),
                        currency="INR",
                    )
                )
            return holdings
        except httpx.HTTPStatusError as e:
            latency = (time.time() - start) * 1000
            telemetry.record_api_call(
                service="Groww",
                endpoint="/v1/holdings/user",
                method="GET",
                status_code=e.response.status_code,
                latency_ms=latency,
                success=False,
                error=f"HTTP {e.response.status_code}",
            )
            logger.error(
                "Groww get_holdings failed for user %s: HTTP %s - %s",
                user_id, e.response.status_code, e.response.text[:200],
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return []
        except Exception as e:
            latency = (time.time() - start) * 1000
            telemetry.record_api_call(
                service="Groww",
                endpoint="/v1/holdings/user",
                method="GET",
                status_code=None,
                latency_ms=latency,
                success=False,
                error=str(e),
            )
            logger.error("Groww get_holdings error for user %s: %s", user_id, str(e))
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return []

    async def get_orders(self, user_id: UUID) -> list[RawOrder]:
        """Fetch order history from GET /v1/order/list."""
        token = await self._get_access_token(user_id)
        if not token:
            return []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{GROWW_BASE_URL}/order/list",
                    params={"segment": "CASH"},
                    headers=_get_headers(token),
                )
                response.raise_for_status()
                data = response.json()

            if data.get("status") != "SUCCESS":
                return []

            orders: list[RawOrder] = []
            for item in data.get("payload", {}).get("orders", []):
                # Map Groww order status to our status
                groww_status = item.get("order_status", "").lower()
                status = "pending"
                if groww_status in ("executed", "filled", "complete"):
                    status = "filled"
                elif groww_status in ("rejected", "cancelled"):
                    status = "rejected"

                placed_at = datetime.now(timezone.utc)
                if item.get("created_at"):
                    try:
                        placed_at = datetime.fromisoformat(item["created_at"])
                    except (ValueError, TypeError):
                        pass

                orders.append(
                    RawOrder(
                        broker_id=self.broker_id,
                        broker_order_id=item.get("groww_order_id", ""),
                        ticker=item.get("trading_symbol", ""),
                        order_type=item.get("order_type", "MARKET").lower(),
                        side=item.get("transaction_type", "BUY").lower(),
                        quantity=Decimal(str(item.get("quantity", 0))),
                        limit_price=(
                            Decimal(str(item["price"]))
                            if item.get("price") and float(item.get("price", 0)) > 0
                            else None
                        ),
                        execution_price=(
                            Decimal(str(item["average_fill_price"]))
                            if item.get("average_fill_price") and float(item.get("average_fill_price", 0)) > 0
                            else None
                        ),
                        status=status,
                        placed_at=placed_at,
                    )
                )
            return orders
        except Exception as e:
            logger.error("Groww get_orders failed for user %s: %s", user_id, str(e))
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return []

    async def place_order(self, user_id: UUID, order: OrderRequest) -> OrderResult:
        """Place an order via POST /v1/order/create."""
        token = await self._get_access_token(user_id)
        if not token:
            return OrderResult(
                broker_order_id="",
                status="rejected",
                rejection_reason="Not connected to Groww",
            )

        # Generate a unique order reference ID
        order_ref = f"sid-{int(time.time())}-{str(user_id)[:8]}"

        payload = {
            "trading_symbol": order.ticker,
            "quantity": int(order.quantity),
            "exchange": "NSE",
            "segment": "CASH",
            "product": "CNC",
            "order_type": order.order_type.upper(),  # MARKET or LIMIT
            "transaction_type": order.side.upper(),  # BUY or SELL
            "validity": "DAY",
            "order_reference_id": order_ref,
        }
        if order.order_type == "limit" and order.limit_price is not None:
            payload["price"] = str(order.limit_price)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{GROWW_BASE_URL}/order/create",
                    json=payload,
                    headers={
                        **_get_headers(token),
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()

            if data.get("status") == "SUCCESS":
                return OrderResult(
                    broker_order_id=data.get("payload", {}).get("groww_order_id", ""),
                    status="pending",
                )
            else:
                return OrderResult(
                    broker_order_id="",
                    status="rejected",
                    rejection_reason=data.get("error", {}).get("message", "Order failed"),
                )
        except httpx.HTTPStatusError as e:
            logger.error("Groww place_order failed: HTTP %s", e.response.status_code)
            return OrderResult(
                broker_order_id="",
                status="rejected",
                rejection_reason=f"Groww API error: {e.response.status_code}",
            )
        except Exception as e:
            logger.error("Groww place_order error: %s", str(e))
            return OrderResult(
                broker_order_id="",
                status="rejected",
                rejection_reason=str(e),
            )

    async def cancel_order(self, user_id: UUID, order_id: str) -> None:
        """Cancel an order via POST /v1/order/cancel."""
        token = await self._get_access_token(user_id)
        if not token:
            raise ValueError("Not connected to Groww")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{GROWW_BASE_URL}/order/cancel",
                    json={
                        "groww_order_id": order_id,
                        "segment": "CASH",
                    },
                    headers={
                        **_get_headers(token),
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
        except Exception as e:
            logger.error("Groww cancel_order failed for order %s: %s", order_id, str(e))
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            raise
