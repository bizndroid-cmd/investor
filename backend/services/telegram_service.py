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
    mood_config = {
        "bullish": {"emoji": "🟢📈", "vibe": "Looking good!"},
        "bearish": {"emoji": "🔴📉", "vibe": "Stay cautious."},
        "neutral": {"emoji": "🟡➡️", "vibe": "Wait and watch."},
    }
    config = mood_config.get(prediction_mood, mood_config["neutral"])

    # Extract key insights (first 3 bullet points from briefing)
    key_points = []
    for line in briefing_text.split("\n"):
        line = line.strip()
        if line.startswith("*") or line.startswith("-") or line.startswith("•"):
            clean = line.lstrip("*-• ").strip()
            if len(clean) > 20:
                key_points.append(clean[:120])
            if len(key_points) >= 3:
                break

    insights = "\n".join(f"  → {p}" for p in key_points) if key_points else "  Open app for full analysis"

    message = (
        f"{config['emoji']} <b>Market Pulse — {prediction_date}</b>\n\n"
        f"<b>AI Mood: {prediction_mood.upper()}</b> — {config['vibe']}\n\n"
        f"<b>Key Takeaways:</b>\n{insights}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💡 <i>Full briefing + stock-by-stock calls available in app</i>\n"
        f"🎯 <i>Your AI accuracy: tracking live</i>"
    )
    return await broadcast_to_all(message)


async def send_prediction_score(prediction_date: str, score: float, mood_accuracy: float, ticker_accuracy: float) -> int:
    """Notify users when a prediction gets scored — make it feel like a game."""
    grade = _get_grade(score)

    # Gamification messages
    if score >= 75:
        reaction = "🔥 Crushing it! The AI nailed this one."
        tip = "High conviction signals are working — trust them more."
    elif score >= 60:
        reaction = "👍 Solid read. Above average performance."
        tip = "The directional call was right. Refine ticker-level precision next."
    elif score >= 45:
        reaction = "🤔 Mixed bag. Some hits, some misses."
        tip = "The AI hedged too much. Look for stronger signals."
    else:
        reaction = "📚 Learning opportunity. The market surprised us."
        tip = "Contrarian day — the AI is adjusting for next time."

    message = (
        f"🎯 <b>Prediction Scorecard</b>\n\n"
        f"📅 {prediction_date}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 <b>Score: {score:.0f}%</b>  •  Grade: <b>{grade}</b>\n\n"
        f"  🧭 Market direction: {mood_accuracy:.0f}%\n"
        f"  📈 Stock-level calls: {ticker_accuracy:.0f}%\n\n"
        f"{reaction}\n\n"
        f"💡 <i>{tip}</i>"
    )
    return await broadcast_to_all(message)


async def send_portfolio_alert(change_pct: float, total_value: float, geo_id: str = "IN") -> int:
    """Alert on significant portfolio movement (>2%)."""
    from backend.geo.currency import format_currency as fmt_currency

    if change_pct > 0:
        direction = "🚀 Rally Mode"
        emoji = "💰"
        action = "Consider booking partial profits on high-conviction winners"
    else:
        direction = "⚠️ Pullback Alert"
        emoji = "🛡️"
        action = "Review stop-losses. Don't panic sell quality holdings"

    formatted_value = fmt_currency(total_value, geo_id)

    message = (
        f"{emoji} <b>{direction}</b>\n\n"
        f"Your portfolio moved <b>{abs(change_pct):.1f}%</b> {'up' if change_pct > 0 else 'down'}\n"
        f"Current value: <b>{formatted_value}</b>\n\n"
        f"💡 <i>{action}</i>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>Open app for detailed stock-by-stock analysis</i>"
    )
    return await broadcast_to_all(message)


async def send_alert_proximity_digest(proximity_data: list[dict]) -> int:
    """Daily digest of alerts approaching their targets.

    Called after market close to warn about imminent/close alerts.
    """
    if not proximity_data:
        return 0

    imminent = [p for p in proximity_data if p["status"] == "imminent"]
    close = [p for p in proximity_data if p["status"] == "close"]

    if not imminent and not close:
        return 0

    lines = ["⚡ <b>Alert Watchlist Update</b>\n"]

    if imminent:
        lines.append("🔴 <b>Imminent (within 2%):</b>")
        for p in imminent[:4]:
            direction = "↓" if p["condition"] == "below" else "↑"
            lines.append(
                f"  {direction} <b>{p['ticker']}</b> — {p['distance_pct']:.1f}% from ₹{p['target_price']:,.0f}"
                f" (now ₹{p['current_price']:,.0f})"
            )
        lines.append("")

    if close:
        lines.append("🟡 <b>Approaching (within 5%):</b>")
        for p in close[:4]:
            direction = "↓" if p["condition"] == "below" else "↑"
            lines.append(
                f"  {direction} {p['ticker']} — {p['distance_pct']:.1f}% from ₹{p['target_price']:,.0f}"
            )
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━")
    lines.append("<i>Manage alerts in app → Alerts section</i>")

    return await broadcast_to_all("\n".join(lines))


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


# ===========================================================================
# Registration Approval via Telegram
# ===========================================================================


async def send_approval_request(user_id: str, email: str) -> bool:
    """Send registration approval request with inline buttons to admin.

    Sends to all allowed chat IDs. Buttons: Approve / Deny.
    """
    if not is_configured():
        logger.debug("Telegram not configured — auto-approving user")
        # Auto-approve if Telegram not configured
        await _auto_approve_user(user_id)
        return True

    allowed = _get_allowed_chat_ids()
    if not allowed:
        logger.debug("No allowed chat IDs — auto-approving user")
        await _auto_approve_user(user_id)
        return True

    message = (
        f"🔐 <b>New Registration Request</b>\n\n"
        f"📧 Email: <code>{email}</code>\n"
        f"🆔 User ID: <code>{user_id[:8]}...</code>\n"
        f"🕐 Time: {datetime.now(timezone.utc).strftime('%b %d, %H:%M UTC')}\n\n"
        f"Approve this user?"
    )

    # Inline keyboard with callback data
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"approve:{user_id}"},
                {"text": "❌ Deny", "callback_data": f"deny:{user_id}"},
            ]
        ]
    }

    success = 0
    for chat_id in allowed:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                        "reply_markup": keyboard,
                    },
                )
                if response.status_code == 200:
                    success += 1
                else:
                    logger.warning("Approval request send failed: %s", response.text[:200])
        except Exception as e:
            logger.error("Approval request send error: %s", str(e))

    return success > 0


async def handle_approval_callback(callback_data: str, from_chat_id: str) -> str:
    """Handle approval/deny callback from Telegram inline button.

    Returns response message to send back.
    Security: Only processes callbacks from allowed chat IDs.
    """
    allowed = _get_allowed_chat_ids()
    if from_chat_id not in allowed:
        logger.warning("Unauthorized approval callback from chat_id: %s", from_chat_id)
        return "⚠️ Unauthorized"

    parts = callback_data.split(":", 1)
    if len(parts) != 2:
        return "❌ Invalid callback data"

    action, user_id = parts

    if action == "approve":
        success = await _approve_user(user_id)
        if success:
            return f"✅ User approved! They can now log in."
        return "❌ Failed to approve (user not found)"
    elif action == "deny":
        success = await _deny_user(user_id)
        if success:
            return f"🚫 User denied and removed."
        return "❌ Failed to deny (user not found)"

    return "❌ Unknown action"


async def _approve_user(user_id: str) -> bool:
    """Set user is_approved = True."""
    try:
        from backend.database import AsyncSessionLocal
        from backend.models.orm import User
        from sqlalchemy import select
        from uuid import UUID

        async with AsyncSessionLocal() as db:
            stmt = select(User).where(User.id == UUID(user_id))
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if not user:
                return False
            user.is_approved = True
            await db.commit()
            return True
    except Exception as e:
        logger.error("Failed to approve user %s: %s", user_id, str(e))
        return False


async def _deny_user(user_id: str) -> bool:
    """Delete the denied user entirely."""
    try:
        from backend.database import AsyncSessionLocal
        from backend.models.orm import User
        from sqlalchemy import select
        from uuid import UUID

        async with AsyncSessionLocal() as db:
            stmt = select(User).where(User.id == UUID(user_id))
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if not user:
                return False
            await db.delete(user)
            await db.commit()
            return True
    except Exception as e:
        logger.error("Failed to deny user %s: %s", user_id, str(e))
        return False


async def _auto_approve_user(user_id: str) -> None:
    """Auto-approve when Telegram not configured."""
    await _approve_user(user_id)
