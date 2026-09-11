import sys
import asyncio
import time
import logging

# Windows fix: Playwright requires ProactorEventLoop for subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Load environment variables
load_dotenv()

# ── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("civicflow")

# ── Configuration diagnostics ──────────────────────────────────────────────
from config import settings
logger.info("="*60)
logger.info("CivicFlow Configuration")
logger.info("Python executable: %s", sys.executable)
logger.info("Gemini API Key: %s", "✓ configured" if settings.gemini_api_key else "✗ missing")
logger.info("Gemini Model: %s", settings.gemini_model or "not set")

# Test PaddleOCR import
try:
    import paddle
    logger.info("paddle import: ✓ OK")
except Exception as e:
    logger.error("paddle import: ✗ FAILED — %s", str(e))

try:
    import paddleocr
    logger.info("paddleocr import: ✓ OK")
except Exception as e:
    logger.error("paddleocr import: ✗ FAILED — %s: %s", type(e).__name__, str(e))

logger.info("="*60)

# ── Directory setup ────────────────────────────────────────────────────────
upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
for subdir in ["docs", "scripts", "screenshots"]:
    Path(upload_dir, subdir).mkdir(parents=True, exist_ok=True)

# ── Router imports ─────────────────────────────────────────────────────────
from api.routes import router as api_router
from api.websocket import websocket_endpoint
from api.auth import router as auth_router
from api.documents import router as documents_router
from api.chat import router as chat_router
from api.search import router as search_router
from api.telegram import router as telegram_router

# ── App factory ────────────────────────────────────────────────────────────
app = FastAPI(
    title="CivicFlow API",
    description="Multi-agent system for automated government form filling",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:3000",
    "null",  # file:// origin for local HTML
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"http://localhost(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request logging middleware ─────────────────────────────────────────────
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    logger.info(
        "%s %s → %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )
    return response

# ── Global exception handlers ──────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    logger.error(f"[422 Validation Error] {request.method} {request.url.path}")
    logger.error(f"Request body: {await request.body()}")
    for e in errors:
        logger.error(f"  - Field: {e['loc']}, Error: {e['msg']}, Type: {e['type']}")
    
    msg = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in errors)
    return JSONResponse(
        status_code=422,
        content={
            "success": False, 
            "message": f"Validation error: {msg}", 
            "data": {},
            "errors": errors  # Include full error details for debugging
        },
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error", "data": {}},
    )

# ── Static file mount (uploads) ────────────────────────────────────────────
if Path(upload_dir).exists():
    app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(api_router, tags=["Sessions"])
app.include_router(auth_router)         # /auth
app.include_router(documents_router)   # /documents
app.include_router(chat_router)        # /chat
app.include_router(search_router)      # /search
app.include_router(telegram_router)    # /telegram

# ── WebSockets ─────────────────────────────────────────────────────────────
@app.websocket("/ws/{session_id}")
async def websocket_route(websocket: WebSocket, session_id: str):
    await websocket_endpoint(websocket, session_id)

# ── Health endpoints ───────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {"service": "CivicFlow API", "version": "1.0.0", "status": "running", "docs": "/api/docs"}

@app.get("/health", tags=["Health"])
async def health():
    from db.mongo import is_connected as mongo_ok
    return {
        "status": "healthy",
        "gemini_api":  "configured" if os.getenv("GEMINI_API_KEY") else "not_configured",
        "telegram":    "configured" if os.getenv("TELEGRAM_BOT_TOKEN") else "not_configured",
        "mongo":       "connected" if mongo_ok() else "disconnected",
        "redis_url":   os.getenv("REDIS_URL", "redis://localhost:6379"),
        "upload_dir":  upload_dir,
    }

@app.get("/health/runtime", tags=["Health"])
async def health_runtime():
    """Comprehensive runtime diagnostics for troubleshooting."""
    from db.mongo import is_connected as mongo_ok
    from config import settings
    
    diagnostics = {
        "python_executable": sys.executable,
        "gemini": {
            "api_key_configured": bool(settings.gemini_api_key),
            "api_key_masked": settings.gemini_api_key[:10] + "..." if settings.gemini_api_key else None,
            "model": settings.gemini_model,
        },
        "imports": {
            "paddle": "ok",
            "paddleocr": "ok",
        },
        "databases": {
            "mongodb": "connected" if mongo_ok() else "disconnected",
            "redis": settings.redis_url,
        }
    }
    
    # Test paddle import
    try:
        import paddle
    except Exception as e:
        diagnostics["imports"]["paddle"] = f"error: {type(e).__name__}: {str(e)}"
    
    # Test paddleocr import
    try:
        import paddleocr
    except Exception as e:
        diagnostics["imports"]["paddleocr"] = f"error: {type(e).__name__}: {str(e)}"
    
    return diagnostics

# ── Lifecycle events ───────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("CivicFlow API v1.0.0 starting...")
    logger.info("Upload dir  : %s", upload_dir)
    logger.info("Gemini API  : %s", "OK" if os.getenv("GEMINI_API_KEY") else "NOT SET")
    logger.info("Telegram    : %s", "OK" if os.getenv("TELEGRAM_BOT_TOKEN") else "NOT SET")

    mongo_uri = os.getenv("MONGO_URI", os.getenv("MONGODB_URI", ""))
    if mongo_uri:
        try:
            from db.mongo import connect_mongo
            from config import settings
            await connect_mongo(mongo_uri, settings.mongo_db_name)
            logger.info("MongoDB     : connected")
        except Exception as e:
            logger.warning("MongoDB connection failed: %s — using in-memory fallback", e)
    else:
        logger.warning("MONGO_URI not set — using Redis/in-memory storage")

    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("CivicFlow API shutting down...")
    try:
        from db.mongo import close_mongo
        await close_mongo()
    except Exception:
        pass

# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,   # Must be False on Windows with Playwright
        loop="asyncio",
    )
