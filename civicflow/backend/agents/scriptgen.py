import os
import ast
import json
import uuid
from pathlib import Path
from datetime import datetime


async def scriptgen(scraped_form, session_id: str, pre_filled_values: dict = None) -> str:
    """
    Generate a Playwright Python script for this specific form.
    Uses confirmed values from session.pre_filled_values.
    Uses executor_field_handler for proper field type handling.
    Returns just the script content (not a tuple).
    """
    print(f"[ScriptGen] Starting script generation for session {session_id}")
    print(f"[ScriptGen] Using confirmed values keys: {list((pre_filled_values or {}).keys())}")
    
    # Use new executor field handler
    from agents.executor_field_handler import generate_autofill_script
    
    try:
        session_dict = {
            'session_id': session_id,
            'url': scraped_form.get('url') if isinstance(scraped_form, dict) else scraped_form.url,
            'scraped_form': scraped_form if isinstance(scraped_form, dict) else scraped_form.model_dump(),
            'pre_filled_values': pre_filled_values or {}
        }
        
        script_content = generate_autofill_script(session_dict, '')
        
        # Save script to file
        upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
        scripts_dir = os.path.join(upload_dir, "scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        script_path = os.path.join(scripts_dir, f"{session_id}.py")
        
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        
        print(f"[ScriptGen] ✓ Script generated using executor_field_handler ({len(script_content)} chars)")
        print(f"[ScriptGen] ✓ Script saved: {script_path}")
        return script_content
        
    except Exception as e:
        print(f"[ScriptGen] ⚠ executor_field_handler failed: {e}")
        print(f"[ScriptGen] Falling back to legacy generation")
    
    # Legacy fallback code below
    print(f"[ScriptGen] Starting legacy script generation for session {session_id}")
    
    # Normalize scraped_form
    if isinstance(scraped_form, dict):
        url = scraped_form.get("url", "")
        fields = scraped_form.get("fields", [])
        submit_selector = scraped_form.get("submit_button_selector", "button[type='submit']")
        has_captcha = scraped_form.get("has_captcha", False)
    else:
        url = scraped_form.url
        fields = scraped_form.fields
        submit_selector = scraped_form.submit_button_selector
        has_captcha = scraped_form.has_captcha
    
    print(f"[ScriptGen] URL: {url}")
    print(f"[ScriptGen] Fields to fill: {len(fields)}")
    
    if not pre_filled_values:
        pre_filled_values = {}
    
    # Build field instructions using pre_filled_values
    field_instructions = []
    for field in fields:
        if isinstance(field, dict):
            fid = field.get("field_id")
            label = field.get("label", "")
            name = field.get("name", "")
            ftype = field.get("field_type", "text")
            selector = field.get("selector", "")
            raw_options = field.get("options", [])
        else:
            fid = field.field_id
            label = field.label
            name = field.name
            ftype = field.field_type
            selector = field.selector
            raw_options = field.options
        
        if ftype in ("submit", "reset", "button", "hidden"):
            continue
        
        # Normalize options to list of strings for script
        options = []
        for opt in raw_options:
            if isinstance(opt, str):
                options.append(opt)
            elif isinstance(opt, dict):
                options.append(opt.get('value', opt.get('label', '')))
        
        # Look up value from pre_filled_values using stable key (name or field_id)
        from utils.generic_mapper import compute_stable_field_key
        stable_key = compute_stable_field_key(field if isinstance(field, dict) else field.model_dump())
        value = pre_filled_values.get(stable_key, "")
        
        field_instructions.append({
            "label": label,
            "type": ftype,
            "selector": selector,
            "value": value,
            "file_path": None,
            "options": options
        })
    
    print(f"[ScriptGen] Building script for {len(field_instructions)} fillable fields")
    
    # Try AI script generation first
    script_content = None
    
    try:
        script_content = await _generate_script_with_ai(
            url, field_instructions, submit_selector, has_captcha, session_id
        )
        print(f"[ScriptGen] ✓ AI generated script ({len(script_content)} chars)")
    except Exception as e:
        print(f"[ScriptGen] ⚠ AI generation failed: {e}")
        print(f"[ScriptGen] Using rule-based script generation as fallback")
        script_content = _generate_script_without_ai(
            url, field_instructions, submit_selector, has_captcha, session_id
        )
        print(f"[ScriptGen] ✓ Rule-based script generated ({len(script_content)} chars)")
    
    # Validate Python syntax
    try:
        ast.parse(script_content)
        print(f"[ScriptGen] ✓ Script syntax is valid Python")
    except SyntaxError as e:
        print(f"[ScriptGen] ⚠ Syntax error in generated script: {e}")
        print(f"[ScriptGen] Falling back to rule-based generation")
        script_content = _generate_script_without_ai(
            url, field_instructions, submit_selector, has_captcha, session_id
        )
    
    # Save script to file
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    scripts_dir = os.path.join(upload_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    script_path = os.path.join(scripts_dir, f"{session_id}.py")
    
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    
    print(f"[ScriptGen] ✓ Script saved: {script_path}")
    return script_content


def _generate_script_without_ai(url, field_instructions, submit_selector, has_captcha, session_id) -> str:
    """
    Pure Python rule-based Playwright script generator.
    No AI needed — works 100% of the time.
    """
    lines = []
    lines.append("import asyncio")
    lines.append("import random")
    lines.append("import os")
    lines.append("import sys")
    lines.append("from playwright.sync_api import sync_playwright")
    lines.append("")
    lines.append("def main():")
    lines.append("    with sync_playwright() as p:")
    lines.append("        browser = p.chromium.launch(headless=False, slow_mo=50)")
    lines.append("        page = browser.new_page()")
    lines.append("        try:")
    lines.append(f"            print('EVENT:status:Navigating to form...')")
    lines.append(f"            page.goto({json.dumps(url)}, wait_until='networkidle', timeout=30000)")
    lines.append(f"            page.wait_for_timeout(1000)")
    lines.append("")
    
    for i, field in enumerate(field_instructions):
        label = field["label"]
        ftype = field["type"]
        selector = field["selector"]
        value = field["value"]
        file_path = field["file_path"]
        options = field["options"]
        
        lines.append(f"            # Field {i+1}: {label} ({ftype})")
        lines.append(f"            print('EVENT:field_start:{label}')")
        
        if ftype == "file":
            if file_path:
                lines.append(f"            try:")
                lines.append(f"                locator = page.locator({json.dumps(selector)})")
                lines.append(f"                if locator.count() > 0:")
                lines.append(f"                    locator.set_input_files({json.dumps(file_path)})")
                lines.append(f"                    page.wait_for_timeout(1000)")
                lines.append(f"                    print('EVENT:file_uploaded:{label}')")
                lines.append(f"                else:")
                lines.append(f"                    print('EVENT:file_skipped:{label}:selector not found')")
                lines.append(f"            except Exception as e:")
                lines.append(f"                print(f'EVENT:file_skipped:{label}:{{e}}')")
            else:
                lines.append(f"            print('EVENT:file_skipped:{label}:no file provided')")
        
        elif ftype == "select" and value:
            lines.append(f"            try:")
            lines.append(f"                locator = page.locator({json.dumps(selector)})")
            lines.append(f"                if locator.count() > 0:")
            lines.append(f"                    locator.select_option({json.dumps(value)})")
            lines.append(f"                    print('EVENT:field_filled:{label}:{str(value)[:20]}')")
            lines.append(f"                else:")
            lines.append(f"                    print('EVENT:field_skipped:{label}:selector not found')")
            lines.append(f"            except Exception as e:")
            lines.append(f"                print(f'EVENT:field_error:{label}:{{e}}')")
        
        elif ftype in ("radio", "checkbox") and value:
            lines.append(f"            try:")
            lines.append(f"                locator = page.locator({json.dumps(selector)})")
            lines.append(f"                if locator.count() > 0:")
            lines.append(f"                    locator.check()")
            lines.append(f"                    print('EVENT:field_filled:{label}:checked')")
            lines.append(f"            except Exception as e:")
            lines.append(f"                print(f'EVENT:field_error:{label}:{{e}}')")
        
        elif value:
            # Text, email, tel, number, date, textarea
            if len(str(value)) > 20:
                # Long values: use fill() for speed
                lines.append(f"            try:")
                lines.append(f"                locator = page.locator({json.dumps(selector)})")
                lines.append(f"                if locator.count() > 0:")
                lines.append(f"                    locator.click()")
                lines.append(f"                    page.wait_for_timeout(random.randint(200, 500))")
                lines.append(f"                    locator.fill({json.dumps(str(value))})")
                lines.append(f"                    page.wait_for_timeout(random.randint(300, 700))")
                lines.append(f"                    print('EVENT:field_filled:{label}:{str(value)[:20]}')")
                lines.append(f"                else:")
                lines.append(f"                    print('EVENT:field_skipped:{label}:selector not found')")
                lines.append(f"            except Exception as e:")
                lines.append(f"                print(f'EVENT:field_error:{label}:{{e}}')")
            else:
                # Short values: use press_sequentially for human-like typing
                lines.append(f"            try:")
                lines.append(f"                locator = page.locator({json.dumps(selector)})")
                lines.append(f"                if locator.count() > 0:")
                lines.append(f"                    locator.click()")
                lines.append(f"                    page.wait_for_timeout(random.randint(200, 400))")
                lines.append(f"                    locator.press_sequentially({json.dumps(str(value))}, delay=random.randint(60, 130))")
                lines.append(f"                    page.wait_for_timeout(random.randint(400, 900))")
                lines.append(f"                    print('EVENT:field_filled:{label}:{str(value)[:20]}')")
                lines.append(f"                else:")
                lines.append(f"                    print('EVENT:field_skipped:{label}:selector not found')")
                lines.append(f"            except Exception as e:")
                lines.append(f"                print(f'EVENT:field_error:{label}:{{e}}')")
        else:
            lines.append(f"            print('EVENT:field_skipped:{label}:no value provided')")
        
        lines.append("")
    
    # CAPTCHA detection before submit
    lines.append("            # Check for CAPTCHA before submitting")
    lines.append("            captcha_found = (")
    lines.append("                page.query_selector('iframe[src*=\"recaptcha\"]') or")
    lines.append("                page.query_selector('.h-captcha') or")
    lines.append("                page.query_selector('[class*=\"captcha\"]') or")
    lines.append("                page.query_selector('#captcha')")
    lines.append("            )")
    lines.append("            if captcha_found:")
    lines.append("                print('EVENT:captcha_detected')")
    lines.append("                print('Please solve the CAPTCHA in the browser window, then press Enter here...')")
    lines.append("                input()  # Wait for user")
    lines.append("")
    
    # Screenshot before submit
    lines.append("            # Take screenshot before submitting")
    lines.append("            page.wait_for_timeout(random.randint(1500, 2500))")
    lines.append("            page.screenshot(path='before_submit.png')")
    lines.append("            print('EVENT:status:Submitting form...')")
    lines.append("")
    
    # Submit
    lines.append(f"            # Click submit button")
    lines.append(f"            try:")
    lines.append(f"                submit = page.locator({json.dumps(submit_selector)})")
    lines.append(f"                if submit.count() == 0:")
    lines.append(f"                    # Try fallback selectors")
    lines.append(f"                    submit = page.locator('button[type=submit], input[type=submit], button:has-text(\"Submit\"), button:has-text(\"Apply\")')")
    lines.append(f"                submit.first.click()")
    lines.append(f"                page.wait_for_timeout(3000)")
    lines.append(f"                page.screenshot(path='after_submit.png')")
    lines.append(f"                print('EVENT:submission_complete')")
    lines.append(f"            except Exception as e:")
    lines.append(f"                print(f'EVENT:error:Submit failed: {{e}}')")
    lines.append("")
    lines.append("            input('Press Enter to close browser...')")
    lines.append("            browser.close()")
    lines.append("")
    lines.append("        except Exception as e:")
    lines.append(f"            print(f'EVENT:error:{{e}}')")
    lines.append("            browser.close()")
    lines.append("")
    lines.append("if __name__ == '__main__':")
    lines.append("    main()")
    
    return "\n".join(lines)


async def _generate_script_with_ai(url, field_instructions, submit_selector, has_captcha, session_id) -> str:
    """Try to generate script using configured AI (OpenRouter LLM)."""
    from utils.llm import get_llm_client
    
    # Build the prompt
    field_summary = json.dumps(field_instructions, indent=2, default=str)
    
    prompt = f"""Generate a complete Python Playwright script to fill this web form.

URL: {url}
Submit button selector: {submit_selector}

Fields to fill:
{field_summary}

Requirements:
- Use sync_playwright (NOT async)
- headless=False so user can see it
- slow_mo=50 for visible automation  
- Use press_sequentially for short text fields (under 20 chars)
- Use fill() for long text fields
- Print EVENT: lines for each action (see below)
- Handle selector not found gracefully with try/except
- Check for CAPTCHA before submit
- Take screenshot before and after submit

EVENT format to print:
  print('EVENT:field_filled:LABEL:VALUE')
  print('EVENT:file_uploaded:LABEL')  
  print('EVENT:captcha_detected')
  print('EVENT:submission_complete')
  print('EVENT:error:MESSAGE')

Return ONLY the Python script. No explanation. No markdown code blocks."""

    # Use OpenRouter LLM
    try:
        llm = get_llm_client()
        if llm.api_key:
            script = await llm.generate_content(
                prompt=prompt,
                temperature=0.1,
                max_tokens=4000
            )
            # Remove markdown code blocks if AI wrapped it
            if script.startswith("```python"):
                script = script[9:]
            if script.startswith("```"):
                script = script[3:]
            if script.endswith("```"):
                script = script[:-3]
            return script.strip()
    except Exception as e:
        print(f"[ScriptGen] LLM failed: {e}")
    
    raise Exception("LLM provider unavailable or failed")
