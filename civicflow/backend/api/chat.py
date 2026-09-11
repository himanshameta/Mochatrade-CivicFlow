"""
CivicFlow — Chat API
======================
REST endpoints for the LLM Counsellor agent.
WebSocket streaming removed - use REST endpoint only.
"""
import os
import sys
import json
import asyncio
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.auth import require_auth, ok
from models.chat_models import ChatRequest, CounsellorResponse
from agents.counsellor import CounsellorAgent
from db.mongo import get_db

router = APIRouter(prefix="/chat", tags=["Chat"])

_counsellor: Optional[CounsellorAgent] = None

def get_counsellor() -> CounsellorAgent:
    global _counsellor
    if _counsellor is None:
        _counsellor = CounsellorAgent()
    return _counsellor


@router.post("", summary="Send a message to the AI counsellor")
async def send_chat_message(request: ChatRequest, payload: dict = Depends(require_auth)):
    """
    Standard REST endpoint for conversational AI.
    Processes the user message and returns the full response + any triggered actions.
    """
    user_id = payload["sub"]
    counsellor = get_counsellor()
    from config import settings
    
    print(f"[Chat API] User {user_id} sent message: {request.message[:50]}...")
    
    # Check if OpenRouter API key is configured
    if not settings.openrouter_api_key:
        print("[Chat API] OpenRouter API key not configured")
        return ok("Chat unavailable", data={
            "response": "The AI counsellor is currently unavailable. Please configure OpenRouter API key.",
            "triggered_action": None,
            "stage": request.stage,
            "fallback_mode": True
        })
    
    try:
        response = await counsellor.chat(
            user_id=user_id,
            session_id=request.session_id,
            message=request.message,
            stage=request.stage
        )
        return ok("Message processed", data=response.model_dump())
    except Exception as e:
        import traceback
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"[Chat API] Error: {error_type}: {error_msg}")
        traceback.print_exc()
        
        # Check for OpenRouter quota/rate limit errors
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
            print("[Chat API] OpenRouter quota exceeded, using fallback")
            return ok("Quota exceeded", data={
                "response": fallback_chat_response(request.message, request.stage),
                "triggered_action": None,
                "stage": request.stage,
                "fallback_mode": True,
                "error_reason": "openrouter_quota_exceeded"
            })
        
        # Generic error fallback
        return ok("Error occurred", data={
            "response": "I'm having trouble processing that right now. Could you try rephrasing your question?",
            "triggered_action": None,
            "stage": request.stage,
            "fallback_mode": True,
            "error_reason": error_type
        })


def fallback_chat_response(message: str, stage: str) -> str:
    """Deterministic fallback when Gemini is unavailable."""
    message_lower = message.lower()
    
    if stage == "welcome":
        return "Welcome to CivicFlow! I'm here to help you with government forms. What would you like to do today?"
    elif stage == "profile_collection":
        if any(word in message_lower for word in ["name", "address", "personal"]):
            return "Please provide your details and I'll help you fill out the form."
        return "Let me know what information you'd like to update in your profile."
    elif stage == "form_filling":
        return "I'm currently unable to assist with automated form filling. Please try again later."
    elif stage == "document_upload":
        return "You can upload your documents using the upload button. I'll help you review them once processing is complete."
    else:
        return "I'm currently experiencing high demand. Please try again in a few moments."


@router.get("/history/{session_id}", summary="Get chat history for a session")
async def get_chat_history(session_id: str, payload: dict = Depends(require_auth)):
    """
    Returns the last 50 messages for the given session.
    """
    user_id = payload["sub"]
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    session = await db.form_sessions.find_one({"session_id": session_id})
    if not session:
        return ok("No history", data={"history": []})

    history = session.get("conversation_history", [])
    # Return last 50 messages
    return ok("Success", data={"history": history[-50:]})
