from datetime import datetime
from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator
from uuid import uuid4


# ===========================================================================
# Enhanced Form Search Models - Strict Multi-Source Classification
# ===========================================================================

class URLClassification(BaseModel):
    """Result of URL classification with evidence"""
    url: str
    source_category: Literal["official_portal", "youtube", "third_party_web", "internal_cache"]
    page_type: Literal["direct_form", "official_guidance", "document_checklist", "faq", 
                       "login_gateway", "dashboard_or_portal_home", "youtube_video", 
                       "article_or_blog", "news", "unknown"]
    official_domain: bool
    automatable: bool
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)
    normalized_title: str = ""
    relevance_reason: str = ""

class YouTubeVideoResult(BaseModel):
    """YouTube video with optional transcript analysis"""
    url: str
    video_id: str
    title: str
    channel: str = ""
    duration: Optional[str] = None
    transcript_available: bool = False
    transcript_source: Optional[str] = None
    transcript_text: Optional[str] = None
    transcript_summary: Optional[str] = None
    key_steps: List[str] = Field(default_factory=list)
    mentioned_documents: List[str] = Field(default_factory=list)
    mentioned_warnings: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)

class DirectFormResult(BaseModel):
    """Best direct form candidate"""
    url: str
    title: str
    display_title: str = ""  # Clean user-facing title
    display_reason: str = ""  # User-facing explanation
    confidence: float = Field(ge=0.0, le=1.0)
    automatable: bool
    evidence: List[str] = Field(default_factory=list)  # Internal only
    form_indicators: List[str] = Field(default_factory=list)

class GuidanceSource(BaseModel):
    """Official guidance or support page"""
    url: str
    title: str
    display_title: str = ""  # Clean user-facing title
    display_reason: str = ""  # User-facing explanation
    page_type: Literal["official_guidance", "document_checklist", "faq"]
    official_domain: bool
    summary: str = ""
    confidence: float = Field(ge=0.0, le=1.0)

class ProcessInsights(BaseModel):
    """Unified guidance from all sources"""
    summary: str
    likely_eligibility: List[str] = Field(default_factory=list)
    likely_required_documents: List[str] = Field(default_factory=list)
    likely_steps: List[str] = Field(default_factory=list)
    likely_portal_flow: List[str] = Field(default_factory=list)
    likely_blockers: List[str] = Field(default_factory=list)
    tips_before_starting: List[str] = Field(default_factory=list)
    automation_readiness: str = "unknown"
    confidence_notes: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)

class EnhancedFormSearchResult(BaseModel):
    """Structured multi-source search result"""
    query: str
    direct_form: Optional[DirectFormResult] = None
    official_guidance: List[GuidanceSource] = Field(default_factory=list)
    document_checklists: List[GuidanceSource] = Field(default_factory=list)
    youtube_videos: List[YouTubeVideoResult] = Field(default_factory=list)
    insights: ProcessInsights
    debug: dict = Field(default_factory=dict)
    valid: bool = True
    error_message: Optional[str] = None


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
    accept: Optional[str] = None
    multiple: bool = False
    
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
    file_requirements: list = Field(default_factory=list) # List of dicts representing file requirements
    matched_documents: list = Field(default_factory=list) # List of dicts for matched user documents
    selected_documents: dict = Field(default_factory=dict)  # {field_name: [document_id or temp_file_path]}
    blockers: list[str] = Field(default_factory=list)
    ready_for_execution: bool = False
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

from enum import Enum
from typing import List, Literal, Optional, Union, Dict, Any

class PageType(str, Enum):
    direct_form = "direct_form"
    official_guidance = "official_guidance"
    document_checklist = "document_checklist"
    faq = "faq"
    login_gateway = "login_gateway"
    dashboard_or_portal_home = "dashboard_or_portal_home"
    youtube_video = "youtube_video"
    article_or_blog = "article_or_blog"
    news = "news"
    unknown = "unknown"

class SourceCategory(str, Enum):
    official_portal = "official_portal"
    youtube = "youtube"
    third_party_web = "third_party_web"
    internal_cache = "internal_cache"

class ClassifiedURL(BaseModel):
    url: str
    title: str = "Unknown"
    source_category: SourceCategory
    page_type: PageType
    official_domain: bool
    automatable: bool
    confidence: float
    evidence: List[str] = Field(default_factory=list)
    normalized_title: str = ""

class DirectFormCandidate(BaseModel):
    url: str
    title: str
    confidence: float
    automatable: bool
    evidence: List[str] = Field(default_factory=list)

class YouTubeVideoNode(BaseModel):
    url: str
    title: str
    channel: str = ""
    transcript_available: bool = False
    transcript_summary: str = ""
    key_steps: List[str] = Field(default_factory=list)
    mentioned_documents: List[str] = Field(default_factory=list)

class ProcessInsightsNode(BaseModel):
    summary: str = ""
    likely_required_documents: List[str] = Field(default_factory=list)
    likely_steps: List[str] = Field(default_factory=list)
    likely_blockers: List[str] = Field(default_factory=list)
    automation_readiness: str = ""
    notes: str = ""

class FormSearchResultV2(BaseModel):
    query: str
    direct_form: Optional[DirectFormCandidate] = None
    official_guidance: List[ClassifiedURL] = Field(default_factory=list)
    document_checklists: List[ClassifiedURL] = Field(default_factory=list)
    youtube_videos: List[YouTubeVideoNode] = Field(default_factory=list)
    insights: ProcessInsightsNode = Field(default_factory=ProcessInsightsNode)
    debug: Dict[str, Any] = Field(default_factory=dict)
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
