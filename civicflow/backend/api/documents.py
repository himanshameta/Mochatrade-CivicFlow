"""
CivicFlow — Documents API
=========================
Endpoints for uploading, extracting, and confirming user documents.
"""
import os
import sys
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.doc_vault_v2 import DocVaultAgent
from utils.auth import require_auth, ok
from db.mongo import get_db
from models.user_models import UploadedDocumentRef
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
