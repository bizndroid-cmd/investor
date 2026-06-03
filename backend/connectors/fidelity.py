"""Fidelity broker connector implementing IBrokerConnector.

Uses SnapTrade SDK for OAuth 2.0 access to Fidelity accounts.
SnapTrade is a regulated aggregator that provides OAuth-based access
to Fidelity (and 50+ other brokers).
"""

from __future__ import annotations

import logging
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
from backend.utils.broker_token_store import (
    delete_broker_tokens,
    get_broker_tokens,
    store_broker_tokens,
    update_broker_status,
)

logger = logging.getLogger(__name__)

SNAPTRADE_BASE_URL = "https://api.snaptrade.com/api/v1"


class FidelityConnector(IBrokerConnector):
    """Fidelity broker connector via SnapTrade.

    Auth model: OAuth 2.0 via SnapTrade. The user is redirected to
    SnapTrade's connection portal where they authorize Fidelity access.
    SnapTrade handles the Fidelity-specific auth and provides a
    unified API for holdings, orders, etc.
    """

    broker_id: BrokerId = "fidelity"

    def _get_auth_headers(self) -> dict[str, str]:
        """Return SnapTrade authentication headers."""
        return {
            "clientId": settings.snaptrade_client_id,
            "consumerKey": settings.snaptrade_consumer_key,
            "Content-Type": "application/json",
        }

    async def get_authorization_url(self, user_id: UUID) -> str:
        """Return the SnapTrade redirect URL for Fidelity OAuth authorization."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{SNAPTRADE_BASE_URL}/snapTrade/login",
                    json={
                        "userId": str(user_id),
                        "broker": "FIDELITY",
                    },
                    headers=self._get_auth_headers(),
                )
                response.raise_for_status()
                data = response.json()

            return data.get("redirectURI", data.get("loginLink", ""))
        except Exception as e:
            logger.error(
                "Fidelity get_authorization_url failed for user %s: %s",
                user_id,
                str(e),
            )
            raise

    async def exchange_code_for_tokens(self, user_id: UUID, code: str) -> None:
        """Exchange the SnapTrade authorization code for tokens.

        After the user completes the SnapTrade OAuth flow, we receive
        a code that we exchange for access credentials.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{SNAPTRADE_BASE_URL}/snapTrade/token",
                    json={
                        "userId": str(user_id),
                        "code": code,
                    },
                    headers=self._get_auth_headers(),
                )
                response.raise_for_status()
                data = response.json()

            access_token = data.get("access_token", "")
            refresh_token = data.get("refresh_token")
            expires_at = None
            if "expires_at" in data:
                expires_at = datetime.fromisoformat(data["expires_at"])

            async with AsyncSessionLocal() as db:
                await store_broker_tokens(
                    db=db,
                    user_id=user_id,
                    broker_id=self.broker_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                )
        except httpx.HTTPStatusError as e:
            logger.error(
                "Fidelity token exchange failed for user %s: %s",
                user_id,
                e.response.status_code,
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            raise
        except Exception as e:
            logger.error(
                "Fidelity token exchange error for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            raise

    async def refresh_tokens(self, user_id: UUID) -> None:
        """Refresh the SnapTrade/Fidelity access token."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                return

            access_token, refresh_token = tokens
            if refresh_token is None:
                logger.warning("No refresh token for Fidelity user %s", user_id)
                return

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{SNAPTRADE_BASE_URL}/snapTrade/refresh",
                    json={
                        "userId": str(user_id),
                        "refreshToken": refresh_token,
                    },
                    headers=self._get_auth_headers(),
                )
                response.raise_for_status()
                data = response.json()

            new_access_token = data.get("access_token", access_token)
            new_refresh_token = data.get("refresh_token", refresh_token)
            expires_at = None
            if "expires_at" in data:
                expires_at = datetime.fromisoformat(data["expires_at"])

            async with AsyncSessionLocal() as db:
                await store_broker_tokens(
                    db=db,
                    user_id=user_id,
                    broker_id=self.broker_id,
                    access_token=new_access_token,
                    refresh_token=new_refresh_token,
                    expires_at=expires_at,
                )
        except Exception as e:
            logger.error(
                "Fidelity token refresh failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")

    async def revoke_tokens(self, user_id: UUID) -> None:
        """Revoke and delete all stored Fidelity/SnapTrade tokens."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.delete(
                    f"{SNAPTRADE_BASE_URL}/snapTrade/connections",
                    params={"userId": str(user_id)},
                    headers=self._get_auth_headers(),
                )
        except Exception as e:
            logger.warning(
                "Fidelity token revocation failed for user %s: %s", user_id, str(e)
            )
        finally:
            async with AsyncSessionLocal() as db:
                await delete_broker_tokens(db, user_id, self.broker_id)

    async def is_connected(self, user_id: UUID) -> bool:
        """Check if the user has a valid Fidelity connection via SnapTrade."""
        async with AsyncSessionLocal() as db:
            tokens = await get_broker_tokens(db, user_id, self.broker_id)
        return tokens is not None

    async def get_holdings(self, user_id: UUID) -> list[RawHolding]:
        """Fetch the user's current holdings from Fidelity via SnapTrade."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                logger.warning("No Fidelity tokens for user %s", user_id)
                return []

            headers = self._get_auth_headers()
            headers["Authorization"] = f"Bearer {tokens[0]}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{SNAPTRADE_BASE_URL}/holdings",
                    params={"userId": str(user_id)},
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

            holdings: list[RawHolding] = []
            # SnapTrade returns holdings grouped by account
            accounts = data if isinstance(data, list) else [data]
            for account in accounts:
                positions = account.get("positions", account.get("holdings", []))
                for item in positions:
                    symbol_info = item.get("symbol", {})
                    ticker = (
                        symbol_info.get("symbol", "")
                        if isinstance(symbol_info, dict)
                        else str(symbol_info)
                    )
                    holdings.append(
                        RawHolding(
                            broker_id=self.broker_id,
                            ticker=ticker,
                            company_name=symbol_info.get("description")
                            if isinstance(symbol_info, dict)
                            else None,
                            quantity=Decimal(str(item.get("units", item.get("quantity", 0)))),
                            avg_buy_price=Decimal(
                                str(item.get("averagePrice", item.get("average_purchase_price", 0)))
                            ),
                            currency=item.get("currency", "USD"),
                            extra={
                                "account_id": account.get("accountId", ""),
                            },
                        )
                    )
            return holdings
        except Exception as e:
            logger.error(
                "Fidelity get_holdings failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return []

    async def get_orders(self, user_id: UUID) -> list[RawOrder]:
        """Fetch the user's order history from Fidelity via SnapTrade."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                return []

            headers = self._get_auth_headers()
            headers["Authorization"] = f"Bearer {tokens[0]}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{SNAPTRADE_BASE_URL}/activities",
                    params={"userId": str(user_id)},
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

            orders: list[RawOrder] = []
            activities = data if isinstance(data, list) else data.get("activities", [])
            for item in activities:
                # Map SnapTrade activity to our domain
                action = item.get("action", "").lower()
                side = "buy" if "buy" in action else "sell"
                order_type = "limit" if item.get("type", "").lower() == "limit" else "market"

                snap_status = item.get("status", "").lower()
                if snap_status in ("executed", "filled"):
                    status = "filled"
                elif snap_status == "rejected":
                    status = "rejected"
                elif snap_status in ("cancelled", "canceled"):
                    status = "cancelled"
                else:
                    status = "pending"

                placed_at_str = item.get("trade_date", item.get("created_at"))
                if placed_at_str:
                    placed_at = datetime.fromisoformat(placed_at_str)
                else:
                    placed_at = datetime.now(timezone.utc)

                symbol_info = item.get("symbol", {})
                ticker = (
                    symbol_info.get("symbol", "")
                    if isinstance(symbol_info, dict)
                    else str(symbol_info)
                )

                orders.append(
                    RawOrder(
                        broker_id=self.broker_id,
                        broker_order_id=str(item.get("id", item.get("order_id", ""))),
                        ticker=ticker,
                        order_type=order_type,
                        side=side,
                        quantity=Decimal(str(item.get("units", item.get("quantity", 0)))),
                        limit_price=(
                            Decimal(str(item["limit_price"]))
                            if item.get("limit_price")
                            else None
                        ),
                        execution_price=(
                            Decimal(str(item["price"]))
                            if item.get("price")
                            else None
                        ),
                        status=status,
                        placed_at=placed_at,
                    )
                )
            return orders
        except Exception as e:
            logger.error(
                "Fidelity get_orders failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return []

    async def place_order(self, user_id: UUID, order: OrderRequest) -> OrderResult:
        """Submit an order to Fidelity via SnapTrade."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                return OrderResult(
                    broker_order_id="",
                    status="rejected",
                    rejection_reason="Not connected to Fidelity",
                )

            headers = self._get_auth_headers()
            headers["Authorization"] = f"Bearer {tokens[0]}"

            payload = {
                "userId": str(user_id),
                "action": order.side.upper(),
                "orderType": order.order_type.upper(),
                "symbol": order.ticker,
                "units": str(order.quantity),
                "timeInForce": "Day",
            }
            if order.limit_price is not None:
                payload["limitPrice"] = str(order.limit_price)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{SNAPTRADE_BASE_URL}/trade/place",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

            return OrderResult(
                broker_order_id=str(data.get("orderId", data.get("id", ""))),
                status=data.get("status", "pending"),
                execution_price=(
                    Decimal(str(data["executionPrice"]))
                    if data.get("executionPrice")
                    else None
                ),
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                "Fidelity place_order failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return OrderResult(
                broker_order_id="",
                status="rejected",
                rejection_reason=f"SnapTrade API error: {e.response.status_code}",
            )
        except Exception as e:
            logger.error(
                "Fidelity place_order error for user %s: %s", user_id, str(e)
            )
            return OrderResult(
                broker_order_id="",
                status="rejected",
                rejection_reason=str(e),
            )

    async def cancel_order(self, user_id: UUID, order_id: str) -> None:
        """Cancel an existing open order at Fidelity via SnapTrade."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                logger.warning(
                    "No Fidelity tokens for user %s, cannot cancel order", user_id
                )
                return

            headers = self._get_auth_headers()
            headers["Authorization"] = f"Bearer {tokens[0]}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{SNAPTRADE_BASE_URL}/trade/cancel",
                    json={
                        "userId": str(user_id),
                        "orderId": order_id,
                    },
                    headers=headers,
                )
                response.raise_for_status()
        except Exception as e:
            logger.error(
                "Fidelity cancel_order failed for user %s, order %s: %s",
                user_id,
                order_id,
                str(e),
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            raise
