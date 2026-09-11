"""
NORMALIZED FORM FLOW - VISUAL DIAGRAM
======================================

┌─────────────────────────────────────────────────────────────────────────┐
│                          USER ENTERS URL                                 │
│                    https://example.gov/form                              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     STEP 1: SCOUT (fetch page)                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  - Launch Playwright browser                                     │   │
│  │  - Navigate to URL                                               │   │
│  │  - Wait for page load                                            │   │
│  │  - Extract HTML content                                          │   │
│  │  - Take screenshot                                               │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  Output: { html, url, title, screenshot_path }                           │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   STEP 2: SCRAPER (extract form)                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  For each <input>, <select>, <textarea>:                         │   │
│  │    1. Extract label (9-step priority)                            │   │
│  │    2. Get name, id, placeholder                                  │   │
│  │    3. Detect field_type                                          │   │
│  │    4. Check if required                                          │   │
│  │    5. Extract options (for select/radio)                         │   │
│  │    6. Generate selector                                          │   │
│  │    7. Assign order index                                         │   │
│  │    8. Detect section (fieldset/legend)                           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  Output: ScrapedForm {                                                   │
│    fields: [                                                             │
│      {                                                                   │
│        field_id, name, label, field_type, required,                     │
│        placeholder, options, selector, order, section                   │
│      }                                                                   │
│    ],                                                                    │
│    submit_button_selector, has_captcha, has_file_upload                 │
│  }                                                                       │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              STEP 3: LOAD USER PROFILE (from MongoDB)                   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  - Query user_profiles collection                                │   │
│  │  - Flatten basic_info, contact, uploaded_documents               │   │
│  │  - Normalize keys (canonical format)                             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  Profile: {                                                              │
│    name: "John Doe", email: "john@example.com",                         │
│    phone: "9876543210", dob: "1990-01-01",                              │
│    gender: "Male", address: "123 Main St"                               │
│  }                                                                       │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│         STEP 4: MAPPER (map profile to form schema)                     │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │  STAGE 1: Deterministic Mapping                                │     │
│  │  ────────────────────────────                                  │     │
│  │  For each scraped field:                                       │     │
│  │    1. Try exact alias match                                    │     │
│  │       "full_name" → profile["name"]                            │     │
│  │    2. Try direct key match                                     │     │
│  │    3. Try name splitting                                       │     │
│  │       "first_name" → split profile["name"]                     │     │
│  │    4. Try token overlap (partial match)                        │     │
│  │                                                                 │     │
│  │  If confidence ≥ 0.8: MATCHED ✓                                │     │
│  │  Else: Add to unmatched list                                   │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │  STAGE 2: LLM Fallback (for unmatched fields)                 │     │
│  │  ──────────────────────────                                    │     │
│  │  Send to LLM:                                                  │     │
│  │    - User profile JSON                                         │     │
│  │    - Unmatched field metadata                                  │     │
│  │                                                                 │     │
│  │  LLM returns:                                                  │     │
│  │    [                                                           │     │
│  │      {                                                         │     │
│  │        field_key: "gender",                                    │     │
│  │        matched_profile_key: "gender",                          │     │
│  │        value: "Male",                                          │     │
│  │        confidence: 0.95                                        │     │
│  │      }                                                         │     │
│  │    ]                                                           │     │
│  │                                                                 │     │
│  │  Only accept if confidence ≥ 0.75                              │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                           │
│  Output: ReviewFormField[] {                                             │
│    key: "full_name",                                                     │
│    label: "Full Name",                                                   │
│    field_type: "text",                                                   │
│    value: "John Doe",  ← MAPPED VALUE                                   │
│    matched_profile_key: "name",                                          │
│    source: "db",  ← or "llm" or "none"                                  │
│    order: 0                                                              │
│  }                                                                       │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              STEP 5: SAVE TO SESSION                                    │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  session.pre_filled_values = {                                   │   │
│  │    "full_name": "John Doe",                                      │   │
│  │    "email": "john@example.com",                                  │   │
│  │    "gender": "Male"                                              │   │
│  │  }                                                               │   │
│  │                                                                  │   │
│  │  session.review_form_schema = [ReviewFormField]                 │   │
│  │  session.status = "awaiting_confirmation"                       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│     STEP 6: FRONTEND DISPLAYS REVIEW FORM                               │
│                                                                           │
│  GET /sessions/{id}/confirm-data                                         │
│  ────────────────────────────────                                        │
│  Returns: { fields: [ReviewFormField], missing_required: [...] }        │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │  DynamicReviewForm.jsx renders:                                │     │
│  │                                                                 │     │
│  │  ┌──────────────────────────────────────────────────────────┐  │     │
│  │  │  Full Name *                           [From Profile] ✓  │  │     │
│  │  │  ┌────────────────────────────────────────────────────┐  │  │     │
│  │  │  │ John Doe                                           │  │  │     │
│  │  │  └────────────────────────────────────────────────────┘  │  │     │
│  │  └──────────────────────────────────────────────────────────┘  │     │
│  │                                                                 │     │
│  │  ┌──────────────────────────────────────────────────────────┐  │     │
│  │  │  Gender *                              [From Profile] ✓  │  │     │
│  │  │  ○ Male  ● Female  ○ Other                             │  │     │
│  │  └──────────────────────────────────────────────────────────┘  │     │
│  │                                                                 │     │
│  │  ┌──────────────────────────────────────────────────────────┐  │     │
│  │  │  Application Type *                   [Not Mapped] ⚠    │  │     │
│  │  │  ○ New  ○ Renewal  ○ Correction                        │  │     │
│  │  └──────────────────────────────────────────────────────────┘  │     │
│  │                                                                 │     │
│  │  [Confirm & Continue]  [Cancel]                                │     │
│  └────────────────────────────────────────────────────────────────┘     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│        STEP 7: USER REVIEWS / EDITS / CONFIRMS                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  User can:                                                       │   │
│  │    - Review all mapped values                                    │   │
│  │    - Edit any field                                              │   │
│  │    - Fill missing required fields                                │   │
│  │    - See which values came from DB vs LLM                        │   │
│  │    - Click "Confirm & Continue"                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  POST /sessions/{id}/confirm                                             │
│  ────────────────────────────────                                        │
│  Body: {                                                                 │
│    confirmed_data: {                                                     │
│      "full_name": "John Doe",                                            │
│      "email": "john@example.com",                                        │
│      "gender": "Male",                                                   │
│      "application_type": "new"  ← User filled this                      │
│    }                                                                     │
│  }                                                                       │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│           STEP 8: UPDATE SESSION WITH CONFIRMED DATA                    │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  - Merge confirmed_data into session.pre_filled_values           │   │
│  │  - Update review_form_schema values                              │   │
│  │  - Recompute missing_required_fields                             │   │
│  │  - If all required filled: status = "confirmed"                  │   │
│  │  - Persist to user profile in MongoDB                            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│          STEP 9: GENERATE PLAYWRIGHT SCRIPT                             │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  scriptgen() calls executor_field_handler:                       │   │
│  │                                                                   │   │
│  │  For each scraped field:                                         │   │
│  │    stable_key = compute_stable_field_key(field)                  │   │
│  │    value = session.pre_filled_values[stable_key]                 │   │
│  │                                                                   │   │
│  │    if field_type == "text":                                      │   │
│  │      → await page.locator(selector).fill(value)                  │   │
│  │                                                                   │   │
│  │    if field_type == "select":                                    │   │
│  │      → await page.locator(selector).select_option(value=value)   │   │
│  │                                                                   │   │
│  │    if field_type == "radio":                                     │   │
│  │      → await page.locator(f'[name="{name}"][value="{value}"]')   │   │
│  │                  .check()                                        │   │
│  │                                                                   │   │
│  │    if field_type == "checkbox":                                  │   │
│  │      → await page.locator(selector).check()                      │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  Output: complete_script.py                                              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│           STEP 10: EXECUTE PLAYWRIGHT SCRIPT                            │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  1. Launch browser (headless=False)                              │   │
│  │  2. Navigate to URL                                              │   │
│  │  3. Fill each field using generated code                         │   │
│  │     - text → fill()                                              │   │
│  │     - select → select_option()                                   │   │
│  │     - radio → check()                                            │   │
│  │     - checkbox → check() / uncheck()                             │   │
│  │  4. Check for CAPTCHA                                            │   │
│  │     - If found: pause and wait for user                          │   │
│  │  5. Click submit button                                          │   │
│  │  6. Wait for submission                                          │   │
│  │  7. Take screenshot                                              │   │
│  │  8. Emit events via WebSocket                                    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  Events:                                                                 │
│    - field_filling:Full Name                                             │
│    - field_filled:Full Name:John Doe                                     │
│    - captcha_detected (if found)                                         │
│    - submission_complete                                                 │
└─────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════
                             KEY PRINCIPLES
═══════════════════════════════════════════════════════════════════════════

1. NORMALIZED SCHEMA
   ✓ Clean JSON structure (not raw HTML)
   ✓ Type-safe field definitions
   ✓ Frontend renders from schema

2. STABLE FIELD KEYS
   ✓ Consistent identifier across all layers
   ✓ name → field_id → id_attr → label (priority order)
   ✓ Used in pre_filled_values and executor

3. TWO-STAGE MAPPING
   ✓ Deterministic first (fast, reliable)
   ✓ LLM fallback only when needed
   ✓ Confidence thresholds for quality

4. USER CONTROL
   ✓ Review all values before execution
   ✓ Edit any field
   ✓ See data source (DB/LLM/None)

5. TYPE-SPECIFIC EXECUTION
   ✓ Each field type has correct Playwright method
   ✓ select uses select_option (not fill)
   ✓ radio uses check on specific option
   ✓ No guessing or fallbacks

6. FIELD ORDER PRESERVATION
   ✓ Scraper assigns order index
   ✓ Schema maintains order
   ✓ Frontend displays in original sequence

7. NO HARDCODED LOGIC
   ✓ Works for ANY form
   ✓ No form-specific code
   ✓ Generic profile mapping

═══════════════════════════════════════════════════════════════════════════
"""

if __name__ == "__main__":
    print(__doc__)
