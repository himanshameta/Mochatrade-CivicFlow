from datetime import datetime
from typing import Literal, Optional
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
