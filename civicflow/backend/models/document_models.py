"""
CivicFlow — Document Models
===========================
Pydantic schemas for the DocVault pipeline and documents API.
"""
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class OCRBlock(BaseModel):
    """A single text block extracted by PaddleOCR."""
    text: str
    confidence: float
    bbox: List[List[float]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    
    # Optional metadata for debugging/sorting
    center_y: float = 0.0


class Conflict(BaseModel):
    """Represents a mismatch between newly extracted document data and existing user profile data."""
    field: str
    existing_value: str
    new_value: str
    similarity: float  # 0.0 to 1.0 (Levenshtein ratio)
    message: str = ""


class DocumentResult(BaseModel):
    """The final result returned by DocVaultAgent.process_document()."""
    doc_id: str
    doc_type: str
    original_filename: str
    mime_type: str
    extracted_fields: Dict[str, Any]
    conflicts: List[Conflict] = Field(default_factory=list)
    raw_ocr_text: str = ""
    status: str = "success"  # success, failed
    error_message: Optional[str] = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class ConfirmDocumentRequest(BaseModel):
    """Payload sent by the frontend when user confirms the extracted fields are correct."""
    corrected_fields: Optional[Dict[str, Any]] = None  # User can override fields before saving
