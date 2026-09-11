"""
Field Validation & Sanitization Helpers
=========================================
Production-grade validation gate for the confirm-data pipeline.

Responsibilities:
- Detect and reject ciphertext / encrypted / non-human-readable values
- Sanitize autofill values before they reach the frontend
- Flatten and decrypt canonical user profile from MongoDB
- Build structured blockers and warnings for the review UI
"""
import re
import math
import string
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("civicflow.field_validation")


# ---------------------------------------------------------------------------
# Ciphertext / readability detection
# ---------------------------------------------------------------------------

# Pattern: base64-like string with colon separator (AES-GCM nonce:ciphertext)
_CIPHERTEXT_PATTERN = re.compile(
    r'^[A-Za-z0-9+/=]{12,}:[A-Za-z0-9+/=]{16,}$'
)

# Dev-mode passthrough pattern from encryption.py
_PLAIN_PREFIX_PATTERN = re.compile(r'^plain:[A-Za-z0-9+/=]+$')

# Non-printable character threshold
_NON_PRINTABLE_THRESHOLD = 0.1  # 10% of chars being non-printable → reject

# Minimum Shannon entropy to flag as "random-looking" (per character)
_HIGH_ENTROPY_THRESHOLD = 4.5  # bits per char; natural language ~3.5-4.2


def _shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string in bits per character."""
    if not s:
        return 0.0
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    entropy = 0.0
    for count in freq.values():
        p = count / length
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def is_human_readable_field_value(value: Any, field_type: str = "text", label: str = "") -> bool:
    """
    Check whether a value is suitable for display in a confirmation UI.

    Rejects:
    - None or empty
    - Ciphertext-like strings (nonce:ciphertext or plain:base64)
    - Strings with high proportion of non-printable characters
    - Highly random strings (high Shannon entropy + long length)
    - Field-specific rules (email must contain @, phone must be mostly digits, etc.)

    Returns:
        True if the value appears to be legitimate human-readable data.
    """
    if value is None:
        return False

    s = str(value).strip()
    if not s:
        return False

    # Reject ciphertext patterns
    if _CIPHERTEXT_PATTERN.match(s):
        return False
    if _PLAIN_PREFIX_PATTERN.match(s):
        return False

    # Reject non-printable strings
    printable_set = set(string.printable)
    non_printable_count = sum(1 for c in s if c not in printable_set)
    if len(s) > 0 and (non_printable_count / len(s)) > _NON_PRINTABLE_THRESHOLD:
        return False

    # Reject highly random strings (only for longer values)
    if len(s) > 20:
        entropy = _shannon_entropy(s)
        if entropy > _HIGH_ENTROPY_THRESHOLD:
            # Additional heuristic: if string has few spaces relative to length,
            # it's more likely to be random/encoded data
            space_ratio = s.count(' ') / len(s)
            if space_ratio < 0.05:
                return False

    # Field-specific validation
    field_type_lower = field_type.lower() if field_type else ""

    if field_type_lower == "email":
        if "@" not in s or "." not in s.split("@")[-1]:
            return False

    if field_type_lower == "tel":
        digit_count = sum(1 for c in s if c.isdigit())
        if digit_count < 7:  # Minimum 7 digits for a phone number
            return False

    return True


def sanitize_autofill_value(
    label: str,
    field_type: str,
    value: Any
) -> Tuple[Any, Optional[str]]:
    """
    Sanitize a single autofill value for safe frontend display.

    Returns:
        (safe_value, warning_or_none)
        - If invalid/suspicious: ("", "Stored value for {label} was rejected because ...")
        - If valid: (normalized_scalar_value, None)
    """
    if value is None or str(value).strip() == "":
        return "", None

    s = str(value).strip()

    # Check ciphertext patterns
    if _CIPHERTEXT_PATTERN.match(s):
        return "", f"Stored value for '{label}' was rejected because it appears encrypted (ciphertext detected)."

    if _PLAIN_PREFIX_PATTERN.match(s):
        return "", f"Stored value for '{label}' was rejected because it appears to be a dev-mode encoded value."

    # Check readability
    if not is_human_readable_field_value(s, field_type, label):
        return "", f"Stored value for '{label}' was rejected because it failed readability validation."

    # Normalize based on field type
    field_type_lower = field_type.lower() if field_type else "text"

    if field_type_lower == "email":
        s = s.lower().strip()
    elif field_type_lower == "tel":
        # Keep only digits, +, -, (, ), space
        s = re.sub(r'[^\d+\-() ]', '', s).strip()

    return s, None


# ---------------------------------------------------------------------------
# Canonical profile flattening with decryption
# ---------------------------------------------------------------------------

async def flatten_canonical_profile(user_id: str) -> Tuple[Dict[str, str], List[str]]:
    """
    Fetch user profile from MongoDB, decrypt encrypted fields, validate all values.

    This is the ONLY function that should be used to get profile data for autofill.
    It replaces the unsafe `get_flat_user_profile()` which did not decrypt.

    Args:
        user_id: User ID to fetch profile for

    Returns:
        (clean_flat_profile, warnings)
        - clean_flat_profile: dict of field_name → safe plaintext value
        - warnings: list of warning strings for rejected values
    """
    from db.mongo import get_db
    from utils.encryption import (
        decrypt_dict_fields,
        ENCRYPTED_BASIC_FIELDS,
        ENCRYPTED_CONTACT_FIELDS,
        ENCRYPTED_IDENTITY_FIELDS,
    )
    from utils.generic_mapper import normalize_profile_data

    warnings = []

    try:
        db = await get_db()
        if db is None:
            logger.warning("MongoDB not available, returning empty profile")
            return {}, warnings

        profile_doc = await db.user_profiles.find_one({"user_id": user_id})
        if not profile_doc:
            logger.info(f"No profile found for user {user_id}")
            return {}, warnings

        raw_flat = {}

        # --- Decrypt basic_info ---
        basic_info = profile_doc.get("basic_info", {})
        if isinstance(basic_info, dict) and basic_info:
            decrypted_basic = decrypt_dict_fields(
                basic_info, user_id, ENCRYPTED_BASIC_FIELDS
            )
            raw_flat.update(decrypted_basic)
            logger.info(f"[FlattenProfile] Decrypted basic_info: {list(decrypted_basic.keys())}")

        # --- Decrypt contact ---
        contact = profile_doc.get("contact", {})
        if isinstance(contact, dict) and contact:
            decrypted_contact = decrypt_dict_fields(
                contact, user_id, ENCRYPTED_CONTACT_FIELDS
            )
            raw_flat.update(decrypted_contact)

        # --- Decrypt identity ---
        identity = profile_doc.get("identity", {})
        if isinstance(identity, dict) and identity:
            decrypted_identity = decrypt_dict_fields(
                identity, user_id, ENCRYPTED_IDENTITY_FIELDS
            )
            raw_flat.update(decrypted_identity)

        # --- Education (not encrypted) ---
        education = profile_doc.get("education", {})
        if isinstance(education, dict):
            raw_flat.update(education)

        # --- Uploaded documents OCR fields (selective) ---
        # Do NOT blindly merge ocr_extracted_fields.
        # Only merge fields that pass readability validation.
        uploaded_docs = profile_doc.get("uploaded_documents", [])
        if isinstance(uploaded_docs, list):
            for doc in uploaded_docs:
                if not isinstance(doc, dict):
                    continue
                ocr_fields = doc.get("ocr_extracted_fields", {})
                if not isinstance(ocr_fields, dict):
                    continue
                # Attempt decryption of all OCR fields (they may be encrypted)
                try:
                    decrypted_ocr = decrypt_dict_fields(
                        ocr_fields, user_id, list(ocr_fields.keys())
                    )
                except Exception as e:
                    logger.warning(f"Could not decrypt OCR fields for doc {doc.get('doc_id')}: {e}")
                    decrypted_ocr = ocr_fields

                for key, val in decrypted_ocr.items():
                    if is_human_readable_field_value(val, "text", key):
                        raw_flat[key] = val
                    else:
                        warnings.append(
                            f"OCR field '{key}' from document '{doc.get('doc_type', 'unknown')}' "
                            f"was rejected (not human-readable)."
                        )

        # --- Normalize keys (canonical aliases) ---
        normalized = normalize_profile_data(raw_flat)

        # --- Auto-derive first/middle/last from full_name if missing ---
        if normalized.get("name") and not normalized.get("first_name"):
            from utils.profile_normalizer import split_full_name as split_name_3way
            parts = split_name_3way(normalized["name"])
            for k, v in parts.items():
                if v and k not in normalized:
                    normalized[k] = v
            logger.info(f"[FlattenProfile] Auto-derived name parts from full_name: {parts}")

        # Also set full_name from parts if missing
        if not normalized.get("name") and normalized.get("first_name"):
            parts = [
                normalized.get("first_name", ""),
                normalized.get("middle_name", ""),
                normalized.get("last_name", ""),
            ]
            full = " ".join(p for p in parts if p).strip()
            if full:
                normalized["name"] = full

        # --- Final sanitization pass on all values ---
        clean_profile = {}
        for key, val in normalized.items():
            safe_val, warning = sanitize_autofill_value(key, "text", val)
            if safe_val:
                clean_profile[key] = safe_val
            if warning:
                warnings.append(warning)

        logger.info(
            f"[FlattenProfile] Final profile: {len(clean_profile)} clean fields, "
            f"{len(warnings)} warnings for user {user_id}"
        )
        return clean_profile, warnings

    except Exception as e:
        logger.error(f"[FlattenProfile] Error: {e}")
        import traceback
        traceback.print_exc()
        return {}, [f"Profile loading failed: {str(e)}"]


# ---------------------------------------------------------------------------
# Blockers & warnings builder
# ---------------------------------------------------------------------------

def build_review_blockers_and_warnings(
    fields: List[Dict],
    missing_required_fields: List[Dict],
    file_requirements: List[Dict],
    profile_warnings: List[str],
) -> Tuple[List[str], List[str]]:
    """
    Build structured lists of blockers (prevent execution) and warnings (informational).

    Args:
        fields: List of mapped form field dicts
        missing_required_fields: List of dicts with 'name', 'label', 'field_type'
        file_requirements: List of file requirement dicts from document matching
        profile_warnings: Warnings from profile sanitization

    Returns:
        (blockers, warnings) — both are lists of human-readable strings
    """
    blockers = []
    warnings = list(profile_warnings)  # Start with profile warnings

    # Blockers from missing required text fields
    for mf in missing_required_fields:
        label = mf.get("label", mf.get("name", "Unknown"))
        blockers.append(f"Required field '{label}' is missing.")

    # Blockers from missing required file uploads
    for fr in file_requirements:
        if fr.get("required") and fr.get("status") == "missing":
            label = fr.get("label", "Unknown document")
            accept = fr.get("accept", "")
            accept_msg = f" ({accept})" if accept else ""
            blockers.append(f"Required document '{label}'{accept_msg} is missing.")

    # Warnings for partially matched fields (low confidence, etc.)
    for field in fields:
        source = field.get("source", "none")
        if source == "none" and not field.get("required"):
            # Optional field with no match — not a blocker but worth noting
            pass  # Don't add noise for optional unmatched fields

    return blockers, warnings


# ---------------------------------------------------------------------------
# Semantic label inference
# ---------------------------------------------------------------------------

# Common field label corrections
_LABEL_INFERENCE_MAP = {
    # When the label looks like an option value rather than a field concept
    "male": "Gender",
    "female": "Gender",
    "other": "Gender",
    "mr": "Title",
    "mrs": "Title",
    "ms": "Title",
    "dr": "Title",
    "yes": None,  # Too ambiguous without context
    "no": None,
}

# File field label inference from accept attributes
_FILE_LABEL_FROM_ACCEPT = {
    ".pdf": "Document Upload",
    "image/*": "Image Upload",
    ".jpg,.jpeg,.png": "Photo Upload",
    ".doc,.docx": "Document Upload",
    ".pdf,.doc,.docx": "Resume/Document Upload",
}


def infer_semantic_label(field_dict: Dict) -> str:
    """
    Infer a better human-readable label for a field when the scraped label
    is missing, generic, or actually an option value.

    Args:
        field_dict: Scraped field dict with label, field_type, options, name, etc.

    Returns:
        Improved label string, or the original label if no inference possible.
    """
    label = field_dict.get("label", "").strip()
    field_type = field_dict.get("field_type", "text")
    name = field_dict.get("name", "")
    options = field_dict.get("options", [])

    # Case 1: Radio/select field where label matches an option value
    if field_type in ("radio", "select") and label:
        label_lower = label.lower().strip()
        inferred = _LABEL_INFERENCE_MAP.get(label_lower)
        if inferred is not None:
            return inferred
        # Also check if label is one of the option values
        for opt in options:
            opt_val = opt.get("value", "") if isinstance(opt, dict) else str(opt)
            opt_label = opt.get("label", "") if isinstance(opt, dict) else str(opt)
            if label_lower == opt_val.lower() or label_lower == opt_label.lower():
                # Label is an option value — try to infer from name attribute
                if name:
                    # Convert name like "gender" or "customGender" to "Gender"
                    from utils.generic_mapper import canonicalize_key
                    canon = canonicalize_key(name)
                    return canon.replace("_", " ").title()
                return f"{field_type.title()} Selection"

    # Case 2: File field with no useful label
    if field_type == "file" and (not label or label.lower() in ("unnamed field", "file", "upload", "")):
        accept = field_dict.get("accept", "")
        if accept:
            for pattern, inferred_label in _FILE_LABEL_FROM_ACCEPT.items():
                if pattern in accept.lower():
                    return inferred_label
        # Try name attribute
        if name:
            from utils.generic_mapper import canonicalize_key
            canon = canonicalize_key(name)
            readable = canon.replace("_", " ").title()
            if readable and readable.lower() != "unnamed field":
                return f"{readable} Upload"
        return "File Upload"

    # Case 3: Generic empty or "Unnamed Field" label
    if not label or label.lower() in ("unnamed field", "unnamed_field", ""):
        if name:
            from utils.generic_mapper import canonicalize_key
            canon = canonicalize_key(name)
            return canon.replace("_", " ").title()
        return f"Field ({field_type})"

    return label
