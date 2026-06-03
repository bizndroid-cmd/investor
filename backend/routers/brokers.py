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


# ---------------------------------------------------------------------------
# Manual token input (for Groww daily access tokens)
# ---------------------------------------------------------------------------


class TokenInputRequest(BaseModel):
    """Manual access token submission."""
    access_token: str


class TokenInfoResponse(BaseModel):
    """Token connection info."""
    broker_id: str
    status: str
    connected_at: str | None = None
    expires_at: str | None = None
    token_preview: str | None = None


@router.post("/{broker_id}/token", response_model=TokenInfoResponse)
async def submit_token(
    broker_id: str,
    request: TokenInputRequest,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TokenInfoResponse:
    """Submit an access token manually (e.g., Groww daily token).

    Stores the token for the user and returns connection info.
    """
    from datetime import datetime, timezone
    from backend.utils.broker_token_store import store_broker_tokens

    if broker_id not in _CONNECTORS:
        raise HTTPException(status_code=404, detail=f"Broker '{broker_id}' not supported")

    if not request.access_token or len(request.access_token) < 10:
        raise HTTPException(status_code=400, detail="Invalid access token")

    # Try to decode JWT expiry from the token (Groww tokens are JWTs)
    expires_at = None
    try:
        import json, base64
        parts = request.access_token.split(".")
        if len(parts) == 3:
            # Decode payload (add padding)
            payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            exp = decoded.get("exp")
            if exp:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    except Exception:
        pass  # Not a JWT or invalid — store anyway

    # Store the token
    await store_broker_tokens(
        db=db,
        user_id=session.user_id,
        broker_id=broker_id,
        access_token=request.access_token,
        refresh_token=None,
        expires_at=expires_at,
    )

    now = datetime.now(timezone.utc)
    token_preview = request.access_token[:20] + "..." + request.access_token[-10:]

    return TokenInfoResponse(
        broker_id=broker_id,
        status="connected",
        connected_at=now.isoformat(),
        expires_at=expires_at.isoformat() if expires_at else None,
        token_preview=token_preview,
    )


@router.get("/{broker_id}/token-info", response_model=TokenInfoResponse)
async def get_token_info(
    broker_id: str,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TokenInfoResponse:
    """Get stored token info for a broker (without exposing the full token)."""
    from datetime import datetime, timezone
    from backend.utils.broker_token_store import get_broker_tokens
    from backend.models.orm import BrokerToken
    from sqlalchemy import select

    if broker_id not in _CONNECTORS:
        raise HTTPException(status_code=404, detail=f"Broker '{broker_id}' not supported")

    # Get token record
    stmt = select(BrokerToken).where(
        BrokerToken.user_id == session.user_id,
        BrokerToken.broker_id == broker_id,
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        return TokenInfoResponse(
            broker_id=broker_id,
            status="disconnected",
        )

    # Check expiry
    now = datetime.now(timezone.utc)
    is_expired = record.expires_at and record.expires_at < now

    return TokenInfoResponse(
        broker_id=broker_id,
        status="expired" if is_expired else "connected",
        connected_at=record.connected_at.isoformat() if record.connected_at else None,
        expires_at=record.expires_at.isoformat() if record.expires_at else None,
        token_preview=None,  # Don't expose token details in GET
    )
