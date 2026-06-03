from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from backend.models.domain import (
    Alert,
    CreateAlertRequest,
    TriggeredAlert,
    UpdateAlertRequest,
)


class IAlertService(ABC):
    """Abstract base class for the price alert service.

    Manages CRUD operations for user-defined price alerts and evaluates
    alert conditions against incoming price ticks.
    """

    @abstractmethod
    async def create_alert(self, user_id: UUID, alert: CreateAlertRequest) -> Alert:
        """Create a new price alert for the given user."""
        ...

    @abstractmethod
    async def update_alert(
        self,
        user_id: UUID,
        alert_id: UUID,
        update: UpdateAlertRequest,
    ) -> Alert:
        """Partially update an existing alert."""
        ...

    @abstractmethod
    async def delete_alert(self, user_id: UUID, alert_id: UUID) -> None:
        """Delete an alert by ID."""
        ...

    @abstractmethod
    async def get_alerts(self, user_id: UUID) -> list[Alert]:
        """Return all alerts (active and triggered) for the given user."""
        ...

    @abstractmethod
    async def evaluate_alerts(
        self,
        ticker: str,
        current_price: float,
    ) -> list[TriggeredAlert]:
        """Evaluate all active alerts for the given ticker against the current price.

        For each alert whose condition is satisfied, transitions the alert to
        ``triggered`` status, removes it from the active Redis set, and returns
        a ``TriggeredAlert`` record. Already-triggered alerts are never re-fired.
        """
        ...
