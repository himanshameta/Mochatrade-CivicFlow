import json
import os
from datetime import datetime
from typing import Any, Optional, Dict
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
    
    async def close(self) -> None:
        self._store.clear()


class SessionStore:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis = None
        self.redis_url = redis_url
        self.ttl = 86400  # 24 hours
        self._fallback: Optional[InMemorySessionStore] = None
        self._use_fallback = False
    
    async def _get_redis(self):
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
        
        if self._use_fallback:
            await store.save(session)
        else:
            key = self._session_key(session.session_id)
            data = session.model_dump_json()
            await store.setex(key, self.ttl, data)
    
    async def load(self, session_id: str) -> Optional[UserSession]:
        store = await self._get_redis()
        
        if self._use_fallback:
            return await store.load(session_id)
        else:
            key = self._session_key(session_id)
            data = await store.get(key)
            if data is None:
                return None
            return UserSession.model_validate_json(data)
    
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
        store = await self._get_redis()
        
        if self._use_fallback:
            await store.delete(session_id)
        else:
            key = self._session_key(session_id)
            await store.delete(key)
    
    async def close(self) -> None:
        if self._use_fallback and self._fallback:
            await self._fallback.close()
        elif self.redis:
            await self.redis.close()
