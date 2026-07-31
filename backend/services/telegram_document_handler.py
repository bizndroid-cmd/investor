"""Telegram Document Handler — processes uploaded trade reports.

Listens for document uploads via Telegram bot, downloads the file,
parses it using trade_report_parser, and stores trades in DB.
"""

from __future__ import annotations

import logging
from uuid import UUID

import httpx

from backend.config import settings
from backend.services import telegram_service

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf"}


async def process_document_update(update: dict, user_id: UUID) -> str | None:
    """Process a Telegram update containing a document.

    Downloads the file, parses it, stores trades, returns summary message.
    """
    message = update.get("message", {})
    document = message.get("document")

    if not document:
        return None

    file_name = document.get("file_name", "unknown")
    file_id = document.get("file_id")
    file_size = document.get("file_size", 0)

    # Check extension
    ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext not in SUPPORTED_EXTENSIONS:
        return f"Unsupported file type: {ext}\nSupported: XLSX, CSV, PDF"

    # Size check (max 10MB)
    if file_size > 10 * 1024 * 1024:
        return "File too large (max 10MB)"

    # Download file from Telegram
    file_bytes = await _download_telegram_file(file_id)
    if not file_bytes:
        return "Failed to download file from Telegram"

    # Parse based on extension
    from backend.services.trade_report_parser import parse_xlsx, parse_csv, store_trades
    from backend.database import AsyncSessionLocal

    try:
        if ext in (".xlsx", ".xls"):
            records = await parse_xlsx(file_bytes, file_name)
        elif ext == ".csv":
            records = await parse_csv(file_bytes, file_name)
        elif ext == ".pdf":
            # PDF parsing placeholder — would need pdfplumber
            return "PDF parsing coming soon. Please export as XLSX or CSV from your broker."
        else:
            return f"Unsupported format: {ext}"

        if not records:
            return (
                f"📄 Parsed <b>{file_name}</b> but found no trade records.\n\n"
                "Make sure the file has columns like: Symbol, Type (BUY/SELL), "
                "Quantity, Price, Date"
            )

        # Store in DB
        async with AsyncSessionLocal() as db:
            # Detect broker from filename or content
            broker = _detect_broker(file_name, records)
            stored = await store_trades(db, user_id, records, broker=broker)

        # Build summary
        buy_count = sum(1 for r in records if r["trade_type"] == "BUY")
        sell_count = sum(1 for r in records if r["trade_type"] == "SELL")
        tickers = sorted(set(r["ticker"] for r in records))
        date_range = _get_date_range(records)

        summary = (
            f"✅ <b>Trade Report Imported</b>\n\n"
            f"📄 File: {file_name}\n"
            f"🏦 Broker: {broker or 'Unknown'}\n"
            f"📊 Trades: {stored} ({buy_count} buys, {sell_count} sells)\n"
            f"📈 Stocks: {len(tickers)} unique\n"
        )
        if date_range:
            summary += f"📅 Period: {date_range}\n"
        summary += f"\n<b>Tickers:</b> {', '.join(tickers[:15])}"
        if len(tickers) > 15:
            summary += f" +{len(tickers) - 15} more"

        summary += "\n\n💡 <i>Dividend earnings will now use actual purchase dates.</i>"

        return summary

    except Exception as e:
        logger.error("Trade report parsing failed: %s", str(e))
        return f"❌ Error parsing file: {str(e)[:100]}"


async def _download_telegram_file(file_id: str) -> bytes | None:
    """Download a file from Telegram using file_id."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get file path
            resp = await client.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id})
            if resp.status_code != 200:
                return None
            file_path = resp.json().get("result", {}).get("file_path")
            if not file_path:
                return None

            # Download file
            file_url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
            file_resp = await client.get(file_url)
            if file_resp.status_code == 200:
                return file_resp.content
    except Exception as e:
        logger.error("Telegram file download failed: %s", str(e))

    return None


def _detect_broker(filename: str, records: list[dict]) -> str | None:
    """Detect broker from filename or record content."""
    fn_lower = filename.lower()
    if "groww" in fn_lower:
        return "groww"
    if "zerodha" in fn_lower or "kite" in fn_lower:
        return "zerodha"
    if "angel" in fn_lower:
        return "angelone"
    if "upstox" in fn_lower:
        return "upstox"
    if "5paisa" in fn_lower:
        return "5paisa"

    # Check from exchange order ID patterns
    for rec in records[:5]:
        oid = rec.get("order_id", "")
        if oid and len(oid) > 10 and oid.startswith("13"):
            return "groww"  # Groww order IDs start with 13

    return None


def _get_date_range(records: list[dict]) -> str | None:
    """Get human-readable date range from records."""
    dates = [r["executed_at"] for r in records if r.get("executed_at")]
    if not dates:
        return None
    dates.sort()
    first = dates[0][:10]
    last = dates[-1][:10]
    if first == last:
        return first
    return f"{first} to {last}"
