"""FastAPI WebSocket endpoint for real-time price and order updates.

Endpoint:
- WS /ws?token=<jwt_access_token>

Authenticates via token query param, registers connection with WebSocketManager,
handles subscribe/unsubscribe JSON messages, and cleans up on disconnect.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from backend.config import settings
from backend.services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# JWT settings (same as auth service)
JWT_ALGORITHM = "HS256"

# Global WebSocket manager instance — set during app startup
_ws_manager: WebSocketManager | None = None


def set_ws_manager(manager: WebSocketManager) -> None:
    """Set the global WebSocket manager instance (called during app startup)."""
    global _ws_manager
    _ws_manager = manager


def get_ws_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    if _ws_manager is None:
        raise RuntimeError("WebSocketManager not initialized")
    return _ws_manager


def _authenticate_ws_token(token: str) -> UUID | None:
    """Validate a JWT access token and return the user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
        token_type = payload.get("type")
        if token_type != "access":
            return None
        user_id = UUID(payload["sub"])
        return user_id
    except (JWTError, KeyError, ValueError):
        return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    """WebSocket endpoint for real-time updates.

    Authentication: pass JWT access token as `token` query parameter.

    Client messages (JSON):
    - {"action": "subscribe", "tickers": ["AAPL", "GOOGL"]}
    - {"action": "unsubscribe", "tickers": ["AAPL"]}

    Server messages (JSON):
    - {"type": "price_update", "data": {...PriceQuote...}}
    - {"type": "order_update", "data": {...Order...}}
    - {"type": "alert_triggered", "data": {...TriggeredAlert...}}
    - {"type": "error", "message": "..."}
    """
    # Authenticate
    user_id = _authenticate_ws_token(token)
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    manager = get_ws_manager()
    await manager.connect(user_id, websocket)

    try:
        while True:
            # Receive and process messages
            raw_message = await websocket.receive_text()
            try:
                message = json.loads(raw_message)
                action = message.get("action")

                if action == "subscribe":
                    tickers = message.get("tickers", [])
                    if isinstance(tickers, list) and all(isinstance(t, str) for t in tickers):
                        manager.subscribe(user_id, tickers)
                        await websocket.send_text(json.dumps({
                            "type": "subscribed",
                            "tickers": [t.upper() for t in tickers],
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Invalid tickers format. Expected list of strings.",
                        }))

                elif action == "unsubscribe":
                    tickers = message.get("tickers", [])
                    if isinstance(tickers, list) and all(isinstance(t, str) for t in tickers):
                        manager.unsubscribe(user_id, tickers)
                        await websocket.send_text(json.dumps({
                            "type": "unsubscribed",
                            "tickers": [t.upper() for t in tickers],
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Invalid tickers format. Expected list of strings.",
                        }))

                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Unknown action: {action}",
                    }))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON message.",
                }))

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for user %s", user_id)
    except Exception as e:
        logger.error("WebSocket error for user %s: %s", user_id, str(e))
    finally:
        await manager.disconnect(user_id, websocket)
