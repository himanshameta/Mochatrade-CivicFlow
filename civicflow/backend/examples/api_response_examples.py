"""
Example API Response
=====================
Complete example showing scraped form with text, select, radio, checkbox fields
and the full mapping + confirmation flow.
"""

# ============================================================================
# Example 1: GET /sessions/{session_id}/confirm-data
# ============================================================================

EXAMPLE_CONFIRM_DATA_RESPONSE = {
    "success": True,
    "data": {
        "session_id": "abc-123-def-456",
        "url": "https://example.gov/application-form",
        "page_title": "Government Service Application",
        "status": "awaiting_confirmation",
        "missing_required_fields": [
            "application_type",
            "preferred_date"
        ],
        "fields": [
            # Text input - matched from DB
            {
                "key": "full_name",
                "name": "applicant_name",
                "label": "Full Name",
                "field_type": "text",
                "required": True,
                "placeholder": "Enter your full name",
                "options": [],
                "value": "John Doe",
                "matched_profile_key": "name",
                "source": "db",
                "order": 0,
                "section": ""
            },
            
            # Email input - matched from DB
            {
                "key": "email",
                "name": "email",
                "label": "Email Address",
                "field_type": "email",
                "required": True,
                "placeholder": "your@email.com",
                "options": [],
                "value": "john.doe@email.com",
                "matched_profile_key": "email",
                "source": "db",
                "order": 1,
                "section": ""
            },
            
            # Phone input - matched from DB
            {
                "key": "phone",
                "name": "contact_number",
                "label": "Phone Number",
                "field_type": "tel",
                "required": True,
                "placeholder": "10-digit number",
                "options": [],
                "value": "9876543210",
                "matched_profile_key": "phone",
                "source": "db",
                "order": 2,
                "section": ""
            },
            
            # Date input - matched from DB
            {
                "key": "dob",
                "name": "date_of_birth",
                "label": "Date Of Birth",
                "field_type": "date",
                "required": True,
                "placeholder": "",
                "options": [],
                "value": "1990-05-15",
                "matched_profile_key": "dob",
                "source": "db",
                "order": 3,
                "section": ""
            },
            
            # Select dropdown - matched from DB via LLM
            {
                "key": "gender",
                "name": "gender",
                "label": "Gender",
                "field_type": "select",
                "required": True,
                "placeholder": "",
                "options": [
                    {"label": "Male", "value": "male"},
                    {"label": "Female", "value": "female"},
                    {"label": "Other", "value": "other"},
                    {"label": "Prefer not to say", "value": "none"}
                ],
                "value": "male",
                "matched_profile_key": "gender",
                "source": "db",
                "order": 4,
                "section": ""
            },
            
            # Radio group - matched by LLM
            {
                "key": "application_type",
                "name": "application_type",
                "label": "Application Type",
                "field_type": "radio",
                "required": True,
                "placeholder": "",
                "options": [
                    {"label": "New Application", "value": "new"},
                    {"label": "Renewal", "value": "renewal"},
                    {"label": "Correction", "value": "correction"}
                ],
                "value": "",
                "matched_profile_key": None,
                "source": "none",
                "order": 5,
                "section": "Application Details"
            },
            
            # Checkbox single - not matched
            {
                "key": "terms_accepted",
                "name": "terms",
                "label": "I Accept The Terms And Conditions",
                "field_type": "checkbox",
                "required": True,
                "placeholder": "",
                "options": [],
                "value": "",
                "matched_profile_key": None,
                "source": "none",
                "order": 6,
                "section": ""
            },
            
            # Textarea - matched from DB
            {
                "key": "address",
                "name": "address",
                "label": "Permanent Address",
                "field_type": "textarea",
                "required": True,
                "placeholder": "Enter complete address",
                "options": [],
                "value": "123 Main St, Apt 4B, Mumbai, Maharashtra 400001",
                "matched_profile_key": "address",
                "source": "db",
                "order": 7,
                "section": "Contact Information"
            },
            
            # Number input - matched from DB
            {
                "key": "pincode",
                "name": "pin_code",
                "label": "Pin Code",
                "field_type": "number",
                "required": True,
                "placeholder": "6-digit code",
                "options": [],
                "value": "400001",
                "matched_profile_key": "pincode",
                "source": "db",
                "order": 8,
                "section": "Contact Information"
            },
            
            # Date picker - not matched (user needs to fill)
            {
                "key": "preferred_date",
                "name": "appointment_date",
                "label": "Preferred Appointment Date",
                "field_type": "date",
                "required": True,
                "placeholder": "",
                "options": [],
                "value": "",
                "matched_profile_key": None,
                "source": "none",
                "order": 9,
                "section": ""
            },
            
            # File upload - not matched
            {
                "key": "id_proof",
                "name": "document_upload",
                "label": "Upload Id Proof",
                "field_type": "file",
                "required": False,
                "placeholder": "",
                "options": [],
                "value": "",
                "matched_profile_key": None,
                "source": "none",
                "order": 10,
                "section": "Documents"
            }
        ]
    }
}


# ============================================================================
# Example 2: POST /sessions/{session_id}/confirm
# ============================================================================

EXAMPLE_CONFIRM_REQUEST = {
    "confirmed_data": {
        "full_name": "John Doe",
        "email": "john.doe@email.com",
        "phone": "9876543210",
        "dob": "1990-05-15",
        "gender": "male",
        "application_type": "new",
        "terms_accepted": "true",
        "address": "123 Main St, Apt 4B, Mumbai, Maharashtra 400001",
        "pincode": "400001",
        "preferred_date": "2024-02-15"
    }
}

EXAMPLE_CONFIRM_RESPONSE_SUCCESS = {
    "success": True,
    "data": {
        "session_id": "abc-123-def-456",
        "status": "confirmed",
        "missing_required_fields": [],
        "message": "Data confirmed. Ready for autofill."
    }
}


if __name__ == "__main__":
    import json
    
    print("=" * 80)
    print("Example 1: GET /confirm-data Response")
    print("=" * 80)
    print(json.dumps(EXAMPLE_CONFIRM_DATA_RESPONSE, indent=2))
    
    print("\n" + "=" * 80)
    print("Example 2: POST /confirm Request")
    print("=" * 80)
    print(json.dumps(EXAMPLE_CONFIRM_REQUEST, indent=2))
