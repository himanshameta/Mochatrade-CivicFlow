"""
Generic Profile to Form Field Mapper
=====================================
Maps user profile data to arbitrary web form fields using semantic matching.
Works for any form (government, registration, contact, application, etc.)
"""
import re
from typing import Dict, List, Tuple, Optional


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
        "father_name": ["father_name", "fathers_name", "father"]
    }


def build_reverse_alias_map() -> Dict[str, str]:
    """Build reverse mapping: alias -> canonical profile key."""
    alias_map = get_alias_map()
    reverse = {}
    for canonical, aliases in alias_map.items():
        for alias in aliases:
            reverse[alias] = canonical
    return reverse


def split_full_name(name: str) -> Tuple[str, str]:
    """Split full name into first and last name."""
    if not name:
        return "", ""
    parts = str(name).strip().split()
    if len(parts) == 0:
        return "", ""
    elif len(parts) == 1:
        return parts[0], ""
    else:
        return parts[0], " ".join(parts[1:])


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
            first, _ = split_full_name(profile['name'])
            return 'name', first if first else None
        
        if canonical == 'last_name' and 'name' in profile:
            _, last = split_full_name(profile['name'])
            return 'name', last if last else None
        
        if canonical == 'name':
            if 'first_name' in profile and 'last_name' in profile:
                full = f"{profile['first_name']} {profile['last_name']}".strip()
                return 'name', full
            elif 'first_name' in profile:
                return 'first_name', profile['first_name']
    
    return None, None


async def get_flat_user_profile(user_id: str) -> Dict:
    """
    Fetch and flatten user profile from MongoDB.
    Includes basic_info, documents OCR data, and any extra fields.
    """
    try:
        from db.mongo import get_db
        
        db = await get_db()
        if db is None:
            return {}
        
        profile_doc = await db.user_profiles.find_one({"user_id": user_id})
        
        if not profile_doc:
            return {}
        
        flat_profile = {}
        
        # Merge basic_info
        if 'basic_info' in profile_doc:
            basic = profile_doc['basic_info']
            if isinstance(basic, dict):
                flat_profile.update(basic)
        
        # Merge contact info
        if 'contact' in profile_doc:
            contact = profile_doc['contact']
            if isinstance(contact, dict):
                flat_profile.update(contact)
        
        # Merge uploaded_documents OCR fields
        if 'uploaded_documents' in profile_doc:
            docs = profile_doc['uploaded_documents']
            if isinstance(docs, list):
                for doc in docs:
                    if isinstance(doc, dict) and 'ocr_extracted_fields' in doc:
                        ocr_fields = doc['ocr_extracted_fields']
                        if isinstance(ocr_fields, dict):
                            flat_profile.update(ocr_fields)
        
        # Normalize
        normalized = normalize_profile_data(flat_profile)
        
        print(f"[FieldMapper] Loaded profile keys: {list(normalized.keys())}")
        
        return normalized
        
    except Exception as e:
        print(f"[FieldMapper] Error loading profile: {e}")
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
        
        if matched_value:
            pre_filled_values[stable_key] = matched_value
        elif field_dict.get('required'):
            missing_fields.append(field_dict.get('label') or stable_key)
            
    return pre_filled_values, missing_fields

__all__ = [
    "canonicalize_key", "get_alias_map", "build_reverse_alias_map",
    "split_full_name", "normalize_phone", "normalize_email", "normalize_gender",
    "normalize_pincode", "normalize_profile_data", "get_candidate_field_keys",
    "compute_stable_field_key", "match_value_to_options", "match_profile_value_to_field",
    "get_flat_user_profile", "compute_missing_required_fields", "map_profile_to_fields"
]

