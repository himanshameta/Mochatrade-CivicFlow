"""
Confirmation API Routes
========================
Clean API for form review and confirmation.
"""
from fastapi import APIRouter, HTTPException
from models.review_schema import (
    ReviewFormSchema, ReviewFormField,
    ConfirmDataResponse, ConfirmSubmitRequest, ConfirmSubmitResponse
)
from models.session_models import SessionStore
from utils.enhanced_mapper import map_profile_to_form_schema, compute_stable_field_key
from utils.generic_mapper import get_flat_user_profile

router = APIRouter()
session_store = SessionStore()


async def upsert_basic_user_profile(user_id: str, fields: dict):
    """Persist confirmed values to user profile."""
    try:
        from db.mongo import get_db
        from utils.enhanced_mapper import canonicalize_key, build_reverse_alias_map
        from datetime import datetime
        
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
        print(f"[Confirm] Persisted {len(canonical_fields)} fields to DB for user {user_id}")
        
    except Exception as e:
        print(f"[Confirm] Could not persist profile: {e}")


@router.get("/sessions/{session_id}/confirm-data", response_model=ConfirmDataResponse)
async def get_confirmation_data(session_id: str):
    """
    Get normalized form schema for review.
    Returns ConfirmDataPayload with file_requirements populated from vault.
    """
    try:
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if not session.scraped_form:
            raise HTTPException(
                status_code=400,
                detail="Form has not been scraped yet. Please wait for analysis to complete."
            )
        
        # Get user profile from DB
        user_profile = {}
        if session.user_id:
            try:
                user_profile = await get_flat_user_profile(session.user_id)
            except Exception as e:
                print(f"[ConfirmData] Could not load profile: {e}")
        
        # Merge with session values
        if session.pre_filled_values:
            user_profile.update(session.pre_filled_values)
        
        scraped_form_dict = (
            session.scraped_form.model_dump()
            if hasattr(session.scraped_form, "model_dump")
            else session.scraped_form
        )
        
        # Map profile to form schema
        review_fields = await map_profile_to_form_schema(scraped_form_dict, user_profile)
        
        # Build pre_filled_values and compute missing
        pre_filled_values = {}
        missing_required = []
        canonical_fields = []
        editable_fields = []
        
        for field in review_fields:
            if field.value:
                pre_filled_values[field.key] = field.value
                canonical_fields.append(field)
            elif field.required:
                missing_required.append({"name": field.key, "label": field.label, "field_type": field.field_type})
                editable_fields.append(field)
            else:
                editable_fields.append(field)
        
        # Build file requirements from session (populated by orchestrator)
        from models.review_schema import FileRequirementItem, MatchedSavedDocument
        file_requirements = []
        blockers = list(session.blockers) if session.blockers else []
        
        for fr in (session.file_requirements or []):
            matched_saved = []
            for ms in fr.get("matched_saved_documents", []):
                matched_saved.append(MatchedSavedDocument(
                    document_id=ms.get("document_id", ""),
                    display_name=ms.get("display_name", ""),
                    category=ms.get("category", "other"),
                    mime_type=ms.get("mime_type", ""),
                    score=ms.get("score", 0.0),
                ))
            
            # Check if user already selected a document for this field
            selected_id = None
            status = fr.get("status", "missing")
            if session.selected_documents:
                sel = session.selected_documents.get(fr.get("key"))
                if sel:
                    selected_id = sel[0] if isinstance(sel, list) else sel
                    status = "selected"
            
            file_requirements.append(FileRequirementItem(
                key=fr.get("key", ""),
                label=fr.get("label", ""),
                selector=fr.get("selector", ""),
                required=fr.get("required", False),
                accept=fr.get("accept", ""),
                multiple=fr.get("multiple", False),
                matched_saved_documents=matched_saved,
                selected_document_id=selected_id,
                status=status,
            ))
        
        # File blocker check
        for freq in file_requirements:
            if freq.required and freq.status != "selected":
                blocker_msg = f"Required file '{freq.label}' not yet selected."
                if blocker_msg not in blockers:
                    blockers.append(blocker_msg)
        
        ready = len(missing_required) == 0 and all(
            fr.status == "selected" or not fr.required for fr in file_requirements
        )
        
        # Save to session
        session.pre_filled_values = pre_filled_values
        session.missing_fields = [{"key": m["name"]} for m in missing_required]
        session.status = "awaiting_confirmation"
        await session_store.save(session)
        
        from models.review_schema import ConfirmDataPayload
        payload = ConfirmDataPayload(
            session_id=session_id,
            url=session.url,
            status="awaiting_confirmation" if not ready else "ready_for_execution",
            ready_for_execution=ready,
            blockers=blockers,
            canonical_fields=[f.model_dump() for f in canonical_fields],
            editable_fields=[f.model_dump() for f in editable_fields],
            missing_required_fields=missing_required,
            file_requirements=file_requirements,
            pre_filled_values=pre_filled_values,
            page_title=scraped_form_dict.get('page_title', ''),
        )
        
        return ConfirmDataResponse(success=True, data=payload)
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate confirmation data: {str(e)}")


@router.post("/sessions/{session_id}/confirm", response_model=ConfirmSubmitResponse)
async def confirm_data(session_id: str, request: ConfirmSubmitRequest):
    """
    User confirms/edits form data.
    
    Merges confirmed values into session and persists to DB.
    """
    try:
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        confirmed_data = request.confirmed_data
        print(f"[Confirm] User confirmed {len(confirmed_data)} fields")
        print(f"[Confirm] Confirmed field keys: {list(confirmed_data.keys())}")
        
        # Merge into session
        if not session.pre_filled_values:
            session.pre_filled_values = {}
        session.pre_filled_values.update(confirmed_data)
        
        # Update review_form_schema if it exists
        if hasattr(session, 'review_form_schema') and session.review_form_schema:
            for field_dict in session.review_form_schema:
                if field_dict['key'] in confirmed_data:
                    field_dict['value'] = confirmed_data[field_dict['key']]
        
        # Persist to DB
        if session.user_id:
            await upsert_basic_user_profile(session.user_id, confirmed_data)
        
        # Recompute missing required fields
        missing_required = []
        if session.scraped_form:
            scraped_form_dict = (
                session.scraped_form.model_dump()
                if hasattr(session.scraped_form, "model_dump")
                else session.scraped_form
            )
            
            for field in scraped_form_dict.get('fields', []):
                if field.get('required', False):
                    stable_key = compute_stable_field_key(field)
                    if not session.pre_filled_values.get(stable_key):
                        missing_required.append(stable_key)
        
        session.missing_fields = [{"key": k} for k in missing_required]
        
        # Check file requirements too
        file_blockers = []
        for fr in (session.file_requirements or []):
            if fr.get("required") and fr.get("status") != "selected":
                file_blockers.append(fr.get("label", fr.get("key")))
        
        # Update status
        if missing_required or file_blockers:
            session.status = "awaiting_confirmation"
            parts = []
            if missing_required:
                parts.append(f"{len(missing_required)} required fields still missing")
            if file_blockers:
                parts.append(f"{len(file_blockers)} required files not selected")
            message = "; ".join(parts)
        else:
            session.status = "confirmed"
            message = "Data confirmed. Ready for autofill."
        
        await session_store.save(session)
        
        print(f"[Confirm] Status: {session.status}, Missing: {len(missing_required)}")
        
        return ConfirmSubmitResponse(
            success=True,
            data={
                "session_id": session_id,
                "status": session.status,
                "missing_required_fields": missing_required,
                "message": message
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to confirm data: {str(e)}")
