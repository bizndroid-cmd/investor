"""Zerodha broker connector implementing IBrokerConnector.

Uses the kiteconnect library for Kite Connect v3.
Auth: OAuth 2.0 (request_token → access_token).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

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


class ZerodhaConnector(IBrokerConnector):
    """Zerodha (Kite Connect v3) broker connector.

    Auth model: OAuth 2.0 — user is redirected to Kite login,
    receives a request_token, which is exchanged for an access_token.
    Uses the kiteconnect Python SDK.
    """

    broker_id: BrokerId = "zerodha"

    def _get_kite_client(self, access_token: str | None = None):
        """Create a KiteConnect client instance."""
        try:
            from kiteconnect import KiteConnect
        except ImportError:
            raise RuntimeError(
                "kiteconnect library is not installed. "
                "Install it with: pip install kiteconnect"
            )
        kite = KiteConnect(api_key=settings.zerodha_api_key)
        if access_token:
            kite.set_access_token(access_token)
        return kite

    async def get_authorization_url(self, user_id: UUID) -> str:
        """Return the Kite Connect login URL for OAuth authorization."""
        kite = self._get_kite_client()
        return kite.login_url()

    async def exchange_code_for_tokens(self, user_id: UUID, code: str) -> None:
        """Exchange the request_token (code) for an access_token via Kite Connect.

        The 'code' parameter is the request_token received after user login.
        """
        try:
            kite = self._get_kite_client()
            # generate_session exchanges request_token for access_token
            session_data = kite.generate_session(
                request_token=code,
                api_secret=settings.zerodha_api_secret,
            )

            access_token = session_data.get("access_token", "")
            # Kite access tokens are valid for one trading day (no refresh token)
            async with AsyncSessionLocal() as db:
                await store_broker_tokens(
                    db=db,
                    user_id=user_id,
                    broker_id=self.broker_id,
                    access_token=access_token,
                    refresh_token=None,
                    expires_at=None,  # Expires at end of trading day
                )
        except Exception as e:
            logger.error(
                "Zerodha token exchange failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            raise

    async def refresh_tokens(self, user_id: UUID) -> None:
        """Refresh the Zerodha access token.

        Kite Connect v3 access tokens are valid for one trading day and
        cannot be refreshed. The user must re-authenticate daily.
        This method updates the status to 'disconnected' if the token
        is no longer valid.
        """
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                return

            # Verify the token is still valid by making a profile call
            kite = self._get_kite_client(access_token=tokens[0])
            kite.profile()  # Raises if token is invalid
        except Exception as e:
            logger.warning(
                "Zerodha token refresh/validation failed for user %s: %s",
                user_id,
                str(e),
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "disconnected")

    async def revoke_tokens(self, user_id: UUID) -> None:
        """Revoke and delete all stored Zerodha tokens."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)

            if tokens is not None:
                kite = self._get_kite_client(access_token=tokens[0])
                try:
                    kite.invalidate_access_token()
                except Exception:
                    pass  # Best-effort revocation
        except Exception as e:
            logger.warning(
                "Zerodha token revocation failed for user %s: %s", user_id, str(e)
            )
        finally:
            async with AsyncSessionLocal() as db:
                await delete_broker_tokens(db, user_id, self.broker_id)

    async def is_connected(self, user_id: UUID) -> bool:
        """Check if the user has a valid Zerodha connection."""
        async with AsyncSessionLocal() as db:
            tokens = await get_broker_tokens(db, user_id, self.broker_id)
        if tokens is None:
            return False

        try:
            kite = self._get_kite_client(access_token=tokens[0])
            kite.profile()
            return True
        except Exception:
            return False

    async def get_holdings(self, user_id: UUID) -> list[RawHolding]:
        """Fetch the user's current holdings from Zerodha via Kite Connect."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                logger.warning("No Zerodha tokens for user %s", user_id)
                return []

            kite = self._get_kite_client(access_token=tokens[0])
            kite_holdings = kite.holdings()

            holdings: list[RawHolding] = []
            for item in kite_holdings:
                holdings.append(
                    RawHolding(
                        broker_id=self.broker_id,
                        ticker=item.get("tradingsymbol", ""),
                        company_name=item.get("instrument_token", None),
                        quantity=Decimal(str(item.get("quantity", 0))),
                        avg_buy_price=Decimal(str(item.get("average_price", 0))),
                        currency="INR",
                        extra={
                            "isin": item.get("isin", ""),
                            "exchange": item.get("exchange", ""),
                            "product": item.get("product", ""),
                        },
                    )
                )
            return holdings
        except Exception as e:
            logger.error(
                "Zerodha get_holdings failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return []

    async def get_orders(self, user_id: UUID) -> list[RawOrder]:
        """Fetch the user's order history from Zerodha via Kite Connect."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                return []

            kite = self._get_kite_client(access_token=tokens[0])
            kite_orders = kite.orders()

            orders: list[RawOrder] = []
            for item in kite_orders:
                # Map Kite order types to our domain
                order_type = "limit" if item.get("order_type") == "LIMIT" else "market"
                side = "buy" if item.get("transaction_type") == "BUY" else "sell"

                # Map Kite status to our domain status
                kite_status = item.get("status", "").upper()
                if kite_status == "COMPLETE":
                    status = "filled"
                elif kite_status == "REJECTED":
                    status = "rejected"
                elif kite_status == "CANCELLED":
                    status = "cancelled"
                else:
                    status = "pending"

                placed_at = item.get("order_timestamp")
                if isinstance(placed_at, str):
                    placed_at = datetime.fromisoformat(placed_at)
                elif placed_at is None:
                    placed_at = datetime.now(timezone.utc)

                orders.append(
                    RawOrder(
                        broker_id=self.broker_id,
                        broker_order_id=str(item.get("order_id", "")),
                        ticker=item.get("tradingsymbol", ""),
                        order_type=order_type,
                        side=side,
                        quantity=Decimal(str(item.get("quantity", 0))),
                        limit_price=(
                            Decimal(str(item["price"]))
                            if item.get("price") and float(item["price"]) > 0
                            else None
                        ),
                        execution_price=(
                            Decimal(str(item["average_price"]))
                            if item.get("average_price")
                            and float(item["average_price"]) > 0
                            else None
                        ),
                        status=status,
                        placed_at=placed_at,
                    )
                )
            return orders
        except Exception as e:
            logger.error(
                "Zerodha get_orders failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return []

    async def place_order(self, user_id: UUID, order: OrderRequest) -> OrderResult:
        """Submit an order to Zerodha via Kite Connect."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                return OrderResult(
                    broker_order_id="",
                    status="rejected",
                    rejection_reason="Not connected to Zerodha",
                )

            kite = self._get_kite_client(access_token=tokens[0])

            # Map our domain to Kite Connect parameters
            transaction_type = "BUY" if order.side == "buy" else "SELL"
            order_type = "LIMIT" if order.order_type == "limit" else "MARKET"

            params = {
                "tradingsymbol": order.ticker,
                "exchange": "NSE",
                "transaction_type": transaction_type,
                "quantity": int(order.quantity),
                "order_type": order_type,
                "product": "CNC",  # Cash and Carry (delivery)
            }
            if order.limit_price is not None:
                params["price"] = float(order.limit_price)

            order_id = kite.place_order(variety="regular", **params)

            return OrderResult(
                broker_order_id=str(order_id),
                status="pending",
            )
        except Exception as e:
            logger.error(
                "Zerodha place_order failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return OrderResult(
                broker_order_id="",
                status="rejected",
                rejection_reason=str(e),
            )

    async def cancel_order(self, user_id: UUID, order_id: str) -> None:
        """Cancel an existing open order at Zerodha via Kite Connect."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                logger.warning(
                    "No Zerodha tokens for user %s, cannot cancel order", user_id
                )
                return

            kite = self._get_kite_client(access_token=tokens[0])
            kite.cancel_order(variety="regular", order_id=order_id)
        except Exception as e:
            logger.error(
                "Zerodha cancel_order failed for user %s, order %s: %s",
                user_id,
                order_id,
                str(e),
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            raise
