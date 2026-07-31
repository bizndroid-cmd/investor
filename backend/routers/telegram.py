"""Telegram webhook/polling router for handling document uploads.

Endpoints:
- POST /telegram/webhook — receives Telegram updates (for webhook mode)
- POST /telegram/poll — manually trigger polling for new messages
- GET /telegram/trade-history — get parsed trade history
"""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models.domain import Session
from backend.models.orm import TradeHistory
from backend.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


@router.post("/poll")
async def poll_for_documents(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Poll Telegram for recent document uploads and process them.

    This is a manual trigger — call this after sending a document to the bot.
    """
    from backend.services.telegram_document_handler import process_document_update
    from backend.services import telegram_service

    if not telegram_service.is_configured():
        return {"status": "error", "message": "Telegram not configured"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{TELEGRAM_API}/getUpdates", params={"limit": 10})
            if resp.status_code != 200:
                return {"status": "error", "message": "Failed to fetch updates"}

            updates = resp.json().get("result", [])

        # Process document uploads
        processed = 0
        results = []

        for update in updates:
            message = update.get("message", {})
            chat_id = str(message.get("chat", {}).get("id", ""))

            # Security: only process from allowed chats
            allowed = telegram_service._get_allowed_chat_ids()
            if chat_id not in allowed:
                continue

            if "document" in message:
                result = await process_document_update(update, session.user_id)
                if result:
                    processed += 1
                    results.append(result)
                    # Send confirmation back to Telegram
                    await telegram_service.send_message(chat_id, result)

        # Clear processed updates
        if updates:
            last_update_id = updates[-1].get("update_id", 0)
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get(
                    f"{TELEGRAM_API}/getUpdates",
                    params={"offset": last_update_id + 1},
                )

        return {
            "status": "ok",
            "processed": processed,
            "messages": results,
        }

    except Exception as e:
        logger.error("Telegram poll failed: %s", str(e))
        return {"status": "error", "message": str(e)[:200]}


@router.get("/trade-history")
async def get_trade_history(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get stored trade history summary."""
    stmt = select(TradeHistory).where(TradeHistory.user_id == session.user_id)
    result = await db.execute(stmt)
    trades = result.scalars().all()

    if not trades:
        return {"has_data": False, "total_trades": 0}

    # Group by ticker
    from collections import defaultdict
    ticker_summary: dict[str, dict] = defaultdict(lambda: {"buys": 0, "sells": 0, "first_buy": None})

    for t in trades:
        ts = ticker_summary[t.ticker]
        if t.trade_type == "BUY":
            ts["buys"] += 1
            if t.executed_at and (ts["first_buy"] is None or t.executed_at < ts["first_buy"]):
                ts["first_buy"] = t.executed_at
        else:
            ts["sells"] += 1

    summary = []
    for ticker, data in sorted(ticker_summary.items()):
        summary.append({
            "ticker": ticker,
            "buy_count": data["buys"],
            "sell_count": data["sells"],
            "first_purchase": data["first_buy"].isoformat() if data["first_buy"] else None,
        })

    return {
        "has_data": True,
        "total_trades": len(trades),
        "tickers": len(ticker_summary),
        "broker": trades[0].broker if trades else None,
        "summary": summary,
    }


@router.get("/purchase-dates")
async def get_purchase_dates(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get earliest purchase date per ticker from trade history."""
    from backend.services.trade_report_parser import get_purchase_dates

    dates = await get_purchase_dates(db, session.user_id)
    return {"has_data": bool(dates), "purchase_dates": dates}
