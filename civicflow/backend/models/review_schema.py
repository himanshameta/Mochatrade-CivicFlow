"""
Normalized Form Schema for Review UI
=====================================
Canonical schema that frontend uses to render the review form.
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class FieldOption(BaseModel):
    """Option for select/radio/checkbox fields"""
    label: str
    value: str


class ReviewFormField(BaseModel):
    """Normalized field schema for frontend rendering"""
    key: str  # Stable field key used in pre_filled_values
    name: Optional[str] = ""  # Raw field name attribute
    label: str  # Best extracted label
    field_type: Literal[
        "text", "email", "tel", "date", "number", "textarea",
        "select", "radio", "checkbox", "checkbox_group", "file"
    ]
    required: bool = False
    placeholder: Optional[str] = ""
    options: List[FieldOption] = Field(default_factory=list)
    value: str = ""  # Mapped value from profile
    matched_profile_key: Optional[str] = None  # Which profile key was matched
    source: Literal["db", "session", "llm", "none"] = "none"
    order: int = 0  # Original field order from scraper
    section: Optional[str] = ""  # Section/fieldset name if available


class ReviewFormSchema(BaseModel):
    """Complete form schema for review"""
    session_id: str
    url: str
    page_title: str
    fields: List[ReviewFormField]
    missing_required_fields: List[str] = Field(default_factory=list)
    status: str = "awaiting_confirmation"
    can_proceed: bool = True


class ConfirmDataResponse(BaseModel):
    """Response for GET /confirm-data"""
    success: bool
    data: ReviewFormSchema


class ConfirmSubmitRequest(BaseModel):
    """Request for POST /confirm"""
    confirmed_data: dict  # {stable_key: value}


class ConfirmSubmitResponse(BaseModel):
    """Response for POST /confirm"""
    success: bool
    data: dict  # {session_id, status, missing_required_fields}
