"""
CivicFlow — Document Vault DB
================================
MongoDB CRUD operations for the `user_documents` collection.
"""
import json
from datetime import datetime
from typing import List, Optional

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.vault_models import UserDocument, DocumentCategory


async def _get_collection():
    """Get the user_documents MongoDB collection."""
    from db.mongo import get_db
    db = await get_db()
    if db is None:
        return None
    return db.user_documents


async def ensure_vault_indexes():
    """Create indexes for the user_documents collection."""
    col = await _get_collection()
    if col is None:
        return
    try:
        await col.create_index("document_id", unique=True)
        await col.create_index("user_id")
        await col.create_index([("user_id", 1), ("category", 1)])
        await col.create_index([("user_id", 1), ("is_active", 1)])
        print("[VaultDB] ✓ Indexes ensured for user_documents")
    except Exception as e:
        print(f"[VaultDB] ⚠ Index creation warning: {e}")


async def create_document(doc: UserDocument) -> Optional[UserDocument]:
    """Insert a new vault document record."""
    col = await _get_collection()
    if col is None:
        print("[VaultDB] ✗ MongoDB unavailable — cannot create document")
        return None

    doc_dict = json.loads(doc.model_dump_json())
    await col.insert_one(doc_dict)
    print(f"[VaultDB] ✓ Created document {doc.document_id} for user {doc.user_id}")
    return doc


async def get_document(document_id: str, user_id: str) -> Optional[UserDocument]:
    """Fetch a single vault document by ID, scoped to user."""
    col = await _get_collection()
    if col is None:
        return None

    doc = await col.find_one({
        "document_id": document_id,
        "user_id": user_id,
        "is_active": True,
    })
    if doc is None:
        return None

    doc.pop("_id", None)
    return UserDocument.model_validate(doc)


async def list_documents(
    user_id: str,
    category: Optional[str] = None,
    is_active: bool = True,
    limit: int = 200,
) -> List[UserDocument]:
    """List vault documents for a user, optionally filtered by category."""
    col = await _get_collection()
    if col is None:
        return []

    query = {"user_id": user_id, "is_active": is_active}
    if category:
        query["category"] = category

    cursor = col.find(query).sort("updated_at", -1).limit(limit)
    results = []
    async for doc in cursor:
        doc.pop("_id", None)
        try:
            results.append(UserDocument.model_validate(doc))
        except Exception:
            pass
    return results


async def update_document(
    document_id: str,
    user_id: str,
    updates: dict,
) -> bool:
    """
    Update specific fields of a vault document.
    Only allowed fields: display_name, category, subcategory, tags.
    """
    col = await _get_collection()
    if col is None:
        return False

    allowed_keys = {"display_name", "category", "subcategory", "tags"}
    safe_updates = {k: v for k, v in updates.items() if k in allowed_keys and v is not None}

    if not safe_updates:
        return False

    safe_updates["updated_at"] = datetime.utcnow().isoformat()

    result = await col.update_one(
        {"document_id": document_id, "user_id": user_id, "is_active": True},
        {"$set": safe_updates},
    )
    return result.modified_count > 0


async def soft_delete_document(document_id: str, user_id: str) -> bool:
    """Mark a vault document as inactive (soft delete)."""
    col = await _get_collection()
    if col is None:
        return False

    result = await col.update_one(
        {"document_id": document_id, "user_id": user_id},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow().isoformat()}},
    )
    return result.modified_count > 0
