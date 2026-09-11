"""
Normalized Form Schema for Review UI
=====================================
Stable confirmation data contract.

This defines the canonical response shape for the confirm-data endpoint.
Frontend MUST use this shape for rendering the confirmation UI.
"""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Field-level models
# ---------------------------------------------------------------------------

class FieldOption(BaseModel):
    """Option for select/radio/checkbox fields"""
    label: str
    value: str


class FormFieldItem(BaseModel):
    """A single form field with mapped value for the review UI."""
    key: str                    # Stable field key used in pre_filled_values
    name: Optional[str] = ""   # Raw field name attribute
    label: str                  # Best extracted label (semantically inferred)
    field_type: Literal[
        "text", "email", "tel", "date", "number", "textarea",
        "select", "radio", "checkbox", "checkbox_group", "file"
    ]
    required: bool = False
    placeholder: Optional[str] = ""
    options: List[FieldOption] = Field(default_factory=list)
    value: str = ""                             # Mapped value from profile
    matched_profile_key: Optional[str] = None   # Which profile key was matched
    source: Literal["db", "session", "llm", "none"] = "none"
    order: int = 0                              # Original field order from scraper
    section: Optional[str] = ""                 # Section/fieldset name if available


class MissingFieldItem(BaseModel):
    """A required field that has no value."""
    name: str           # Stable field key
    label: str          # Human-readable label
    field_type: str     # Input type hint for the UI


class MatchedSavedDocument(BaseModel):
    """A vault document that matches a file field requirement."""
    document_id: str
    display_name: str
    category: str
    mime_type: str
    score: float = 0.0


class FileRequirementItem(BaseModel):
    """A file upload requirement with matching status and suggestions."""
    key: str                        # field_name / name attr
    label: str                      # "Upload Resume"
    selector: str = ""              # CSS selector for execution
    required: bool = False
    accept: str = ""                # ".pdf,.doc,.docx"
    multiple: bool = False
    matched_saved_documents: List[MatchedSavedDocument] = Field(default_factory=list)
    selected_document_id: Optional[str] = None
    status: Literal["missing", "selected", "optional_unset"] = "missing"


class ProposedProfileUpdateItem(BaseModel):
    """A value extracted from a document that could update the user's profile."""
    field_name: str
    current_value: str = ""
    proposed_value: str
    source_document: str = ""
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Response payload
# ---------------------------------------------------------------------------

class ConfirmDataPayload(BaseModel):
    """
    Stable confirmation data payload.

    Status / ready_for_execution rules:
    - status="error"                → ready_for_execution=False (backend failed)
    - status="awaiting_confirmation" → ready_for_execution=False (user must review)
    - status="blocked"              → ready_for_execution=False (missing required data)
    - status="ready_for_execution"  → ready_for_execution=True  (user confirmed all)

    NEVER return:
    - status="awaiting_confirmation" with ready_for_execution=True
    - missing_required_fields non-empty with ready_for_execution=True
    """
    session_id: str
    url: str
    status: Literal[
        "awaiting_confirmation",
        "ready_for_execution",
        "blocked",
        "error"
    ] = "awaiting_confirmation"
    ready_for_execution: bool = False
    blockers: List[str] = Field(default_factory=list)
    canonical_fields: List[FormFieldItem] = Field(default_factory=list)
    editable_fields: List[FormFieldItem] = Field(default_factory=list)
    missing_required_fields: List[MissingFieldItem] = Field(default_factory=list)
    file_requirements: List[FileRequirementItem] = Field(default_factory=list)
    pre_filled_values: Dict[str, Any] = Field(default_factory=dict)
    proposed_profile_updates: List[ProposedProfileUpdateItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    page_title: str = ""

    # --- DEPRECATED: kept for one release cycle for backward compat ---
    # Frontend should migrate to canonical_fields + editable_fields
    form_fields: Optional[List[Dict]] = Field(default=None, deprecated=True)
    # Frontend should migrate to ready_for_execution
    can_proceed: Optional[bool] = Field(default=None, deprecated=True)


class ConfirmDataResponse(BaseModel):
    """Response for GET /confirm-data"""
    success: bool
    data: ConfirmDataPayload


# ---------------------------------------------------------------------------
# Legacy ReviewFormField — kept for confirm_routes.py backward compat
# ---------------------------------------------------------------------------

class ReviewFormField(BaseModel):
    """Normalized field schema for frontend rendering (LEGACY — use FormFieldItem)"""
    key: str
    name: Optional[str] = ""
    label: str
    field_type: Literal[
        "text", "email", "tel", "date", "number", "textarea",
        "select", "radio", "checkbox", "checkbox_group", "file"
    ]
    required: bool = False
    placeholder: Optional[str] = ""
    options: List[FieldOption] = Field(default_factory=list)
    value: str = ""
    matched_profile_key: Optional[str] = None
    source: Literal["db", "session", "llm", "none"] = "none"
    order: int = 0
    section: Optional[str] = ""


class ReviewFormSchema(BaseModel):
    """Complete form schema for review (LEGACY — use ConfirmDataPayload)"""
    session_id: str
    url: str
    page_title: str
    fields: List[ReviewFormField]
    missing_required_fields: List[str] = Field(default_factory=list)
    status: str = "awaiting_confirmation"
    can_proceed: bool = True  # DEPRECATED


# ---------------------------------------------------------------------------
# Confirmation submit models
# ---------------------------------------------------------------------------

class ConfirmSubmitRequest(BaseModel):
    """Request for POST /confirm"""
    confirmed_data: dict  # {stable_key: value}


class ConfirmSubmitResponse(BaseModel):
    """Response for POST /confirm"""
    success: bool
    data: dict  # {session_id, status, missing_required_fields, ready_for_execution}
