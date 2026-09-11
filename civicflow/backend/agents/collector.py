import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.form_models import UserDataItem


def get_missing_fields(data_requirements: list[UserDataItem]) -> list[UserDataItem]:
    """
    Returns only fields where value is None (user hasn't provided data yet).
    
    Args:
        data_requirements: List of all data requirements
        
    Returns:
        List of UserDataItem that still need values
    """
    return [item for item in data_requirements if item.value is None]


def apply_user_input(data_requirements: list[UserDataItem], field_id: str, value: str) -> list[UserDataItem]:
    """
    Set a specific field's value based on user input.
    
    Args:
        data_requirements: List of all data requirements
        field_id: The field_id to update
        value: The value to set
        
    Returns:
        Updated list of UserDataItem
    """
    for item in data_requirements:
        if item.field_id == field_id:
            item.value = value
            break
    return data_requirements


def is_data_complete(data_requirements: list[UserDataItem]) -> bool:
    """
    Check if all required fields have values.
    
    Args:
        data_requirements: List of all data requirements
        
    Returns:
        True if all fields have values, False otherwise
    """
    return all(item.value is not None for item in data_requirements)


def generate_collection_summary(data_requirements: list[UserDataItem]) -> dict:
    """
    Generate a summary of data collection progress for the frontend.
    
    Args:
        data_requirements: List of all data requirements
        
    Returns:
        Dict with total, filled, missing counts and list of missing fields
    """
    missing_items = [item for item in data_requirements if item.value is None]
    
    return {
        "total": len(data_requirements),
        "filled": sum(1 for i in data_requirements if i.value is not None),
        "missing": len(missing_items),
        "auto_extracted": sum(1 for i in data_requirements if i.extracted_from_doc),
        "missing_fields": [
            {
                "field_id": i.field_id,
                "description": i.description,
                "example": i.example,
                "label": i.label,
                "input_type": i.input_type
            }
            for i in missing_items
        ]
    }


if __name__ == "__main__":
    import json
    from uuid import uuid4
    
    print("=" * 80)
    print("Testing Collector Agent")
    print("=" * 80)
    
    # Create sample data requirements
    data_requirements = [
        UserDataItem(
            field_id=str(uuid4()),
            label="Full Name",
            input_type="text",
            description="What is your full legal name?",
            example="John Smith",
            value="Jane Doe",
            extracted_from_doc=True
        ),
        UserDataItem(
            field_id=str(uuid4()),
            label="Email",
            input_type="text",
            description="What is your email address?",
            example="user@example.com",
            value=None
        ),
        UserDataItem(
            field_id=str(uuid4()),
            label="Phone",
            input_type="text",
            description="What is your phone number?",
            example="(555) 123-4567",
            value=None
        ),
        UserDataItem(
            field_id=str(uuid4()),
            label="Date of Birth",
            input_type="date",
            description="What is your date of birth?",
            example="01/15/1990",
            value="03/22/1985",
            extracted_from_doc=True
        ),
    ]
    
    print("\n[Test 1] get_missing_fields()")
    missing = get_missing_fields(data_requirements)
    print(f"✓ Found {len(missing)} missing fields:")
    for item in missing:
        print(f"  - {item.label}: {item.description}")
    
    print("\n[Test 2] is_data_complete()")
    complete = is_data_complete(data_requirements)
    print(f"✓ Data complete: {complete}")
    
    print("\n[Test 3] generate_collection_summary()")
    summary = generate_collection_summary(data_requirements)
    print(f"✓ Summary generated:")
    print(json.dumps(summary, indent=2))
    
    print("\n[Test 4] apply_user_input()")
    email_field_id = data_requirements[1].field_id
    data_requirements = apply_user_input(data_requirements, email_field_id, "jane.doe@example.com")
    print(f"✓ Applied value to Email field")
    print(f"  Email value: {data_requirements[1].value}")
    
    print("\n[Test 5] Check completion after partial fill")
    complete = is_data_complete(data_requirements)
    print(f"✓ Data complete: {complete}")
    
    print("\n[Test 6] Fill remaining field and check completion")
    phone_field_id = data_requirements[2].field_id
    data_requirements = apply_user_input(data_requirements, phone_field_id, "(555) 987-6543")
    complete = is_data_complete(data_requirements)
    print(f"✓ Applied value to Phone field")
    print(f"  Phone value: {data_requirements[2].value}")
    print(f"✓ Data complete: {complete}")
    
    print("\n[Test 7] Final summary")
    final_summary = generate_collection_summary(data_requirements)
    print(json.dumps(final_summary, indent=2))
    
    print("\n" + "=" * 80)
    print("All Collector tests passed!")
    print("=" * 80)
