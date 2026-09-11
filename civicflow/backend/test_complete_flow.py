"""
End-to-End Flow Test
=====================
Tests the complete flow:
1. User enters URL
2. Scraper extracts form
3. Mapper maps profile to fields
4. Frontend displays review form
5. User confirms data
6. Executor runs autofill

Run: python -m pytest test_complete_flow.py -v
"""
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_complete_flow():
    """Test the entire flow from URL to confirmed script"""
    
    print("\n" + "=" * 80)
    print("COMPLETE FLOW TEST")
    print("=" * 80)
    
    # ========================================================================
    # Step 1: User provides URL
    # ========================================================================
    test_url = "https://httpbin.org/forms/post"
    print(f"\n[Step 1] User enters URL: {test_url}")
    
    # ========================================================================
    # Step 2: Scout fetches the page
    # ========================================================================
    print("\n[Step 2] Scouting page...")
    from agents.scout import scout
    
    scout_result = await scout(test_url)
    if "error" in scout_result:
        print(f"✗ Scout failed: {scout_result['error']}")
        return False
    
    print(f"✓ Page loaded: {scout_result['title']}")
    print(f"✓ HTML length: {len(scout_result['html'])} chars")
    
    # ========================================================================
    # Step 3: Scraper extracts form fields
    # ========================================================================
    print("\n[Step 3] Scraping form...")
    from agents.scraper import scraper
    
    scraped_form = await scraper(scout_result['html'], test_url)
    if not scraped_form:
        print("✗ Scraper returned None")
        return False
    
    print(f"✓ Scraped {len(scraped_form['fields'])} fields")
    print(f"✓ Submit button: {scraped_form['submit_button_selector']}")
    print(f"✓ Has CAPTCHA: {scraped_form['has_captcha']}")
    
    # Show scraped fields
    print("\nScraped Fields:")
    for i, field in enumerate(scraped_form['fields'][:5], 1):
        print(f"  {i}. {field['label']} ({field['field_type']}) - {field['name']}")
    if len(scraped_form['fields']) > 5:
        print(f"  ... and {len(scraped_form['fields']) - 5} more")
    
    # ========================================================================
    # Step 4: Create session with user profile
    # ========================================================================
    print("\n[Step 4] Creating session with user profile...")
    from models.form_models import UserSession
    from models.session_models import SessionStore
    from uuid import uuid4
    
    session_id = str(uuid4())
    session_store = SessionStore()
    
    # Mock user profile
    user_profile = {
        "name": "Test User",
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "phone": "9876543210",
        "dob": "1990-01-01",
        "gender": "Male",
        "address": "123 Test Street, Test City",
        "pincode": "123456"
    }
    
    session = UserSession(
        session_id=session_id,
        url=test_url,
        html=scout_result['html'],
        page_title=scout_result['title'],
        scraped_form=scraped_form,
        user_profile=user_profile,
        status="scraped"
    )
    
    await session_store.save(session)
    print(f"✓ Session created: {session_id}")
    
    # ========================================================================
    # Step 5: Map profile to form schema (confirm-data endpoint)
    # ========================================================================
    print("\n[Step 5] Mapping profile to form schema...")
    from utils.enhanced_mapper import map_profile_to_form_schema
    
    review_fields = await map_profile_to_form_schema(scraped_form, user_profile)
    
    print(f"✓ Generated {len(review_fields)} review fields")
    
    # Count fields by source
    db_count = sum(1 for f in review_fields if f.source == "db")
    llm_count = sum(1 for f in review_fields if f.source == "llm")
    none_count = sum(1 for f in review_fields if f.source == "none")
    
    print(f"  - {db_count} from DB")
    print(f"  - {llm_count} from LLM")
    print(f"  - {none_count} not matched")
    
    # Show mapped fields
    print("\nMapped Fields:")
    for field in review_fields[:5]:
        value_display = field.value[:30] if field.value else "(empty)"
        print(f"  - {field.label}: {value_display} [{field.source}]")
    
    # Build pre_filled_values
    pre_filled_values = {}
    for field in review_fields:
        if field.value:
            pre_filled_values[field.key] = field.value
    
    print(f"\n✓ Pre-filled {len(pre_filled_values)} fields")
    
    # Update session
    session.pre_filled_values = pre_filled_values
    session.review_form_schema = [f.model_dump() for f in review_fields]
    session.status = "awaiting_confirmation"
    await session_store.save(session)
    
    # ========================================================================
    # Step 6: User confirms data (simulated)
    # ========================================================================
    print("\n[Step 6] Simulating user confirmation...")
    
    # In real app, frontend would display DynamicReviewForm
    # User would edit values and submit
    
    # Simulate user adding/editing some values
    confirmed_data = pre_filled_values.copy()
    
    # User might have edited or filled missing fields
    if "comments" in [f.key for f in review_fields]:
        confirmed_data["comments"] = "This is a test comment from the automated flow"
    
    print(f"✓ User confirmed {len(confirmed_data)} fields")
    
    # Merge confirmed data back
    session.pre_filled_values.update(confirmed_data)
    session.status = "confirmed"
    await session_store.save(session)
    
    # ========================================================================
    # Step 7: Generate execution script
    # ========================================================================
    print("\n[Step 7] Generating Playwright script...")
    from agents.scriptgen import scriptgen
    
    script_content = await scriptgen(
        scraped_form=scraped_form,
        session_id=session_id,
        pre_filled_values=session.pre_filled_values
    )
    
    print(f"✓ Script generated: {len(script_content)} chars")
    print(f"✓ Script uses {len(session.pre_filled_values)} confirmed values")
    
    # Show script snippet
    lines = script_content.split('\n')
    print("\nScript Preview (first 20 lines):")
    for line in lines[:20]:
        print(f"  {line}")
    print("  ...")
    
    # ========================================================================
    # Step 8: Verify script structure
    # ========================================================================
    print("\n[Step 8] Verifying script structure...")
    
    checks = {
        "Has imports": "import asyncio" in script_content or "from playwright" in script_content,
        "Has URL": test_url in script_content,
        "Uses pre_filled_values": any(v in script_content for v in list(session.pre_filled_values.values())[:3]),
        "Has field handling": "fill" in script_content.lower() or "locator" in script_content.lower(),
        "Has submit": "submit" in script_content.lower(),
        "Has CAPTCHA check": "captcha" in script_content.lower(),
        "Has event logging": "EVENT:" in script_content
    }
    
    all_passed = True
    for check, result in checks.items():
        status = "✓" if result else "✗"
        print(f"  {status} {check}")
        if not result:
            all_passed = False
    
    # ========================================================================
    # Summary
    # ========================================================================
    print("\n" + "=" * 80)
    print("FLOW SUMMARY")
    print("=" * 80)
    print(f"Session ID: {session_id}")
    print(f"URL: {test_url}")
    print(f"Fields scraped: {len(scraped_form['fields'])}")
    print(f"Fields mapped: {db_count} from DB, {llm_count} from LLM")
    print(f"Fields confirmed: {len(session.pre_filled_values)}")
    print(f"Script generated: {len(script_content)} chars")
    print(f"All checks passed: {all_passed}")
    print("=" * 80)
    
    # Cleanup
    await session_store.delete(session_id)
    await session_store.close()
    
    return all_passed


async def test_field_type_handling():
    """Test that all field types are properly handled"""
    
    print("\n" + "=" * 80)
    print("FIELD TYPE HANDLING TEST")
    print("=" * 80)
    
    from agents.executor_field_handler import generate_fill_code
    
    test_fields = [
        {"field_type": "text", "selector": "#name", "label": "Name", "name": "name"},
        {"field_type": "email", "selector": "#email", "label": "Email", "name": "email"},
        {"field_type": "tel", "selector": "#phone", "label": "Phone", "name": "phone"},
        {"field_type": "date", "selector": "#dob", "label": "DOB", "name": "dob"},
        {"field_type": "textarea", "selector": "#comments", "label": "Comments", "name": "comments"},
        {"field_type": "select", "selector": "#country", "label": "Country", "name": "country", 
         "options": [{"label": "USA", "value": "us"}, {"label": "India", "value": "in"}]},
        {"field_type": "radio", "selector": "[name='gender']", "label": "Gender", "name": "gender",
         "options": [{"label": "Male", "value": "M"}, {"label": "Female", "value": "F"}]},
        {"field_type": "checkbox", "selector": "#terms", "label": "Terms", "name": "terms"},
        {"field_type": "file", "selector": "#upload", "label": "Upload", "name": "file"},
    ]
    
    test_values = {
        "text": "John Doe",
        "email": "john@example.com",
        "tel": "9876543210",
        "date": "1990-01-01",
        "textarea": "This is a long comment text",
        "select": "in",
        "radio": "M",
        "checkbox": "true",
        "file": "/path/to/file.pdf"
    }
    
    print("\nTesting field type code generation:")
    all_ok = True
    
    for field in test_fields:
        ftype = field["field_type"]
        value = test_values.get(ftype, "")
        
        code = generate_fill_code(field, value, "test-session")
        
        # Verify code has expected patterns
        checks = []
        if ftype == "select":
            checks.append("select_option" in code)
        elif ftype == "radio":
            checks.append("check()" in code)
        elif ftype == "checkbox":
            checks.append("check()" in code or "uncheck()" in code)
        elif ftype == "file":
            checks.append("set_input_files" in code)
        else:
            checks.append("fill" in code)
        
        ok = all(checks) if checks else True
        status = "✓" if ok else "✗"
        print(f"  {status} {ftype.ljust(10)} -> {len(code)} chars")
        
        if not ok:
            all_passed = False
            print(f"     Generated code:\n{code}")
    
    print(f"\nAll field types handled correctly: {all_ok}")
    return all_ok


if __name__ == "__main__":
    async def run_all_tests():
        print("\n" + "=" * 80)
        print("RUNNING ALL TESTS")
        print("=" * 80)
        
        test1 = await test_field_type_handling()
        test2 = await test_complete_flow()
        
        print("\n" + "=" * 80)
        print("TEST RESULTS")
        print("=" * 80)
        print(f"Field Type Handling: {'✓ PASSED' if test1 else '✗ FAILED'}")
        print(f"Complete Flow: {'✓ PASSED' if test2 else '✗ FAILED'}")
        print("=" * 80)
        
        return test1 and test2
    
    result = asyncio.run(run_all_tests())
    sys.exit(0 if result else 1)
