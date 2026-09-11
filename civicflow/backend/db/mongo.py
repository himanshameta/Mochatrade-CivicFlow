"""
CivicFlow — MongoDB Client (Motor async)
==========================================
Provides an async Motor client and FastAPI dependency.

If MONGO_URI is not set in .env, all MongoDB calls raise RuntimeError
and SessionStore/UserStore fall back to in-memory mode automatically.
"""
import os
from typing import Optional

try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False
    AsyncIOMotorClient = None
    AsyncIOMotorDatabase = None


_client: Optional[object] = None
_db: Optional[object] = None


async def connect_mongo(uri: str, db_name: str = "civicflow") -> object:
    """
    Connect to MongoDB and return the database handle.
    Called once during FastAPI startup (via on_startup hook).

    Connection pool: maxPoolSize=10, minPoolSize=2.
    Timeout: 5 seconds before declaring MongoDB unreachable.
    """
    global _client, _db

    if not MOTOR_AVAILABLE:
        print("[MongoDB] [ERROR] motor not installed — run: pip install motor")
        return None

    try:
        _client = AsyncIOMotorClient(
            uri,
            maxPoolSize=10,
            minPoolSize=2,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
        _db = _client[db_name]

        # Verify connection with a ping
        await _client.admin.command("ping")
        print(f"[MongoDB] [OK] Connected — database: '{db_name}' | pool: 2–10 connections")

        # Create indexes on first connect
        await _ensure_indexes(_db)
        return _db

    except Exception as e:
        print(f"[MongoDB] [ERROR] Connection failed: {e}")
        print(f"[MongoDB]   URI used: {uri[:30]}...")
        print(f"[MongoDB]   -> Is MongoDB running? Check: docker ps | grep mongo")
        print(f"[MongoDB]   -> Verify MONGO_URI in backend/.env")
        print(f"[MongoDB]   -> CivicFlow will use Redis/in-memory fallback instead")
        _client = None
        _db = None
        return None


async def _ensure_indexes(db) -> None:
    """Create indexes for common query patterns."""
    try:
        # sessions: query by session_id (unique) and user_id
        await db.sessions.create_index("session_id", unique=True)
        await db.sessions.create_index("user_id")

        # users: query by email (unique) and user_id (unique)
        await db.users.create_index("email", unique=True)
        await db.users.create_index("user_id", unique=True)

        print("[MongoDB] [OK] Indexes ensured")
    except Exception as e:
        print(f"[MongoDB] [WARN] Index creation warning: {e}")


async def get_db() -> Optional[object]:
    """
    FastAPI dependency and general accessor.
    Returns None (not raises) when MongoDB is unavailable —
    callers must check for None and use fallback.
    """
    global _db
    if _db is not None:
        return _db

    # Try lazy connect
    try:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import settings
        if settings.mongo_uri:
            return await connect_mongo(settings.mongo_uri, settings.mongo_db_name)
    except Exception:
        pass

    return None


async def on_startup() -> None:
    """
    FastAPI lifespan startup hook — connect to MongoDB if MONGO_URI is set.
    Add to your app with: app.add_event_handler("startup", mongo.on_startup)
    (or call directly from your existing startup_event)
    """
    try:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import settings
        if settings.mongo_uri:
            await connect_mongo(settings.mongo_uri, settings.mongo_db_name)
        else:
            print("[MongoDB] MONGO_URI not set — skipping MongoDB startup")
    except Exception as e:
        print(f"[MongoDB] Startup hook error: {e}")


async def on_shutdown() -> None:
    """
    FastAPI lifespan shutdown hook — gracefully closes all pooled connections.
    """
    await close_mongo()


async def close_mongo() -> None:
    """Called during FastAPI shutdown."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        print("[MongoDB] Connection closed")


def is_connected() -> bool:
    """Quick check whether MongoDB is available."""
    return _db is not None
