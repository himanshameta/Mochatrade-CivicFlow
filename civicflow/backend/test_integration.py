import pytest
import asyncio
import time
import ast
import json
from unittest.mock import Mock, patch, AsyncMock
import httpx
import sys

# Base URL for the backend API
BASE_URL = "http://localhost:8000"
TEST_FORM_URL = "https://httpbin.org/forms/post"

# =============================================================================
# END-TO-END INTEGRATION TEST
# =============================================================================

@pytest.mark.asyncio
async def test_full_pipeline_integration():
    """
    Full end-to-end integration test against httpbin.org/forms/post
    Tests the complete flow from session creation to form execution
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # STEP 1: Create session
        print("\n[1/9] Creating session...")
        response = await client.post(
            f"{BASE_URL}/sessions/start",
            json={"url": TEST_FORM_URL}
        )
        assert response.status_code == 200, f"Failed to create session: {response.text}"
        session_data = response.json()
        session_id = session_data["session_id"]
        print(f"✓ Session created: {session_id}")

        # STEP 2: Run pipeline (scraper + analyst + extractor)
        print("\n[2/9] Running analysis pipeline...")
        response = await client.post(f"{BASE_URL}/sessions/{session_id}/run")
        assert response.status_code == 200, f"Failed to run pipeline: {response.text}"
        print("✓ Pipeline completed")

        # STEP 3: Check scraped form
        print("\n[3/9] Verifying scraped form...")
        response = await client.get(f"{BASE_URL}/sessions/{session_id}")
        assert response.status_code == 200
        session = response.json()
        scraped_form = session.get("scraped_form")
        assert scraped_form is not None, "Scraped form is None"
        
        if isinstance(scraped_form, str):
            scraped_form = json.loads(scraped_form)
        
        fields = scraped_form.get("fields", [])
        assert len(fields) >= 3, f"Expected at least 3 fields, got {len(fields)}"
        print(f"✓ Scraped form has {len(fields)} fields")

        # STEP 4: Check data requirements
        print("\n[4/9] Checking data requirements...")
        response = await client.get(f"{BASE_URL}/sessions/{session_id}/data-requirements")
        assert response.status_code == 200
        data_req = response.json()
        missing_fields = data_req.get("missing_fields", [])
        assert len(missing_fields) > 0, "Data requirements is empty"
        print(f"✓ Data requirements has {len(missing_fields)} fields")

        # STEP 5: Fill all fields with test data
        print("\n[5/9] Filling form fields...")
        field_values = {}
        for field in missing_fields:
            field_name = field["field_name"]
            # Use example value or generate test data
            if field.get("example"):
                field_values[field_name] = field["example"]
            elif "email" in field_name.lower():
                field_values[field_name] = "test@example.com"
            elif "name" in field_name.lower():
                field_values[field_name] = "Test User"
            else:
                field_values[field_name] = "Test Value"
        
        response = await client.post(
            f"{BASE_URL}/sessions/{session_id}/fill-all",
            json={"field_values": field_values}
        )
        assert response.status_code == 200, f"Failed to fill fields: {response.text}"
        print(f"✓ Filled {len(field_values)} fields")

        # STEP 6: Assert is_complete
        print("\n[6/9] Verifying completion status...")
        response = await client.get(f"{BASE_URL}/sessions/{session_id}")
        assert response.status_code == 200
        session = response.json()
        assert session.get("is_complete") == True, "Session is not marked complete"
        print("✓ Session marked as complete")

        # STEP 7: Run executor
        print("\n[7/9] Starting form execution...")
        response = await client.post(f"{BASE_URL}/sessions/{session_id}/execute")
        assert response.status_code == 200, f"Failed to start execution: {response.text}"
        print("✓ Execution started")

        # STEP 8: Poll status
        print("\n[8/9] Polling status (max 60 seconds)...")
        max_attempts = 30  # 30 attempts * 2 seconds = 60 seconds
        final_status = None
        
        for i in range(max_attempts):
            await asyncio.sleep(2)
            response = await client.get(f"{BASE_URL}/sessions/{session_id}/status")
            assert response.status_code == 200
            status_data = response.json()
            current_status = status_data.get("status")
            print(f"  [{i+1}/{max_attempts}] Status: {current_status}")
            
            if current_status in ["completed", "paused_captcha", "paused_otp", "failed"]:
                final_status = current_status
                break
        
        # STEP 9: Assert final status
        print("\n[9/9] Verifying final status...")
        assert final_status in ["completed", "paused_captcha"], \
            f"Expected 'completed' or 'paused_captcha', got '{final_status}'"
        print(f"✓ Final status: {final_status}")

        # STEP 10: Print full session
        print("\n" + "="*70)
        print("FINAL SESSION DATA:")
        print("="*70)
        response = await client.get(f"{BASE_URL}/sessions/{session_id}")
        session_final = response.json()
        print(json.dumps(session_final, indent=2))
        print("="*70)
        
        print("\n✅ Full pipeline integration test PASSED")


# =============================================================================
# UNIT TEST: scraper.py
# =============================================================================

@pytest.mark.asyncio
async def test_scraper_with_hardcoded_html():
    """
    Unit test for scraper module with hardcoded HTML containing 5 different field types
    """
    from agents.scraper import scraper
    
    # Hardcoded HTML form with 5 different field types
    test_html = """
    <!DOCTYPE html>
    <html>
    <body>
        <form action="/submit" method="POST">
            <input type="text" name="full_name" id="name" placeholder="Enter your name" required />
            <input type="email" name="email_address" id="email" placeholder="you@example.com" />
            <select name="country" id="country">
                <option value="">Select Country</option>
                <option value="US">United States</option>
                <option value="IN">India</option>
                <option value="UK">United Kingdom</option>
            </select>
            <textarea name="comments" id="comments" rows="5" placeholder="Your comments"></textarea>
            <input type="checkbox" name="agree_terms" id="terms" value="yes" />
            <button type="submit">Submit</button>
        </form>
    </body>
    </html>
    """
    
    # Call scraper directly with HTML
    result = await scraper(test_html, "http://test.example.com/form")
    
    assert result is not None, "Scraper returned None"
    
    fields = result.fields
    assert len(fields) >= 4, f"Expected at least 4 fields, got {len(fields)}"
    
    # Check for specific field types
    field_names = [f.name for f in fields]
    assert "full_name" in field_names, "Missing text input field"
    assert "email_address" in field_names, "Missing email field"
    assert "country" in field_names, "Missing select field"
    assert "comments" in field_names, "Missing textarea field"
    
    # Verify field types
    field_types = {f.name: f.field_type for f in fields}
    assert field_types.get("full_name") == "text", "Wrong type for text field"
    assert field_types.get("email_address") == "email", "Wrong type for email field"
    assert field_types.get("country") == "select", "Wrong type for select field"
    assert field_types.get("comments") == "textarea", "Wrong type for textarea field"
    
    print("\n✓ Scraper unit test PASSED")
    print(f"  - Extracted {len(fields)} fields")
    print(f"  - Field names: {field_names}")


# =============================================================================
# UNIT TEST: analyst.py
# =============================================================================

@pytest.mark.asyncio
async def test_analyst_with_mock_claude():
    """
    Unit test for analyst module with mocked Claude/Anthropic client
    """
    from datetime import datetime
    from uuid import uuid4
    
    # Mock anthropic BEFORE importing analyst
    with patch.dict('sys.modules', {'anthropic': Mock()}):
        from agents.analyst import analyst
        from models.form_models import ScrapedForm, FormField
        
        # Mock scraped form data using the actual model
        scraped_form = ScrapedForm(
            url="http://test.com/form",
            page_title="Test Form",
            form_html="<form></form>",
            fields=[
                FormField(
                    field_id=str(uuid4()),
                    label="Full Name",
                    field_type="text",
                    name="applicant_name",
                    id_attr="",
                    placeholder="",
                    required=False,
                    options=[],
                    selector="#name",
                    section=""
                ),
                FormField(
                    field_id=str(uuid4()),
                    label="Date of Birth",
                    field_type="date",
                    name="dob",
                    id_attr="",
                    placeholder="",
                    required=False,
                    options=[],
                    selector="#dob",
                    section=""
                ),
                FormField(
                    field_id=str(uuid4()),
                    label="Email Address",
                    field_type="email",
                    name="email",
                    id_attr="",
                    placeholder="",
                    required=False,
                    options=[],
                    selector="#email",
                    section=""
                )
            ],
            submit_button_selector="button[type='submit']",
            has_captcha=False,
            has_file_upload=False,
            captcha_type=None,
            scraped_at=datetime.utcnow()
        )
        
        # Mock Claude response - analyst returns JSON array
        field_id_1 = scraped_form.fields[0].field_id
        field_id_2 = scraped_form.fields[1].field_id
        field_id_3 = scraped_form.fields[2].field_id
        
        mock_claude_response = f'''[
            {{
                "field_id": "{field_id_1}",
                "label": "Full Name",
                "input_type": "text",
                "description": "Full legal name of the applicant",
                "example": "Rajesh Kumar"
            }},
            {{
                "field_id": "{field_id_2}",
                "label": "Date of Birth",
                "input_type": "date",
                "description": "Date of birth in DD/MM/YYYY format",
                "example": "15/08/1990"
            }},
            {{
                "field_id": "{field_id_3}",
                "label": "Email Address",
                "input_type": "text",
                "description": "Valid email address",
                "example": "rajesh@example.com"
            }}
        ]'''
        
        # Mock the Anthropic client
        with patch('agents.analyst.AsyncAnthropic') as mock_anthropic:
            mock_client = Mock()
            mock_message = Mock()
            mock_message.content = [Mock(text=mock_claude_response)]
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_anthropic.return_value = mock_client
            
            result = await analyst(scraped_form, {})
            
            assert result is not None, "Analyst returned None"
            assert isinstance(result, list), "Result is not a list"
            assert len(result) == 3, f"Expected 3 fields, got {len(result)}"
            
            # Verify field structure
            for item in result:
                assert hasattr(item, 'field_id'), "Field missing 'field_id'"
                assert hasattr(item, 'description'), "Field missing 'description'"
                assert hasattr(item, 'input_type'), "Field missing 'input_type'"
            
            # Verify specific fields
            labels = [item.label for item in result]
            assert "Full Name" in labels
            assert "Date of Birth" in labels
            assert "Email Address" in labels
            
            print("\n✓ Analyst unit test PASSED")
            print(f"  - Analyzed {len(result)} fields")
            print(f"  - Mock Claude called successfully")


# =============================================================================
# UNIT TEST: scriptgen.py
# =============================================================================

@pytest.mark.asyncio
async def test_scriptgen_generates_valid_python():
    """
    Unit test for scriptgen module - verifies generated script is valid Python
    """
    from datetime import datetime
    from uuid import uuid4
    
    # Mock anthropic BEFORE importing scriptgen
    with patch.dict('sys.modules', {'anthropic': Mock()}):
        from agents.scriptgen import scriptgen
        from models.form_models import ScrapedForm, FormField, UserDataItem
        
        # Test data using actual models
        form_url = "https://example.com/form"
        
        field1_id = str(uuid4())
        field2_id = str(uuid4())
        field3_id = str(uuid4())
        
        scraped_form = ScrapedForm(
            url=form_url,
            page_title="Test Form",
            form_html="<form></form>",
            fields=[
                FormField(
                    field_id=field1_id,
                    label="Username",
                    field_type="text",
                    name="username",
                    id_attr="username",
                    placeholder="",
                    required=False,
                    options=[],
                    selector="#username",
                    section=""
                ),
                FormField(
                    field_id=field2_id,
                    label="Email",
                    field_type="email",
                    name="email",
                    id_attr="email",
                    placeholder="",
                    required=False,
                    options=[],
                    selector="#email",
                    section=""
                ),
                FormField(
                    field_id=field3_id,
                    label="Country",
                    field_type="select",
                    name="country",
                    id_attr="country",
                    placeholder="",
                    required=False,
                    options=["US", "UK", "IN"],
                    selector="#country",
                    section=""
                )
            ],
            submit_button_selector="button[type='submit']",
            has_captcha=False,
            has_file_upload=False,
            captcha_type=None,
            scraped_at=datetime.utcnow()
        )
        
        data_requirements = [
            UserDataItem(
                field_id=field1_id,
                label="Username",
                input_type="text",
                description="Your username",
                example="testuser",
                value="testuser",
                document_path=None,
                extracted_from_doc=False
            ),
            UserDataItem(
                field_id=field2_id,
                label="Email",
                input_type="text",
                description="Your email",
                example="test@example.com",
                value="test@example.com",
                document_path=None,
                extracted_from_doc=False
            ),
            UserDataItem(
                field_id=field3_id,
                label="Country",
                input_type="selection",
                description="Your country",
                example="US",
                value="US",
                document_path=None,
                extracted_from_doc=False
            )
        ]
        
        # Mock Claude to return a simple valid script
        mock_script = '''from playwright.async_api import async_playwright
import asyncio

async def main():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto("https://example.com/form")
            await page.fill("#username", "testuser")
            await page.fill("#email", "test@example.com")
            await page.select_option("#country", "US")
            await page.screenshot(path="before_submit.png")
            await page.click("button[type='submit']")
            await asyncio.sleep(3)
            await page.screenshot(path="after_submit.png")
            print("SUBMISSION_COMPLETE")
            await browser.close()
    except Exception as e:
        print(f"SCRIPT_ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
'''
        
        with patch('agents.scriptgen.AsyncAnthropic') as mock_anthropic:
            mock_client = Mock()
            mock_message = Mock()
            mock_message.content = [Mock(text=mock_script)]
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_anthropic.return_value = mock_client
            
            # Generate script
            script = await scriptgen(scraped_form, data_requirements, "test_session")
            
            assert script is not None, "Generated script is None"
            assert len(script) > 0, "Generated script is empty"
            assert "async def main" in script, "Script missing async function definition"
            assert "playwright" in script.lower(), "Script missing Playwright import"
            
            # Most important: Verify it's valid Python syntax
            try:
                ast.parse(script)
                syntax_valid = True
            except SyntaxError as e:
                syntax_valid = False
                print(f"\n❌ Syntax Error: {e}")
            
            assert syntax_valid, "Generated script has invalid Python syntax"
            
            # Verify it contains key operations
            assert "page.goto" in script, "Script missing page navigation"
            assert "page.fill" in script or "page.locator" in script, "Script missing form filling"
            
            print("\n✓ Scriptgen unit test PASSED")
            print(f"  - Generated script length: {len(script)} chars")
            print(f"  - Valid Python syntax: ✓")
            print(f"  - Contains form operations: ✓")


# =============================================================================
# UNIT TEST: ocr.py
# =============================================================================

@pytest.mark.asyncio
async def test_ocr_with_text_file():
    """
    Unit test for OCR utility with text file
    """
    from utils.ocr import extract_text_from_document
    from pathlib import Path
    
    # Create a temporary test file
    test_file = Path("test_doc.txt")
    test_content = "John Smith\nDate of Birth: 01/15/1990\nEmail: john@example.com"
    
    with open(test_file, "w") as f:
        f.write(test_content)
    
    try:
        result = await extract_text_from_document(str(test_file))
        
        assert result is not None, "OCR returned None"
        assert isinstance(result, str), "Result is not a string"
        assert "John Smith" in result, "Missing expected text"
        assert "01/15/1990" in result, "Missing date"
        
        print("\n✓ OCR unit test PASSED")
        print(f"  - Extracted text length: {len(result)} chars")
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()


# =============================================================================
# DEMO SCRIPT
# =============================================================================

if __name__ == "__main__":
    import subprocess
    
    print("="*70)
    print("🚀 CIVICFLOW INTEGRATION TEST DEMO")
    print("="*70)
    print(f"\nTarget: {TEST_FORM_URL}")
    print(f"Backend: {BASE_URL}")
    print("\nThis will run the full end-to-end test including:")
    print("  1. Session creation")
    print("  2. Form scraping & analysis")
    print("  3. Data extraction")
    print("  4. Form filling")
    print("  5. Execution & status polling")
    print("\n" + "="*70)
    
    # Check if backend is running
    print("\n📡 Checking backend connection...")
    try:
        import httpx
        response = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        if response.status_code == 200:
            print("✓ Backend is running")
        else:
            print("⚠️  Backend responded but may not be ready")
    except Exception as e:
        print(f"❌ Cannot connect to backend at {BASE_URL}")
        print(f"   Error: {e}")
        print("\n💡 Start the backend first with:")
        print("   cd civicflow/backend && uvicorn main:app --reload")
        sys.exit(1)
    
    print("\n▶️  Running integration tests...\n")
    
    # Run pytest with verbose output
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            __file__,
            "-v",
            "--asyncio-mode=auto",
            "-s",  # Show print statements
            "--tb=short"  # Short traceback format
        ],
        cwd="."
    )
    
    print("\n" + "="*70)
    if result.returncode == 0:
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\n🎉 CivicFlow is working correctly!")
    else:
        print("❌ SOME TESTS FAILED")
        print("="*70)
        print("\n🔧 Check the output above for details")
    
    sys.exit(result.returncode)
