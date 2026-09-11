import asyncio
from datetime import datetime
from typing import Optional


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
