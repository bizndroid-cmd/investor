"""Telegram router — attachment management + document processing.

Endpoints:
- POST /telegram/sync — poll Telegram for new documents, store in attachments table
- GET /telegram/attachments — list all attachments
- POST /telegram/attachments/{id}/process — parse a specific attachment into trade history
- GET /telegram/trade-history — trade history summary
- GET /telegram/purchase-dates — earliest buy date per ticker
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models.domain import Session
from backend.models.orm import Attachment, TradeHistory
from backend.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


@router.post("/sync")
async def sync_attachments(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Poll Telegram for new document uploads and store them in attachments table."""
    from backend.services import telegram_service

    if not telegram_service.is_configured():
        return {"status": "error", "message": "Telegram not configured"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{TELEGRAM_API}/getUpdates", params={"limit": 50})
            if resp.status_code != 200:
                return {"status": "error", "message": "Failed to reach Telegram"}

            updates = resp.json().get("result", [])

        allowed = telegram_service._get_allowed_chat_ids()
        new_count = 0

        for update in updates:
            message = update.get("message", {})
            chat_id = str(message.get("chat", {}).get("id", ""))

            if chat_id not in allowed:
                continue

            document = message.get("document")
            if not document:
                continue

            file_name = document.get("file_name", "")
            file_id = document.get("file_id", "")
            file_size = document.get("file_size", 0)
            mime_type = document.get("mime_type", "")

            # Check extension
            ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            # Check if already stored (by file_id)
            existing = await db.execute(
                select(Attachment).where(Attachment.file_id == file_id)
            )
            if existing.scalar_one_or_none():
                continue

            # Store attachment
            attachment = Attachment(
                id=uuid4(),
                user_id=session.user_id,
                file_name=file_name,
                file_id=file_id,
                file_size=file_size,
                mime_type=mime_type,
                status="pending",
                telegram_chat_id=chat_id,
            )
            db.add(attachment)
            new_count += 1

        await db.commit()

        # Clear processed updates
        if updates:
            last_id = updates[-1].get("update_id", 0)
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get(f"{TELEGRAM_API}/getUpdates", params={"offset": last_id + 1})

        return {"status": "ok", "new_attachments": new_count}

    except Exception as e:
        logger.error("Telegram sync failed: %s", str(e))
        return {"status": "error", "message": str(e)[:150]}


@router.get("/attachments")
async def list_attachments(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all attachments received via Telegram."""
    stmt = (
        select(Attachment)
        .where(Attachment.user_id == session.user_id)
        .order_by(desc(Attachment.received_at))
    )
    result = await db.execute(stmt)
    attachments = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "file_name": a.file_name,
            "file_size": a.file_size,
            "mime_type": a.mime_type,
            "status": a.status,
            "records_imported": a.records_imported,
            "error_message": a.error_message,
            "received_at": a.received_at.isoformat() if a.received_at else None,
            "processed_at": a.processed_at.isoformat() if a.processed_at else None,
        }
        for a in attachments
    ]


@router.post("/attachments/{attachment_id}/process")
async def process_attachment(
    attachment_id: str,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Download and parse a specific attachment into trade history."""
    from backend.services.trade_report_parser import parse_xlsx, parse_csv, store_trades
    from backend.services.telegram_document_handler import _download_telegram_file, _detect_broker

    # Get attachment
    stmt = select(Attachment).where(
        Attachment.id == UUID(attachment_id),
        Attachment.user_id == session.user_id,
    )
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()

    if not attachment:
        return {"status": "error", "message": "Attachment not found"}

    # Download file from Telegram
    file_bytes = await _download_telegram_file(attachment.file_id)
    if not file_bytes:
        attachment.status = "failed"
        attachment.error_message = "Failed to download from Telegram"
        await db.commit()
        return {"status": "error", "message": "Failed to download file from Telegram"}

    # Parse
    try:
        ext = "." + attachment.file_name.rsplit(".", 1)[-1].lower()
        if ext in (".xlsx", ".xls"):
            records = await parse_xlsx(file_bytes, attachment.file_name)
        elif ext == ".csv":
            records = await parse_csv(file_bytes, attachment.file_name)
        else:
            attachment.status = "failed"
            attachment.error_message = f"Unsupported format: {ext}"
            await db.commit()
            return {"status": "error", "message": f"Unsupported: {ext}"}

        if not records:
            attachment.status = "failed"
            attachment.error_message = "No trade records found in file"
            await db.commit()
            return {"status": "error", "message": "No trade records found"}

        # Store trades
        broker = _detect_broker(attachment.file_name, records)
        stored = await store_trades(db, session.user_id, records, broker=broker)

        # Update attachment status
        attachment.status = "processed"
        attachment.processed_at = datetime.now(timezone.utc)
        attachment.records_imported = stored
        await db.commit()

        # Send Telegram confirmation
        try:
            from backend.services import telegram_service
            tickers = sorted(set(r["ticker"] for r in records))
            buy_count = sum(1 for r in records if r["trade_type"] == "BUY")
            msg = (
                f"✅ <b>Trade Report Processed</b>\n\n"
                f"📄 {attachment.file_name}\n"
                f"📊 {stored} trades ({buy_count} buys)\n"
                f"📈 {len(tickers)} stocks: {', '.join(tickers[:10])}\n\n"
                f"Dividend calculations updated."
            )
            if attachment.telegram_chat_id:
                await telegram_service.send_message(attachment.telegram_chat_id, msg)
        except Exception:
            pass

        return {
            "status": "ok",
            "records_imported": stored,
            "tickers": sorted(set(r["ticker"] for r in records)),
            "buy_count": buy_count,
        }

    except Exception as e:
        attachment.status = "failed"
        attachment.error_message = str(e)[:200]
        await db.commit()
        logger.error("Attachment processing failed: %s", str(e))
        return {"status": "error", "message": str(e)[:150]}


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
async def get_purchase_dates_endpoint(
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get earliest purchase date per ticker."""
    from backend.services.trade_report_parser import get_purchase_dates
    dates = await get_purchase_dates(db, session.user_id)
    return {"has_data": bool(dates), "purchase_dates": dates}


# ===========================================================================
# Telegram Webhook for approval callbacks (no auth required — verified by chat_id)
# ===========================================================================


@router.post("/webhook")
async def telegram_webhook(body: dict) -> dict:
    """Handle incoming Telegram webhook updates (callback queries for approval).

    This endpoint is called by Telegram when admin clicks Approve/Deny buttons.
    No user auth required — security is via allowed chat_id verification.
    """
    from backend.services.telegram_service import handle_approval_callback, send_message

    # Handle callback query (inline button press)
    callback_query = body.get("callback_query")
    if callback_query:
        callback_data = callback_query.get("data", "")
        from_chat = callback_query.get("message", {}).get("chat", {})
        from_chat_id = str(from_chat.get("id", ""))
        callback_id = callback_query.get("id", "")

        # Process approval/denial
        response_msg = await handle_approval_callback(callback_data, from_chat_id)

        # Answer the callback query (removes loading spinner on button)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/answerCallbackQuery",
                    json={"callback_query_id": callback_id, "text": response_msg[:200]},
                )
        except Exception:
            pass

        # Send confirmation message
        await send_message(from_chat_id, response_msg)

        return {"ok": True}

    return {"ok": True}


@router.post("/setup-webhook")
async def setup_telegram_webhook(
    session: Session = Depends(get_current_user),
) -> dict:
    """Set up the Telegram webhook URL for this server.

    Call this once after deployment to register the webhook with Telegram.
    Requires the DOMAIN env var to be set.
    """
    if not settings.telegram_bot_token:
        return {"error": "TELEGRAM_BOT_TOKEN not configured"}

    # Use domain from settings or construct from request
    domain = getattr(settings, "domain", None) or "localhost"
    webhook_url = f"https://{domain}/api/telegram/webhook"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
                json={"url": webhook_url, "allowed_updates": ["callback_query"]},
            )
            data = response.json()
            return {
                "success": data.get("ok", False),
                "webhook_url": webhook_url,
                "description": data.get("description", ""),
            }
    except Exception as e:
        return {"error": str(e)}
