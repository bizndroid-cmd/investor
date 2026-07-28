"""Telegram Bot Service — Air-sealed notification delivery.

Security model:
- Only pre-approved chat IDs can receive messages
- Bot ignores all incoming messages from unauthorized users
- No commands exposed to public — one-way notification only
- Chat ID must be explicitly added to TELEGRAM_ALLOWED_CHAT_IDS env var
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


def _get_allowed_chat_ids() -> set[str]:
    """Parse allowed chat IDs from config (comma-separated)."""
    if not settings.telegram_allowed_chat_ids:
        return set()
    return {cid.strip() for cid in settings.telegram_allowed_chat_ids.split(",") if cid.strip()}


def is_configured() -> bool:
    """Check if Telegram bot is configured."""
    return bool(settings.telegram_bot_token)


async def send_message(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Send a message to a specific chat ID (must be in allowed list).

    Returns True if sent successfully, False otherwise.
    Security: Only sends to pre-approved chat IDs.
    """
    if not is_configured():
        logger.debug("Telegram not configured, skipping")
        return False

    allowed = _get_allowed_chat_ids()
    if allowed and chat_id not in allowed:
        logger.warning("Blocked Telegram send to unauthorized chat_id: %s", chat_id)
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text[:4096],  # Telegram max message length
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
            )
            if response.status_code == 200:
                return True
            else:
                logger.warning("Telegram send failed: %s", response.text[:200])
                return False
    except Exception as e:
        logger.error("Telegram send error: %s", str(e))
        return False


async def broadcast_to_all(text: str) -> int:
    """Send a message to ALL allowed chat IDs. Returns count of successful sends."""
    if not is_configured():
        return 0

    allowed = _get_allowed_chat_ids()
    if not allowed:
        logger.debug("No allowed chat IDs configured")
        return 0

    success = 0
    for chat_id in allowed:
        if await send_message(chat_id, text):
            success += 1

    return success


async def send_daily_briefing(briefing_text: str, prediction_mood: str, prediction_date: str) -> int:
    """Send the daily portfolio briefing to all authorized users."""
    mood_emoji = {"bullish": "📈", "bearish": "📉", "neutral": "➡️"}.get(prediction_mood, "🔮")

    message = (
        f"<b>{mood_emoji} Daily Portfolio Briefing</b>\n"
        f"<i>{prediction_date}</i>\n\n"
        f"<b>Market Mood: {prediction_mood.upper()}</b>\n\n"
        f"{_truncate_html(briefing_text, 3500)}\n\n"
        f"<i>— Investor AI ({datetime.now(timezone.utc).strftime('%H:%M UTC')})</i>"
    )
    return await broadcast_to_all(message)


async def send_prediction_score(prediction_date: str, score: float, mood_accuracy: float, ticker_accuracy: float) -> int:
    """Notify users when a prediction gets scored."""
    grade = _get_grade(score)

    message = (
        f"<b>🎯 Prediction Scored!</b>\n\n"
        f"📅 Date: {prediction_date}\n"
        f"📊 Score: <b>{score}%</b> (Grade: {grade})\n"
        f"  • Mood Accuracy: {mood_accuracy}%\n"
        f"  • Ticker Accuracy: {ticker_accuracy}%\n\n"
        f"{'🟢 Good call!' if score >= 60 else '🔴 Room for improvement' if score < 40 else '🟡 Mixed results'}"
    )
    return await broadcast_to_all(message)


async def send_portfolio_alert(change_pct: float, total_value: float) -> int:
    """Alert on significant portfolio movement (>2%)."""
    direction = "📈 UP" if change_pct > 0 else "📉 DOWN"
    message = (
        f"<b>⚡ Portfolio Alert</b>\n\n"
        f"{direction} <b>{abs(change_pct):.1f}%</b>\n"
        f"Current Value: ₹{total_value:,.0f}\n\n"
        f"<i>Significant movement detected</i>"
    )
    return await broadcast_to_all(message)


async def get_bot_updates() -> list[dict]:
    """Fetch recent messages sent TO the bot (for getting chat IDs).

    This is a helper for setup — shows which chat IDs have messaged the bot.
    Only call this during initial setup.
    """
    if not is_configured():
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{TELEGRAM_API}/getUpdates")
            if response.status_code == 200:
                data = response.json()
                updates = data.get("result", [])
                chats = []
                seen = set()
                for u in updates:
                    msg = u.get("message", {})
                    chat = msg.get("chat", {})
                    chat_id = str(chat.get("id", ""))
                    if chat_id and chat_id not in seen:
                        seen.add(chat_id)
                        chats.append({
                            "chat_id": chat_id,
                            "username": chat.get("username"),
                            "first_name": chat.get("first_name"),
                            "type": chat.get("type"),
                        })
                return chats
    except Exception as e:
        logger.error("Failed to get bot updates: %s", str(e))

    return []


def _truncate_html(text: str, max_len: int) -> str:
    """Truncate text for Telegram, preserving meaning."""
    # Convert markdown-style bold to HTML
    text = text.replace("**", "<b>").replace("**", "</b>")
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _get_grade(score: float) -> str:
    if score >= 85: return "A+"
    if score >= 75: return "A"
    if score >= 65: return "B+"
    if score >= 55: return "B"
    if score >= 45: return "C"
    if score >= 35: return "D"
    return "F"
