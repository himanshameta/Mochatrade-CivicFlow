import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.form_models import ScrapedForm, UserDataItem


async def analyst(scraped_form: ScrapedForm, user_profile: dict) -> tuple[list[UserDataItem], dict, list]:
    """
    Analyze form fields, map user profile, and identify missing data.
    
    Args:
        scraped_form: The scraped form structure
        user_profile: Flat dict of user profile data
        
    Returns:
        Tuple of (data_requirements, pre_filled_values, missing_fields)
    """
    try:
        import utils.generic_mapper as gm
        print("[Analyst] generic_mapper loaded from:", getattr(gm, '__file__', 'unknown'))
        print("[Analyst] available exports:", [x for x in dir(gm) if "map" in x.lower()])
        from utils.generic_mapper import map_profile_to_fields
    except Exception as e:
        raise RuntimeError(f"Failed to import map_profile_to_fields from utils.generic_mapper: {e}")
    
    fields = scraped_form.fields if hasattr(scraped_form, 'fields') else scraped_form.get('fields', [])
    
    # Convert FormField objects to dicts if needed
    fields_dicts = []
    for f in fields:
        if hasattr(f, 'model_dump'):
            fields_dicts.append(f.model_dump())
        elif isinstance(f, dict):
            fields_dicts.append(f)
        else:
            fields_dicts.append({
                "name": getattr(f, 'name', ''),
                "label": getattr(f, 'label', ''),
                "field_type": getattr(f, 'field_type', 'text'),
                "required": getattr(f, 'required', False),
                "options": getattr(f, 'options', []),
                "field_id": getattr(f, 'field_id', '')
            })
    
    # Map profile to fields
    try:
        pre_filled_values, missing_fields = map_profile_to_fields(fields_dicts, user_profile or {})
    except Exception as e:
        raise RuntimeError(f"Mapping failed in map_profile_to_fields: {e}")
    
    print(f"[Analyst] Scraped fields count: {len(fields_dicts)}")
    print(f"[Analyst] Profile keys available: {len(user_profile or {})}")
    print(f"[Analyst] Mapped {len(pre_filled_values)} fields from profile")
    print(f"[Analyst] Missing {len(missing_fields)} required fields")
    
    # Build UserDataItem list for backwards compatibility
    data_items = []
    for field_dict in fields_dicts:
        field_id = field_dict.get("field_id", "")
        label = field_dict.get("label", "")
        field_type = field_dict.get("field_type", "text")
        options = field_dict.get("options", [])
        name = field_dict.get("name", "")
        
        # Skip hidden fields
        if field_type == "hidden":
            continue
        
        # Determine input_type
        if field_type == "file":
            input_type = "document"
            description = f"Upload document for: {label}"
            example = "PDF, JPG, or PNG file"
        elif field_type in ("select", "radio"):
            input_type = "selection"
            description = f"Choose option for: {label}"
            example = options[0] if options else "Select an option"
        elif field_type == "checkbox":
            input_type = "boolean"
            description = f"Check if applicable: {label}"
            example = "yes or no"
        elif field_type == "date":
            input_type = "date"
            description = f"Enter date for: {label}"
            example = "YYYY-MM-DD"
        elif field_type == "email":
            input_type = "text"
            description = f"Enter your email address"
            example = "example@email.com"
        elif field_type == "tel":
            input_type = "text"
            description = f"Enter phone number"
            example = "9876543210"
        else:
            input_type = "text"
            description = f"Enter {label}"
            example = f"Your {label.lower()}"
        
        # Check if we have a value from profile
        key = name or field_id or label
        value = pre_filled_values.get(key)
        
        item = UserDataItem(
            field_id=field_id,
            label=label,
            input_type=input_type,
            description=description,
            example=example,
            value=value,
            document_path=None,
            extracted_from_doc=bool(value)
        )
        data_items.append(item)
    
    return data_items, pre_filled_values, missing_fields
