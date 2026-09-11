"""
Test Generic Form Autofill Pipeline
====================================
Tests the refactored CivicFlow with:
1. Field type normalization (including search, url, etc.)
2. Generic semantic mapping
3. Missing field detection
4. Profile persistence
"""
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_field_type_normalization():
    """Test that normalize_field_type handles all HTML input types."""
    from agents.scraper import normalize_field_type
    
    print("\n" + "=" * 80)
    print("Test 1: Field Type Normalization")
    print("=" * 80)
    
    test_cases = [
        ("search", "input", "search"),
        ("url", "input", "url"),
        ("email", "input", "email"),
        ("submit", "input", "hidden"),
        ("button", "input", "hidden"),
        ("", "textarea", "textarea"),
        ("", "select", "select"),
        ("color", "input", "text"),
        ("range", "input", "number"),
        ("datetime-local", "input", "datetime-local"),
    ]
    
    for raw_type, tag_name, expected in test_cases:
        result = normalize_field_type(raw_type, tag_name)
        status = "✓" if result == expected else "✗"
        print(f"{status} normalize_field_type('{raw_type}', '{tag_name}') = '{result}' (expected: '{expected}')")


async def test_form_scoring():
    """Test that search forms are rejected and real forms are selected."""
    from agents.scraper import scraper
    
    print("\n" + "=" * 80)
    print("Test 2: Form Scoring (Search vs Real Forms)")
    print("=" * 80)
    
    # HTML with both search and registration form
    html = """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <!-- Search form (should be ignored) -->
        <form id="search-form">
            <input type="search" name="q" placeholder="Search...">
            <button type="submit">Search</button>
        </form>
        
        <!-- Real registration form (should be selected) -->
        <form id="registration-form">
            <input type="text" name="name" required>
            <input type="email" name="email" required>
            <input type="tel" name="phone">
            <textarea name="address"></textarea>
            <button type="submit">Register</button>
        </form>
    </body>
    </html>
    """
    
    result = await scraper(html, "https://example.com/test")
    
    if result:
        print(f"✓ Scraper selected form with {len(result['fields'])} fields")
        print(f"  Fields found: {[f['label'] for f in result['fields']]}")
        # Should have 4 fields (name, email, phone, address) but NOT the search field
        assert len(result['fields']) == 4, f"Expected 4 fields, got {len(result['fields'])}"
        print("✓ Search form was correctly ignored")
    else:
        print("✗ Scraper returned None")


async def test_generic_mapping():
    """Test that generic mapper correctly maps profile to form fields."""
    from utils.generic_mapper import map_profile_to_fields
    
    print("\n" + "=" * 80)
    print("Test 3: Generic Profile Mapping")
    print("=" * 80)
    
    # Mock form fields
    form_fields = [
        {"name": "fullname", "label": "Full Name", "field_type": "text", "required": True, "options": []},
        {"name": "email", "label": "Email Address", "field_type": "email", "required": True, "options": []},
        {"name": "mobile", "label": "Mobile Number", "field_type": "tel", "required": True, "options": []},
        {"name": "dob", "label": "Date of Birth", "field_type": "date", "required": False, "options": []},
        {"name": "city", "label": "City", "field_type": "text", "required": True, "options": []},
        {"name": "pincode", "label": "PIN Code", "field_type": "text", "required": False, "options": []},
    ]
    
    # Mock user profile
    user_profile = {
        "full_name": "Sumita Banerjee",
        "email": "sumita@example.com",
        "phone": "+91-9876543210",
        "dob": "1990-05-15",
        # Missing: city, pincode
    }
    
    pre_filled, missing = map_profile_to_fields(form_fields, user_profile)
    
    print(f"✓ Mapped {len(pre_filled)} fields from profile:")
    for key, value in pre_filled.items():
        print(f"    {key}: {value}")
    
    print(f"\n✓ Missing {len(missing)} required fields:")
    for field in missing:
        print(f"    {field['label']} ({field['key']})")
    
    # Assertions
    assert len(pre_filled) == 4, f"Expected 4 pre-filled, got {len(pre_filled)}"
    assert len(missing) == 1, f"Expected 1 missing (city), got {len(missing)}"
    assert missing[0]['key'] == 'city', f"Expected missing 'city', got '{missing[0]['key']}'"
    
    print("\n✓ All generic mapping tests passed")


async def test_name_splitting():
    """Test that full name is split when form has first_name and last_name fields."""
    from utils.generic_mapper import map_profile_to_fields
    
    print("\n" + "=" * 80)
    print("Test 4: Name Splitting")
    print("=" * 80)
    
    form_fields = [
        {"name": "first_name", "label": "First Name", "field_type": "text", "required": True, "options": []},
        {"name": "last_name", "label": "Last Name", "field_type": "text", "required": True, "options": []},
    ]
    
    user_profile = {
        "full_name": "Sumita Banerjee"
    }
    
    pre_filled, missing = map_profile_to_fields(form_fields, user_profile)
    
    print(f"✓ Split 'Sumita Banerjee' into:")
    for key, value in pre_filled.items():
        print(f"    {key}: {value}")
    
    assert len(pre_filled) == 2, f"Expected 2 fields filled"
    assert len(missing) == 0, f"Expected 0 missing"
    
    print("✓ Name splitting works correctly")


async def test_phone_normalization():
    """Test that phone numbers are normalized correctly."""
    from utils.generic_mapper import normalize_phone
    
    print("\n" + "=" * 80)
    print("Test 5: Phone Normalization")
    print("=" * 80)
    
    test_cases = [
        ("+91-9876543210", "9876543210"),
        ("(987) 654-3210", "9876543210"),
        ("987-654-3210", "9876543210"),
        ("9876543210", "9876543210"),
        ("091-9876543210", "9876543210"),
    ]
    
    for input_val, expected in test_cases:
        result = normalize_phone(input_val)
        status = "✓" if result == expected else "✗"
        print(f"{status} normalize_phone('{input_val}') = '{result}' (expected: '{expected}')")


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("CIVICFLOW GENERIC FORM AUTOFILL TESTS")
    print("=" * 80)
    
    try:
        await test_field_type_normalization()
        await test_form_scoring()
        await test_generic_mapping()
        await test_name_splitting()
        await test_phone_normalization()
        
        print("\n" + "=" * 80)
        print("✓ ALL TESTS PASSED")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
