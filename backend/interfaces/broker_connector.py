from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from backend.models.domain import (
    BrokerId,
    OrderRequest,
    OrderResult,
    RawHolding,
    RawOrder,
)


class IBrokerConnector(ABC):
    """Abstract base class that every broker connector must implement.

    Each concrete connector is responsible for a single broker and handles
    the full auth lifecycle as well as data fetching and order placement.
    """

    broker_id: BrokerId

    # ------------------------------------------------------------------
    # Auth lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_authorization_url(self, user_id: UUID) -> str:
        """Return the broker's OAuth authorization URL for the given user."""
        ...

    @abstractmethod
    async def exchange_code_for_tokens(self, user_id: UUID, code: str) -> None:
        """Exchange an authorization code for access/refresh tokens and persist them."""
        ...

    @abstractmethod
    async def refresh_tokens(self, user_id: UUID) -> None:
        """Refresh the stored access token using the stored refresh token."""
        ...

    @abstractmethod
    async def revoke_tokens(self, user_id: UUID) -> None:
        """Revoke and delete all stored tokens for the given user."""
        ...

    @abstractmethod
    async def is_connected(self, user_id: UUID) -> bool:
        """Return True if the user has a valid, non-expired connection to this broker."""
        ...

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_holdings(self, user_id: UUID) -> list[RawHolding]:
        """Fetch the user's current holdings from the broker."""
        ...

    @abstractmethod
    async def get_orders(self, user_id: UUID) -> list[RawOrder]:
        """Fetch the user's order history from the broker."""
        ...

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    @abstractmethod
    async def place_order(self, user_id: UUID, order: OrderRequest) -> OrderResult:
        """Submit an order to the broker and return the result."""
        ...

    @abstractmethod
    async def cancel_order(self, user_id: UUID, order_id: str) -> None:
        """Cancel an existing open order at the broker."""
        ...
