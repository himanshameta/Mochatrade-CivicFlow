import os
import sys
from pathlib import Path
from uuid import uuid4
import asyncio
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright


# Use a dedicated thread pool for all Playwright operations
_playwright_executor = ThreadPoolExecutor(max_workers=2)


def _run_scout_sync(url: str, screenshot_dir: str) -> dict:
    """Runs synchronous Playwright in an isolated thread."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
            title = page.title()
            
            # Check for forms
            forms = page.query_selector_all("form")
            if not forms:
                # Also check for inputs outside forms
                inputs = page.query_selector_all("input, select, textarea")
                if not inputs:
                    browser.close()
                    return {"error": "No form found on this page. Make sure the URL points directly to a form."}
            
            # Take screenshot
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_path = os.path.join(screenshot_dir, f"{uuid4()}.png")
            page.screenshot(path=screenshot_path, full_page=True)
            
            browser.close()
            return {
                "html": html,
                "title": title,
                "screenshot_path": screenshot_path,
                "url": url,
                "error": None
            }
        except Exception as e:
            browser.close()
            return {"error": str(e), "html": "", "title": "", "screenshot_path": "", "url": url}


async def scout(url: str) -> dict:
    """Async wrapper that runs sync Playwright in a thread pool."""
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    screenshot_dir = os.path.join(upload_dir, "screenshots")
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _playwright_executor,
        _run_scout_sync,
        url,
        screenshot_dir
    )
    
    if result.get("error"):
        print(f"[Scout] ✗ Error: {result['error']}")
    else:
        print(f"[Scout] ✓ Page loaded: {result['title']} | HTML length: {len(result['html'])}")
    
    return result

