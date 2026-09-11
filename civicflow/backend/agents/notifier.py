import os
import asyncio
from datetime import datetime
from typing import Optional

try:
    from telegram import Bot
    from telegram.error import TelegramError
except ImportError:
    Bot, TelegramError = None, None

async def notify(
    session_id: str,
    status: str,
    message: str,
    url: Optional[str] = None,
    details: Optional[dict] = None
) -> None:
    """
    Send status notifications and log completion events.
    
    In production, this would:
    - Send email notifications
    - Push to websocket for real-time frontend updates
    - Log to analytics/monitoring system
    - Trigger webhooks
    
    Args:
        session_id: Session identifier
        status: Current status (completed, failed, paused, etc.)
        message: Notification message
        url: Optional URL of the form
        details: Optional additional details
    """
    timestamp = datetime.utcnow().isoformat()
    
    notification = {
        "timestamp": timestamp,
        "session_id": session_id,
        "status": status,
        "message": message,
        "url": url,
        "details": details or {}
    }
    
    # For now, just log the notification
    print(f"\n[Notifier] {'=' * 60}")
    print(f"[Notifier] NOTIFICATION")
    print(f"[Notifier] Time: {timestamp}")
    print(f"[Notifier] Session: {session_id}")
    print(f"[Notifier] Status: {status}")
    print(f"[Notifier] Message: {message}")
    if url:
        print(f"[Notifier] URL: {url}")
    if details:
        print(f"[Notifier] Details: {details}")
    print(f"[Notifier] {'=' * 60}\n")
    
    # Future implementations:
    # - await send_email_notification(session_id, status, message)
    # - await websocket_broadcast(session_id, notification)
    # - await log_to_analytics(notification)
    # - await trigger_webhook(notification)
    
    # Simulate async notification sending
    await asyncio.sleep(0.1)


async def notify_pause(
    session_id: str,
    pause_type: str,
    pause_reason: str,
    url: Optional[str] = None
) -> None:
    """
    Send notification for paused execution.
    
    Args:
        session_id: Session identifier
        pause_type: Type of pause (captcha, otp, payment)
        pause_reason: Reason for pause
        url: Optional URL of the form
    """
    await notify(
        session_id=session_id,
        status=f"paused_{pause_type}",
        message=f"Execution paused: {pause_reason}",
        url=url,
        details={"pause_type": pause_type, "reason": pause_reason}
    )


async def notify_error(
    session_id: str,
    error_message: str,
    url: Optional[str] = None,
    error_details: Optional[dict] = None
) -> None:
    """
    Send notification for execution errors.
    
    Args:
        session_id: Session identifier
        error_message: Error message
        url: Optional URL of the form
        error_details: Optional error details
    """
    await notify(
        session_id=session_id,
        status="failed",
        message=f"Execution failed: {error_message}",
        url=url,
        details=error_details or {"error": error_message}
    )


async def notify_completion(
    session_id: str,
    url: str,
    execution_time: Optional[float] = None
) -> None:
    """
    Send notification for successful completion.
    
    Args:
        session_id: Session identifier
        url: URL of the completed form
        execution_time: Optional execution time in seconds
    """
    details = {}
    if execution_time:
        details["execution_time_seconds"] = execution_time
    
    await notify(
        session_id=session_id,
        status="completed",
        message="Form automation completed successfully!",
        url=url,
        details=details
    )


if __name__ == "__main__":
    async def test_notifier():
        print("=" * 80)
        print("Testing Notifier Agent")
        print("=" * 80)
        
        test_session = "test-session-123"
        test_url = "https://example.com/form"
        
        print("\n[Test 1] Basic notification")
        await notify(
            session_id=test_session,
            status="created",
            message="Session created",
            url=test_url
        )
        
        print("\n[Test 2] Pause notification")
        await notify_pause(
            session_id=test_session,
            pause_type="captcha",
            pause_reason="CAPTCHA detected - user action required",
            url=test_url
        )
        
        print("\n[Test 3] Error notification")
        await notify_error(
            session_id=test_session,
            error_message="Selector not found: #submit-button",
            url=test_url,
            error_details={
                "error_type": "TimeoutError",
                "selector": "#submit-button",
                "line": 42
            }
        )
        
        print("\n[Test 4] Completion notification")
        await notify_completion(
            session_id=test_session,
            url=test_url,
            execution_time=45.3
        )
        
        print("\n" + "=" * 80)
        print("All notifier tests passed!")
        print("=" * 80)
    
    asyncio.run(test_notifier())

# ============================================================================
# Telegram Notifier
# ============================================================================

class TelegramNotifier:
    """
    Sends notifications to users via Telegram Bot API.
    Requires user to have linked their Telegram account via /start command.
    """

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
        if not self.token or Bot is None:
            print("[Warning] TELEGRAM_BOT_TOKEN missing or python-telegram-bot not installed. Notifications disabled.")
            self.bot = None
        else:
            self.bot = Bot(token=self.token)

    async def setup_webhook(self, url: str) -> bool:
        """Register webhook URL with Telegram."""
        if not self.bot:
            return False
            
        try:
            return await self.bot.set_webhook(
                url=url,
                secret_token=self.webhook_secret
            )
        except TelegramError as e:
            print(f"[Telegram Error] Failed to set webhook: {e}")
            return False

    async def send_message(
        self, 
        telegram_chat_id: str, 
        message: str,
        parse_mode: str = "HTML"
    ) -> bool:
        """Send a plain or HTML-formatted message."""
        if not self.bot or not telegram_chat_id:
            return False
            
        try:
            await self.bot.send_message(
                chat_id=telegram_chat_id,
                text=message,
                parse_mode=parse_mode
            )
            return True
        except TelegramError as e:
            print(f"[Telegram Error] Failed to send message to {telegram_chat_id}: {e}")
            return False

    async def send_form_started(
        self, user_name: str, form_name: str, chat_id: str
    ):
        """Notify that form filling has started."""
        msg = f"🚀 <b>Hello {user_name}!</b>\n\nI have started automatically filling your <b>{form_name}</b>. I will keep you updated on the progress."
        await self.send_message(chat_id, msg)

    async def send_form_completed(
        self, user_name: str, form_name: str, 
        application_id: str, chat_id: str
    ):
        """Notify form submission was successful with application ID."""
        msg = (
            f"✅ <b>Form Completed Successfully!</b>\n\n"
            f"Your <b>{form_name}</b> has been submitted.\n"
            f"<b>Application ID:</b> <code>{application_id}</code>\n\n"
            f"Please keep this ID safe for future reference."
        )
        await self.send_message(chat_id, msg)

    async def send_correction_needed(
        self, field_name: str, error_msg: str, chat_id: str
    ):
        """Notify user their input for a specific field needs correction."""
        msg = (
            f"⚠️ <b>Action Required</b>\n\n"
            f"There was an issue with the field: <b>{field_name}</b>\n"
            f"<i>{error_msg}</i>\n\n"
            f"Please open the CivicFlow app to correct this."
        )
        await self.send_message(chat_id, msg)

    async def send_status_update(
        self, form_name: str, status: str, chat_id: str
    ):
        """Notify about status change from Chronicle agent."""
        msg = f"🔄 <b>Status Update: {form_name}</b>\n\nCurrently: {status}"
        await self.send_message(chat_id, msg)

    async def send_document_processed(
        self, doc_type: str, fields_extracted: int, chat_id: str
    ):
        """Notify document OCR is complete."""
        msg = (
            f"📄 <b>Document Processed</b>\n\n"
            f"Your <b>{doc_type}</b> has been successfully scanned.\n"
            f"Extracted {fields_extracted} fields.\n"
            f"Please review and confirm them in the app."
        )
        await self.send_message(chat_id, msg)
