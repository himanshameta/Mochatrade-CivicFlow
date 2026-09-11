import os
import re
import base64
import asyncio
import sys
import subprocess
import threading
import queue
import time
from pathlib import Path
from typing import Optional
from datetime import datetime
from redis.asyncio import Redis, from_url

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.session_models import SessionStore


class ExecutorRedis:
    """Dedicated Redis client for executor coordination with in-memory fallback"""
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis: Optional[Redis] = None
        self.redis_url = redis_url
        self._fallback: Dict[str, str] = {}  # In-memory fallback
        self._use_fallback = False
    
    async def get_redis(self):
        if self._use_fallback:
            return self  # Use self as fallback with dict methods
        
        if self.redis is None:
            try:
                self.redis = await from_url(self.redis_url, decode_responses=True)
                await self.redis.ping()
            except Exception as e:
                print(f"[ExecutorRedis] ✗ Redis unavailable: {e}")
                print(f"[ExecutorRedis] → Using in-memory fallback")
                self._use_fallback = True
                return self
        return self.redis
    
    async def setex(self, key: str, ttl: int, value: str) -> None:
        """Fallback-compatible setex"""
        if self._use_fallback:
            self._fallback[key] = value
        else:
            redis = await self.get_redis()
            await redis.setex(key, ttl, value)
    
    async def get(self, key: str) -> Optional[str]:
        """Fallback-compatible get"""
        if self._use_fallback:
            return self._fallback.get(key)
        else:
            redis = await self.get_redis()
            return await redis.get(key)
    
    async def delete(self, key: str) -> None:
        """Fallback-compatible delete"""
        if self._use_fallback:
            self._fallback.pop(key, None)
        else:
            redis = await self.get_redis()
            await redis.delete(key)
    
    async def set_resume_signal(self, session_id: str, signal_type: str) -> None:
        await self.setex(f"resume:{session_id}", 300, signal_type)
    
    async def set_otp_value(self, session_id: str, otp: str) -> None:
        await self.setex(f"otp:{session_id}", 300, otp)
    
    async def close(self) -> None:
        if self.redis:
            await self.redis.close()


redis_client = ExecutorRedis()


def extract_selector_from_error(error_msg: str) -> Optional[str]:
    """Extract the failing selector from an error message"""
    # Look for common Playwright error patterns
    patterns = [
        r"locator\(['\"]([^'\"]+)['\"]\)",
        r"selector ['\"]([^'\"]+)['\"]",
        r"waiting for locator\(['\"]([^'\"]+)['\"]\)",
        r"#[\w-]+",  # ID selector
        r"\[name=['\"][\w-]+['\"]\]",  # Name selector
    ]
    
    for pattern in patterns:
        match = re.search(pattern, error_msg)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    
    return None


def _run_script_in_thread(script_path: str, output_queue: queue.Queue):
    """Run the Playwright script in a thread, capture stdout line by line."""
    try:
        proc = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        
        for line in iter(proc.stdout.readline, ""):
            line = line.strip()
            if line:
                output_queue.put(("stdout", line))
        
        proc.wait()
        stderr = proc.stderr.read()
        if stderr:
            output_queue.put(("stderr", stderr))
        output_queue.put(("done", proc.returncode))
        
    except Exception as e:
        output_queue.put(("error", str(e)))


async def executor(script_path: str, session_id: str, session_store: SessionStore, max_retries: int = 2) -> dict:
    """Run script in thread, process output events asynchronously."""
    output_queue = queue.Queue()
    
    # Start script in background thread
    thread = threading.Thread(
        target=_run_script_in_thread,
        args=(script_path, output_queue),
        daemon=True
    )
    thread.start()
    
    loop = asyncio.get_event_loop()
    
    # Process output events
    while True:
        # Check queue without blocking the async loop
        try:
            msg_type, msg_data = await loop.run_in_executor(
                None,
                lambda: output_queue.get(timeout=0.5)
            )
        except queue.Empty:
            # Check if thread is done
            if not thread.is_alive():
                break
            continue
        
        print(f"[Executor stdout] {msg_data}")
        
        if msg_type == "stdout":
            line = msg_data
            
            if line.startswith("EVENT:"):
                parts = line.split(":", 2)
                event_type = parts[1] if len(parts) > 1 else "unknown"
                event_data = parts[2] if len(parts) > 2 else ""
                
                # Broadcast to WebSocket if available
                try:
                    from api.websocket import broadcast_event
                    await broadcast_event(session_id, {
                        "event": event_type,
                        "data": event_data,
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception:
                    pass
                
                if event_type == "captcha_detected":
                    await session_store.update_status(session_id, "paused_captcha")
                    return {"status": "paused_captcha", "message": "CAPTCHA detected — please solve it"}
                
                elif event_type == "otp_detected":
                    await session_store.update_status(session_id, "paused_otp")
                    return {"status": "paused_otp", "message": "OTP required"}
                
                elif event_type == "submission_complete":
                    await session_store.update_status(session_id, "completed")
                    return {"status": "completed", "message": "Form submitted successfully!"}
                
                elif event_type == "error":
                    await session_store.update_status(session_id, "failed")
                    return {"status": "failed", "message": event_data}
        
        elif msg_type == "done":
            return_code = msg_data
            if return_code == 0:
                await session_store.update_status(session_id, "completed")
                return {"status": "completed", "message": "Script completed"}
            else:
                await session_store.update_status(session_id, "failed")
                return {"status": "failed", "message": f"Script exited with code {return_code}"}
        
        elif msg_type in ("error", "stderr"):
            await session_store.update_status(session_id, "failed")
            return {"status": "failed", "message": f"Script error: {msg_data}"}
    
    return {"status": "failed", "message": "Script ended without completion signal"}


async def resume_after_captcha(session_id: str, session_store: SessionStore) -> dict:
    """
    Signal the paused script to continue after user solved CAPTCHA manually.
    The script is polling Redis for this signal.
    
    Args:
        session_id: Session ID
        session_store: SessionStore instance
        
    Returns:
        Dict with status and message
    """
    print(f"[Executor] Sending CAPTCHA resume signal for session {session_id}")
    
    # Set Redis key that script is polling for
    await redis_client.set_resume_signal(session_id, "captcha_solved")
    
    # Update session status
    await session_store.update_status(session_id, "running")
    await session_store.update_field(session_id, "pause_reason", None)
    
    return {
        "status": "running",
        "message": "Resume signal sent. Script will continue execution."
    }


async def resume_after_otp(session_id: str, otp_value: str, session_store: SessionStore) -> dict:
    """
    Provide OTP value to the paused script.
    The script is polling Redis for this value.
    
    Args:
        session_id: Session ID
        otp_value: The OTP code provided by user
        session_store: SessionStore instance
        
    Returns:
        Dict with status and message
    """
    print(f"[Executor] Injecting OTP for session {session_id}: {otp_value}")
    
    # Set Redis key with OTP value
    await redis_client.set_otp_value(session_id, otp_value)
    
    # Update session status
    await session_store.update_status(session_id, "running")
    await session_store.update_field(session_id, "pause_reason", None)
    
    return {
        "status": "running",
        "message": "OTP injected. Script will continue with verification."
    }


async def check_resume_signal(session_id: str) -> Optional[str]:
    """
    Check if resume signal exists for this session.
    Used by generated scripts to poll for resume.
    
    Args:
        session_id: Session ID
        
    Returns:
        Signal type or None
    """
    redis_inst = await redis_client.get_redis()
    signal = await redis_client.get(f"resume:{session_id}")
    if signal:
        # Delete the key after reading
        await redis_client.delete(f"resume:{session_id}")
    return signal


async def check_otp_value(session_id: str) -> Optional[str]:
    """
    Check if OTP value exists for this session.
    Used by generated scripts to poll for OTP.
    
    Args:
        session_id: Session ID
        
    Returns:
        OTP value or None
    """
    redis_inst = await redis_client.get_redis()
    otp = await redis_client.get(f"otp:{session_id}")
    if otp:
        # Delete the key after reading
        await redis_client.delete(f"otp:{session_id}")
    return otp


if __name__ == "__main__":
    async def test_executor():
        from models.session_models import SessionStore
        import json
        
        print("=" * 80)
        print("Testing Executor Agent")
        print("=" * 80)
        
        # Create a simple test script that demonstrates the signal flow
        test_script = '''
import asyncio
import os
import sys

# Add parent to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    try:
        print("Starting test script...")
        
        # Simulate form filling
        await asyncio.sleep(1)
        print("Filling field 1...")
        await asyncio.sleep(1)
        print("Filling field 2...")
        
        # Simulate CAPTCHA detection
        print("CAPTCHA_DETECTED")
        
        # Poll for resume signal
        session_id = os.environ.get("SESSION_ID", "test")
        from agents.executor import check_resume_signal
        
        print("Waiting for user to solve CAPTCHA...")
        while True:
            signal = await check_resume_signal(session_id)
            if signal == "captcha_solved":
                print("Resume signal received! Continuing...")
                break
            await asyncio.sleep(2)
        
        # Continue after CAPTCHA
        await asyncio.sleep(1)
        print("Clicking submit button...")
        await asyncio.sleep(2)
        
        print("SUBMISSION_COMPLETE")
        
    except Exception as e:
        print(f"SCRIPT_ERROR: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
'''
        
        # Save test script
        upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
        scripts_dir = Path(upload_dir) / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        test_script_path = scripts_dir / "test_executor.py"
        with open(test_script_path, "w", encoding="utf-8") as f:
            f.write(test_script)
        
        print(f"\n✓ Created test script: {test_script_path}")
        
        # Initialize session store
        session_store = SessionStore()
        
        # Create test session
        from models.form_models import UserSession
        test_session = UserSession(
            session_id="test_exec_123",
            url="https://example.com/form",
            status="created"
        )
        await session_store.save(test_session)
        
        print(f"✓ Created test session: {test_session.session_id}")
        
        # Start executor in background
        print("\n[1] Starting executor...")
        executor_task = asyncio.create_task(
            executor(str(test_script_path), test_session.session_id, session_store)
        )
        
        # Wait a bit for script to reach CAPTCHA
        await asyncio.sleep(5)
        
        # Check session status
        updated_session = await session_store.load(test_session.session_id)
        print(f"\n[2] Session status after CAPTCHA: {updated_session.status}")
        print(f"    Pause reason: {updated_session.pause_reason}")
        
        if updated_session.status == "paused_captcha":
            print("\n✓ Script correctly paused on CAPTCHA!")
            
            # Simulate user solving CAPTCHA
            print("\n[3] Simulating user solving CAPTCHA...")
            await asyncio.sleep(2)
            
            print("[4] Sending resume signal...")
            resume_result = await resume_after_captcha(test_session.session_id, session_store)
            print(f"    Resume result: {resume_result}")
            
            # Wait for completion
            print("\n[5] Waiting for script to complete...")
            result = await executor_task
            
            print(f"\n✓ Executor finished!")
            print(f"    Status: {result['status']}")
            print(f"    Message: {result['message']}")
            
            # Check final session status
            final_session = await session_store.load(test_session.session_id)
            print(f"\n[6] Final session status: {final_session.status}")
            
            if final_session.status == "completed":
                print("\n" + "=" * 80)
                print("✓ EXECUTOR TEST PASSED!")
                print("  - Script paused on CAPTCHA")
                print("  - Resume signal worked")
                print("  - Script completed successfully")
                print("=" * 80)
            else:
                print(f"\n⚠ Final status was {final_session.status}, expected 'completed'")
        else:
            print(f"\n⚠ Expected paused_captcha, got {updated_session.status}")
            result = await executor_task
            print(f"Executor result: {result}")
        
        # Cleanup
        await session_store.delete(test_session.session_id)
        await session_store.close()
        await redis_client.close()
    
    asyncio.run(test_executor())
