"""
CivicFlow — Profile to Form Field Mapper
==========================================
Fetches user profile from MongoDB and maps it to form fields.
"""
import logging
from typing import Optional

logger = logging.getLogger("civicflow.profile_mapper")


async def get_user_profile_for_pipeline(user_id: str) -> dict:
    """
    Fetch and decrypt user profile for use in pipeline.
    
    Args:
        user_id: User ID to fetch profile for
        
    Returns:
        Flat dictionary of profile fields
    """
    from db.mongo import get_db
    from utils.encryption import decrypt_dict_fields
    
    db = await get_db()
    if db is None:
        logger.warning("MongoDB not available, returning empty profile")
        return {}
    
    profile = await db.user_profiles.find_one({"user_id": user_id})
    if not profile:
        logger.info(f"No profile found for user {user_id}")
        return {}
    
    # Collect all confirmed document fields
    flat_profile = {}
    
    for doc in profile.get("uploaded_documents", []):
        enc_fields = doc.get("ocr_extracted_fields", {})
        if enc_fields:
            try:
                decrypted = decrypt_dict_fields(
                    enc_fields,
                    user_id,
                    list(enc_fields.keys())
                )
                flat_profile.update(decrypted)
            except Exception as e:
                logger.warning(f"Could not decrypt fields for doc {doc.get('doc_id')}: {e}")
    
    # Also include top-level profile fields if stored
    for section_key in ["basic_info", "contact", "identity", "education"]:
        section = profile.get(section_key, {})
        if isinstance(section, dict):
            flat_profile.update(section)
    
    logger.info(f"Loaded profile for user {user_id}: {len(flat_profile)} fields")
    return flat_profile


def map_profile_to_form(form_fields: list, user_profile: dict) -> tuple[dict, list[str]]:
    """
    Map user profile data to form fields.
    
    Args:
        form_fields: List of FormField objects or dicts
        user_profile: Flat dict of user profile data
        
    Returns:
        Tuple of (pre_filled dict, missing_fields list)
        - pre_filled: {field_name: value} for fields we can fill
        - missing: [field_label] for required fields we can't fill
    """
    # Semantic mapping: form field names/labels → profile keys
    FIELD_MAP = {
        # Name variants
        "firstname": "full_name", "first_name": "full_name",
        "lastname": "full_name", "last_name": "full_name",
        "fullname": "full_name", "full_name": "full_name",
        "name": "full_name", "applicantname": "full_name",
        
        # DOB variants
        "dob": "dob", "dateofbirth": "dob",
        "date_of_birth": "dob", "birthdate": "dob",
        "birth_date": "dob",
        
        # Contact
        "phone": "phone", "mobile": "phone",
        "mobileno": "phone", "phoneno": "phone",
        "phone_number": "phone", "mobile_number": "phone",
        "email": "email", "emailid": "email",
        "email_id": "email",
        
        # Identity
        "pan": "pan_number", "pannumber": "pan_number",
        "pan_number": "pan_number", "panno": "pan_number",
        "aadhaar": "aadhaar_last4", "aadhaarnumber": "aadhaar_last4",
        "aadhaar_number": "aadhaar_last4",
        
        # Address
        "address": "address", "permanentaddress": "address",
        "currentaddress": "address", "residential_address": "address",
        "pincode": "pincode", "pin": "pincode",
        "postalcode": "pincode", "zipcode": "pincode",
        "city": "city", "state": "state",
        
        # Gender
        "gender": "gender", "sex": "gender",
        
        # Father
        "fathername": "father_name", "father_name": "father_name",
        "fathersname": "father_name",
        
        # Nationality
        "nationality": "nationality", "country": "nationality",
    }
    
    pre_filled = {}
    missing = []
    
    for field in form_fields:
        # Handle both dict and object formats
        if isinstance(field, dict):
            field_name = field.get("name", "")
            field_id = field.get("id_attr", "")
            label = field.get("label", "")
            required = field.get("required", False)
            field_type = field.get("field_type", "text")
        else:
            field_name = field.name
            field_id = field.id_attr
            label = field.label
            required = field.required
            field_type = field.field_type
        
        # Skip file upload fields
        if field_type == "file":
            continue
        
        # Try to match by field name, id, and label
        lookup_keys = []
        if field_name:
            lookup_keys.append(field_name.lower().replace("-", "_").replace(" ", "_"))
        if field_id:
            lookup_keys.append(field_id.lower().replace("-", "_").replace(" ", "_"))
        if label:
            # Remove common prefixes and clean label
            clean_label = label.lower().strip()
            for prefix in ["enter", "enter your", "provide", "your"]:
                if clean_label.startswith(prefix):
                    clean_label = clean_label[len(prefix):].strip()
            lookup_keys.append(clean_label.replace("-", "_").replace(" ", "_"))
        
        profile_key = None
        for key in lookup_keys:
            if key in FIELD_MAP:
                profile_key = FIELD_MAP[key]
                break
            # Also try direct match in profile
            if key in user_profile:
                profile_key = key
                break
        
        if profile_key and profile_key in user_profile and user_profile[profile_key]:
            pre_filled[field_name or field_id or label] = str(user_profile[profile_key])
        elif required:
            missing.append(label or field_name or field_id or "Unknown field")
    
    logger.info(f"Profile mapping: {len(pre_filled)} fields pre-filled, {len(missing)} missing")
    return pre_filled, missing
