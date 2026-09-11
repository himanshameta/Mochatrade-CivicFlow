"""
Generic Profile to Form Field Mapper
=====================================
Maps user profile data to arbitrary web form fields using semantic matching.
Works for any form (government, registration, contact, application, etc.)
"""
import re
from typing import Dict, List, Tuple, Optional, Any

def normalize_mapped_value_for_storage(value: Any) -> str:
    """
    Convert mapped field value into a scalar value for session/models/executor.
    Rules:
    - if value is None -> ""
    - if value is str/int/float/bool -> string form
    - if value is dict and has "value" -> return value["value"]
    - else if value is dict and has "label" -> return value["label"]
    - if value is list of dicts -> map each entry to its scalar value
    - if value is list of scalars -> join depending on target model
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("value", value.get("label", "")))
    if isinstance(value, list):
        normalized_list = []
        for item in value:
            if isinstance(item, dict):
                normalized_list.append(str(item.get("value", item.get("label", ""))))
            else:
                normalized_list.append(str(item))
        return ", ".join(normalized_list)
    return str(value)


def normalize_example_value(value: Any) -> str:
    """
    Return a user-friendly string for display in UserDataItem.example.
    For dict option -> use label first, then value
    For list -> comma-separated string
    For scalar -> string(value)
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("label", value.get("value", "")))
    if isinstance(value, list):
        normalized_list = []
        for item in value:
            if isinstance(item, dict):
                normalized_list.append(str(item.get("label", item.get("value", ""))))
            else:
                normalized_list.append(str(item))
        return ", ".join(normalized_list)
    return str(value)

def canonicalize_key(s: str) -> str:
    """Normalize field key: lowercase, strip, collapse underscores."""
    if not s:
        return ""
    v = s.lower().strip()
    v = re.sub(r'[-\s]+', '_', v)
    v = re.sub(r'[^a-z0-9_]', '', v)
    v = re.sub(r'_+', '_', v)
    return v.strip('_')


def get_alias_map() -> Dict[str, List[str]]:
    """Return canonical alias map for common profile fields."""
    return {
        "name": ["name", "full_name", "fullname", "applicant_name", "candidate_name"],
        "first_name": ["first_name", "firstname", "given_name", "givenname"],
        "middle_name": ["middle_name", "middlename", "middle"],
        "last_name": ["last_name", "lastname", "surname", "family_name"],
        "email": ["email", "email_id", "emailaddress", "email_address", "mail"],
        "phone": ["phone", "mobile", "mobile_number", "mobileno", "phone_number", "contact", "tel"],
        "dob": ["dob", "date_of_birth", "dateofbirth", "birth_date", "birthdate"],
        "gender": ["gender", "sex"],
        "address": ["address", "full_address", "street_address", "current_address", "permanent_address"],
        "city": ["city", "town"],
        "state": ["state", "province", "region"],
        "pincode": ["pincode", "pin", "pin_code", "postal_code", "postcode", "zip", "zipcode"],
        "country": ["country", "nation"],
        "pan_number": ["pan", "pan_number", "pan_no", "pannumber"],
        "aadhaar_last4": ["aadhaar", "aadhaar_number", "aadhaar_no", "aadhaar_last4"],
        "passport_number": ["passport", "passport_number", "passport_no"],
        "father_name": ["father_name", "fathers_name", "father"],
        "mother_name": ["mother_name", "mothers_name", "mother"],
    }


def build_reverse_alias_map() -> Dict[str, str]:
    """Build reverse mapping: alias -> canonical profile key."""
    alias_map = get_alias_map()
    reverse = {}
    for canonical, aliases in alias_map.items():
        for alias in aliases:
            reverse[alias] = canonical
    return reverse


def split_full_name(name: str) -> Dict[str, str]:
    """Split full name into first, middle, and last name.
    
    Rules:
    - 1 token:  first_name only
    - 2 tokens: first_name + last_name
    - 3+ tokens: first_name + middle_name + last_name
    
    Returns dict with first_name, middle_name, last_name keys.
    Also returns a (first, last) tuple via indexing for backward compat.
    """
    if not name:
        return {"first_name": "", "middle_name": "", "last_name": ""}
    parts = str(name).strip().split()
    if len(parts) == 0:
        return {"first_name": "", "middle_name": "", "last_name": ""}
    elif len(parts) == 1:
        return {"first_name": parts[0], "middle_name": "", "last_name": ""}
    elif len(parts) == 2:
        return {"first_name": parts[0], "middle_name": "", "last_name": parts[1]}
    else:
        return {
            "first_name": parts[0],
            "middle_name": " ".join(parts[1:-1]),
            "last_name": parts[-1],
        }


def normalize_phone(phone: str) -> str:
    """Extract last 10 digits from phone."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', str(phone))
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_email(email: str) -> str:
    """Lowercase and strip email."""
    if not email:
        return ""
    return str(email).lower().strip()


def normalize_gender(gender: str) -> str:
    """Normalize gender to Male/Female/Other."""
    if not gender:
        return ""
    g = str(gender).lower().strip()
    if g in ['m', 'male', 'man']:
        return "Male"
    elif g in ['f', 'female', 'woman']:
        return "Female"
    else:
        return "Other"


def normalize_pincode(pincode: str) -> str:
    """Extract digits only from pincode."""
    if not pincode:
        return ""
    return re.sub(r'\D', '', str(pincode))


def normalize_profile_data(profile: Dict) -> Dict:
    """Canonicalize profile keys and normalize common values."""
    normalized = {}
    reverse_map = build_reverse_alias_map()
    
    for key, value in profile.items():
        if not value:
            continue
        
        canon_key = canonicalize_key(key)
        mapped_key = reverse_map.get(canon_key, canon_key)
        
        # Normalize value based on field type
        if mapped_key == 'phone':
            value = normalize_phone(value)
        elif mapped_key == 'email':
            value = normalize_email(value)
        elif mapped_key == 'gender':
            value = normalize_gender(value)
        elif mapped_key == 'pincode':
            value = normalize_pincode(value)
        
        if value:
            normalized[mapped_key] = value
    
    return normalized


def get_candidate_field_keys(field_dict: Dict) -> List[str]:
    """Extract candidate keys from scraped field metadata."""
    candidates = []
    for attr in ['name', 'label', 'field_id', 'id_attr', 'placeholder']:
        val = field_dict.get(attr)
        if val:
            canon = canonicalize_key(str(val))
            if canon and canon not in candidates:
                candidates.append(canon)
    return candidates


def compute_stable_field_key(field_dict: Dict) -> str:
    """Compute stable key for field (used for pre_filled_values)."""
    return (field_dict.get('name') or 
            field_dict.get('field_id') or 
            field_dict.get('id_attr') or
            canonicalize_key(field_dict.get('label', 'unnamed_field')))


def match_value_to_options(value: str, options: List) -> Optional[str]:
    """Match a profile value to the closest option in a select/radio field."""
    if not value or not options:
        return None
    
    value_lower = str(value).lower().strip()
    
    # Handle both string options and dict options (normalized format)
    def get_option_value(opt):
        if isinstance(opt, str):
            return opt
        elif isinstance(opt, dict):
            return opt.get('value', opt.get('label', ''))
        return str(opt)
    
    def get_option_label(opt):
        if isinstance(opt, str):
            return opt
        elif isinstance(opt, dict):
            return opt.get('label', opt.get('value', ''))
        return str(opt)
    
    # Try exact match on value first
    for opt in options:
        opt_val = get_option_value(opt)
        if opt_val.lower() == value_lower:
            return opt_val
    
    # Try exact match on label
    for opt in options:
        opt_label = get_option_label(opt)
        if opt_label.lower() == value_lower:
            return get_option_value(opt)
    
    # Try partial match on value
    for opt in options:
        opt_val = get_option_value(opt)
        if value_lower in opt_val.lower() or opt_val.lower() in value_lower:
            return opt_val
    
    # Try partial match on label
    for opt in options:
        opt_label = get_option_label(opt)
        if value_lower in opt_label.lower() or opt_label.lower() in value_lower:
            return get_option_value(opt)
    
    return None


def match_profile_value_to_field(field_dict: Dict, profile: Dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Match a scraped field to profile data using intelligent aliasing.
    
    Returns:
        (matched_profile_key, matched_value) or (None, None)
    """
    candidates = get_candidate_field_keys(field_dict)
    reverse_map = build_reverse_alias_map()
    field_type = field_dict.get('field_type', 'text')
    options = field_dict.get('options', [])
    
    if not candidates:
        return None, None
    
    # Strategy 1: Exact alias match
    for candidate in candidates:
        canonical = reverse_map.get(candidate)
        if canonical and canonical in profile:
            value = profile[canonical]
            # Handle choice fields with options
            if field_type in ['select', 'radio'] and options:
                matched_option = match_value_to_options(value, options)
                return canonical, matched_option if matched_option else value
            return canonical, value
    
    # Strategy 2: Direct key match
    for candidate in candidates:
        if candidate in profile:
            value = profile[candidate]
            if field_type in ['select', 'radio'] and options:
                matched_option = match_value_to_options(value, options)
                return candidate, matched_option if matched_option else value
            return candidate, value
    
    # Strategy 3: Name splitting
    for candidate in candidates:
        canonical = reverse_map.get(candidate)
        
        if canonical == 'first_name' and 'name' in profile:
            name_parts = split_full_name(profile['name'])
            first = name_parts["first_name"]
            return 'name', first if first else None
        
        if canonical == 'middle_name' and 'name' in profile:
            name_parts = split_full_name(profile['name'])
            middle = name_parts["middle_name"]
            return 'name', middle if middle else None
        
        if canonical == 'last_name' and 'name' in profile:
            name_parts = split_full_name(profile['name'])
            last = name_parts["last_name"]
            return 'name', last if last else None
        
        if canonical == 'name':
            if 'first_name' in profile and 'last_name' in profile:
                middle = profile.get('middle_name', '')
                parts = [profile['first_name'], middle, profile['last_name']]
                full = " ".join(p for p in parts if p).strip()
                return 'name', full
            elif 'first_name' in profile:
                return 'first_name', profile['first_name']
    
    return None, None


async def get_flat_user_profile(user_id: str) -> Dict:
    """
    Fetch, decrypt, and flatten user profile from MongoDB.

    Decrypts AES-256-GCM encrypted fields (full_name, dob, address, phone, pan_number)
    and validates all values for human readability before returning.
    Rejects ciphertext-like or non-readable values silently.
    """
    try:
        from db.mongo import get_db
        from utils.encryption import (
            decrypt_dict_fields,
            ENCRYPTED_BASIC_FIELDS,
            ENCRYPTED_CONTACT_FIELDS,
            ENCRYPTED_IDENTITY_FIELDS,
        )
        from utils.field_validation import is_human_readable_field_value

        db = await get_db()
        if db is None:
            return {}

        profile_doc = await db.user_profiles.find_one({"user_id": user_id})

        if not profile_doc:
            return {}

        flat_profile = {}

        # Decrypt and merge basic_info
        if 'basic_info' in profile_doc:
            basic = profile_doc['basic_info']
            if isinstance(basic, dict):
                decrypted = decrypt_dict_fields(basic, user_id, ENCRYPTED_BASIC_FIELDS)
                flat_profile.update(decrypted)
                print(f"[FieldMapper] Decrypted basic_info fields: {list(decrypted.keys())}")

        # Decrypt and merge contact info
        if 'contact' in profile_doc:
            contact = profile_doc['contact']
            if isinstance(contact, dict):
                decrypted = decrypt_dict_fields(contact, user_id, ENCRYPTED_CONTACT_FIELDS)
                flat_profile.update(decrypted)

        # Decrypt and merge identity info
        if 'identity' in profile_doc:
            identity = profile_doc['identity']
            if isinstance(identity, dict):
                decrypted = decrypt_dict_fields(identity, user_id, ENCRYPTED_IDENTITY_FIELDS)
                flat_profile.update(decrypted)

        # Education (not encrypted)
        if 'education' in profile_doc:
            education = profile_doc['education']
            if isinstance(education, dict):
                flat_profile.update(education)

        # Merge uploaded_documents OCR fields — only if human-readable
        if 'uploaded_documents' in profile_doc:
            docs = profile_doc['uploaded_documents']
            if isinstance(docs, list):
                for doc in docs:
                    if isinstance(doc, dict) and 'ocr_extracted_fields' in doc:
                        ocr_fields = doc['ocr_extracted_fields']
                        if isinstance(ocr_fields, dict):
                            # Attempt decryption of OCR fields
                            try:
                                decrypted_ocr = decrypt_dict_fields(
                                    ocr_fields, user_id, list(ocr_fields.keys())
                                )
                            except Exception:
                                decrypted_ocr = ocr_fields
                            for key, val in decrypted_ocr.items():
                                if is_human_readable_field_value(val, "text", key):
                                    flat_profile[key] = val
                                else:
                                    print(f"[FieldMapper] Rejected OCR field '{key}': not human-readable")

        # Filter out any remaining ciphertext-like values
        clean_profile = {}
        for key, val in flat_profile.items():
            if val and is_human_readable_field_value(val, "text", key):
                clean_profile[key] = val
            elif val:
                print(f"[FieldMapper] Rejected field '{key}': value failed readability check")

        # Normalize
        normalized = normalize_profile_data(clean_profile)

        print(f"[FieldMapper] Loaded {len(normalized)} clean profile keys: {list(normalized.keys())}")

        return normalized

    except Exception as e:
        print(f"[FieldMapper] Error loading profile: {e}")
        import traceback
        traceback.print_exc()
        return {}


def compute_missing_required_fields(scraped_form: Dict, pre_filled_values: Dict) -> List[Dict]:
    """
    Compute list of required fields that are still missing values.
    
    Returns:
        List of dicts with name, label, field_type
    """
    missing = []
    
    fields = scraped_form.get('fields', [])
    
    for field in fields:
        field_dict = field if isinstance(field, dict) else getattr(field, 'model_dump', lambda: {})()
        
        stable_key = compute_stable_field_key(field_dict)
        is_required = field_dict.get('required', False)
        current_value = pre_filled_values.get(stable_key, '').strip() if pre_filled_values.get(stable_key) else ''
        
        if is_required and not current_value:
            missing.append({
                'name': stable_key,
                'label': field_dict.get('label', stable_key),
                'field_type': field_dict.get('field_type', 'text')
            })
    
    return missing

def map_profile_to_fields(fields_list: List[Dict], profile: Dict) -> Tuple[Dict, List]:
    """
    Backward-compatible wrapper for analyst.py.
    """
    pre_filled_values = {}
    missing_fields = []
    
    for field_dict in fields_list:
        matched_key, matched_value = match_profile_value_to_field(field_dict, profile)
        stable_key = compute_stable_field_key(field_dict)
        
        if matched_value is not None and matched_value != "":
            pre_filled_values[stable_key] = normalize_mapped_value_for_storage(matched_value)
        elif field_dict.get('required'):
            missing_fields.append(field_dict.get('label') or stable_key)
            
    return pre_filled_values, missing_fields

__all__ = [
    "normalize_mapped_value_for_storage", "normalize_example_value",
    "canonicalize_key", "get_alias_map", "build_reverse_alias_map",
    "split_full_name", "normalize_phone", "normalize_email", "normalize_gender",
    "normalize_pincode", "normalize_profile_data", "get_candidate_field_keys",
    "compute_stable_field_key", "match_value_to_options", "match_profile_value_to_field",
    "get_flat_user_profile", "compute_missing_required_fields", "map_profile_to_fields"
]

