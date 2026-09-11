"""
CivicFlow — Chat Models
=========================
Schemas for the LLM Counsellor agent API.
"""
from typing import Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str
    stage: str


class CounsellorResponse(BaseModel):
    response: str
    triggered_action: Optional[str] = None
    stage: str
