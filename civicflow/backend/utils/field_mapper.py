"""
Generic field mapper for robust profile-to-form matching.
Handles aliasing, normalization, name splitting, phone/email formats.
"""
import re
from typing import Optional, Dict, List, Tuple


def canonicalize_key(value: str) -> str:
    """Normalize field key: lowercase, strip, replace hyphens, remove non-alphanumeric."""
    if not value:
        return ""
    
    # Lowercase and strip
    v = value.lower().strip()
    
    # Replace hyphens/spaces with underscores
    v = re.sub(r'[-\s]+', '_', v)
    
    # Remove non-alphanumeric except underscore
    v = re.sub(r'[^a-z0-9_]', '', v)
    
    # Collapse repeated underscores
    v = re.sub(r'_+', '_', v)
    
    # Strip leading/trailing underscores
    v = v.strip('_')
    
    return v


def get_alias_map() -> Dict[str, List[str]]:
    """Return canonical alias map for common profile fields."""
    return {
        "name": [
            "name", "full_name", "fullname", "applicant_name", "candidate_name",
            "your_name", "person_name", "user_name", "username", "completename"
        ],
        "first_name": [
            "first_name", "firstname", "given_name", "givenname", "fname", "forename"
        ],
        "last_name": [
            "last_name", "lastname", "surname", "family_name", "familyname", "lname"
        ],
        "email": [
            "email", "email_id", "emailid", "email_address", "emailaddress", 
            "mail", "e_mail", "emailid", "mail_id"
        ],
        "phone": [
            "phone", "mobile", "mobile_number", "mobileno", "mobilenumber",
            "phone_number", "phonenumber", "phoneno", "contact_number", 
            "contactnumber", "contact", "telephone", "tel", "cell", "cellphone"
        ],
        "dob": [
            "dob", "date_of_birth", "dateofbirth", "birth_date", "birthdate", "bdate"
        ],
        "gender": [
            "gender", "sex"
        ],
        "address": [
            "address", "full_address", "fulladdress", "street_address", 
            "streetaddress", "current_address", "currentaddress",
            "permanent_address", "permanentaddress", "residential_address",
            "residentialaddress", "addr"
        ],
        "city": [
            "city", "town", "municipality"
        ],
        "state": [
            "state", "province", "region"
        ],
        "pincode": [
            "pincode", "pin_code", "pin", "postal_code", "postalcode", 
            "postcode", "zip", "zipcode", "zip_code"
        ],
        "country": [
            "country", "nation", "nationality"
        ],
        "pan_number": [
            "pan", "pan_number", "pan_no", "pannumber", "panno", "pan_card"
        ],
        "aadhaar_last4": [
            "aadhaar", "aadhar", "aadhaar_number", "aadhaar_no", "aadhaarnumber",
            "aadhaar_last4", "aadhar_last4", "uid"
        ],
        "passport_number": [
            "passport", "passport_number", "passport_no", "passportno", "passportnumber"
        ],
        "father_name": [
            "father_name", "fathers_name", "father", "fathersname", "fathername"
        ],
        "mother_name": [
            "mother_name", "mothers_name", "mother", "mothersname", "mothername"
        ]
    }


def build_reverse_alias_map() -> Dict[str, str]:
    """Build reverse mapping: alias -> canonical profile key."""
    alias_map = get_alias_map()
    reverse = {}
    
    for canonical, aliases in alias_map.items():
        for alias in aliases:
            reverse[alias] = canonical
    
    return reverse


def normalize_phone(phone: str) -> str:
    """Extract last 10 digits from phone."""
    if not phone:
        return ""
    
    digits = re.sub(r'\D', '', str(phone))
    
    # Take last 10 digits (Indian standard)
    if len(digits) >= 10:
        return digits[-10:]
    
    return digits


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
        
        # Canonicalize key
        canon_key = canonicalize_key(key)
        
        # Map to canonical profile key if alias exists
        mapped_key = reverse_map.get(canon_key, canon_key)
        
        # Normalize value based on field type
        if mapped_key in ['phone', 'mobile', 'contact_number']:
            value = normalize_phone(value)
        elif mapped_key == 'email':
            value = normalize_email(value)
        elif mapped_key == 'gender':
            value = normalize_gender(value)
        elif mapped_key == 'pincode':
            value = normalize_pincode(value)
        
        # Store with canonical key
        if value:  # Only store non-empty values
            normalized[mapped_key] = value
    
    return normalized


def get_candidate_field_keys(field_dict: Dict) -> List[str]:
    """Extract candidate keys from scraped field metadata."""
    candidates = []
    
    # Gather from various metadata
    for attr in ['name', 'label', 'field_id', 'id', 'placeholder']:
        val = field_dict.get(attr)
        if val:
            canon = canonicalize_key(str(val))
            if canon and canon not in candidates:
                candidates.append(canon)
    
    return candidates


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


def match_profile_value_to_field(field_dict: Dict, profile: Dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Match a scraped field to profile data using intelligent aliasing.
    
    Returns:
        (matched_profile_key, matched_value) or (None, None)
    """
    candidates = get_candidate_field_keys(field_dict)
    reverse_map = build_reverse_alias_map()
    
    if not candidates:
        return None, None
    
    # Strategy 1: Exact alias match
    for candidate in candidates:
        canonical = reverse_map.get(candidate)
        if canonical and canonical in profile:
            return canonical, profile[canonical]
    
    # Strategy 2: Direct key match (already canonicalized profile)
    for candidate in candidates:
        if candidate in profile:
            return candidate, profile[candidate]
    
    # Strategy 3: Contains-based fuzzy match
    for candidate in candidates:
        for profile_key, profile_value in profile.items():
            if candidate in profile_key or profile_key in candidate:
                return profile_key, profile_value
    
    # Strategy 4: Name splitting logic
    # If field wants first_name but only "name" exists in profile
    for candidate in candidates:
        canonical = reverse_map.get(candidate)
        
        if canonical == 'first_name' and 'name' in profile:
            first, _ = split_full_name(profile['name'])
            return 'name', first
        
        if canonical == 'last_name' and 'name' in profile:
            _, last = split_full_name(profile['name'])
            return 'name', last
        
        # If field wants full name but only first+last exist
        if canonical == 'name':
            if 'first_name' in profile and 'last_name' in profile:
                full = f"{profile['first_name']} {profile['last_name']}".strip()
                return 'name', full
            elif 'first_name' in profile:
                return 'first_name', profile['first_name']
    
    # Strategy 5: Token overlap heuristic (simple scoring)
    best_match = None
    best_score = 0
    
    for candidate in candidates:
        candidate_tokens = set(candidate.split('_'))
        
        for profile_key, profile_value in profile.items():
            profile_tokens = set(profile_key.split('_'))
            
            # Count common tokens
            overlap = len(candidate_tokens & profile_tokens)
            if overlap > best_score:
                best_score = overlap
                best_match = (profile_key, profile_value)
    
    if best_score >= 1:  # At least one token match
        return best_match
    
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
        
        # Fetch user profile
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
        
        # Merge any top-level extra fields
        for key, value in profile_doc.items():
            if key not in ['_id', 'user_id', 'basic_info', 'contact', 
                          'uploaded_documents', 'created_at', 'updated_at']:
                if not isinstance(value, (dict, list)):
                    flat_profile[key] = value
        
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
    
    # Extract fields from scraped_form
    fields = scraped_form.get('fields', [])
    
    for field in fields:
        field_dict = field if isinstance(field, dict) else getattr(field, 'model_dump', lambda: {})()
        
        # Get stable field key
        stable_key = field_dict.get('name') or field_dict.get('field_id') or canonicalize_key(field_dict.get('label', ''))
        
        # Check if required
        is_required = field_dict.get('required', False)
        
        # Check if value exists and non-empty
        current_value = pre_filled_values.get(stable_key, '').strip() if pre_filled_values.get(stable_key) else ''
        
        if is_required and not current_value:
            missing.append({
                'name': stable_key,
                'label': field_dict.get('label', stable_key),
                'field_type': field_dict.get('field_type', 'text')
            })
    
    return missing
