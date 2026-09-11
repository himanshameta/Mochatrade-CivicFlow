"""
CivicFlow — Documents API
=========================
Endpoints for uploading, extracting, and confirming user documents.
"""
import os
import sys
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Path as FastApiPath
from pydantic import BaseModel
import shutil
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.doc_vault_v2 import DocVaultAgent
from utils.auth import require_auth, ok
from db.mongo import get_db
from models.user_models import UploadedDocumentRef, DocumentDB
from models.document_models import ConfirmDocumentRequest

router = APIRouter(prefix="/documents", tags=["Documents"])

# Lazy instantiation to avoid loading heavy ML models at import time
_doc_vault: Optional[DocVaultAgent] = None
_doc_vault_error: Optional[str] = None
_doc_vault_error: Optional[str] = None

def get_doc_vault() -> Optional[DocVaultAgent]:
    global _doc_vault, _doc_vault_error
    if _doc_vault is None and _doc_vault_error is None:
        try:
            _doc_vault = DocVaultAgent()
        except Exception as e:
            # If DocVaultAgent fails to load, log it and continue
            import logging
            logger = logging.getLogger("civicflow.documents")
            _doc_vault_error = f"{type(e).__name__}: {str(e)}"
            logger.error("DocVaultAgent initialization failed: %s", _doc_vault_error)
            logger.warning("Document processing will use fallback mode")
            _doc_vault = None
    return _doc_vault


@router.post("/upload", summary="Upload and extract data from a document")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    session_id: str = Form(""),
    payload: dict = Depends(require_auth)
):
    """
    1. Validates file
    2. Runs DocVault OCR & Gemini extraction
    3. Returns extracted fields for user review
    Does NOT save fields to user profile automatically.
    """
    user_id = payload["sub"]
    file_bytes = await file.read()
    from config import settings
    
    agent = get_doc_vault()
    
    # Check if DocVault is available
    if agent is None:
        global _doc_vault_error
        return ok("Document upload unavailable", data={
            "doc_id": None,
            "extracted_fields": {},
            "fallback_mode": True,
            "error_reason": "docvault_unavailable",
            "message": f"Document processing is currently unavailable. Error: {_doc_vault_error or 'Unknown'}"
        })
    
    # Check if OCR service is available
    ocr_healthy = await agent.check_ocr_health()
    if not ocr_healthy:
        return ok("OCR service unavailable", data={
            "doc_id": None,
            "extracted_fields": {},
            "fallback_mode": True,
            "error_reason": "ocr_service_unavailable",
            "message": "OCR service is not responding. Please ensure it's running on " + agent.ocr_api_url
        })
    
    try:
        result = await agent.process_document(
            file_bytes=file_bytes,
            filename=file.filename,
            mime_type_hint=file.content_type,
            doc_type=doc_type,
            user_id=user_id,
            session_id=session_id
        )
        return ok("Document processed successfully", data=result.model_dump())
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"success": False, "message": str(ve), "data": {}})
    except Exception as e:
        import traceback
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"[Documents API] Error: {error_type}: {error_msg}")
        traceback.print_exc()
        
        # Check for OpenRouter quota errors
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
            print("[Documents API] OpenRouter quota exceeded, using basic OCR extraction")
            # Return partial result with OCR only, no OpenRouter enrichment
            return ok("Document processed with limited features", data={
                "doc_id": None,
                "extracted_fields": {},
                "fallback_mode": True,
                "error_reason": "openrouter_quota_exceeded",
                "message": "Document uploaded but AI enrichment is currently unavailable. Basic OCR extraction was attempted."
            })
        
        raise HTTPException(status_code=500, detail={"success": False, "message": f"Processing failed: {str(e)}", "data": {}})


@router.post("/confirm/{doc_id}", summary="Confirm and save document to profile")
async def confirm_document(
    doc_id: str,
    request: ConfirmDocumentRequest,
    payload: dict = Depends(require_auth)
):
    """
    Saves the confirmed document and fields to the user profile.
    """
    user_id = payload["sub"]
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Fetch document metadata
    doc_meta = await db.documents.find_one({"doc_id": doc_id, "user_id": user_id})
    if not doc_meta:
        raise HTTPException(status_code=404, detail="Document not found")

    # Use corrected fields if provided, else use OCR results
    fields_to_save = request.corrected_fields if request.corrected_fields is not None else doc_meta.get("ocr_results", {})

    # Encrypt the fields to save in the profile
    # For now, we store them in the `uploaded_documents` array inside UserProfileData
    # However, some fields like `aadhaar_last4` might need to go to `identity`
    # We will just append the reference.
    from utils.encryption import encrypt_dict_fields
    encrypted_fields = encrypt_dict_fields(fields_to_save, user_id, list(fields_to_save.keys()))
    
    doc_ref = UploadedDocumentRef(
        doc_id=doc_id,
        doc_type=doc_meta.get("doc_type", "unknown"),
        original_filename=doc_meta["original_filename"],
        storage_path=doc_meta["storage_path"],
        ocr_extracted_fields=encrypted_fields,
        is_verified=True
    )
    
    # Update profile
    result = await db.user_profiles.update_one(
        {"user_id": user_id},
        {"$push": {"uploaded_documents": doc_ref.model_dump()}}
    )
    
    # If profile doesn't exist, create it
    if result.matched_count == 0:
        from models.user_models import UserProfileData
        new_profile = UserProfileData(user_id=user_id, uploaded_documents=[doc_ref])
        await db.user_profiles.insert_one(new_profile.model_dump())

    return ok("Document confirmed and saved to profile")


@router.get("/list", summary="List uploaded documents")
async def list_documents(payload: dict = Depends(require_auth)):
    """Returns metadata for all user's uploaded documents."""
    user_id = payload["sub"]
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    cursor = db.documents.find({"user_id": user_id, "is_deleted": {"$ne": True}})
    docs = await cursor.to_list(length=100)
    
    # Remove MongoDB _id
    for d in docs:
        d.pop("_id", None)
        
    return ok("Success", data={"documents": docs})


@router.delete("/{doc_id}", summary="Soft delete a document")
async def delete_document(doc_id: str, payload: dict = Depends(require_auth)):
    """Marks document as deleted. Retains in DB for audit."""
    user_id = payload["sub"]
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    result = await db.documents.update_one(
        {"doc_id": doc_id, "user_id": user_id},
        {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")

    # Also remove from user_profiles.uploaded_documents
    await db.user_profiles.update_one(
        {"user_id": user_id},
        {"$pull": {"uploaded_documents": {"doc_id": doc_id}}}
    )

    return ok("Document deleted successfully")


@router.get("/{doc_id}/fields", summary="Get decrypted fields for a document")
async def get_document_fields(doc_id: str, payload: dict = Depends(require_auth)):
    """Returns the decrypted extracted fields for the owner."""
    user_id = payload["sub"]
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    doc = await db.documents.find_one({"doc_id": doc_id, "user_id": user_id})
    if not doc or doc.get("is_deleted"):
        raise HTTPException(status_code=404, detail="Document not found")

    # Also check if it's confirmed in the profile to get the final (possibly corrected) encrypted fields
    profile = await db.user_profiles.find_one({"user_id": user_id})
    fields = doc.get("ocr_results", {})
    
    if profile:
        for udoc in profile.get("uploaded_documents", []):
            if udoc["doc_id"] == doc_id:
                # Decrypt the final fields
                from utils.encryption import decrypt_dict_fields
                enc_fields = udoc.get("ocr_extracted_fields", {})
                fields = decrypt_dict_fields(enc_fields, user_id, list(enc_fields.keys()))
                break

    return ok("Success", data={"fields": fields})

# ===========================================================================
# Physical File Upload and Retrieval
# ===========================================================================

@router.post("/users/{user_id}/documents/upload", summary="Upload and store a physical document")
async def store_physical_document(
    user_id: str = FastApiPath(...),
    file: UploadFile = File(...),
    doc_key: str = Form(...),
    doc_label: Optional[str] = Form(None),
    payload: dict = Depends(require_auth)
):
    """
    Stores a physical document on disk and creates a DB record for it.
    Does not run OCR immediately.
    """
    if payload["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to upload for this user")
        
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    import os
    import time
    
    # Sanitize inputs
    safe_original_name = "".join(c for c in file.filename if c.isalnum() or c in ".-_ ").strip()
    _, ext = os.path.splitext(safe_original_name)
    timestamp = int(time.time())
    
    # Generate storage path
    upload_base_dir = os.getenv("UPLOAD_DIR", "./uploads")
    user_docs_dir = os.path.join(upload_base_dir, "user_docs", user_id)
    os.makedirs(user_docs_dir, exist_ok=True)
    
    stored_filename = f"{doc_key}__{timestamp}__{safe_original_name}"
    file_path = os.path.join(user_docs_dir, stored_filename)
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
        
    file_size = os.path.getsize(file_path)
    
    # Create metadata record
    doc_meta = {
        "doc_id": str(uuid.uuid4()),
        "user_id": user_id,
        "doc_key": doc_key,
        "doc_label": doc_label or doc_key.replace("_", " ").title(),
        "original_filename": safe_original_name,
        "stored_filename": stored_filename,
        "mime_type": file.content_type,
        "extension": ext,
        "file_path": os.path.abspath(file_path),
        "file_size_bytes": file_size,
        "uploaded_at": datetime.utcnow(),
        "is_active": True,
        "is_deleted": False
    }
    
    # Invalidate older documents with same doc_key
    await db.physical_documents.update_many(
        {"user_id": user_id, "doc_key": doc_key},
        {"$set": {"is_active": False}}
    )
    
    # Insert new record
    await db.physical_documents.insert_one(doc_meta)
    
    # Remove Mongo _id for response
    doc_meta.pop("_id", None)
    
    return ok("Document uploaded and stored successfully", data=doc_meta)


@router.get("/users/{user_id}/documents", summary="List stored physical documents")
async def list_physical_documents(
    user_id: str = FastApiPath(...),
    payload: dict = Depends(require_auth)
):
    """Returns metadata for user's stored physical documents."""
    if payload["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Get active documents
    cursor = db.physical_documents.find({"user_id": user_id, "is_deleted": {"$ne": True}})
    docs = await cursor.to_list(length=100)
    
    for d in docs:
        d.pop("_id", None)
        
    return ok("Success", data={"documents": docs})


# ═══════════════════════════════════════════════════════════════════════════
# VAULT API — Privacy-first local document storage
# ═══════════════════════════════════════════════════════════════════════════

from models.vault_models import (
    UserDocument, UserDocumentPublic, DocumentCategory, DocumentSource,
    AttachDocumentRequest, UpdateDocumentRequest,
)
from utils.vault_storage import (
    validate_file_upload, save_file_to_vault, save_temp_session_file,
    resolve_document_path,
)
from db.vault_db import (
    create_document as vault_create,
    get_document as vault_get,
    list_documents as vault_list,
    update_document as vault_update,
    soft_delete_document as vault_delete,
)


@router.post("/vault/upload", summary="Upload a document to the vault")
async def vault_upload(
    file: UploadFile = File(...),
    display_name: str = Form(...),
    category: str = Form("other"),
    subcategory: str = Form(None),
    tags: str = Form(""),
    user=Depends(require_auth),
):
    """Upload and store a file in the user's local vault."""
    user_id = user["sub"]
    file_bytes = await file.read()

    try:
        mime_type, extension = validate_file_upload(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    stored_filename, storage_path, size_bytes = save_file_to_vault(
        file_bytes, user_id, category, display_name, extension,
    )

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    doc = UserDocument(
        user_id=user_id,
        display_name=display_name,
        category=category,
        subcategory=subcategory or None,
        original_filename=file.filename or "unknown",
        stored_filename=stored_filename,
        storage_path=storage_path,
        mime_type=mime_type,
        extension=extension,
        size_bytes=size_bytes,
        tags=tag_list,
        source=DocumentSource.MANUAL_UPLOAD,
    )

    await vault_create(doc)
    return ok("Document uploaded", data=UserDocumentPublic.from_document(doc).model_dump())


@router.get("/vault/list", summary="List vault documents")
async def vault_list_docs(
    category: str = None,
    user=Depends(require_auth),
):
    docs = await vault_list(user["sub"], category=category)
    return ok("Success", data={
        "documents": [UserDocumentPublic.from_document(d).model_dump() for d in docs]
    })


@router.get("/vault/{document_id}", summary="Get vault document metadata")
async def vault_get_doc(document_id: str, user=Depends(require_auth)):
    doc = await vault_get(document_id, user["sub"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return ok("Success", data=UserDocumentPublic.from_document(doc).model_dump())


@router.patch("/vault/{document_id}", summary="Update vault document metadata")
async def vault_update_doc(
    document_id: str,
    body: UpdateDocumentRequest,
    user=Depends(require_auth),
):
    updates = body.model_dump(exclude_none=True)
    if "category" in updates and isinstance(updates["category"], DocumentCategory):
        updates["category"] = updates["category"].value
    success = await vault_update(document_id, user["sub"], updates)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found or no changes")
    return ok("Document updated")


@router.delete("/vault/{document_id}", summary="Delete vault document")
async def vault_delete_doc(document_id: str, user=Depends(require_auth)):
    success = await vault_delete(document_id, user["sub"])
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return ok("Document deleted")


# ── Session document endpoints ─────────────────────────────────────────

@router.post("/session/{session_id}/attach-document", summary="Attach a vault document to a session file field")
async def session_attach_document(
    session_id: str,
    body: AttachDocumentRequest,
    user=Depends(require_auth),
):
    """Link an existing vault document to a session's file requirement."""
    from models.session_models import SessionStore
    store = SessionStore()
    session = await store.load(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify document exists and belongs to user
    doc = await vault_get(body.document_id, user["sub"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in your vault")

    # Verify file exists on disk
    abs_path = resolve_document_path(doc.storage_path)
    if not abs_path:
        raise HTTPException(status_code=410, detail="Document file missing from disk")

    # Store selection in session
    if not session.selected_documents:
        session.selected_documents = {}
    session.selected_documents[body.field_name] = [body.document_id]

    # Update file_requirements status
    for fr in (session.file_requirements or []):
        if fr.get("key") == body.field_name:
            fr["selected_document_id"] = body.document_id
            fr["status"] = "selected"

    await store.save(session)
    return ok("Document attached", data={"field_name": body.field_name, "document_id": body.document_id})


@router.post("/session/{session_id}/upload-document", summary="Upload a file for a session file field")
async def session_upload_document(
    session_id: str,
    file: UploadFile = File(...),
    field_name: str = Form(...),
    display_name: str = Form(...),
    category: str = Form("other"),
    save_for_reuse: bool = Form(True),
    user=Depends(require_auth),
):
    """Upload a file during form review. Optionally saves to vault for reuse."""
    from models.session_models import SessionStore
    store = SessionStore()
    session = await store.load(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_id = user["sub"]
    file_bytes = await file.read()

    try:
        mime_type, extension = validate_file_upload(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    doc_id = None
    if save_for_reuse:
        # Save to vault permanently
        stored_filename, storage_path, size_bytes = save_file_to_vault(
            file_bytes, user_id, category, display_name, extension,
        )
        doc = UserDocument(
            user_id=user_id,
            display_name=display_name,
            category=category,
            original_filename=file.filename or "unknown",
            stored_filename=stored_filename,
            storage_path=storage_path,
            mime_type=mime_type,
            extension=extension,
            size_bytes=size_bytes,
            source=DocumentSource.SESSION_UPLOAD,
        )
        await vault_create(doc)
        doc_id = doc.document_id
    else:
        # Save to temp session dir only
        stored_filename, storage_path = save_temp_session_file(
            file_bytes, session_id, field_name, extension,
        )
        doc_id = storage_path  # Use path as identifier for temp files

    # Store selection in session
    if not session.selected_documents:
        session.selected_documents = {}
    session.selected_documents[field_name] = [doc_id]

    # Update file_requirements status
    for fr in (session.file_requirements or []):
        if fr.get("key") == field_name:
            fr["selected_document_id"] = doc_id
            fr["status"] = "selected"

    await store.save(session)
    return ok("File uploaded and attached", data={
        "field_name": field_name,
        "document_id": doc_id,
        "saved_to_vault": save_for_reuse,
    })
