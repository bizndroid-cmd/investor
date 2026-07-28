"""FastAPI telemetry router for the "Nerd Stats" page.

Protected by a simple PIN. Shows LLM usage, API calls, tokens consumed, etc.

Endpoints:
- POST /telemetry/verify-pin — verify PIN and get access
- GET /telemetry/stats — aggregated stats
- GET /telemetry/llm-calls — recent LLM call log
- GET /telemetry/api-calls — recent API call log
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.config import settings
from backend.services.telemetry_service import get_telemetry_service

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# PIN for accessing telemetry - defaults to "1234"
TELEMETRY_PIN = getattr(settings, "telemetry_pin", "1234") or "1234"


class PinRequest(BaseModel):
    pin: str


class PinResponse(BaseModel):
    valid: bool


@router.post("/verify-pin", response_model=PinResponse)
async def verify_pin(request: PinRequest) -> PinResponse:
    """Verify the telemetry access PIN."""
    return PinResponse(valid=request.pin == TELEMETRY_PIN)


@router.get("/stats")
async def get_stats(pin: str = Query(..., description="Access PIN")):
    """Get aggregated telemetry statistics."""
    if pin != TELEMETRY_PIN:
        raise HTTPException(status_code=403, detail="Invalid PIN")
    service = get_telemetry_service()
    return service.get_stats()


@router.get("/llm-calls")
async def get_llm_calls(
    pin: str = Query(..., description="Access PIN"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent LLM call log."""
    if pin != TELEMETRY_PIN:
        raise HTTPException(status_code=403, detail="Invalid PIN")
    service = get_telemetry_service()
    return service.get_recent_llm_calls(limit=limit)


@router.get("/api-calls")
async def get_api_calls(
    pin: str = Query(..., description="Access PIN"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent external API call log."""
    if pin != TELEMETRY_PIN:
        raise HTTPException(status_code=403, detail="Invalid PIN")
    service = get_telemetry_service()
    return service.get_recent_api_calls(limit=limit)


@router.get("/llm-status")
async def get_llm_status():
    """Get current LLM operational status (public — no PIN required).

    Used by the frontend to display status messages about AI analysis availability.
    """
    service = get_telemetry_service()
    return service.get_llm_status()


@router.get("/telegram-setup")
async def telegram_setup(pin: str = Query(..., description="Access PIN")):
    """Get Telegram bot info and recent chat IDs (for initial setup).
    
    Steps:
    1. Message your bot on Telegram
    2. Call this endpoint to see your chat_id
    3. Add it to TELEGRAM_ALLOWED_CHAT_IDS in .env
    """
    if pin != TELEMETRY_PIN:
        raise HTTPException(status_code=403, detail="Invalid PIN")

    from backend.services import telegram_service

    if not telegram_service.is_configured():
        return {"error": "TELEGRAM_BOT_TOKEN not set in .env"}

    chats = await telegram_service.get_bot_updates()
    return {
        "configured": True,
        "recent_chats": chats,
        "instructions": "Add your chat_id to TELEGRAM_ALLOWED_CHAT_IDS in .env (comma-separated for multiple users)",
    }


@router.post("/telegram-test")
async def telegram_test(pin: str = Query(..., description="Access PIN")):
    """Send a test message to all allowed Telegram chats."""
    if pin != TELEMETRY_PIN:
        raise HTTPException(status_code=403, detail="Invalid PIN")

    from backend.services import telegram_service

    if not telegram_service.is_configured():
        return {"error": "TELEGRAM_BOT_TOKEN not set"}

    count = await telegram_service.broadcast_to_all(
        "🧪 <b>Test Message</b>\n\nYour Investor Dashboard Telegram integration is working! "
        "You'll receive daily briefings and prediction scores here."
    )
    return {"sent_to": count, "message": "Test sent to all allowed chats"}
