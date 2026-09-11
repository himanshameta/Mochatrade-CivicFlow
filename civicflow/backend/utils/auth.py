"""
CivicFlow — Auth Utilities
============================
Single source of truth for password hashing, JWT tokens, FastAPI auth
dependencies, and Redis-backed login rate limiting.

The existing api/auth.py delegates to these functions.
All new agent/route code should import from here.
"""
import os
import sys
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Optional dependencies — graceful degradation if not installed
# ---------------------------------------------------------------------------

try:
    from passlib.context import CryptContext
    # pbkdf2_sha256: reliable on Python 3.11; bcrypt listed deprecated for migration
    _pwd_context = CryptContext(
        schemes=["pbkdf2_sha256", "bcrypt"],
        deprecated=["bcrypt"]
    )
    PASSLIB_AVAILABLE = True
except ImportError:
    PASSLIB_AVAILABLE = False
    _pwd_context = None
    print("[AuthUtils] ⚠ passlib not installed — using insecure dev fallback")

try:
    from jose import JWTError, jwt as _jose_jwt
    JOSE_AVAILABLE = True
except ImportError:
    JOSE_AVAILABLE = False
    _jose_jwt = None
    print("[AuthUtils] ⚠ python-jose not installed — using dev token fallback")

# ---------------------------------------------------------------------------
# JWT Configuration (from env / config.py)
# ---------------------------------------------------------------------------

_JWT_SECRET = os.getenv("JWT_SECRET", "civicflow-dev-secret-change-in-production")
_JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
_JWT_EXPIRE_HOURS = 24

# ---------------------------------------------------------------------------
# Rate limiter configuration
# ---------------------------------------------------------------------------

RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 600  # 10 minutes

# In-memory fallback (non-distributed, dev-only)
_ip_attempts: dict = {}

# ---------------------------------------------------------------------------
# HTTP Bearer extractor
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


# ===========================================================================
# Password Hashing
# ===========================================================================

def password_hash(plain: str) -> str:
    """
    Hash a password using pbkdf2_sha256 (passlib).
    Falls back to SHA-256 hex digest prefixed with 'dev:' if passlib is missing.
    NEVER log the plain text password.
    """
    if not PASSLIB_AVAILABLE:
        import hashlib
        return "dev:" + hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain password against a stored hash.
    Handles both pbkdf2_sha256 and the legacy dev: prefix.
    """
    if not plain or not hashed:
        return False

    if hashed.startswith("dev:"):
        import hashlib
        return hashed == "dev:" + hashlib.sha256(plain.encode("utf-8")).hexdigest()

    if not PASSLIB_AVAILABLE:
        return False

    try:
        return _pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ===========================================================================
# JWT Tokens
# ===========================================================================

def create_jwt_token(user_id: str, role: str = "primary") -> str:
    """
    Create a signed JWT token with 24-hour expiry.

    Payload:
        sub  — user_id (UUID string)
        role — "primary" | "relative"
        iat  — issued-at timestamp (Unix seconds)
        exp  — expiry timestamp (Unix seconds)

    Falls back to a base64-encoded dev token if python-jose is missing.
    """
    expire = datetime.utcnow() + timedelta(hours=_JWT_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int(expire.timestamp()),
    }

    if not JOSE_AVAILABLE:
        import base64
        safe_payload = {"sub": user_id, "role": role}
        return "dev." + base64.b64encode(
            json.dumps(safe_payload).encode("utf-8")
        ).decode("utf-8")

    return _jose_jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT token.
    Returns the payload dict on success, None on any failure.
    """
    if not token:
        return None

    # Dev-mode tokens
    if token.startswith("dev."):
        try:
            import base64
            return json.loads(base64.b64decode(token[4:]).decode("utf-8"))
        except Exception:
            return None

    if not JOSE_AVAILABLE:
        return None

    try:
        payload = _jose_jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        # Normalize exp/iat to timestamp if stored as ISO strings
        if isinstance(payload.get("exp"), str):
            payload["exp"] = int(datetime.fromisoformat(payload["exp"]).timestamp())
        if isinstance(payload.get("iat"), str):
            payload["iat"] = int(datetime.fromisoformat(payload["iat"]).timestamp())
        return payload
    except JWTError as e:
        print(f"[Auth] JWT decode error: {e}")
        return None


# ===========================================================================
# FastAPI Auth Dependencies
# ===========================================================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[dict]:
    """
    OPTIONAL auth dependency.
    Returns decoded token payload (with 'sub' = user_id, 'role') or None.
    Does NOT raise 401 — existing unauthenticated routes continue to work.
    """
    if not credentials:
        return None
    return decode_jwt_token(credentials.credentials)


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """
    STRICT auth dependency.
    Returns decoded token payload or raises HTTP 401.
    Use this on routes that require a logged-in user.
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail=_error("Authentication required — provide a Bearer token")
        )

    payload = decode_jwt_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail=_error("Invalid or expired token")
        )

    return payload


# ===========================================================================
# Rate Limiting (login endpoint)
# ===========================================================================

async def check_login_rate_limit(request: Request) -> None:
    """
    Raise HTTP 429 if the client IP has exceeded RATE_LIMIT_MAX_ATTEMPTS
    login attempts within RATE_LIMIT_WINDOW_SECONDS.

    Uses Redis if available; falls back to in-memory dict (dev / single-node).

    Call this at the START of POST /auth/login before any DB lookup.
    """
    ip = _get_client_ip(request)
    key = f"login_attempts:{ip}"

    # ---- Try Redis ----
    try:
        from redis.asyncio import from_url as redis_from_url
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = await redis_from_url(redis_url, decode_responses=True)

        count = await r.incr(key)
        if count == 1:
            await r.expire(key, RATE_LIMIT_WINDOW_SECONDS)
        await r.aclose()

        if count > RATE_LIMIT_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail=_error(
                    f"Too many login attempts from this IP. "
                    f"Try again in {RATE_LIMIT_WINDOW_SECONDS // 60} minutes.",
                    data={"attempts": count, "max": RATE_LIMIT_MAX_ATTEMPTS},
                )
            )
        return

    except HTTPException:
        raise  # Re-raise 429s

    except Exception:
        pass  # Redis unavailable — use in-memory

    # ---- In-memory fallback ----
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)

    attempts = _ip_attempts.get(ip, [])
    # Purge expired attempts
    attempts = [t for t in attempts if t > cutoff]
    attempts.append(now)
    _ip_attempts[ip] = attempts

    if len(attempts) > RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail=_error(
                f"Too many login attempts. "
                f"Try again in {RATE_LIMIT_WINDOW_SECONDS // 60} minutes.",
                data={"attempts": len(attempts), "max": RATE_LIMIT_MAX_ATTEMPTS},
            )
        )


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For from proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ===========================================================================
# Consistent response format helper
# ===========================================================================

def _error(message: str, data: dict = None) -> dict:
    """Consistent error response body."""
    return {"success": False, "message": message, "data": data or {}}


def ok(message: str = "Success", data: dict = None) -> dict:
    """Consistent success response body."""
    return {"success": True, "message": message, "data": data or {}}
