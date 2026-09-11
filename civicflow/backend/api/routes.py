import os
import re
import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel, validator

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.form_models import UserSession
from models.session_models import SessionStore
from agents.collector import get_missing_fields, apply_user_input, is_data_complete, generate_collection_summary
from pipeline.orchestrator import run_pipeline, resume_pipeline
from utils.ocr import extract_text_from_document
from api.websocket import manager


# Initialize router and session store
router = APIRouter()
session_store = SessionStore()


# Request/Response Models
class StartSessionRequest(BaseModel):
    url: str
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class StartSessionResponse(BaseModel):
    session_id: str
    status: str


class FillFieldRequest(BaseModel):
    field_id: str
    value: str


class FillAllFieldsRequest(BaseModel):
    fields: List[dict]  # [{field_id: str, value: str}]


class ResumeRequest(BaseModel):
    type: str  # "captcha" | "otp"
    value: Optional[str] = None


class FillResponse(BaseModel):
    filled: int
    remaining: int
    is_complete: bool


class ExecuteResponse(BaseModel):
    status: str
    message: str


# Endpoints

@router.post("/sessions/start", response_model=StartSessionResponse)
async def start_session(request: StartSessionRequest):
    """
    Create a new session for form automation.
    """
    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Create session
        session = UserSession(
            session_id=session_id,
            url=request.url,
            status="created"
        )
        
        # Save to Redis
        await session_store.save(session)
        
        # Broadcast status
        await manager.broadcast_status_change(session_id, "created", "Session created")
        
        return StartSessionResponse(
            session_id=session_id,
            status="created"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.post("/sessions/{session_id}/documents")
async def upload_documents(
    session_id: str,
    files: List[UploadFile] = File(...)
):
    """
    Upload documents and run OCR to extract text.
    """
    try:
        # Load session
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Create upload directory
        upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
        docs_dir = Path(upload_dir) / "docs" / session_id
        docs_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each file
        extracted_texts = {}
        files_processed = 0
        
        for file in files:
            # Validate file size
            max_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
            max_size_bytes = max_size_mb * 1024 * 1024
            
            # Save file
            file_path = docs_dir / file.filename
            content = await file.read()
            
            if len(content) > max_size_bytes:
                print(f"[API] Skipping {file.filename} - exceeds {max_size_mb}MB limit")
                continue
            
            with open(file_path, "wb") as f:
                f.write(content)
            
            # Run OCR
            print(f"[API] Extracting text from {file.filename}")
            text = await extract_text_from_document(str(file_path))
            
            if text:
                extracted_texts[file.filename] = text
                session.user_documents.append(str(file_path))
                files_processed += 1
                
                print(f"[API] Extracted {len(text)} characters from {file.filename}")
        
        # Save updated session
        await session_store.save(session)
        
        # Preview of extracted data (first 200 chars of each file)
        preview = {
            filename: text[:200] + "..." if len(text) > 200 else text
            for filename, text in extracted_texts.items()
        }
        
        return {
            "files_processed": files_processed,
            "extracted_fields_preview": preview
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process documents: {str(e)}")


@router.post("/sessions/{session_id}/run")
async def run_analysis(session_id: str, background_tasks: BackgroundTasks):
    """
    Run initial pipeline (scout, scraper, analyst) and return data requirements.
    """
    try:
        # Load session
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Prepare document texts for analyst
        user_docs_text = {}
        for doc_path in session.user_documents:
            filename = Path(doc_path).name
            text = await extract_text_from_document(doc_path)
            if text:
                user_docs_text[filename] = text
        
        # Run pipeline in background (only up to analyst stage)
        async def run_analysis_pipeline():
            await manager.broadcast_status_change(session_id, "running", "Starting analysis...")
            
            try:
                # Run full pipeline (it will pause at data collection)
                await run_pipeline(session_id, session.url, user_docs_text)
                
                # Reload session to get updated data
                updated_session = await session_store.load(session_id)
                
                if updated_session and updated_session.data_requirements:
                    # Broadcast extracted fields
                    for item in updated_session.data_requirements:
                        if item.value and item.extracted_from_doc:
                            await manager.broadcast_field_extracted(
                                session_id,
                                item.field_id,
                                item.value,
                                item.label
                            )
            
            except Exception as e:
                print(f"[API] Pipeline error: {e}")
                await session_store.update_status(session_id, "failed")
                await session_store.update_field(session_id, "error", str(e))
                await manager.broadcast_error(session_id, str(e))
        
        # Start background task
        background_tasks.add_task(run_analysis_pipeline)
        
        # Return immediately
        return {
            "session_id": session_id,
            "message": "Analysis started",
            "status": "running"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run analysis: {str(e)}")


@router.post("/sessions/{session_id}/fill", response_model=FillResponse)
async def fill_field(session_id: str, request: FillFieldRequest):
    """
    Fill a single field with user-provided value.
    """
    try:
        # Load session
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if not session.data_requirements:
            raise HTTPException(status_code=400, detail="No data requirements found. Run analysis first.")
        
        # Update the field
        updated_requirements = apply_user_input(
            session.data_requirements,
            request.field_id,
            request.value
        )
        
        session.data_requirements = updated_requirements
        await session_store.save(session)
        
        # Generate summary
        summary = generate_collection_summary(updated_requirements)
        
        # Broadcast field update
        for item in updated_requirements:
            if item.field_id == request.field_id:
                await manager.broadcast_field_extracted(
                    session_id,
                    item.field_id,
                    item.value,
                    item.label
                )
                break
        
        return FillResponse(
            filled=summary["filled"],
            remaining=summary["missing"],
            is_complete=is_data_complete(updated_requirements)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fill field: {str(e)}")


@router.post("/sessions/{session_id}/fill-all", response_model=FillResponse)
async def fill_all_fields(session_id: str, request: FillAllFieldsRequest):
    """
    Bulk fill multiple fields at once.
    """
    try:
        # Load session
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if not session.data_requirements:
            raise HTTPException(status_code=400, detail="No data requirements found. Run analysis first.")
        
        # Update all fields
        updated_requirements = session.data_requirements
        
        for field_data in request.fields:
            field_id = field_data.get("field_id")
            value = field_data.get("value")
            
            if field_id and value:
                updated_requirements = apply_user_input(
                    updated_requirements,
                    field_id,
                    value
                )
        
        session.data_requirements = updated_requirements
        await session_store.save(session)
        
        # Generate summary
        summary = generate_collection_summary(updated_requirements)
        
        # Broadcast updates
        for field_data in request.fields:
            field_id = field_data.get("field_id")
            if field_id:
                for item in updated_requirements:
                    if item.field_id == field_id and item.value:
                        await manager.broadcast_field_extracted(
                            session_id,
                            item.field_id,
                            item.value,
                            item.label
                        )
                        break
        
        return FillResponse(
            filled=summary["filled"],
            remaining=summary["missing"],
            is_complete=is_data_complete(updated_requirements)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fill fields: {str(e)}")


@router.post("/sessions/{session_id}/execute", response_model=ExecuteResponse)
async def execute_automation(session_id: str, background_tasks: BackgroundTasks):
    """
    Execute the automation script (scriptgen + executor).
    """
    try:
        # Load session
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if not session.data_requirements:
            raise HTTPException(status_code=400, detail="No data requirements found. Run analysis first.")
        
        # Check if all required fields are filled
        if not is_data_complete(session.data_requirements):
            missing = get_missing_fields(session.data_requirements)
            missing_details = [
                {"field_id": item.field_id, "label": item.label, "description": item.description}
                for item in missing
            ]
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Not all required fields are filled",
                    "missing_fields": missing_details
                }
            )
        
        # Execute in background
        async def execute_pipeline():
            await manager.broadcast_status_change(session_id, "running", "Generating script...")
            
            try:
                # Resume pipeline from user_data completion
                await resume_pipeline(session_id, "user_data")
                
                # Check final status
                final_session = await session_store.load(session_id)
                
                if final_session:
                    if final_session.status == "paused_captcha":
                        await manager.broadcast_captcha_detected(
                            session_id,
                            final_session.pause_screenshot or ""
                        )
                    elif final_session.status == "completed":
                        await manager.broadcast_status_change(
                            session_id,
                            "completed",
                            "Form submitted successfully!"
                        )
                    elif final_session.status == "failed":
                        await manager.broadcast_error(
                            session_id,
                            final_session.error or "Execution failed"
                        )
            
            except Exception as e:
                print(f"[API] Execution error: {e}")
                await session_store.update_status(session_id, "failed")
                await session_store.update_field(session_id, "error", str(e))
                await manager.broadcast_error(session_id, str(e))
        
        # Start background task
        background_tasks.add_task(execute_pipeline)
        
        return ExecuteResponse(
            status="running",
            message="Automation started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute automation: {str(e)}")


@router.post("/sessions/{session_id}/resume")
async def resume_execution(session_id: str, request: ResumeRequest):
    """
    Resume paused execution (after CAPTCHA or OTP).
    """
    try:
        # Load session
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Validate resume type
        if request.type not in ["captcha", "otp"]:
            raise HTTPException(status_code=400, detail="Invalid resume type. Must be 'captcha' or 'otp'")
        
        if request.type == "otp" and not request.value:
            raise HTTPException(status_code=400, detail="OTP value is required")
        
        # Resume pipeline
        await resume_pipeline(session_id, request.type, request.value)
        
        # Broadcast status
        await manager.broadcast_status_change(
            session_id,
            "running",
            f"Resumed after {request.type}"
        )
        
        return {
            "status": "running",
            "message": f"Execution resumed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume execution: {str(e)}")


@router.get("/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """
    Get current session status and data.
    """
    try:
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Convert to dict with proper serialization
        session_dict = session.model_dump()
        
        # Add summary if data requirements exist
        if session.data_requirements:
            summary = generate_collection_summary(session.data_requirements)
            session_dict["collection_summary"] = summary
        
        return session_dict
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session and cleanup resources.
    """
    try:
        await session_store.delete(session_id)
        
        return {
            "message": "Session deleted successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


# ---------------------------------------------------------------------------
# NEW: Session list
# ---------------------------------------------------------------------------

@router.get("/sessions", summary="List all sessions")
async def list_sessions(user_id: Optional[str] = None):
    """
    Return a list of sessions, optionally filtered by user_id.
    Works with MongoDB (full list) and in-memory (current process sessions).
    Returns empty list for raw Redis mode.
    """
    try:
        sessions = await session_store.list_all(user_id=user_id)
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "url": s.url,
                    "status": s.status,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                    "field_count": len(s.data_requirements) if s.data_requirements else 0,
                }
                for s in sessions
            ],
            "total": len(sessions),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


# ---------------------------------------------------------------------------
# NEW: Script retrieval
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/script", summary="Get the generated automation script")
async def get_session_script(session_id: str):
    """
    Return the Playwright script generated for this session.
    The script is saved to uploads/scripts/{session_id}.py during scriptgen.
    """
    session = await session_store.load(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    script_path = Path(upload_dir) / "scripts" / f"{session_id}.py"

    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not yet generated for this session")

    try:
        content = script_path.read_text(encoding="utf-8")
        return {
            "session_id": session_id,
            "script": content,
            "script_path": str(script_path),
            "size_bytes": script_path.stat().st_size,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read script: {str(e)}")


# ---------------------------------------------------------------------------
# NEW: Form search (LLM-powered government portal discovery)
# ---------------------------------------------------------------------------

class FormSearchRequest(BaseModel):
    description: str          # e.g. "I want to apply for a passport"
    custom_url: Optional[str] = None  # user-provided URL bypass


@router.post("/forms/search", summary="Find a government portal by description")
async def search_form(request: FormSearchRequest):
    """
    Given a plain-English description of what the user wants to do,
    returns the best matching Indian government portal URL.

    Powered by Gemini 2.0 Flash with a pre-seeded list of 24 known portals.
    Falls back to keyword matching if AI is unavailable.
    """
    if not request.description.strip() and not request.custom_url:
        raise HTTPException(status_code=400, detail="Provide a description or a custom URL")

    try:
        from agents.form_finder import find_government_portal
        result = await find_government_portal(
            description=request.description.strip(),
            custom_url=request.custom_url,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Form search failed: {str(e)}")

