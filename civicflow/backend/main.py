import sys
import asyncio

# Windows fix: Playwright requires ProactorEventLoop for subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

# Create uploads directory
upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
Path(upload_dir).mkdir(parents=True, exist_ok=True)
Path(upload_dir, "docs").mkdir(exist_ok=True)
Path(upload_dir, "scripts").mkdir(exist_ok=True)
Path(upload_dir, "screenshots").mkdir(exist_ok=True)

# Import routes and websocket
from api.routes import router as api_router
from api.websocket import websocket_endpoint

# Create FastAPI app
app = FastAPI(
    title="CivicFlow API",
    description="Multi-agent system for automated web form filling",
    version="1.0.0"
)

# Configure CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes (no prefix so routes work at root level)
app.include_router(api_router, tags=["CivicFlow"])

# WebSocket endpoint
@app.websocket("/ws/{session_id}")
async def websocket_route(websocket: WebSocket, session_id: str):
    await websocket_endpoint(websocket, session_id)


# Health check endpoint
@app.get("/")
async def root():
    return {
        "service": "CivicFlow API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "redis": "connected",  # TODO: Add actual Redis health check
        "gemini_api": "configured" if os.getenv("GEMINI_API_KEY") else "not_configured"
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    print("=" * 80)
    print("CivicFlow API Starting...")
    print("=" * 80)
    print(f"Upload Directory: {upload_dir}")
    print(f"Redis URL: {os.getenv('REDIS_URL', 'redis://localhost:6379')}")
    print(f"Gemini API: {'Configured' if os.getenv('GEMINI_API_KEY') else 'NOT CONFIGURED'}")
    print("=" * 80)


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    print("\nCivicFlow API Shutting Down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,   # MUST be False on Windows with Playwright
        loop="asyncio"  # Use asyncio loop explicitly
    )
