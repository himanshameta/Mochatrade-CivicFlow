from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class FormField(BaseModel):
    field_id: str = Field(default_factory=lambda: str(uuid4()))
    label: str
    field_type: Literal["text", "email", "tel", "date", "number", "select", 
                        "radio", "checkbox", "file", "textarea", "password"]
    name: str
    id_attr: str = ""
    placeholder: str = ""
    required: bool = False
    options: list[str] = Field(default_factory=list)
    selector: str
    section: str = ""


class ScrapedForm(BaseModel):
    url: str
    page_title: str
    form_html: str
    fields: list[FormField]
    submit_button_selector: str
    has_captcha: bool
    has_file_upload: bool
    captcha_type: Optional[Literal["recaptcha", "hcaptcha", "image", "math", "unknown"]] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    # --- form_templates collection extensions (Phase 2) ---
    llm_found: bool = False                                      # True if URL was found by LLM search
    source: Literal["llm_search", "user_provided"] = "user_provided"  # how the URL was obtained
    last_verified_at: Optional[datetime] = None                  # last time the form was re-scraped
    verification_count: int = 0                                  # how many times verified


class UserDataItem(BaseModel):
    field_id: str
    label: str
    input_type: Literal["text", "document", "date", "selection", "boolean"]
    description: str
    example: str
    value: Optional[str] = None
    document_path: Optional[str] = None
    extracted_from_doc: bool = False


class UserSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    url: str
    html: Optional[str] = None
    page_title: Optional[str] = None
    scraped_form: Optional[ScrapedForm] = None
    user_documents_text: dict[str, str] = Field(default_factory=dict)
    data_requirements: list[UserDataItem] = Field(default_factory=list)
    user_documents: list[str] = Field(default_factory=list)
    generated_script: Optional[str] = None
    script_path: Optional[str] = None
    status: Literal["created", "scraped", "collecting", "ready", "running",
                    "paused_captcha", "paused_otp", "paused_payment",
                    "completed", "failed"] = "created"
    pause_reason: Optional[str] = None
    pause_screenshot: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # --- form_sessions collection extensions (Phase 2) ---
    user_id: Optional[str] = None             # FK → users.user_id
    profile_id: Optional[str] = None          # FK → user_profiles.profile_id
    conversation_history: List[dict] = Field(default_factory=list)  # [{role, message, timestamp}]
    telegram_notified: bool = False            # True after Telegram notification sent


# Safe deserialization helpers for LangGraph state
def safe_parse_scraped_form(data) -> Optional[ScrapedForm]:
    """
    Safely converts whatever LangGraph gives us back to a ScrapedForm.
    Handles: ScrapedForm object, dict, None, invalid data.
    """
    if data is None:
        return None
    if isinstance(data, ScrapedForm):
        return data
    if isinstance(data, dict):
        try:
            return ScrapedForm(**data)
        except Exception as e:
            print(f"[safe_parse_scraped_form] Failed to parse dict: {e}")
            return None
    return None


# ===========================================================================
# Form Search Models
# ===========================================================================

class FormSearchOption(BaseModel):
    url: str
    portal_name: str
    confidence: float
    notes: str = ""

class FormSearchResult(BaseModel):
    options: List[FormSearchOption]
    is_user_provided: bool = False
    valid: bool = True
    error_message: Optional[str] = None

class SearchFormRequest(BaseModel):
    service_name: str
    state: Optional[str] = None
    user_url: Optional[str] = None

class VerifyUrlRequest(BaseModel):
    url: str


def safe_parse_user_data_items(data) -> list[UserDataItem]:
    """Safely converts list of dicts back to list[UserDataItem]"""
    if not data:
        return []
    result = []
    for item in data:
        if isinstance(item, UserDataItem):
            result.append(item)
        elif isinstance(item, dict):
            try:
                result.append(UserDataItem(**item))
            except Exception:
                pass
    return result
