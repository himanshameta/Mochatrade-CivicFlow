"""
CivicFlow — Setup Verification Script
======================================
Checks all dependencies, connections, and configurations.
Run from the project root: python scripts/verify_setup.py

Prints a PASS / FAIL / WARN table for each requirement.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / "backend" / ".env")

# ANSI colors
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

results = []

def PASS(name, detail=""):
    results.append(("PASS", name, detail))

def FAIL(name, detail=""):
    results.append(("FAIL", name, detail))

def WARN(name, detail=""):
    results.append(("WARN", name, detail))


# ── 1. Required ENV variables ──────────────────────────────────────────────
def check_env():
    required = [
        "GEMINI_API_KEY", "JWT_SECRET", "UPLOAD_DIR",
    ]
    recommended = [
        "MONGODB_URI", "MONGO_URI", "REDIS_URL",
        "TELEGRAM_BOT_TOKEN", "ENCRYPTION_MASTER_KEY",
    ]
    for key in required:
        if os.getenv(key):
            PASS(f"ENV: {key}")
        else:
            FAIL(f"ENV: {key}", "Not set — required")

    for key in recommended:
        if os.getenv(key):
            PASS(f"ENV: {key}")
        else:
            WARN(f"ENV: {key}", "Not set — some features disabled")


# ── 2. MongoDB connection ──────────────────────────────────────────────────
async def check_mongo():
    uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI", "")
    if not uri:
        WARN("MongoDB", "MONGO_URI not set — skipping connection check")
        return
    try:
        import motor.motor_asyncio
        client = motor.motor_asyncio.AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
        await client.admin.command("ping")
        PASS("MongoDB", f"Connected to {uri.split('@')[-1]}")
    except Exception as e:
        FAIL("MongoDB", str(e)[:80])


# ── 3. Redis connection ────────────────────────────────────────────────────
async def check_redis():
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        from redis.asyncio import from_url as redis_from_url
        r = await redis_from_url(url, decode_responses=True, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        PASS("Redis", f"Connected to {url}")
    except Exception as e:
        WARN("Redis", f"{str(e)[:60]} — in-memory fallback will be used")


# ── 4. Gemini API key ──────────────────────────────────────────────────────
async def check_gemini():
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        FAIL("Gemini API", "GEMINI_API_KEY not set")
        return
    try:
        from google import genai
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model='gemini-2.0-flash-lite',
            contents='Reply with only the word: OK'
        )
        if "ok" in response.text.strip().lower():
            PASS("Gemini API", "Test call succeeded")
        else:
            WARN("Gemini API", f"Unexpected response: {response.text[:40]}")
    except Exception as e:
        FAIL("Gemini API", str(e)[:80])


# ── 5. Telegram Bot Token ──────────────────────────────────────────────────
async def check_telegram():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or token == "your_bot_token_here":
        WARN("Telegram", "TELEGRAM_BOT_TOKEN not configured")
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            data = r.json()
            if data.get("ok"):
                PASS("Telegram", f"Bot: @{data['result']['username']}")
            else:
                FAIL("Telegram", data.get("description", "Invalid token"))
    except Exception as e:
        FAIL("Telegram", str(e)[:80])


# ── 6. PaddleOCR ───────────────────────────────────────────────────────────
def check_paddleocr():
    try:
        import paddleocr
        PASS("PaddleOCR", f"v{paddleocr.__version__}")
    except ImportError:
        FAIL("PaddleOCR", "pip install paddleocr paddlepaddle")
    except Exception as e:
        WARN("PaddleOCR", str(e)[:60])


# ── 7. pdf2image / Poppler ─────────────────────────────────────────────────
def check_poppler():
    poppler_path = os.getenv("POPPLER_PATH", "")
    try:
        from pdf2image import convert_from_bytes
        # Create a minimal 1-byte PDF to test
        minimal_pdf = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj "
            b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
            b"0000000058 00000 n\n0000000115 00000 n\n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
        )
        kwargs = {"poppler_path": poppler_path} if poppler_path else {}
        convert_from_bytes(minimal_pdf, **kwargs)
        PASS("pdf2image + Poppler", poppler_path or "system poppler")
    except ImportError:
        FAIL("pdf2image", "pip install pdf2image")
    except Exception as e:
        if "poppler" in str(e).lower() or "pdfinfo" in str(e).lower():
            FAIL("Poppler", f"Not found. Set POPPLER_PATH in .env. Error: {str(e)[:60]}")
        else:
            WARN("pdf2image", str(e)[:80])


# ── 8. Playwright Chromium ─────────────────────────────────────────────────
async def check_playwright():
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
        PASS("Playwright Chromium", "Browser launched successfully")
    except Exception as e:
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e).lower():
            FAIL("Playwright Chromium", "Run: playwright install chromium")
        else:
            FAIL("Playwright Chromium", str(e)[:80])


# ── 9. FastAPI import check ────────────────────────────────────────────────
def check_imports():
    modules = [
        ("fastapi",        "FastAPI"),
        ("uvicorn",        "uvicorn"),
        ("motor",          "Motor (MongoDB async)"),
        ("jose",           "python-jose"),
        ("passlib",        "passlib"),
        ("cryptography",   "cryptography"),
        ("rapidfuzz",      "rapidfuzz"),
        ("httpx",          "httpx"),
    ]
    for mod, label in modules:
        try:
            __import__(mod)
            PASS(f"Import: {label}")
        except ImportError:
            FAIL(f"Import: {label}", f"pip install {mod}")


# ── Print report ───────────────────────────────────────────────────────────
def print_report():
    print()
    print(BOLD + "=" * 70 + RESET)
    print(BOLD + "  CivicFlow — Setup Verification Report" + RESET)
    print(BOLD + "=" * 70 + RESET)
    print(f"  {'Status':<8} {'Check':<36} {'Detail'}")
    print("  " + "-" * 66)

    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for status, name, detail in results:
        counts[status] += 1
        if status == "PASS":
            color = GREEN
        elif status == "WARN":
            color = YELLOW
        else:
            color = RED
        print(f"  {color}{status:<8}{RESET} {name:<36} {detail}")

    print()
    print(
        f"  Summary: "
        f"{GREEN}{counts['PASS']} PASS{RESET}  "
        f"{YELLOW}{counts['WARN']} WARN{RESET}  "
        f"{RED}{counts['FAIL']} FAIL{RESET}"
    )
    print(BOLD + "=" * 70 + RESET)
    if counts["FAIL"] > 0:
        print(f"  {RED}! Fix FAIL items before running CivicFlow.{RESET}")
    elif counts["WARN"] > 0:
        print(f"  {YELLOW}* Some optional features are disabled. Review WARN items.{RESET}")
    else:
        print(f"  {GREEN}OK Everything looks good! Start with: uvicorn main:app --reload{RESET}")
    print()


async def main():
    print(f"\nRunning checks...\n")

    check_env()
    check_imports()
    check_paddleocr()
    check_poppler()

    await check_playwright()
    await check_mongo()
    await check_redis()
    await check_gemini()
    await check_telegram()

    print_report()


if __name__ == "__main__":
    asyncio.run(main())
