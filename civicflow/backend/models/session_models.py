import json
import os
from datetime import datetime
from typing import Any, Optional, Dict, List
from .form_models import UserSession


class InMemorySessionStore:
    """In-memory fallback when Redis is not available"""
    def __init__(self):
        self._store: Dict[str, UserSession] = {}
        print("[SessionStore] ⚠ Using in-memory storage (Redis not available)")
    
    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"
    
    async def save(self, session: UserSession) -> None:
        session.updated_at = datetime.utcnow()
        key = self._session_key(session.session_id)
        # Deep copy to avoid reference issues
        self._store[key] = UserSession.model_validate_json(session.model_dump_json())
    
    async def load(self, session_id: str) -> Optional[UserSession]:
        key = self._session_key(session_id)
        session = self._store.get(key)
        if session is None:
            return None
        # Return a copy
        return UserSession.model_validate_json(session.model_dump_json())
    
    async def update_status(self, session_id: str, status: str) -> None:
        session = await self.load(session_id)
        if session:
            session.status = status
            session.updated_at = datetime.utcnow()
            await self.save(session)
    
    async def update_field(self, session_id: str, field_name: str, value: Any) -> None:
        session = await self.load(session_id)
        if session:
            setattr(session, field_name, value)
            session.updated_at = datetime.utcnow()
            await self.save(session)
    
    async def delete(self, session_id: str) -> None:
        key = self._session_key(session_id)
        self._store.pop(key, None)
    
    async def list_all(self, user_id: Optional[str] = None) -> List[UserSession]:
        """Return all sessions, optionally filtered by user_id."""
        sessions = list(self._store.values())
        if user_id:
            sessions = [s for s in sessions if getattr(s, 'user_id', None) == user_id]
        return sessions
    
    async def close(self) -> None:
        self._store.clear()


class MongoSessionStore:
    """MongoDB-backed session store — used when MONGO_URI is configured."""

    def __init__(self):
        print("[SessionStore] ✓ Using MongoDB storage")

    def _session_key(self, session_id: str) -> str:
        return session_id

    async def _get_db(self):
        try:
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from db.mongo import get_db
            return await get_db()
        except Exception:
            return None

    async def save(self, session: UserSession) -> None:
        session.updated_at = datetime.utcnow()
        db = await self._get_db()
        if db is None:
            return
        doc = json.loads(session.model_dump_json())
        await db.sessions.update_one(
            {"session_id": session.session_id},
            {"$set": doc},
            upsert=True
        )

    async def load(self, session_id: str) -> Optional[UserSession]:
        db = await self._get_db()
        if db is None:
            return None
        doc = await db.sessions.find_one({"session_id": session_id})
        if doc is None:
            return None
        doc.pop("_id", None)
        return UserSession.model_validate(doc)

    async def update_status(self, session_id: str, status: str) -> None:
        db = await self._get_db()
        if db is None:
            return
        await db.sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": status, "updated_at": datetime.utcnow().isoformat()}}
        )

    async def update_field(self, session_id: str, field_name: str, value: Any) -> None:
        db = await self._get_db()
        if db is None:
            return
        # Serialize value if it's a Pydantic model or dict of models
        if hasattr(value, 'model_dump'):
            value = json.loads(value.model_dump_json())
        elif isinstance(value, list) and value and hasattr(value[0], 'model_dump'):
            value = [json.loads(v.model_dump_json()) for v in value]
        await db.sessions.update_one(
            {"session_id": session_id},
            {"$set": {field_name: value, "updated_at": datetime.utcnow().isoformat()}}
        )

    async def delete(self, session_id: str) -> None:
        db = await self._get_db()
        if db is None:
            return
        await db.sessions.delete_one({"session_id": session_id})

    async def list_all(self, user_id: Optional[str] = None) -> List[UserSession]:
        db = await self._get_db()
        if db is None:
            return []
        query = {}
        if user_id:
            query["user_id"] = user_id
        cursor = db.sessions.find(query).sort("updated_at", -1).limit(100)
        sessions = []
        async for doc in cursor:
            doc.pop("_id", None)
            try:
                sessions.append(UserSession.model_validate(doc))
            except Exception:
                pass
        return sessions

    async def close(self) -> None:
        pass  # Motor client managed by db/mongo.py



class SessionStore:
    """Auto-selects backend: MongoDB → Redis → InMemory."""

    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        mongo_uri = os.getenv("MONGO_URI", "")
        self.redis = None
        self.redis_url = redis_url
        self.mongo_uri = mongo_uri
        self.ttl = 86400  # 24 hours
        self._fallback: Optional[InMemorySessionStore] = None
        self._mongo: Optional[MongoSessionStore] = None
        self._use_fallback = False
        self._use_mongo = False


    async def _get_redis(self):
        # Priority 1: MongoDB (if configured)
        if self.mongo_uri and not self._use_mongo:
            try:
                from db.mongo import connect_mongo, get_db, is_connected
                if not is_connected():
                    await connect_mongo(self.mongo_uri)
                if is_connected():
                    self._use_mongo = True
                    if self._mongo is None:
                        self._mongo = MongoSessionStore()
            except Exception as e:
                print(f"[SessionStore] ✗ MongoDB init failed: {e}")

        if self._use_mongo and self._mongo:
            return self._mongo

        # Priority 2: Redis
        if self._use_fallback:
            if self._fallback is None:
                self._fallback = InMemorySessionStore()
            return self._fallback
        
        if self.redis is None:
            try:
                from redis.asyncio import Redis, from_url
                self.redis = await from_url(self.redis_url, decode_responses=True)
                # Test connection
                await self.redis.ping()
                print("[SessionStore] ✓ Connected to Redis")
            except Exception as e:
                print(f"[SessionStore] ✗ Redis connection failed: {e}")
                print("[SessionStore] → Falling back to in-memory storage")
                self._use_fallback = True
                self._fallback = InMemorySessionStore()
                return self._fallback
        return self.redis
    
    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"
    
    async def save(self, session: UserSession) -> None:
        session.updated_at = datetime.utcnow()
        store = await self._get_redis()
        
        if self._use_mongo:
            await store.save(session)
        elif self._use_fallback:
            await store.save(session)
        else:
            key = self._session_key(session.session_id)
            data = session.model_dump_json()
            await store.setex(key, self.ttl, data)
    
    async def load(self, session_id: str) -> Optional[UserSession]:
        store = await self._get_redis()
        
        if self._use_mongo:
            return await store.load(session_id)
        elif self._use_fallback:
            return await store.load(session_id)
        else:
            key = self._session_key(session_id)
            data = await store.get(key)
            if data is None:
                return None
            return UserSession.model_validate_json(data)
    
    async def update_status(self, session_id: str, status: str) -> None:
        store = await self._get_redis()
        if self._use_mongo or self._use_fallback:
            await store.update_status(session_id, status)
        else:
            session = await self.load(session_id)
            if session:
                session.status = status
                session.updated_at = datetime.utcnow()
                await self.save(session)
    
    async def update_field(self, session_id: str, field_name: str, value: Any) -> None:
        store = await self._get_redis()
        if self._use_mongo or self._use_fallback:
            await store.update_field(session_id, field_name, value)
        else:
            session = await self.load(session_id)
            if session:
                setattr(session, field_name, value)
                session.updated_at = datetime.utcnow()
                await self.save(session)
    
    async def delete(self, session_id: str) -> None:
        store = await self._get_redis()
        
        if self._use_mongo or self._use_fallback:
            await store.delete(session_id)
        else:
            key = self._session_key(session_id)
            await store.delete(key)
    
    async def list_all(self, user_id: Optional[str] = None) -> List[UserSession]:
        """List all sessions, optionally filtered by user_id."""
        store = await self._get_redis()
        if self._use_mongo or self._use_fallback:
            return await store.list_all(user_id=user_id)
        # Redis doesn't support list without key scan — return empty for raw Redis mode
        return []
    
    async def close(self) -> None:
        if self._use_mongo and self._mongo:
            await self._mongo.close()
        elif self._use_fallback and self._fallback:
            await self._fallback.close()
        elif self.redis:
            await self.redis.close()
