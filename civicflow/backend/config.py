"""
CivicFlow — Central Configuration
==================================
Single source of truth for all environment variables.
All values are loaded from backend/.env automatically.

Existing code that uses os.getenv() still works.
New code should import `settings` from here instead.
"""
from functools import lru_cache
from typing import Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback: pydantic v1 had BaseSettings built in
    from pydantic import BaseSettings  # type: ignore


class Settings(BaseSettings):
    # --- Gemini AI ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-lite"  # Default model

    # --- Redis (executor signaling: captcha / otp resume) ---
    redis_url: str = "redis://localhost:6379"

    # --- MongoDB (durable session + user persistence) ---
    # Leave blank to use in-memory fallback (dev mode)
    mongo_uri: str = ""
    mongo_db_name: str = "civicflow"

    # --- JWT Authentication ---
    # Generate a strong secret: python -c "import secrets; print(secrets.token_hex(32))"
    jwt_secret: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- File Storage ---
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 10

    # --- Telegram Notifications (Phase 4) ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",          # ignore unknown env vars gracefully
    }


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton — loaded once, reused everywhere."""
    return Settings()


# Module-level singleton for convenience:  from config import settings
settings = get_settings()
