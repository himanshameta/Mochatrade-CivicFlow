import os
import re
import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Depends
from pydantic import BaseModel, validator
from api.auth import require_auth

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.form_models import UserSession
from models.session_models import SessionStore
from agents.collector import get_missing_fields, apply_user_input, is_data_complete, generate_collection_summary
from pipeline.orchestrator import run_pipeline, resume_pipeline
from utils.ocr import extract_text_from_document
from api.websocket import manager


async def upsert_basic_user_profile(user_id: str, fields: dict):
    """Persist common identity/contact fields to user profile for future autofill."""
    try:
        from db.mongo import get_db
        from utils.generic_mapper import canonicalize_key, build_reverse_alias_map
        
        db = await get_db()
        if db is None:
            return
        
        reverse_map = build_reverse_alias_map()
        canonical_fields = {}
        
        for key, value in fields.items():
            if not value or not str(value).strip():
                continue
            
            canon_key = canonicalize_key(key)
            mapped_key = reverse_map.get(canon_key, canon_key)
            canonical_fields[mapped_key] = value
        
        if not canonical_fields:
            return
        
        # Upsert to user_profiles - only update non-empty values
        update_ops = {}
        for key, value in canonical_fields.items():
            update_ops[f"basic_info.{key}"] = value
        
        await db.user_profiles.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    **update_ops,
                    "updated_at": datetime.utcnow()
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        print(f"[Routes] Persisted {len(canonical_fields)} canonical fields to DB: {list(canonical_fields.keys())}")
        
    except Exception as e:
        print(f"[Routes] Could not persist profile: {e}")


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

@router.post("/start")
async def start_compat(request: StartSessionRequest, background_tasks: BackgroundTasks, payload: dict = Depends(require_auth)):
    """Creates session and starts analysis in background."""
    try:
        # Extract user_id from JWT token
        user_id = payload.get("sub")  # JWT standard claim for user ID
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Create session with user_id
        session = UserSession(
            session_id=session_id,
            url=request.url,
            user_id=user_id,
            status="created"
        )
        
        # Save to store
        await session_store.save(session)
        
        print(f"[Start] Session created: {session_id} for user: {user_id}")
        
        # Trigger analysis in background
        async def run_initial_analysis():
            try:
                print(f"[Start] Launching pipeline for {session_id} with user {user_id}")
                await manager.broadcast_status_change(session_id, "analyzing", "Analyzing form...")
                # Pass user_id to pipeline so it fetches profile from DB
                await run_pipeline(session_id, request.url, user_id, {})
                print(f"[Start] Pipeline completed for {session_id}")
            except Exception as e:
                print(f"[Start] Pipeline error for {session_id}: {e}")
                import traceback
                traceback.print_exc()
                await session_store.update_status(session_id, "failed")
                await session_store.update_field(session_id, "error", str(e))
                try:
                    await manager.broadcast_error(session_id, str(e))
                except:
                    pass
        
        background_tasks.add_task(run_initial_analysis)
        
        # Return immediately with session_id
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "status": "analyzing",
                "url": request.url,
                "message": "Form automation pipeline started"
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

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


@router.post("/sessions/{session_id}/fill")
async def fill_field_frontend(session_id: str, payload: dict = None):
    """Accept missing field values from user, persist to DB, and merge into session."""
    try:
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # If no payload, return current status
        if not payload or not payload.get("user_provided"):
            return {
                "success": True,
                "data": {
                    "needs_user_input": session.status == "needs_user_input",
                    "missing_fields": session.missing_fields or [],
                    "pre_filled_values": session.pre_filled_values or {}
                }
            }
        
        user_provided = payload.get("user_provided", {})
        print(f"[Fill] User provided fields: {list(user_provided.keys())}")
        
        # STEP 1: Persist to user profile in DB for future use
        if session.user_id and user_provided:
            await upsert_basic_user_profile(session.user_id, user_provided)
            print(f"[Fill] Persisted {len(user_provided)} fields to user profile")
        
        # STEP 2: Merge into session pre_filled_values
        if not hasattr(session, 'pre_filled_values') or not session.pre_filled_values:
            session.pre_filled_values = {}
        session.pre_filled_values.update(user_provided)
        
        # STEP 3: Update data_requirements with new values
        if session.data_requirements:
            for item in session.data_requirements:
                # Handle both dict and object
                if isinstance(item, dict):
                    field_key = item.get('name') or item.get('label')
                    if field_key in user_provided:
                        item['value'] = user_provided[field_key]
                else:
                    field_key = getattr(item, 'name', None) or getattr(item, 'label', None)
                    if field_key and field_key in user_provided:
                        item.value = user_provided[field_key]
        
        # STEP 4: Remove satisfied fields from missing_fields
        if hasattr(session, 'missing_fields') and session.missing_fields:
            session.missing_fields = [
                field for field in session.missing_fields
                if field.get('key') not in user_provided
            ]
            print(f"[Fill] Remaining missing fields: {len(session.missing_fields)}")
        
        # STEP 5: Update status based on remaining missing fields
        if not session.missing_fields or len(session.missing_fields) == 0:
            session.status = "ready"
            print(f"[Fill] All fields filled, status -> ready")
        else:
            session.status = "needs_user_input"
            print(f"[Fill] Still missing {len(session.missing_fields)} fields")
        
        await session_store.save(session)
        
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "status": session.status,
                "needs_user_input": len(session.missing_fields or []) > 0,
                "missing_fields": session.missing_fields or [],
                "pre_filled_values": session.pre_filled_values or {}
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fill fields: {str(e)}")

@router.post("/sessions/{session_id}/fill-single", response_model=FillResponse)
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


@router.get("/sessions/{session_id}/confirm-data")
async def get_confirmation_data(session_id: str):
    """Get all pre-filled data for user review before autofill."""
    try:
        from utils.generic_mapper import (
            get_flat_user_profile, 
            match_profile_value_to_field,
            compute_stable_field_key,
            compute_missing_required_fields
        )
        
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Fetch latest from DB if user_id exists
        db_profile = {}
        if session.user_id:
            try:
                db_profile = await get_flat_user_profile(session.user_id)
                print(f"[ConfirmData] Loaded DB profile keys: {list(db_profile.keys())}")
            except Exception as e:
                print(f"[ConfirmData] Could not fetch DB profile: {e}")
        
        # Merge: DB profile + existing session values (session takes priority)
        merged_profile = {**db_profile, **(session.pre_filled_values or {})}
        
        # Build form fields with intelligent matching
        form_fields = []
        pre_filled_values = {}
        matched_count = 0
        
        if session.scraped_form:
            scraped_form = session.scraped_form
            scraped_form_dict = scraped_form.model_dump() if hasattr(scraped_form, "model_dump") else scraped_form
            fields = scraped_form_dict.get('fields', [])
            
            for field in fields:
                field_dict = field if isinstance(field, dict) else field.model_dump()
                
                # Get stable field key for frontend and executor
                stable_key = compute_stable_field_key(field_dict)
                
                # Try intelligent matching
                matched_profile_key, matched_value = match_profile_value_to_field(field_dict, merged_profile)
                
                # Determine source
                source = 'none'
                final_value = ''
                
                if matched_value:
                    final_value = str(matched_value)
                    matched_count += 1
                    
                    # Check if from session or DB
                    if stable_key in (session.pre_filled_values or {}):
                        source = 'session'
                    else:
                        source = 'db'
                
                form_fields.append({
                    'name': stable_key,
                    'label': field_dict.get('label', stable_key),
                    'field_type': field_dict.get('field_type', 'text'),
                    'value': final_value,
                    'required': field_dict.get('required', False),
                    'options': field_dict.get('options', []),
                    'matched_profile_key': matched_profile_key,
                    'source': source
                })
                
                # Store in pre_filled_values with stable key
                if final_value:
                    pre_filled_values[stable_key] = final_value
        
        print(f"[ConfirmData] Matched {matched_count}/{len(form_fields)} fields from DB/session")
        
        # Save merged values back to session
        session.pre_filled_values = pre_filled_values
        
        # Compute missing required fields
        scraped_form_dict_for_missing = (
            session.scraped_form.model_dump()
            if hasattr(session.scraped_form, "model_dump")
            else session.scraped_form
        ) if session.scraped_form else {}
        
        missing_required = compute_missing_required_fields(
            scraped_form_dict_for_missing,
            pre_filled_values
        )
        
        print(f"[ConfirmData] Missing required fields: {len(missing_required)}")
        
        # Update session state
        session.missing_fields = missing_required
        session.status = "awaiting_confirmation"
        await session_store.save(session)
        
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "url": session.url,
                "form_fields": form_fields,
                "pre_filled_values": pre_filled_values,
                "missing_required_fields": missing_required,
                "can_proceed": True,
                "status": "awaiting_confirmation"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get confirmation data: {str(e)}")


@router.post("/sessions/{session_id}/confirm")
async def confirm_and_update_data(session_id: str, payload: dict):
    """User confirms/updates data before autofill execution."""
    try:
        from utils.generic_mapper import compute_missing_required_fields
        
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        confirmed_data = payload.get("confirmed_data", {})
        
        if not isinstance(confirmed_data, dict):
            raise HTTPException(status_code=400, detail="confirmed_data must be a dict")
        
        print(f"[Confirm] User confirmed {len(confirmed_data)} fields")
        print(f"[Confirm] Confirmed keys: {list(confirmed_data.keys())}")
        
        # Merge into session pre_filled_values
        if not hasattr(session, 'pre_filled_values') or not session.pre_filled_values:
            session.pre_filled_values = {}
        session.pre_filled_values.update(confirmed_data)
        
        # Persist to DB for future use
        if session.user_id and confirmed_data:
            await upsert_basic_user_profile(session.user_id, confirmed_data)
            print(f"[Confirm] Persisted {len(confirmed_data)} fields to DB")
        
        # Recompute missing required fields
        scraped_form_dict_for_missing = (
            session.scraped_form.model_dump()
            if hasattr(session.scraped_form, "model_dump")
            else session.scraped_form
        ) if session.scraped_form else {}
        
        missing_required = compute_missing_required_fields(
            scraped_form_dict_for_missing,
            session.pre_filled_values
        )
        
        session.missing_fields = missing_required
        
        # Update status based on missing fields
        if missing_required:
            session.status = "awaiting_confirmation"
            message = f"Some required fields are still missing ({len(missing_required)})"
        else:
            session.status = "confirmed"
            message = "Data confirmed. Ready for autofill."
        
        await session_store.save(session)
        
        print(f"[Confirm] Status: {session.status}, Missing: {len(missing_required)}")
        
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "status": session.status,
                "missing_required_fields": missing_required,
                "message": message
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to confirm data: {str(e)}")


@router.post("/sessions/{session_id}/execute", response_model=ExecuteResponse)
async def execute_automation(session_id: str, background_tasks: BackgroundTasks):
    """
    Execute the automation script (scriptgen + executor).
    Only proceeds if data is confirmed.
    """
    try:
        # Load session
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if not session.scraped_form:
            raise HTTPException(status_code=400, detail="No form found. Run analysis first.")
        
        # Check if data is confirmed
        if session.status not in ["confirmed", "ready"]:
            raise HTTPException(status_code=400, detail="Please confirm data before executing autofill.")
        
        print(f"[Execute] Using {len(session.pre_filled_values or {})} confirmed values for autofill")
        print(f"[Execute] Confirmed value keys: {list((session.pre_filled_values or {}).keys())}")
        
        # Execute in background - proceed with confirmed data
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


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Compatibility endpoint - same as /sessions/{session_id}/status"""
    return await get_session_status(session_id)

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
        
        # Add summary if scraped_form exists
        if session.scraped_form:
            scraped_form_dict = (
                session.scraped_form.model_dump()
                if hasattr(session.scraped_form, "model_dump")
                else session.scraped_form
            )
            total_fields = len(scraped_form_dict.get('fields', []))
            has_captcha = scraped_form_dict.get('has_captcha', False)
            
            session_dict["scraped_form_summary"] = {
                "total_fields": total_fields,
                "fillable_fields": total_fields,
                "has_captcha": has_captcha
            }
        
        # Add analyst summary
        if session.data_requirements or session.pre_filled_values:
            mapped_count = len(session.pre_filled_values or {})
            missing_count = len(session.missing_fields or [])
            session_dict["analyst_summary"] = {
                "mapped_fields": mapped_count,
                "missing_required": missing_count
            }
        
        # Normalize status for frontend
        status = session.status
        if status == "collecting":
            status = "needs_user_input"
        elif status == "script_ready":
            status = "ready_to_fill"
        elif status == "paused_captcha":
            status = "captcha_required"
        
        session_dict["status"] = status
        session_dict["needs_user_input"] = len(session.missing_fields or []) > 0
        
        # Still expose missing_fields for frontend
        if not session_dict.get("missing_fields"):
            session_dict["missing_fields"] = []
        
        # Wrap in success envelope
        return {
            "success": True,
            "data": session_dict
        }
        
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


@router.post("/forms/search", summary="Find any form URL by description")
async def search_form(request: FormSearchRequest):
    """
    Given a plain-English description, returns matching form URLs.

    Works with ANY website - government, private, registration forms,
    job applications, surveys, etc. Not limited to government sites.
    
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

