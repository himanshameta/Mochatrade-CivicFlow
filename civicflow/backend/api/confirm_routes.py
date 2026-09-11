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
    
    Returns form with all fields mapped from user profile.
    Frontend renders this as a dynamic review form.
    """
    try:
        # Load session
        session = await session_store.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if not session.scraped_form:
            print(f"[ConfirmData] ERROR: scraped_form is None for session {session_id}")
            raise HTTPException(
                status_code=400,
                detail="Form has not been scraped yet. Please wait for analysis to complete."
            )
        
        print(f"[ConfirmData] scraped_form exists: True")
        
        # Get user profile from DB
        user_profile = {}
        if session.user_id:
            try:
                user_profile = await get_flat_user_profile(session.user_id)
                print(f"[ConfirmData] Loaded {len(user_profile)} profile fields for user {session.user_id}")
            except Exception as e:
                print(f"[ConfirmData] Could not load profile: {e}")
        
        # Merge with existing session values (session takes priority)
        if session.pre_filled_values:
            user_profile.update(session.pre_filled_values)
            print(f"[ConfirmData] Merged with {len(session.pre_filled_values)} session values")
        
        # Convert scraped_form to dict if needed
        scraped_form_dict = (
            session.scraped_form.model_dump()
            if hasattr(session.scraped_form, "model_dump")
            else session.scraped_form
        )
        
        print(f"[ConfirmData] scraped_form has {len(scraped_form_dict.get('fields', []))} fields")
        
        # Map profile to form schema
        review_fields = await map_profile_to_form_schema(scraped_form_dict, user_profile)
        
        print(f"[ConfirmData] Mapped {len([f for f in review_fields if f.value])} out of {len(review_fields)} fields")
        
        # Build pre_filled_values dict for session
        pre_filled_values = {}
        for field in review_fields:
            if field.value:
                pre_filled_values[field.key] = field.value
        
        # Compute missing required fields
        missing_required = []
        for field in review_fields:
            if field.required and not field.value:
                missing_required.append(field.key)
        
        # Save to session
        session.pre_filled_values = pre_filled_values
        session.review_form_schema = [field.model_dump() for field in review_fields]
        session.missing_fields = [{"key": k} for k in missing_required]
        session.status = "awaiting_confirmation"
        await session_store.save(session)
        
        print(f"[ConfirmData] Generated schema with {len(review_fields)} fields")
        print(f"[ConfirmData] {len(pre_filled_values)} fields have values")
        print(f"[ConfirmData] {len(missing_required)} required fields missing: {missing_required}")
        
        # Build response
        schema = ReviewFormSchema(
            session_id=session_id,
            url=session.url,
            page_title=scraped_form_dict.get('page_title', ''),
            fields=review_fields,
            missing_required_fields=missing_required,
            status="awaiting_confirmation",
            can_proceed=True
        )
        
        return ConfirmDataResponse(success=True, data=schema)
        
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
        
        # Update status
        if missing_required:
            session.status = "awaiting_confirmation"
            message = f"{len(missing_required)} required fields still missing"
            print(f"[Confirm] Status set to: awaiting_confirmation (missing: {missing_required})")
        else:
            session.status = "confirmed"
            message = "Data confirmed. Ready for autofill."
            print(f"[Confirm] Status set to: confirmed")
        
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
