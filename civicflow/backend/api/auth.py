"""
CivicFlow — Auth API
======================
Uses utils/auth.py for core JWT, hashing, and rate limiting logic.
Provides endpoints for registration, login, profile info, and relative linking.
Returns consistent {success, message, data} responses.
"""
import os
import sys
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.user_models import (
    UserDB,
    RegisterRequestV2,
    LoginRequest,
    UserDBPublic,
    AddRelativeRequest,
)
from utils.auth import (
    password_hash,
    verify_password,
    create_jwt_token,
    require_auth,
    check_login_rate_limit,
    ok,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

# In-memory fallback if Mongo is not configured
_memory_users: dict = {}

async def _save_user(user: UserDB) -> None:
    user.updated_at = datetime.utcnow()
    try:
        from db.mongo import get_db
        db = await get_db()
        if db is not None:
            doc = user.model_dump()
            await db.users.update_one(
                {"user_id": user.user_id},
                {"$set": doc},
                upsert=True
            )
            return
    except Exception as e:
        print(f"[Auth API] MongoDB save failed, using memory: {e}")
    _memory_users[user.email] = user

async def _get_user_by_email(email: str) -> Optional[UserDB]:
    try:
        from db.mongo import get_db
        db = await get_db()
        if db is not None:
            doc = await db.users.find_one({"email": email})
            if doc:
                doc.pop("_id", None)
                return UserDB(**doc)
    except Exception as e:
        pass
    return _memory_users.get(email)

async def _get_user_by_id(user_id: str) -> Optional[UserDB]:
    try:
        from db.mongo import get_db
        db = await get_db()
        if db is not None:
            doc = await db.users.find_one({"user_id": user_id})
            if doc:
                doc.pop("_id", None)
                return UserDB(**doc)
    except Exception as e:
        pass
    for user in _memory_users.values():
        if user.user_id == user_id:
            return user
    return None

def _to_public(user: UserDB) -> UserDBPublic:
    return UserDBPublic(
        user_id=user.user_id,
        email=user.email,
        phone=user.phone,
        role=user.role,
        is_verified=user.is_verified,
        linked_user_ids=user.linked_user_ids,
        telegram_chat_id=user.telegram_chat_id,
        created_at=user.created_at,
        last_login=user.last_login,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register", summary="Create a new account")
async def register(request: RegisterRequestV2):
    try:
        print(f"[Auth API] Register request received: email={request.email}, role={request.role}, phone={request.phone}, parent_user_id={request.parent_user_id}")
        email = request.email.lower().strip()
        
        if await _get_user_by_email(email):
            return {"success": False, "message": "Email already registered", "data": {}}

        user = UserDB(
            email=email,
            phone=request.phone,
            password_hash=password_hash(request.password),
            role=request.role,
            parent_user_id=request.parent_user_id,
        )
        await _save_user(user)
        print(f"[Auth API] User registered successfully: user_id={user.user_id}, email={email}")
        
        # Optional: If this is a relative, link it to the parent right away
        if user.role == "relative" and user.parent_user_id:
            parent = await _get_user_by_id(user.parent_user_id)
            if parent:
                if user.user_id not in parent.linked_user_ids:
                    parent.linked_user_ids.append(user.user_id)
                    await _save_user(parent)

        return ok("User registered successfully", data=_to_public(user).model_dump())
    except Exception as e:
        print(f"[Auth API] Registration error: {type(e).__name__}: {str(e)}")
        raise


@router.post("/login", summary="Login and get JWT token")
async def login(request: LoginRequest, req: Request):
    # await check_login_rate_limit(req)

    email = request.email.lower()
    user = await _get_user_by_email(email)

    if not user or not verify_password(request.password, user.password_hash):
        print(f"[Auth API] Login failed for email: {email}")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user.last_login = datetime.utcnow()
    await _save_user(user)

    token = create_jwt_token(user.user_id, user.role)
    print(f"[Auth API] Login successful for user_id={user.user_id}")
    return ok("Login successful", data={
        "access_token": token,
        "token_type": "bearer",
        "user": _to_public(user).model_dump()
    })


@router.post("/token", include_in_schema=False)
async def login_form(req: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 password flow — enables Swagger UI 'Authorize' button."""
    await check_login_rate_limit(req)
    email = form_data.username.lower().strip()
    user = await _get_user_by_email(email)

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user.last_login = datetime.utcnow()
    await _save_user(user)

    token = create_jwt_token(user.user_id, user.role)
    # Swagger expects exactly this flat format:
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout", summary="Logout user")
async def logout(payload: dict = Depends(require_auth)):
    """
    Since JWTs are stateless, logout is primarily a frontend action (discard token).
    We just return a success confirmation.
    """
    return ok("Logged out successfully")


@router.get("/me", summary="Get current user info")
async def get_me(payload: dict = Depends(require_auth)):
    print("[Auth API] /me endpoint called with payload:", payload)
    user = await _get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return ok("Success", data=_to_public(user).model_dump())


@router.post("/add-relative", summary="Link a relative account to current user")
async def add_relative(request: AddRelativeRequest, payload: dict = Depends(require_auth)):
    current_user = await _get_user_by_id(payload["sub"])
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    relative = await _get_user_by_id(request.relative_user_id)
    if not relative:
        return {"success": False, "message": "Relative user not found", "data": {}}
        
    if relative.user_id not in current_user.linked_user_ids:
        current_user.linked_user_ids.append(relative.user_id)
        await _save_user(current_user)
        
    return ok("Relative linked successfully", data=_to_public(current_user).model_dump())


@router.get("/relatives", summary="List linked family members")
async def get_relatives(payload: dict = Depends(require_auth)):
    current_user = await _get_user_by_id(payload["sub"])
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    relatives = []
    for rel_id in current_user.linked_user_ids:
        rel = await _get_user_by_id(rel_id)
        if rel:
            relatives.append(_to_public(rel).model_dump())
            
    return ok("Success", data={"relatives": relatives})


@router.post("/profile", summary="Update user profile")
async def update_profile(request: dict, payload: dict = Depends(require_auth)):
    """
    Update user profile information.
    Creates or updates the user_profiles collection with encrypted data.

    Normalizes frontend field names to canonical backend names before assignment.
    Returns 422 with field-level errors if any field fails validation.
    """
    user_id = payload["sub"]
    print(f"[Auth API] Profile update request for user_id={user_id}")
    print(f"[Auth API] Raw payload keys: {list(request.keys())}")

    # Log raw payload (redact sensitive values)
    for section_name in ["basic_info", "contact", "identity", "education"]:
        section_data = request.get(section_name, {})
        if isinstance(section_data, dict):
            safe_keys = {k: ("***" if k in ("pan_number", "aadhaar_number") else v[:30] if isinstance(v, str) and len(v) > 30 else v)
                         for k, v in section_data.items() if v}
            print(f"[Auth API]   {section_name}: {safe_keys}")

    try:
        from db.mongo import get_db
        from models.user_models import UserProfileData, BasicInfo, ContactInfo, IdentityInfo, EducationInfo
        from utils.profile_normalizer import normalize_profile_update_payload, get_valid_keys_for_section
        from utils.encryption import encrypt_profile

        db = await get_db()
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database unavailable"
            )

        # ── Step 1: Normalize frontend keys to canonical backend keys ──
        normalized, normalize_errors = normalize_profile_update_payload(request)

        print(f"[Auth API] Normalized payload:")
        for section_name, section_data in normalized.items():
            if section_data:
                print(f"[Auth API]   {section_name}: {list(section_data.keys())}")
        if normalize_errors:
            print(f"[Auth API] Normalization warnings: {normalize_errors}")

        # ── Step 2: Load or create profile ──
        profile_doc = await db.user_profiles.find_one({"user_id": user_id})

        if profile_doc:
            profile_doc.pop("_id", None)
            try:
                profile_data = UserProfileData(**profile_doc)
            except Exception as e:
                print(f"[Auth API] Failed to parse existing profile, creating new: {e}")
                profile_data = UserProfileData(user_id=user_id)
        else:
            profile_data = UserProfileData(user_id=user_id)

        # ── Step 3: Safe merge — only set keys that exist in the model ──
        validation_errors = []
        fields_written = []

        section_models = {
            "basic_info": (profile_data.basic_info, BasicInfo),
            "contact": (profile_data.contact, ContactInfo),
            "identity": (profile_data.identity, IdentityInfo),
            "education": (profile_data.education, EducationInfo),
        }

        for section_name, (section_obj, model_cls) in section_models.items():
            section_data = normalized.get(section_name, {})
            if not section_data:
                continue

            valid_keys = get_valid_keys_for_section(section_name)
            model_fields = set(model_cls.model_fields.keys())

            for key, val in section_data.items():
                if key.startswith("_"):
                    continue  # skip compound intermediates

                if key not in model_fields:
                    validation_errors.append(
                        f"Field '{key}' is not valid for section '{section_name}'"
                    )
                    print(f"[Auth API] SKIP: '{key}' not in {section_name} model fields")
                    continue

                try:
                    setattr(section_obj, key, val)
                    fields_written.append(f"{section_name}.{key}")
                except Exception as e:
                    validation_errors.append(
                        f"Failed to set {section_name}.{key}: {str(e)}"
                    )
                    print(f"[Auth API] ERROR: setattr({section_name}.{key}, {val!r}): {e}")

        print(f"[Auth API] Fields written: {fields_written}")

        if not fields_written:
            return {
                "success": False,
                "message": "No valid fields to update",
                "errors": validation_errors or ["No recognized fields in payload"],
            }

        # ── Step 4: Encrypt and save ──
        profile_data.updated_at = datetime.utcnow()

        profile_dict = profile_data.model_dump()
        encrypted_dict = encrypt_profile(profile_dict, user_id)

        await db.user_profiles.update_one(
            {"user_id": user_id},
            {"$set": encrypted_dict},
            upsert=True
        )

        print(f"[Auth API] Profile saved: {len(fields_written)} fields, {len(validation_errors)} errors")

        # ── Step 5: Return result ──
        response = {
            "success": True,
            "message": f"Profile updated: {len(fields_written)} fields saved",
            "data": {
                "fields_written": fields_written,
                "warnings": validation_errors if validation_errors else [],
            }
        }
        if validation_errors:
            response["message"] += f" ({len(validation_errors)} warnings)"

        return response

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Auth API] Profile update FAILED: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=422,
            detail={
                "success": False,
                "message": "Profile update failed",
                "errors": [f"{type(e).__name__}: {str(e)}"],
            }
        )
