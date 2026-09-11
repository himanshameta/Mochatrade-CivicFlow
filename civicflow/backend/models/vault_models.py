"""
CivicFlow — Document Vault Models
====================================
Pydantic schemas for the privacy-first local document vault.
Supports categorized document storage with metadata tracking.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DocumentCategory(str, Enum):
    """Supported document categories for the vault."""
    IDENTITY = "identity"
    ADDRESS_PROOF = "address_proof"
    EDUCATION = "education"
    CERTIFICATE = "certificate"
    PHOTO = "photo"
    RESUME = "resume"
    FINANCIAL = "financial"
    MEDICAL = "medical"
    OTHER = "other"


class DocumentSource(str, Enum):
    """How the document entered the vault."""
    MANUAL_UPLOAD = "manual_upload"       # Uploaded via My Documents page
    SESSION_UPLOAD = "session_upload"     # Uploaded during form review (save_for_reuse=True)
    MIGRATION = "migration"              # Migrated from legacy physical_documents


# ---------------------------------------------------------------------------
# Core vault document model (stored in MongoDB `user_documents` collection)
# ---------------------------------------------------------------------------

class UserDocument(BaseModel):
    """
    A single document stored in the user's local vault.
    Maps to the `user_documents` MongoDB collection.
    """
    document_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str                                  # FK → users.user_id
    display_name: str                             # User-friendly name, e.g. "My Resume 2026"
    category: DocumentCategory = DocumentCategory.OTHER
    subcategory: Optional[str] = None             # Free-text, e.g. "electricity" under address_proof
    original_filename: str                        # Original uploaded filename
    stored_filename: str                          # Filename on disk after sanitization
    storage_path: str                             # Absolute path on disk
    mime_type: str                                # e.g. "application/pdf"
    extension: str                                # e.g. ".pdf"
    size_bytes: int = 0
    tags: List[str] = Field(default_factory=list) # User-defined tags for search
    source: DocumentSource = DocumentSource.MANUAL_UPLOAD
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# API response model — never expose storage_path to frontend
# ---------------------------------------------------------------------------

class UserDocumentPublic(BaseModel):
    """Safe document info returned to the frontend — no storage_path."""
    document_id: str
    user_id: str
    display_name: str
    category: str
    subcategory: Optional[str] = None
    original_filename: str
    mime_type: str
    extension: str
    size_bytes: int = 0
    tags: List[str] = []
    source: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, doc: UserDocument) -> "UserDocumentPublic":
        return cls(
            document_id=doc.document_id,
            user_id=doc.user_id,
            display_name=doc.display_name,
            category=doc.category.value if isinstance(doc.category, DocumentCategory) else doc.category,
            subcategory=doc.subcategory,
            original_filename=doc.original_filename,
            mime_type=doc.mime_type,
            extension=doc.extension,
            size_bytes=doc.size_bytes,
            tags=doc.tags,
            source=doc.source.value if isinstance(doc.source, DocumentSource) else doc.source,
            is_active=doc.is_active,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )

    @classmethod
    def from_dict(cls, d: dict) -> "UserDocumentPublic":
        """Build from a MongoDB document dict."""
        return cls(
            document_id=d["document_id"],
            user_id=d["user_id"],
            display_name=d["display_name"],
            category=d.get("category", "other"),
            subcategory=d.get("subcategory"),
            original_filename=d["original_filename"],
            mime_type=d.get("mime_type", ""),
            extension=d.get("extension", ""),
            size_bytes=d.get("size_bytes", 0),
            tags=d.get("tags", []),
            source=d.get("source", "manual_upload"),
            is_active=d.get("is_active", True),
            created_at=d.get("created_at", datetime.utcnow()),
            updated_at=d.get("updated_at", datetime.utcnow()),
        )


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class VaultUploadMeta(BaseModel):
    """Metadata sent alongside a multipart file upload to the vault."""
    display_name: str
    category: DocumentCategory = DocumentCategory.OTHER
    subcategory: Optional[str] = None
    tags: Optional[List[str]] = None


class AttachDocumentRequest(BaseModel):
    """Link an existing vault document to a session file requirement."""
    field_name: str
    document_id: str


class SessionUploadMeta(BaseModel):
    """Metadata sent alongside a multipart file upload during a session."""
    field_name: str
    display_name: str
    category: DocumentCategory = DocumentCategory.OTHER
    save_for_reuse: bool = True


class UpdateDocumentRequest(BaseModel):
    """Rename or re-categorize a vault document."""
    display_name: Optional[str] = None
    category: Optional[DocumentCategory] = None
    subcategory: Optional[str] = None
    tags: Optional[List[str]] = None
