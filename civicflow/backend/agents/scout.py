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
            # BUG FIX: Use domcontentloaded instead of networkidle for SPA portals
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for actual page content, not network idle
            try:
                page.wait_for_selector("body", timeout=10000)
                # Give JS frameworks time to hydrate
                page.wait_for_timeout(2000)
            except Exception:
                pass  # Continue anyway, body selector should always exist
            
            # Get page content with retry for SPA hydration
            html = ""
            for attempt in range(3):
                html = page.content()
                if html and len(html) > 500 and "<body" in html.lower():
                    break
                page.wait_for_timeout(1500)
            
            # Check for meaningful content (not just HTML shell)
            if not html or len(html) < 500:
                browser.close()
                return {"error": f"Page returned empty content after 3 attempts: {url}", "html": "", "title": "", "screenshot_path": "", "url": url}
            
            if "<body" not in html.lower():
                browser.close()
                return {"error": f"Response is not valid HTML: {url}", "html": "", "title": "", "screenshot_path": "", "url": url}
            
            title = page.title()
            
            # Check for forms
            forms = page.query_selector_all("form")
            if not forms:
                # Also check for inputs outside forms
                inputs = page.query_selector_all("input, select, textarea")
                if not inputs:
                    browser.close()
                    return {"error": "No form found on this page. Make sure the URL points directly to a form.", "html": html, "title": title, "screenshot_path": "", "url": url}
            
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
        print(f"[Scout] [FAIL] Error: {result['error']}")
    else:
        print(f"[Scout] [OK] Page loaded: {result['title']} | HTML length: {len(result['html'])}")
    
    return result

