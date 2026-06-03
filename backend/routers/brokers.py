"""FastAPI broker router for managing broker connections.

Endpoints:
- GET /brokers — list all brokers with connection status for current user
- POST /brokers/{broker_id}/connect — initiate OAuth flow, return redirect URL
- GET /brokers/{broker_id}/callback — handle OAuth callback, exchange code for tokens
- DELETE /brokers/{broker_id} — disconnect broker, delete tokens
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.connectors.fidelity import FidelityConnector
from backend.connectors.groww import GrowwConnector
from backend.connectors.robinhood import RobinhoodConnector
from backend.connectors.zerodha import ZerodhaConnector
from backend.database import get_db
from backend.interfaces.broker_connector import IBrokerConnector
from backend.models.domain import BrokerId, Session
from backend.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brokers", tags=["brokers"])

# Registry of all available broker connectors
_CONNECTORS: dict[BrokerId, IBrokerConnector] = {
    "groww": GrowwConnector(),
    "zerodha": ZerodhaConnector(),
    "fidelity": FidelityConnector(),
    "robinhood": RobinhoodConnector(),
}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class BrokerStatusResponse(BaseModel):
    """Connection status for a single broker."""

    broker_id: BrokerId
    name: str
    status: Literal["connected", "disconnected", "error"]


class BrokerListResponse(BaseModel):
    """Response for listing all brokers."""

    brokers: list[BrokerStatusResponse]


class ConnectResponse(BaseModel):
    """Response for initiating a broker connection."""

    authorization_url: str


class CallbackResponse(BaseModel):
    """Response for handling an OAuth callback."""

    message: str
    broker_id: BrokerId


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BROKER_NAMES: dict[BrokerId, str] = {
    "groww": "Groww",
    "zerodha": "Zerodha",
    "fidelity": "Fidelity Investments",
    "robinhood": "Robinhood",
}


def _get_connector(broker_id: str) -> IBrokerConnector:
    """Retrieve the connector for the given broker_id or raise 404."""
    connector = _CONNECTORS.get(broker_id)  # type: ignore[arg-type]
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Broker '{broker_id}' is not supported.",
        )
    return connector


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=BrokerListResponse)
async def list_brokers(
    session: Session = Depends(get_current_user),
) -> BrokerListResponse:
    """List all brokers with their connection status for the current user."""
    statuses: list[BrokerStatusResponse] = []

    for broker_id, connector in _CONNECTORS.items():
        try:
            connected = await connector.is_connected(session.user_id)
            broker_status: Literal["connected", "disconnected", "error"] = (
                "connected" if connected else "disconnected"
            )
        except Exception as e:
            logger.error(
                "Error checking connection status for broker %s, user %s: %s",
                broker_id,
                session.user_id,
                str(e),
            )
            broker_status = "error"

        statuses.append(
            BrokerStatusResponse(
                broker_id=broker_id,
                name=_BROKER_NAMES.get(broker_id, broker_id),
                status=broker_status,
            )
        )

    return BrokerListResponse(brokers=statuses)


@router.post("/{broker_id}/connect", response_model=ConnectResponse)
async def connect_broker(
    broker_id: str,
    session: Session = Depends(get_current_user),
) -> ConnectResponse:
    """Initiate the OAuth/auth flow for a broker and return the redirect URL."""
    connector = _get_connector(broker_id)

    try:
        authorization_url = await connector.get_authorization_url(session.user_id)
        return ConnectResponse(authorization_url=authorization_url)
    except Exception as e:
        logger.error(
            "Failed to get authorization URL for broker %s, user %s: %s",
            broker_id,
            session.user_id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to initiate connection with {_BROKER_NAMES.get(broker_id, broker_id)}: {str(e)}",
        )


@router.get("/{broker_id}/callback", response_model=CallbackResponse)
async def broker_callback(
    broker_id: str,
    code: str = Query(..., description="Authorization code from the broker OAuth callback"),
    session: Session = Depends(get_current_user),
) -> CallbackResponse:
    """Handle the OAuth callback from a broker, exchange code for tokens."""
    connector = _get_connector(broker_id)

    try:
        await connector.exchange_code_for_tokens(session.user_id, code)
        return CallbackResponse(
            message=f"Successfully connected to {_BROKER_NAMES.get(broker_id, broker_id)}.",
            broker_id=broker_id,  # type: ignore[arg-type]
        )
    except Exception as e:
        logger.error(
            "OAuth callback failed for broker %s, user %s: %s",
            broker_id,
            session.user_id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to complete authentication with {_BROKER_NAMES.get(broker_id, broker_id)}: {str(e)}",
        )


@router.delete("/{broker_id}")
async def disconnect_broker(
    broker_id: str,
    session: Session = Depends(get_current_user),
) -> Response:
    """Disconnect a broker by revoking and deleting all stored tokens."""
    connector = _get_connector(broker_id)

    try:
        await connector.revoke_tokens(session.user_id)
    except Exception as e:
        logger.error(
            "Failed to disconnect broker %s for user %s: %s",
            broker_id,
            session.user_id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to disconnect from {_BROKER_NAMES.get(broker_id, broker_id)}: {str(e)}",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
