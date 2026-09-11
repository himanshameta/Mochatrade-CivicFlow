"""
Enhanced Profile to Form Mapper
=================================
Two-stage mapping: Deterministic first, then LLM fallback for ambiguous fields.
"""
import re
import json
from typing import Dict, List, Tuple, Optional
from models.review_schema import ReviewFormField, FieldOption


def canonicalize_key(s: str) -> str:
    """Normalize field key."""
    if not s:
        return ""
    v = s.lower().strip()
    v = re.sub(r'[-\s]+', '_', v)
    v = re.sub(r'[^a-z0-9_]', '', v)
    v = re.sub(r'_+', '_', v)
    return v.strip('_')


def compute_stable_field_key(field_dict: Dict) -> str:
    """Compute stable key for field."""
    return (field_dict.get('name') or 
            field_dict.get('field_id') or 
            field_dict.get('id_attr') or
            canonicalize_key(field_dict.get('label', 'unnamed_field')))


def get_alias_map() -> Dict[str, List[str]]:
    """Return canonical alias map."""
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
    """Build reverse mapping: alias -> canonical."""
    alias_map = get_alias_map()
    reverse = {}
    for canonical, aliases in alias_map.items():
        for alias in aliases:
            reverse[alias] = canonical
    return reverse


def split_full_name(name: str) -> Tuple[str, str]:
    """Split full name into first and last."""
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
    """Extract last 10 digits."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', str(phone))
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_email(email: str) -> str:
    """Lowercase email."""
    if not email:
        return ""
    return str(email).lower().strip()


def match_value_to_options(value: str, options: List[Dict]) -> Optional[str]:
    """Match profile value to field options."""
    if not value or not options:
        return None
    
    value_lower = str(value).lower().strip()
    
    # Try exact match on value
    for opt in options:
        opt_val = opt.get('value', '')
        if opt_val.lower() == value_lower:
            return opt_val
    
    # Try exact match on label
    for opt in options:
        opt_label = opt.get('label', '')
        if opt_label.lower() == value_lower:
            return opt.get('value', opt_label)
    
    # Try partial match on label
    for opt in options:
        opt_label = opt.get('label', '')
        if value_lower in opt_label.lower() or opt_label.lower() in value_lower:
            return opt.get('value', opt_label)
    
    return None


def deterministic_field_mapping(field_dict: Dict, profile: Dict) -> Tuple[Optional[str], Optional[str], float]:
    """
    Deterministic field mapping using alias matching.
    
    Returns:
        (matched_profile_key, matched_value, confidence)
    """
    reverse_map = build_reverse_alias_map()
    field_type = field_dict.get('field_type', 'text')
    options = field_dict.get('options', [])
    
    # Get candidate keys from field metadata
    candidates = []
    for attr in ['name', 'label', 'field_id', 'id_attr', 'placeholder']:
        val = field_dict.get(attr)
        if val:
            canon = canonicalize_key(str(val))
            if canon and canon not in candidates:
                candidates.append(canon)
    
    if not candidates:
        return None, None, 0.0
    
    # Strategy 1: Exact alias match
    for candidate in candidates:
        canonical = reverse_map.get(candidate)
        if canonical and canonical in profile:
            value = profile[canonical]
            
            # Handle choice fields
            if field_type in ['select', 'radio'] and options:
                matched_option = match_value_to_options(value, options)
                if matched_option:
                    return canonical, matched_option, 1.0
                else:
                    # Profile has value but no matching option
                    return canonical, None, 0.5
            
            return canonical, value, 1.0
    
    # Strategy 2: Direct key match in profile
    for candidate in candidates:
        if candidate in profile:
            value = profile[candidate]
            
            if field_type in ['select', 'radio'] and options:
                matched_option = match_value_to_options(value, options)
                if matched_option:
                    return candidate, matched_option, 0.9
            
            return candidate, value, 0.9
    
    # Strategy 3: Name splitting
    for candidate in candidates:
        canonical = reverse_map.get(candidate)
        
        if canonical == 'first_name' and 'name' in profile:
            first, _ = split_full_name(profile['name'])
            if first:
                return 'name', first, 0.95
        
        if canonical == 'last_name' and 'name' in profile:
            _, last = split_full_name(profile['name'])
            if last:
                return 'name', last, 0.95
        
        if canonical == 'name':
            if 'first_name' in profile and 'last_name' in profile:
                full = f"{profile['first_name']} {profile['last_name']}".strip()
                return 'name', full, 0.95
            elif 'first_name' in profile:
                return 'first_name', profile['first_name'], 0.8
    
    # Strategy 4: Token overlap (partial match)
    best_match = None
    best_score = 0.0
    
    for candidate in candidates:
        candidate_tokens = set(candidate.split('_'))
        
        for profile_key, profile_value in profile.items():
            if not profile_value:
                continue
            
            profile_tokens = set(profile_key.split('_'))
            overlap = len(candidate_tokens & profile_tokens)
            
            if overlap > 0:
                score = overlap / max(len(candidate_tokens), len(profile_tokens))
                if score > best_score and score >= 0.5:
                    best_score = score * 0.7  # Reduce confidence for partial match
                    best_match = (profile_key, profile_value)
    
    if best_match:
        return best_match[0], best_match[1], best_score
    
    return None, None, 0.0


async def llm_field_mapping(unmatched_fields: List[Dict], profile: Dict) -> Dict[str, Tuple[Optional[str], Optional[str], float]]:
    """
    LLM fallback for ambiguous fields.
    
    Args:
        unmatched_fields: List of field dicts that had no deterministic match
        profile: User profile dict
        
    Returns:
        Dict mapping field_key -> (matched_profile_key, value, confidence)
    """
    if not unmatched_fields:
        return {}
    
    try:
        from utils.llm import get_llm_client
        
        llm = get_llm_client()
        if not llm.api_key:
            print("[LLM Mapper] No API key, skipping LLM mapping")
            return {}
        
        # Build prompt
        fields_summary = []
        for field in unmatched_fields:
            fields_summary.append({
                "key": field.get('key'),
                "label": field.get('label'),
                "name": field.get('name'),
                "placeholder": field.get('placeholder'),
                "field_type": field.get('field_type'),
                "options": [opt.get('label') for opt in field.get('options', [])][:5]  # Limit to 5 options
            })
        
        prompt = f"""You are mapping a user's profile to web form fields.

User Profile:
{json.dumps(profile, indent=2)}

Unmatched Form Fields:
{json.dumps(fields_summary, indent=2)}

Return ONLY a JSON array with this exact structure:
[
  {{
    "field_key": "...",
    "matched_profile_key": "... or null",
    "value": "... or null",
    "confidence": 0.0-1.0,
    "reason": "short explanation"
  }}
]

Rules:
- Do not invent values
- If not confident, return null for value
- For select/radio fields, choose ONLY from provided options
- For first_name/last_name, you may split from full name if needed
- Preserve user data faithfully
- Do not return values with confidence < 0.75
"""
        
        response = await llm.generate_content(
            prompt=prompt,
            temperature=0.1,
            max_tokens=2000
        )
        
        # Parse response
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        mappings = json.loads(response.strip())
        
        # Convert to result format
        result = {}
        for mapping in mappings:
            field_key = mapping.get('field_key')
            confidence = mapping.get('confidence', 0.0)
            
            # Only accept high confidence mappings
            if confidence >= 0.75:
                result[field_key] = (
                    mapping.get('matched_profile_key'),
                    mapping.get('value'),
                    confidence
                )
        
        print(f"[LLM Mapper] Mapped {len(result)}/{len(unmatched_fields)} fields")
        return result
        
    except Exception as e:
        print(f"[LLM Mapper] Error: {e}")
        return {}


async def map_profile_to_form_schema(scraped_form: Dict, user_profile: Dict) -> List[ReviewFormField]:
    """
    Main mapping function: Deterministic first, then LLM fallback.
    
    Args:
        scraped_form: Scraped form dict with fields
        user_profile: User profile dict from DB
        
    Returns:
        List of ReviewFormField with mapped values
    """
    fields = scraped_form.get('fields', [])
    review_fields = []
    unmatched_fields = []
    
    print(f"[Mapper] Mapping {len(fields)} fields to profile with {len(user_profile)} keys")
    
    # Stage 1: Deterministic mapping
    for field_dict in fields:
        stable_key = compute_stable_field_key(field_dict)
        
        # Normalize options
        raw_options = field_dict.get('options', [])
        normalized_options = []
        for opt in raw_options:
            if isinstance(opt, dict):
                normalized_options.append(FieldOption(
                    label=opt.get('label', opt.get('value', '')),
                    value=opt.get('value', opt.get('label', ''))
                ))
            else:
                normalized_options.append(FieldOption(label=str(opt), value=str(opt)))
        
        # Try deterministic mapping
        matched_key, matched_value, confidence = deterministic_field_mapping(field_dict, user_profile)
        
        if confidence >= 0.8 and matched_value:
            # High confidence match
            review_fields.append(ReviewFormField(
                key=stable_key,
                name=field_dict.get('name', ''),
                label=field_dict.get('label', ''),
                field_type=field_dict.get('field_type', 'text'),
                required=field_dict.get('required', False),
                placeholder=field_dict.get('placeholder', ''),
                options=normalized_options,
                value=str(matched_value),
                matched_profile_key=matched_key,
                source="db",
                order=field_dict.get('order', 0),
                section=field_dict.get('section', '')
            ))
        else:
            # No match or low confidence - collect for LLM
            review_field = ReviewFormField(
                key=stable_key,
                name=field_dict.get('name', ''),
                label=field_dict.get('label', ''),
                field_type=field_dict.get('field_type', 'text'),
                required=field_dict.get('required', False),
                placeholder=field_dict.get('placeholder', ''),
                options=normalized_options,
                value="",
                matched_profile_key=None,
                source="none",
                order=field_dict.get('order', 0),
                section=field_dict.get('section', '')
            )
            review_fields.append(review_field)
            
            # Add to unmatched list for LLM
            unmatched_fields.append({
                'key': stable_key,
                'label': field_dict.get('label', ''),
                'name': field_dict.get('name', ''),
                'placeholder': field_dict.get('placeholder', ''),
                'field_type': field_dict.get('field_type', 'text'),
                'options': [{'label': opt.label, 'value': opt.value} for opt in normalized_options]
            })
    
    print(f"[Mapper] Deterministic: {len(review_fields) - len(unmatched_fields)} matched, {len(unmatched_fields)} unmatched")
    
    # Stage 2: LLM fallback for unmatched fields
    if unmatched_fields:
        llm_mappings = await llm_field_mapping(unmatched_fields, user_profile)
        
        # Apply LLM mappings
        for review_field in review_fields:
            if review_field.key in llm_mappings:
                matched_key, matched_value, confidence = llm_mappings[review_field.key]
                if matched_value:
                    review_field.value = str(matched_value)
                    review_field.matched_profile_key = matched_key
                    review_field.source = "llm"
        
        print(f"[Mapper] LLM: {len(llm_mappings)} additional matches")
    
    # Sort by order to preserve original field sequence
    review_fields.sort(key=lambda f: f.order)
    
    return review_fields
