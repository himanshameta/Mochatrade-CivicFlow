"""
CivicFlow — User & Auth Models
================================
Pydantic models for user profiles, family members, and auth request/response schemas.
Stored in MongoDB (users collection) with in-memory fallback.
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator
from uuid import uuid4


# ---------------------------------------------------------------------------
# Core domain models (stored in DB)
# ---------------------------------------------------------------------------

class FamilyMember(BaseModel):
    """A relative/family member linked to a main user account."""
    member_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    relationship: Literal[
        "spouse", "parent", "child", "sibling",
        "grandparent", "grandchild", "other"
    ] = "other"
    phone: Optional[str] = None
    email: Optional[str] = None
    # Pre-saved field values for this member (name → value)
    saved_data: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserProfile(BaseModel):
    """Main user account with optional family members."""
    user_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    email: str
    phone: Optional[str] = None
    hashed_password: str
    role: Literal["user", "admin"] = "user"

    # Family members (sub-profiles)
    family_members: List[FamilyMember] = Field(default_factory=list)

    # Reusable saved field values (e.g. address, date of birth)
    # These pre-fill future sessions automatically
    saved_data: dict = Field(default_factory=dict)

    # Session IDs this user has created
    session_ids: List[str] = Field(default_factory=list)

    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Request schemas (inbound from frontend)
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None

    @field_validator("email")
    @classmethod
    def email_must_have_at(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class AddFamilyMemberRequest(BaseModel):
    name: str
    relationship: str = "other"
    phone: Optional[str] = None
    email: Optional[str] = None


class UpdateSavedDataRequest(BaseModel):
    """Save reusable field values for auto-fill on future sessions."""
    data: dict  # {field_label: value}


# ---------------------------------------------------------------------------
# Response schemas (outbound — never expose hashed_password)
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    email: str


class UserPublic(BaseModel):
    """Safe user info returned to the frontend — no password."""
    user_id: str
    name: str
    email: str
    phone: Optional[str] = None
    role: str = "user"
    family_members: List[FamilyMember] = []
    saved_data: dict = {}
    session_ids: List[str] = []
    created_at: datetime


class FamilyMemberPublic(BaseModel):
    member_id: str
    name: str
    relationship: str
    phone: Optional[str] = None
    email: Optional[str] = None
    saved_data: dict = {}


# ===========================================================================
# MongoDB Collection: users
# Full user record — auth + identity + links to family members
# ===========================================================================

class UserDB(BaseModel):
    """
    Maps to the `users` MongoDB collection.
    Separates auth concerns from profile data (UserProfileData handles that).
    """
    user_id: str = Field(default_factory=lambda: str(uuid4()))
    email: str                             # unique, indexed
    phone: Optional[str] = None            # unique, indexed
    password_hash: str                     # pbkdf2_sha256 via utils/auth.py
    role: Literal["primary", "relative"] = "primary"
    parent_user_id: Optional[str] = None   # set when role="relative"
    linked_user_ids: List[str] = Field(default_factory=list)  # family UUIDs
    is_verified: bool = False
    telegram_chat_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ===========================================================================
# MongoDB Collection: user_profiles
# All sensitive personal data — encrypted at rest via utils/encryption.py
# ===========================================================================

class BasicInfo(BaseModel):
    full_name: str = ""          # AES-256 encrypted in MongoDB
    first_name: str = ""         # Derived from full_name or set directly
    middle_name: str = ""        # Derived from full_name or set directly
    last_name: str = ""          # Derived from full_name or set directly
    dob: str = ""                # AES-256 encrypted in MongoDB  (YYYY-MM-DD)
    gender: str = ""
    address: str = ""            # AES-256 encrypted in MongoDB
    city: str = ""
    state: str = ""
    pincode: str = ""
    nationality: str = "Indian"
    father_name: str = ""
    mother_name: str = ""


class ContactInfo(BaseModel):
    email: str = ""
    phone: str = ""              # AES-256 encrypted in MongoDB
    alternate_phone: str = ""
    address: Optional[str] = ""  # Frontend sends this field
    city: str = ""               # Also in BasicInfo for legacy compat
    state: str = ""              # Also in BasicInfo for legacy compat
    pincode: Optional[str] = ""  # Frontend sends this field
    country: str = "India"


class IdentityInfo(BaseModel):
    aadhaar_last4: str = ""      # store ONLY last 4 digits — never full Aadhaar
    pan_number: str = ""         # AES-256 encrypted in MongoDB
    voter_id: str = ""
    passport_number: str = ""
    driving_license: str = ""


class EducationInfo(BaseModel):
    highest_qualification: str = ""
    college: str = ""
    university: str = ""
    year_of_passing: str = ""


class UploadedDocumentRef(BaseModel):
    """Reference to a document stored in the `documents` collection."""
    doc_id: str = Field(default_factory=lambda: str(uuid4()))
    doc_type: str                # e.g. "aadhaar", "pan", "marksheet"
    original_filename: str
    storage_path: str
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    ocr_extracted_fields: dict = Field(default_factory=dict)
    is_verified: bool = False


class UserProfileData(BaseModel):
    """
    Maps to the `user_profiles` MongoDB collection.
    Created on first profile update — does NOT exist at registration.

    IMPORTANT: before saving to MongoDB, call:
        from utils.encryption import encrypt_profile
        doc = encrypt_profile(profile.model_dump(), user_id)

    Before returning to the frontend, call:
        from utils.encryption import decrypt_profile
        data = decrypt_profile(doc, user_id)
    """
    profile_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str                   # FK → users.user_id, indexed
    basic_info: BasicInfo = Field(default_factory=BasicInfo)
    contact: ContactInfo = Field(default_factory=ContactInfo)
    identity: IdentityInfo = Field(default_factory=IdentityInfo)
    education: EducationInfo = Field(default_factory=EducationInfo)
    uploaded_documents: List[UploadedDocumentRef] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ===========================================================================
# MongoDB Collection: documents
# Metadata for every uploaded file
# ===========================================================================

class DocumentDB(BaseModel):
    """Maps to the `documents` MongoDB collection."""
    doc_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str                          # FK → users.user_id, indexed
    original_filename: str
    mime_type: str                        # e.g. "application/pdf", "image/png"
    storage_path: str                     # absolute path on disk
    file_size_bytes: int = 0
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    ocr_status: Literal["pending", "processing", "done", "failed"] = "pending"
    ocr_results: dict = Field(default_factory=dict)
    encryption_key_id: str = ""           # future: per-document key rotation ID


# ===========================================================================
# MongoDB Collection: form_sessions extensions
# New fields added to UserSession (in form_models.py) for Phase 2
# Stored as a separate schema here so we don't break the existing model
# ===========================================================================

class ConversationMessage(BaseModel):
    """One turn in a counsellor chat conversation."""
    role: Literal["user", "assistant"] = "user"
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ===========================================================================
# New Auth Request / Response schemas (extend existing ones)
# ===========================================================================

class RegisterRequestV2(BaseModel):
    """Extended register request supporting role + parent linking."""
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    role: Literal["primary", "relative"] = "primary"
    parent_user_id: Optional[str] = None  # required when role="relative"

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v):
        if v == "" or v is None:
            return None
        return v.strip() if v else None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

    @field_validator("parent_user_id")
    @classmethod
    def relative_needs_parent(cls, v, info):
        role = info.data.get("role", "primary")
        if role == "relative" and not v:
            raise ValueError("parent_user_id is required when role is 'relative'")
        return v


class AddRelativeRequest(BaseModel):
    """Link a relative account (already registered) to the current user."""
    relative_user_id: str
    relationship: str = "other"


class UpdateProfileRequest(BaseModel):
    """Update the UserProfileData document for the current user."""
    basic_info: Optional[BasicInfo] = None
    contact: Optional[ContactInfo] = None
    identity: Optional[IdentityInfo] = None
    education: Optional[EducationInfo] = None


class UserDBPublic(BaseModel):
    """Safe UserDB response — no password_hash."""
    user_id: str
    email: str
    phone: Optional[str] = None
    role: str
    is_verified: bool
    linked_user_ids: List[str] = []
    telegram_chat_id: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None

