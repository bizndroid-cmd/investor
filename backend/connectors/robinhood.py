"""Robinhood broker connector implementing IBrokerConnector.

Uses the robin_stocks library directly (in-process, no sidecar).
Auth: username + password + TOTP MFA.
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


class RobinhoodConnector(IBrokerConnector):
    """Robinhood broker connector using robin_stocks.

    Auth model: username + password + TOTP MFA.
    robin_stocks runs in-process as a first-class connector.
    The connector is isolated behind IBrokerConnector so it can
    be replaced without affecting other components.
    """

    broker_id: BrokerId = "robinhood"
    supported_geographies: list[str] = ["US"]

    def _login(self) -> bool:
        """Authenticate with Robinhood using robin_stocks.

        Returns True if login was successful.
        """
        try:
            import robin_stocks.robinhood as rh
        except ImportError:
            raise RuntimeError(
                "robin_stocks library is not installed. "
                "Install it with: pip install robin_stocks"
            )

        try:
            # robin_stocks handles TOTP internally if configured
            login_result = rh.login(
                username=settings.robinhood_username,
                password=settings.robinhood_password,
                store_session=False,
            )
            return login_result is not None
        except Exception as e:
            logger.error("Robinhood login failed: %s", str(e))
            return False

    def _ensure_logged_in(self) -> bool:
        """Ensure we have an active robin_stocks session."""
        try:
            import robin_stocks.robinhood as rh

            # Check if already logged in by trying to get account info
            account = rh.load_account_profile()
            if account:
                return True
        except Exception:
            pass

        return self._login()

    async def get_authorization_url(self, user_id: UUID) -> str:
        """Return the Robinhood authorization URL.

        Robinhood doesn't use OAuth redirects — authentication is done
        via username/password/TOTP. This returns a placeholder URL that
        the frontend can use to show a credential input form.
        """
        # Robinhood uses direct credential auth, not OAuth redirect
        return "robinhood://auth/credentials"

    async def exchange_code_for_tokens(self, user_id: UUID, code: str) -> None:
        """Authenticate with Robinhood and store the session token.

        For Robinhood, the 'code' parameter represents the TOTP MFA code.
        The username and password come from settings.
        """
        try:
            import robin_stocks.robinhood as rh

            login_result = rh.login(
                username=settings.robinhood_username,
                password=settings.robinhood_password,
                mfa_code=code,
                store_session=False,
            )

            if login_result is None:
                raise ValueError("Robinhood login returned None")

            # Store the access token from the login result
            access_token = login_result.get("access_token", "")
            refresh_token = login_result.get("refresh_token")

            async with AsyncSessionLocal() as db:
                await store_broker_tokens(
                    db=db,
                    user_id=user_id,
                    broker_id=self.broker_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=None,
                )
        except Exception as e:
            logger.error(
                "Robinhood token exchange failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            raise

    async def refresh_tokens(self, user_id: UUID) -> None:
        """Refresh the Robinhood session.

        robin_stocks handles token refresh internally. We re-login
        if the current session is invalid.
        """
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                return

            import robin_stocks.robinhood as rh

            # Try to refresh using the stored refresh token
            access_token, refresh_token = tokens
            if refresh_token:
                try:
                    # Attempt to use refresh token
                    login_result = rh.login(
                        username=settings.robinhood_username,
                        password=settings.robinhood_password,
                        store_session=False,
                    )
                    if login_result:
                        new_access = login_result.get("access_token", access_token)
                        new_refresh = login_result.get("refresh_token", refresh_token)
                        async with AsyncSessionLocal() as db:
                            await store_broker_tokens(
                                db=db,
                                user_id=user_id,
                                broker_id=self.broker_id,
                                access_token=new_access,
                                refresh_token=new_refresh,
                            )
                        return
                except Exception:
                    pass

            # Fallback: full re-login
            if self._login():
                account = rh.load_account_profile()
                if account:
                    async with AsyncSessionLocal() as db:
                        await update_broker_status(
                            db, user_id, self.broker_id, "connected"
                        )
                    return

            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "disconnected")
        except Exception as e:
            logger.error(
                "Robinhood token refresh failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")

    async def revoke_tokens(self, user_id: UUID) -> None:
        """Revoke and delete all stored Robinhood tokens."""
        try:
            import robin_stocks.robinhood as rh

            rh.logout()
        except Exception as e:
            logger.warning(
                "Robinhood logout failed for user %s: %s", user_id, str(e)
            )
        finally:
            async with AsyncSessionLocal() as db:
                await delete_broker_tokens(db, user_id, self.broker_id)

    async def is_connected(self, user_id: UUID) -> bool:
        """Check if the user has a valid Robinhood connection."""
        async with AsyncSessionLocal() as db:
            tokens = await get_broker_tokens(db, user_id, self.broker_id)
        return tokens is not None

    async def get_holdings(self, user_id: UUID) -> list[RawHolding]:
        """Fetch the user's current holdings from Robinhood."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                logger.warning("No Robinhood tokens for user %s", user_id)
                return []

            if not self._ensure_logged_in():
                async with AsyncSessionLocal() as db:
                    await update_broker_status(db, user_id, self.broker_id, "error")
                return []

            import robin_stocks.robinhood as rh

            rh_holdings = rh.build_holdings()

            holdings: list[RawHolding] = []
            for ticker, data in rh_holdings.items():
                holdings.append(
                    RawHolding(
                        broker_id=self.broker_id,
                        ticker=ticker,
                        company_name=data.get("name"),
                        quantity=Decimal(str(data.get("quantity", 0))),
                        avg_buy_price=Decimal(str(data.get("average_buy_price", 0))),
                        currency="USD",
                        extra={
                            "equity": data.get("equity", ""),
                            "percent_change": data.get("percent_change", ""),
                            "equity_change": data.get("equity_change", ""),
                        },
                    )
                )
            return holdings
        except Exception as e:
            logger.error(
                "Robinhood get_holdings failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return []

    async def get_orders(self, user_id: UUID) -> list[RawOrder]:
        """Fetch the user's order history from Robinhood."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                return []

            if not self._ensure_logged_in():
                async with AsyncSessionLocal() as db:
                    await update_broker_status(db, user_id, self.broker_id, "error")
                return []

            import robin_stocks.robinhood as rh

            rh_orders = rh.get_all_stock_orders()

            orders: list[RawOrder] = []
            for item in rh_orders or []:
                # Map Robinhood order data to our domain
                side = item.get("side", "buy")
                rh_type = item.get("type", "market")
                order_type = "limit" if rh_type == "limit" else "market"

                rh_state = item.get("state", "").lower()
                if rh_state == "filled":
                    status = "filled"
                elif rh_state == "rejected":
                    status = "rejected"
                elif rh_state in ("cancelled", "canceled"):
                    status = "cancelled"
                else:
                    status = "pending"

                placed_at_str = item.get("created_at")
                if placed_at_str:
                    # Robinhood uses ISO format with Z suffix
                    placed_at = datetime.fromisoformat(
                        placed_at_str.replace("Z", "+00:00")
                    )
                else:
                    placed_at = datetime.now(timezone.utc)

                # Get ticker from instrument URL (robin_stocks pattern)
                ticker = item.get("symbol", "")
                if not ticker:
                    # Try to extract from instrument data
                    instrument_data = item.get("instrument_data", {})
                    ticker = instrument_data.get("symbol", "UNKNOWN")

                orders.append(
                    RawOrder(
                        broker_id=self.broker_id,
                        broker_order_id=item.get("id", ""),
                        ticker=ticker,
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
                "Robinhood get_orders failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return []

    async def place_order(self, user_id: UUID, order: OrderRequest) -> OrderResult:
        """Submit an order to Robinhood via robin_stocks."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                return OrderResult(
                    broker_order_id="",
                    status="rejected",
                    rejection_reason="Not connected to Robinhood",
                )

            if not self._ensure_logged_in():
                return OrderResult(
                    broker_order_id="",
                    status="rejected",
                    rejection_reason="Failed to authenticate with Robinhood",
                )

            import robin_stocks.robinhood as rh

            quantity = float(order.quantity)
            result = None

            if order.side == "buy":
                if order.order_type == "limit" and order.limit_price is not None:
                    result = rh.order_buy_limit(
                        symbol=order.ticker,
                        quantity=quantity,
                        limitPrice=float(order.limit_price),
                        timeInForce="gfd",
                    )
                else:
                    result = rh.order_buy_market(
                        symbol=order.ticker,
                        quantity=quantity,
                        timeInForce="gfd",
                    )
            else:  # sell
                if order.order_type == "limit" and order.limit_price is not None:
                    result = rh.order_sell_limit(
                        symbol=order.ticker,
                        quantity=quantity,
                        limitPrice=float(order.limit_price),
                        timeInForce="gfd",
                    )
                else:
                    result = rh.order_sell_market(
                        symbol=order.ticker,
                        quantity=quantity,
                        timeInForce="gfd",
                    )

            if result is None:
                return OrderResult(
                    broker_order_id="",
                    status="rejected",
                    rejection_reason="Robinhood returned no result",
                )

            # Check for rejection
            if "detail" in result:
                return OrderResult(
                    broker_order_id="",
                    status="rejected",
                    rejection_reason=result["detail"],
                )

            return OrderResult(
                broker_order_id=result.get("id", ""),
                status="pending",
                execution_price=(
                    Decimal(str(result["average_price"]))
                    if result.get("average_price")
                    and float(result["average_price"]) > 0
                    else None
                ),
            )
        except Exception as e:
            logger.error(
                "Robinhood place_order failed for user %s: %s", user_id, str(e)
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            return OrderResult(
                broker_order_id="",
                status="rejected",
                rejection_reason=str(e),
            )

    async def cancel_order(self, user_id: UUID, order_id: str) -> None:
        """Cancel an existing open order at Robinhood."""
        try:
            async with AsyncSessionLocal() as db:
                tokens = await get_broker_tokens(db, user_id, self.broker_id)
            if tokens is None:
                logger.warning(
                    "No Robinhood tokens for user %s, cannot cancel order", user_id
                )
                return

            if not self._ensure_logged_in():
                async with AsyncSessionLocal() as db:
                    await update_broker_status(db, user_id, self.broker_id, "error")
                return

            import robin_stocks.robinhood as rh

            rh.cancel_stock_order(order_id)
        except Exception as e:
            logger.error(
                "Robinhood cancel_order failed for user %s, order %s: %s",
                user_id,
                order_id,
                str(e),
            )
            async with AsyncSessionLocal() as db:
                await update_broker_status(db, user_id, self.broker_id, "error")
            raise
