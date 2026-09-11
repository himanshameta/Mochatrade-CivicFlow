"""
Profile Update Normalizer
==========================
Central alias mapping layer between frontend field names and backend canonical names.

The frontend (ProfileSetup.jsx) sends keys like `date_of_birth`, `address_line1`,
`aadhaar_number`, `institution_name` — but the Pydantic models use `dob`, `address`,
`aadhaar_last4`, `college`.

This module resolves ALL mismatches in one place so that:
- api/auth.py never calls setattr with raw frontend keys
- confirm-data inline updates use the same mapping
- upsert_basic_user_profile uses the same mapping
"""
import re
import logging
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("civicflow.profile_normalizer")


# ---------------------------------------------------------------------------
# Alias map: frontend_key → (section, canonical_backend_key)
# Keys prefixed with _ are compound/synthetic and handled specially.
# ---------------------------------------------------------------------------

FIELD_ALIAS_MAP: Dict[str, Tuple[str, str]] = {
    # ── basic_info ──
    "full_name":        ("basic_info", "full_name"),
    "fullName":         ("basic_info", "full_name"),
    "fullname":         ("basic_info", "full_name"),
    "applicant_name":   ("basic_info", "full_name"),
    "candidate_name":   ("basic_info", "full_name"),
    "first_name":       ("basic_info", "first_name"),
    "firstName":        ("basic_info", "first_name"),
    "given_name":       ("basic_info", "first_name"),
    "middle_name":      ("basic_info", "middle_name"),
    "middleName":       ("basic_info", "middle_name"),
    "last_name":        ("basic_info", "last_name"),
    "lastName":         ("basic_info", "last_name"),
    "surname":          ("basic_info", "last_name"),
    "family_name":      ("basic_info", "last_name"),
    "date_of_birth":    ("basic_info", "dob"),
    "dateOfBirth":      ("basic_info", "dob"),
    "dateofbirth":      ("basic_info", "dob"),
    "birth_date":       ("basic_info", "dob"),
    "birthdate":        ("basic_info", "dob"),
    "dob":              ("basic_info", "dob"),
    "gender":           ("basic_info", "gender"),
    "sex":              ("basic_info", "gender"),
    "nationality":      ("basic_info", "nationality"),
    "father_name":      ("basic_info", "father_name"),
    "fathers_name":     ("basic_info", "father_name"),
    "fatherName":       ("basic_info", "father_name"),
    "mother_name":      ("basic_info", "mother_name"),
    "mothers_name":     ("basic_info", "mother_name"),
    "motherName":       ("basic_info", "mother_name"),

    # ── contact ──
    "email":            ("contact", "email"),
    "email_id":         ("contact", "email"),
    "emailaddress":     ("contact", "email"),
    "email_address":    ("contact", "email"),
    "mail":             ("contact", "email"),
    "phone":            ("contact", "phone"),
    "mobile":           ("contact", "phone"),
    "mobile_number":    ("contact", "phone"),
    "mobileno":         ("contact", "phone"),
    "phone_number":     ("contact", "phone"),
    "contact":          ("contact", "phone"),
    "tel":              ("contact", "phone"),
    "alternate_phone":  ("contact", "alternate_phone"),
    "alt_phone":        ("contact", "alternate_phone"),
    "address":          ("contact", "address"),
    "full_address":     ("contact", "address"),
    "street_address":   ("contact", "address"),
    "current_address":  ("contact", "address"),
    "permanent_address":("contact", "address"),
    "address_line1":    ("contact", "_address_line1"),   # compound → address
    "address_line2":    ("contact", "_address_line2"),   # compound → address
    "addressLine1":     ("contact", "_address_line1"),
    "addressLine2":     ("contact", "_address_line2"),
    "city":             ("contact", "city"),
    "town":             ("contact", "city"),
    "state":            ("contact", "state"),
    "province":         ("contact", "state"),
    "region":           ("contact", "state"),
    "pincode":          ("contact", "pincode"),
    "pin":              ("contact", "pincode"),
    "pin_code":         ("contact", "pincode"),
    "postal_code":      ("contact", "pincode"),
    "postcode":         ("contact", "pincode"),
    "zip":              ("contact", "pincode"),
    "zip_code":         ("contact", "pincode"),
    "zipcode":          ("contact", "pincode"),
    "country":          ("contact", "country"),
    "nation":           ("contact", "country"),

    # ── identity ──
    "aadhaar_number":   ("identity", "aadhaar_last4"),   # auto-truncate to last 4
    "aadhaar":          ("identity", "aadhaar_last4"),
    "aadhaar_no":       ("identity", "aadhaar_last4"),
    "aadhaar_last4":    ("identity", "aadhaar_last4"),
    "pan_number":       ("identity", "pan_number"),
    "pan":              ("identity", "pan_number"),
    "pan_no":           ("identity", "pan_number"),
    "pannumber":        ("identity", "pan_number"),
    "voter_id":         ("identity", "voter_id"),
    "passport_number":  ("identity", "passport_number"),
    "passport":         ("identity", "passport_number"),
    "passport_no":      ("identity", "passport_number"),
    "driving_license":  ("identity", "driving_license"),

    # ── education ──
    "highest_qualification": ("education", "highest_qualification"),
    "qualification":         ("education", "highest_qualification"),
    "institution_name":      ("education", "college"),
    "college":               ("education", "college"),
    "college_name":          ("education", "college"),
    "university":            ("education", "university"),
    "university_name":       ("education", "university"),
    "year_of_passing":       ("education", "year_of_passing"),
    "passing_year":          ("education", "year_of_passing"),
}


# ---------------------------------------------------------------------------
# Sensitive field patterns — NEVER persist to user_profiles
# ---------------------------------------------------------------------------

SENSITIVE_FIELD_PATTERNS = [
    re.compile(r'(?i)password'),
    re.compile(r'(?i)^pwd$'),
    re.compile(r'(?i)secret'),
    re.compile(r'(?i)^otp$'),
    re.compile(r'(?i)^pin$'),       # standalone "pin" (not pincode)
    re.compile(r'(?i)captcha'),
    re.compile(r'(?i)token'),
    re.compile(r'(?i)cvv'),
    re.compile(r'(?i)card_number'),
    re.compile(r'(?i)credit_card'),
]


def is_sensitive_field(key: str) -> bool:
    """Check if a field key matches sensitive patterns (passwords, OTPs, etc.)."""
    for pattern in SENSITIVE_FIELD_PATTERNS:
        if pattern.search(key):
            return True
    return False


# ---------------------------------------------------------------------------
# Name splitting
# ---------------------------------------------------------------------------

def split_full_name(full_name: str) -> Dict[str, str]:
    """
    Split a full name into first, middle, and last name components.

    Rules:
    - 1 token:  first_name only
    - 2 tokens: first_name + last_name
    - 3+ tokens: first_name + middle_name (all middle) + last_name

    Returns:
        {"first_name": ..., "middle_name": ..., "last_name": ...}
    """
    if not full_name or not full_name.strip():
        return {"first_name": "", "middle_name": "", "last_name": ""}

    parts = full_name.strip().split()

    if len(parts) == 1:
        return {"first_name": parts[0], "middle_name": "", "last_name": ""}
    elif len(parts) == 2:
        return {"first_name": parts[0], "middle_name": "", "last_name": parts[1]}
    else:
        return {
            "first_name": parts[0],
            "middle_name": " ".join(parts[1:-1]),
            "last_name": parts[-1],
        }


# ---------------------------------------------------------------------------
# Aadhaar truncation
# ---------------------------------------------------------------------------

def truncate_aadhaar(value: str) -> str:
    """Extract last 4 digits from an Aadhaar number. Never store full Aadhaar."""
    if not value:
        return ""
    digits = re.sub(r'\D', '', str(value))
    if len(digits) >= 4:
        return digits[-4:]
    return digits


# ---------------------------------------------------------------------------
# Main normalization function
# ---------------------------------------------------------------------------

def normalize_profile_update_payload(payload: dict) -> dict:
    """
    Accept a raw frontend profile payload and normalize ALL keys to canonical
    backend field names, grouped by correct section.

    Input shape (from ProfileSetup.jsx):
        {
            "basic_info": {"full_name": "John", "date_of_birth": "1990-01-01", ...},
            "contact": {"address_line1": "123 Main St", "address_line2": "Apt 4", ...},
            "identity": {"aadhaar_number": "123456789012", ...},
            "education": {"institution_name": "MIT", ...}
        }

    Output shape (canonical):
        {
            "basic_info": {"full_name": "John", "dob": "1990-01-01", ...},
            "contact": {"address": "123 Main St, Apt 4", ...},
            "identity": {"aadhaar_last4": "9012", ...},
            "education": {"college": "MIT", ...}
        }

    Also handles flat payloads (from confirm-data inline updates):
        {"date_of_birth": "1990-01-01", "email": "test@test.com"}
        →
        {"basic_info": {"dob": "1990-01-01"}, "contact": {"email": "test@test.com"}}
    """
    normalized: Dict[str, dict] = {
        "basic_info": {},
        "contact": {},
        "identity": {},
        "education": {},
    }
    errors: List[str] = []

    # Detect if payload is already sectioned or flat
    sections = ["basic_info", "contact", "identity", "education"]
    is_sectioned = any(
        isinstance(payload.get(s), dict) for s in sections
    )

    if is_sectioned:
        # Sectioned payload — iterate each section
        for section_name in sections:
            section_data = payload.get(section_name, {})
            if not isinstance(section_data, dict):
                continue
            for raw_key, raw_value in section_data.items():
                _map_single_field(raw_key, raw_value, normalized, errors)
    else:
        # Flat payload — map each key
        for raw_key, raw_value in payload.items():
            if raw_key in sections:
                continue  # skip section names themselves
            _map_single_field(raw_key, raw_value, normalized, errors)

    # Post-processing: compound address fields
    _resolve_compound_address(normalized)

    # Post-processing: auto-derive first/last from full_name if not provided
    basic = normalized["basic_info"]
    if basic.get("full_name") and not basic.get("first_name"):
        parts = split_full_name(basic["full_name"])
        for k, v in parts.items():
            if v and k not in basic:
                basic[k] = v

    # Log
    total_fields = sum(len(v) for v in normalized.values())
    logger.info(f"[Normalize] {total_fields} canonical fields, {len(errors)} errors")
    if errors:
        for e in errors:
            logger.warning(f"[Normalize] {e}")

    return normalized, errors


def _map_single_field(
    raw_key: str,
    raw_value,
    normalized: Dict[str, dict],
    errors: List[str],
) -> None:
    """Map a single raw key/value to the correct section and canonical key."""
    if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
        return

    value = str(raw_value).strip()

    # Look up alias
    lookup = FIELD_ALIAS_MAP.get(raw_key)
    if not lookup:
        # Try lowercase
        lookup = FIELD_ALIAS_MAP.get(raw_key.lower())
    if not lookup:
        # Try camelCase → snake_case conversion
        snake = re.sub(r'([A-Z])', r'_\1', raw_key).lower().strip('_')
        lookup = FIELD_ALIAS_MAP.get(snake)

    if not lookup:
        # Unknown key — log and skip
        logger.debug(f"[Normalize] Unknown field key '{raw_key}', skipping")
        return

    section, canonical_key = lookup

    # Special handling for aadhaar
    if canonical_key == "aadhaar_last4":
        value = truncate_aadhaar(value)

    normalized[section][canonical_key] = value


def _resolve_compound_address(normalized: Dict[str, dict]) -> None:
    """Merge _address_line1 + _address_line2 into address."""
    contact = normalized.get("contact", {})
    line1 = contact.pop("_address_line1", "")
    line2 = contact.pop("_address_line2", "")

    if line1 or line2:
        parts = [p for p in [line1, line2] if p]
        compound = ", ".join(parts)
        # Only override if no direct address was set
        if not contact.get("address"):
            contact["address"] = compound


# ---------------------------------------------------------------------------
# Section membership check
# ---------------------------------------------------------------------------

# Valid keys per section (for safe setattr)
VALID_SECTION_KEYS: Dict[str, Set[str]] = {
    "basic_info": {
        "full_name", "first_name", "middle_name", "last_name",
        "dob", "gender", "nationality", "father_name", "mother_name",
        "address", "city", "state", "pincode",
    },
    "contact": {
        "email", "phone", "alternate_phone",
        "address", "city", "state", "pincode", "country",
    },
    "identity": {
        "aadhaar_last4", "pan_number", "voter_id",
        "passport_number", "driving_license",
    },
    "education": {
        "highest_qualification", "college", "university", "year_of_passing",
    },
}


def get_valid_keys_for_section(section: str) -> Set[str]:
    """Return the set of valid canonical keys for a given section."""
    return VALID_SECTION_KEYS.get(section, set())


# ---------------------------------------------------------------------------
# Flat → sectioned helper (for confirm-data inline updates)
# ---------------------------------------------------------------------------

def route_flat_fields_to_sections(flat_fields: dict) -> dict:
    """
    Given a flat dict of canonical field values, route them to the correct
    profile sections.

    Example:
        {"dob": "1990-01-01", "email": "test@test.com", "pan_number": "ABCDE1234F"}
        →
        {
            "basic_info": {"dob": "1990-01-01"},
            "contact": {"email": "test@test.com"},
            "identity": {"pan_number": "ABCDE1234F"},
            "education": {}
        }
    """
    sectioned = {s: {} for s in VALID_SECTION_KEYS}

    for key, value in flat_fields.items():
        if not value or is_sensitive_field(key):
            continue
        placed = False
        for section, valid_keys in VALID_SECTION_KEYS.items():
            if key in valid_keys:
                sectioned[section][key] = value
                placed = True
                break
        if not placed:
            # Try alias map
            lookup = FIELD_ALIAS_MAP.get(key)
            if lookup:
                section, canon = lookup
                if not canon.startswith("_"):
                    sectioned[section][canon] = value

    return sectioned
