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
