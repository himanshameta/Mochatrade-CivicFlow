from datetime import datetime
from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator
from uuid import uuid4


class FieldOption(BaseModel):
    """Structured option for select/radio fields"""
    value: str
    label: str


class FormField(BaseModel):
    field_id: str = Field(default_factory=lambda: str(uuid4()))
    label: str
    field_type: str = "text"  # Support any HTML input type, normalized in scraper
    name: str
    id_attr: str = ""
    placeholder: str = ""
    required: bool = False
    options: Union[List[str], List[FieldOption], List[dict]] = Field(default_factory=list)
    selector: str
    selector_priority: list[str] = Field(default_factory=list)  # Multiple selector strategies
    section: str = ""
    
    @field_validator('options', mode='before')
    @classmethod
    def normalize_options(cls, v):
        """Normalize options to support both string and dict formats"""
        if not v:
            return []
        
        normalized = []
        for opt in v:
            if isinstance(opt, str):
                # Backward compatibility: string options
                normalized.append({"value": opt, "label": opt})
            elif isinstance(opt, dict):
                # New format: dict with value and label
                if 'value' in opt and 'label' in opt:
                    normalized.append(opt)
                elif 'value' in opt:
                    normalized.append({"value": opt['value'], "label": opt['value']})
                else:
                    # Fallback for malformed dicts
                    normalized.append({"value": str(opt), "label": str(opt)})
            else:
                # Fallback for unexpected types
                normalized.append({"value": str(opt), "label": str(opt)})
        
        return normalized


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
    scrape_warning: Optional[str] = None  # Warning messages, e.g. "No fillable fields found"
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
    user_profile: dict = Field(default_factory=dict)  # Flattened profile from DB
    pre_filled_values: dict = Field(default_factory=dict)  # {field_name: value}
    missing_fields: list = Field(default_factory=list)  # [field_label] for required missing fields
    generated_script: Optional[str] = None
    script_path: Optional[str] = None
    status: Literal["created", "scraped", "collecting", "needs_user_input", "awaiting_confirmation",
                    "confirmed", "ready", "running", "paused_captcha", "paused_otp", "paused_payment",
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
