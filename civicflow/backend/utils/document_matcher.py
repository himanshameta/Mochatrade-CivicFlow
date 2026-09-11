"""
CivicFlow — Document Matcher (v2)
====================================
Smart matching of user vault documents to form file fields.
Returns ranked matches with confidence scores.
"""
import mimetypes
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# Category inference map: keywords in field labels → vault category
LABEL_TO_CATEGORY: Dict[str, str] = {
    "resume": "resume", "cv": "resume", "biodata": "resume", "curriculum": "resume",
    "photo": "photo", "photograph": "photo", "picture": "photo", "headshot": "photo", "selfie": "photo", "avatar": "photo",
    "aadhaar": "identity", "aadhar": "identity", "pan card": "identity", "pan": "identity",
    "passport": "identity", "voter": "identity", "driving": "identity", "license": "identity",
    "id proof": "identity", "identity": "identity", "id card": "identity",
    "address proof": "address_proof", "utility bill": "address_proof", "electricity": "address_proof",
    "water bill": "address_proof", "bank statement": "address_proof", "rent": "address_proof", "lease": "address_proof",
    "marksheet": "education", "transcript": "education", "degree": "education", "diploma": "education",
    "scorecard": "education", "result": "education", "grade": "education",
    "certificate": "certificate", "certification": "certificate",
    "income": "financial", "salary": "financial", "tax": "financial", "itr": "financial",
    "medical": "medical", "health": "medical", "prescription": "medical", "report": "medical",
}


@dataclass
class DocumentMatch:
    """A ranked match between a vault document and a form file field."""
    document_id: str
    display_name: str
    category: str
    mime_type: str
    score: float = 0.0
    reason: str = ""


def normalize_accept_types(accept_str: str) -> List[str]:
    if not accept_str:
        return []
    types = [t.strip().lower() for t in accept_str.split(",")]
    normalized = []
    for t in types:
        if t == "application/pdf":
            normalized.extend([".pdf", t])
        elif t in ("image/jpeg", "image/jpg"):
            normalized.extend([".jpg", ".jpeg", t])
        elif t == "image/png":
            normalized.extend([".png", t])
        else:
            normalized.append(t)
    return list(set(normalized))


def file_matches_accept(mime_type: str, extension: str, accept_str: str) -> bool:
    if not accept_str:
        return True
    allowed = normalize_accept_types(accept_str)
    if extension and extension.lower() in allowed:
        return True
    if mime_type and mime_type.lower() in allowed:
        return True
    if mime_type:
        main_type = mime_type.split("/")[0]
        if f"{main_type}/*" in allowed:
            return True
    if extension and not mime_type:
        guessed, _ = mimetypes.guess_type(f"dummy{extension}")
        if guessed:
            if guessed in allowed:
                return True
            if f"{guessed.split('/')[0]}/*" in allowed:
                return True
    return False


def infer_category_from_label(label: str) -> Optional[str]:
    """Infer a vault category from a form field label."""
    if not label:
        return None
    label_lower = label.lower()
    for keyword, category in LABEL_TO_CATEGORY.items():
        if keyword in label_lower:
            return category
    return None


def _token_overlap(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two strings."""
    if not a or not b:
        return 0.0
    tokens_a = set(re.split(r'[\s_\-]+', a.lower()))
    tokens_b = set(re.split(r'[\s_\-]+', b.lower()))
    tokens_a.discard("")
    tokens_b.discard("")
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def match_documents_for_file_field(
    field_dict: dict,
    user_documents: list,
) -> List[DocumentMatch]:
    """
    Find and rank vault documents that match a form file field.

    Ranking signals:
      1. Category match (inferred from label)
      2. Accept-compatible MIME/extension
      3. Display name similarity to field label
      4. Recency (newer documents score slightly higher)

    Returns list sorted by score descending. Never auto-selects.
    """
    if not user_documents:
        return []

    label = field_dict.get("label", "")
    accept = field_dict.get("accept", "")
    inferred_cat = infer_category_from_label(label)

    matches = []
    for doc in user_documents:
        doc_mime = doc.get("mime_type", "")
        doc_ext = doc.get("extension", "")
        if not doc_ext and doc.get("storage_path"):
            _, doc_ext = os.path.splitext(doc["storage_path"])

        # Filter by accept compatibility
        if not file_matches_accept(doc_mime, doc_ext, accept):
            continue

        score = 0.0
        reasons = []

        # Signal 1: category match
        doc_cat = doc.get("category", "other")
        if inferred_cat and doc_cat == inferred_cat:
            score += 40
            reasons.append(f"category={doc_cat}")

        # Signal 2: display name similarity to field label
        doc_name = doc.get("display_name", "")
        name_sim = _token_overlap(label, doc_name)
        if name_sim > 0.3:
            score += name_sim * 30
            reasons.append(f"name_sim={name_sim:.2f}")

        # Signal 3: original filename similarity
        orig = doc.get("original_filename", "")
        orig_sim = _token_overlap(label, orig)
        if orig_sim > 0.2:
            score += orig_sim * 15
            reasons.append(f"orig_sim={orig_sim:.2f}")

        # Signal 4: recency boost (max 10 points)
        try:
            from datetime import datetime
            created = doc.get("created_at")
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            if isinstance(created, datetime):
                age_days = (datetime.utcnow() - created).days
                recency = max(0, 10 - age_days * 0.05)
                score += recency
        except Exception:
            pass

        # Minimum threshold
        if score >= 5:
            matches.append(DocumentMatch(
                document_id=doc.get("document_id", ""),
                display_name=doc_name,
                category=doc_cat,
                mime_type=doc_mime,
                score=round(score, 2),
                reason="; ".join(reasons),
            ))

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:10]  # Cap at 10 suggestions


def validate_document_for_field(document: dict, file_requirement: dict) -> tuple:
    """
    Check if a document is compatible with a file requirement.
    Returns (is_compatible: bool, reason: str).
    """
    accept = file_requirement.get("accept", "")
    doc_mime = document.get("mime_type", "")
    doc_ext = document.get("extension", "")

    if not file_matches_accept(doc_mime, doc_ext, accept):
        return False, f"File type {doc_ext or doc_mime} not accepted (requires: {accept})"

    return True, "Compatible"


def match_user_document_to_field(
    label: str,
    accept: str,
    user_documents: List[dict],
) -> Optional[dict]:
    """
    Match a user's physical document to a form file field.
    Returns the best matching document dict or None.
    """
    if not user_documents:
        return None

    # Filter by accept-compatibility first
    valid_docs = []
    for doc in user_documents:
        mime_type = doc.get("mime_type", "")
        extension = doc.get("extension", "")
        if not extension and doc.get("file_path"):
            _, extension = os.path.splitext(doc["file_path"])
        if file_matches_accept(mime_type, extension, accept):
            valid_docs.append(doc)

    if not valid_docs:
        return None

    # Score each doc
    best_doc = None
    best_score = -1.0

    for doc in valid_docs:
        score = 0.0
        doc_label = doc.get("doc_label", "")
        doc_key = doc.get("doc_key", "")
        orig_name = doc.get("original_filename", "")

        # 1. Check direct token overlap on label and doc_label/doc_key
        label_sim = _token_overlap(label, doc_label)
        key_sim = _token_overlap(label, doc_key)
        orig_sim = _token_overlap(label, orig_name)

        score += max(label_sim, key_sim) * 50
        score += orig_sim * 20

        # 2. Exact match check
        if label.lower().strip() == doc_label.lower().strip() or label.lower().strip() == doc_key.lower().strip():
            score += 100

        if score > best_score:
            best_score = score
            best_doc = doc

    # Only return if there is some confidence
    if best_score > 0:
        return best_doc
    return None

