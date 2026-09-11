"""
CivicFlow — Telegram Integration API
====================================
Endpoints for handling Telegram webhooks, generating link tokens,
and associating Telegram chat IDs with CivicFlow user accounts.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.auth import require_auth, ok
from agents.notifier import TelegramNotifier
from db.mongo import get_db

router = APIRouter(prefix="/telegram", tags=["Telegram"])

_notifier: Optional[TelegramNotifier] = None

def get_notifier() -> TelegramNotifier:
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier


class LinkTokenResponse(BaseModel):
    token: str
    bot_username: str
    expires_at: datetime


@router.get("/link-token", summary="Generate a token to link Telegram account")
async def generate_link_token(payload: dict = Depends(require_auth)):
    """
    Generate a one-time token valid for 15 minutes.
    The user must send `/start <token>` to the Telegram bot.
    """
    user_id = payload["sub"]
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    token = str(uuid.uuid4())[:8].upper() # 8 char short token
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    # Save to MongoDB
    await db.telegram_link_tokens.insert_one({
        "user_id": user_id,
        "token": token,
        "expires_at": expires_at
    })

    # You would typically pull the bot username from env or hardcode it
    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "CivicFlowBot")

    return ok("Token generated", data={
        "token": token,
        "bot_username": bot_username,
        "expires_at": expires_at
    })


@router.post("/link", summary="Link account (Fallback/Manual)")
async def manual_link(token: str, chat_id: str):
    """
    Internal endpoint to link the telegram_chat_id to the user.
    Usually this logic is handled directly in the webhook handler.
    """
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    # Find valid token
    record = await db.telegram_link_tokens.find_one({
        "token": token,
        "expires_at": {"$gt": datetime.utcnow()}
    })

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user_id = record["user_id"]

    # Update user profile with chat_id
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"telegram_chat_id": chat_id}}
    )

    # Delete used token
    await db.telegram_link_tokens.delete_one({"_id": record["_id"]})

    return ok("Account linked successfully")


@router.post("/webhook", summary="Telegram Webhook Handler")
async def telegram_webhook(request: Request):
    """
    Receives updates from Telegram.
    Validates X-Telegram-Bot-Api-Secret-Token to ensure authenticity.
    """
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    expected_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    
    if expected_secret and secret != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized webhook call")

    try:
        update = await request.json()
    except Exception:
        return {"ok": False, "message": "Invalid JSON"}

    message = update.get("message", {})
    chat = message.get("chat", {})
    text = message.get("text", "")
    chat_id = str(chat.get("id", ""))

    if not chat_id or not text:
        return {"ok": True} # Ignore non-text messages gracefully

    notifier = get_notifier()
    db = await get_db()
    
    # Process Commands
    if text.startswith("/start"):
        # Format: /start TOKEN
        parts = text.split(" ")
        if len(parts) > 1:
            token = parts[1].strip()
            if db is not None:
                record = await db.telegram_link_tokens.find_one({
                    "token": token,
                    "expires_at": {"$gt": datetime.utcnow()}
                })
                
                if record:
                    # Link account
                    await db.users.update_one(
                        {"user_id": record["user_id"]},
                        {"$set": {"telegram_chat_id": chat_id}}
                    )
                    await db.telegram_link_tokens.delete_one({"_id": record["_id"]})
                    await notifier.send_message(chat_id, "✅ <b>Account Linked!</b>\n\nYou will now receive live updates from CivicFlow here.")
                else:
                    await notifier.send_message(chat_id, "❌ <b>Invalid or expired token.</b>\nPlease generate a new one from the CivicFlow app.")
        else:
            await notifier.send_message(chat_id, "Welcome to CivicFlow! Please generate a link token from the app and send it to me using `/start YOUR_TOKEN`.")

    elif text.startswith("/status"):
        if db is not None:
            # Find user by chat_id
            user = await db.users.find_one({"telegram_chat_id": chat_id})
            if user:
                # Find most recent active session
                session = await db.form_sessions.find_one(
                    {"user_id": user["user_id"]},
                    sort=[("updated_at", -1)]
                )
                if session:
                    status = session.get("status", "unknown")
                    form_name = session.get("scraped_form", {}).get("form_title", "Unknown Form")
                    await notifier.send_message(chat_id, f"📋 <b>Current Status</b>\n\nForm: {form_name}\nStatus: {status.upper()}")
                else:
                    await notifier.send_message(chat_id, "You don't have any active form sessions.")
            else:
                await notifier.send_message(chat_id, "Your account is not linked. Please link it via the CivicFlow app.")

    elif text.startswith("/help"):
        help_text = (
            "🤖 <b>CivicFlow Bot Commands:</b>\n\n"
            "/start [token] - Link your account\n"
            "/status - Check your current form progress\n"
            "/help - Show this message"
        )
        await notifier.send_message(chat_id, help_text)
        
    else:
        # Ignore normal chat or handle conversation via LLM counsellor in the future
        await notifier.send_message(chat_id, "I only understand commands right now. Try /help.")

    return {"ok": True}
