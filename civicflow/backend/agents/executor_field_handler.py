"""
Executor Field Handler
=======================
Handles autofill for different field types using session.pre_filled_values.
This is the contract between the confirmation system and Playwright execution.
"""
import json
import os

def py_string(value: str) -> str:
    """Safely convert a value to a python string literal."""
    return repr("" if value is None else str(value))

def safe_event_label(label: str) -> str:
    """Normalize label for event logging to prevent string injection."""
    return "Unnamed Field" if not label else " ".join(str(label).split())


class PyBuilder:
    def __init__(self):
        self.lines = []
        self.level = 0

    def add(self, line=""):
        if not line:
            self.lines.append("")
        else:
            self.lines.append("    " * self.level + line)

    def indent(self):
        self.level += 1

    def dedent(self):
        self.level = max(0, self.level - 1)

    def render(self):
        return "\n".join(self.lines) + "\n"


def generate_fill_code(field: dict, value: str, session_id: str, b: PyBuilder) -> None:
    """
    Generate Playwright code to fill a specific field type using PyBuilder.
    """
    field_type = field.get('field_type', 'text')
    selector = field.get('selector', '')
    raw_label = field.get('label', 'Unknown')
    name = field.get('name', '')
    
    if not value or not selector:
        b.add(f"# Skip {raw_label}: no value or selector")
        return
        
    label = safe_event_label(raw_label)
    
    print(f"[ScriptGen] Rendering field label={repr(label)} type={repr(field_type)} selector={repr(selector)} value={repr(value)}")
    
    b.add(f"# Fill: {raw_label}")
    b.add(f"print({py_string('EVENT:field_filling:' + label)}, flush=True)")
    b.add("try:")
    b.indent()
    
    value_json = json.dumps(str(value))
    selector_json = json.dumps(str(selector))
    
    if field_type in ['text', 'email', 'tel', 'number', 'password', 'url', 'search', 'textarea', 'date']:
        b.add(f"target_loc = page.locator({selector_json})")
        b.add("if await target_loc.count() != 1:")
        b.indent()
        fallback_sel_str = f'div[role="listitem"]:has-text("{raw_label}") input, div[role="listitem"]:has-text("{raw_label}") textarea, input[aria-label="{raw_label}"]'
        b.add(f"refined = page.locator({json.dumps(fallback_sel_str)})")
        b.add("if await refined.count() > 0:")
        b.indent()
        b.add("target_loc = refined.first")
        b.dedent()
        b.dedent()
        b.add("if await target_loc.count() > 0:")
        b.indent()
        b.add("elem = target_loc.first")
        b.add("tag = await elem.evaluate('el => el.tagName.toLowerCase()')")
        b.add("if tag not in ['input', 'textarea', 'select'] and not (await elem.evaluate('el => el.isContentEditable')):")
        b.indent()
        b.add("inner = elem.locator('input, textarea')")
        b.add("if await inner.count() > 0:")
        b.indent()
        b.add("elem = inner.first")
        b.dedent()
        b.dedent()
        b.add(f"await elem.fill({value_json})")
        b.add("await asyncio.sleep(0.3)")
        b.add(f"print({py_string('EVENT:field_filled:' + label + ':')}, flush=True)")
        b.dedent()
        b.add("else:")
        b.indent()
        b.add(f"print({py_string('EVENT:field_skipped:' + label + ':selector not found')}, flush=True)")
        b.dedent()
    
    elif field_type == 'select':
        b.add(f"select_elem = page.locator({selector_json})")
        b.add(f"await select_elem.select_option(value={value_json})")
        b.add("await asyncio.sleep(0.3)")
    
    elif field_type == 'radio':
        css_value = str(value).replace('"', '\\"')
        if name:
            css_name = str(name).replace('"', '\\"')
            locator_str = f'[name="{css_name}"][value="{css_value}"]'
        else:
            locator_str = f'{selector}[value="{css_value}"]'
        
        radio_locator_json = json.dumps(locator_str)
        b.add(f"radio = page.locator({radio_locator_json})")
        b.add("await radio.check()")
        b.add("await asyncio.sleep(0.3)")
    
    elif field_type == 'checkbox':
        should_check = str(value).lower() in ['true', 'yes', '1', 'on']
        action = 'check' if should_check else 'uncheck'
        b.add(f"checkbox = page.locator({selector_json})")
        b.add(f"await checkbox.{action}()")
        b.add("await asyncio.sleep(0.3)")
    
    elif field_type == 'file':
        b.add(f"# File upload: {raw_label} — resolved from vault/temp path")
        b.add(f"file_input = page.locator({selector_json})")
        # value is an absolute file path (resolved by scriptgen from selected_documents)
        # For multiple files, value is a JSON-encoded list of paths
        try:
            paths = json.loads(value) if value.startswith('[') else None
        except (json.JSONDecodeError, AttributeError):
            paths = None
        
        if paths and isinstance(paths, list):
            paths_json = json.dumps(paths)
            b.add(f"await file_input.set_input_files({paths_json})")
        else:
            b.add(f"await file_input.set_input_files({value_json})")
        b.add("await asyncio.sleep(0.5)")
    
    else:
        b.add(f"# Fallback fill for type {field_type}")
        b.add(f"await page.locator({selector_json}).fill({value_json})")
        b.add("await asyncio.sleep(0.3)")
    
    b.dedent()
    b.add("except Exception as e:")
    b.indent()
    b.add("err_str = str(e)")
    b.add('if "Target page, context or browser has been closed" in err_str or "TargetClosedError" in type(e).__name__ or "BrowserClosedError" in type(e).__name__:')
    b.indent()
    b.add("raise")
    b.dedent()
    b.add("else:")
    b.indent()
    b.add(f"print({py_string('EVENT:field_error:Failed to fill ' + label + ': ')} + err_str, flush=True)")
    b.dedent()
    b.dedent()
    b.add("")


def generate_autofill_script(session_dict: dict, script_path: str) -> str:
    """
    Generate complete Playwright script using ONLY session.pre_filled_values.
    """
    from utils.enhanced_mapper import compute_stable_field_key
    
    url = session_dict.get('url', '')
    session_id = session_dict.get('session_id', 'unknown')
    scraped_form = session_dict.get('scraped_form', {})
    pre_filled_values = session_dict.get('pre_filled_values', {})
    
    if not scraped_form or not pre_filled_values:
        raise ValueError("Missing scraped_form or pre_filled_values")
    
    fields = scraped_form.get('fields', [])
    submit_selector = scraped_form.get('submit_button_selector', 'button[type="submit"]')
    
    b = PyBuilder()
    
    b.add('"""')
    b.add("Auto-generated Playwright form filler")
    b.add("======================================")
    b.add("Generated from confirmed user data.")
    b.add('"""')
    b.add("import asyncio")
    b.add("from playwright.async_api import async_playwright, Error as PlaywrightError")
    b.add("import sys")
    b.add("import os")
    b.add("")
    b.add("# Add backend directory to path so 'agents', 'utils', 'models' are importable")
    b.add(f"sys.path.insert(0, {json.dumps(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))})")
    b.add("")
    b.add("async def main():")
    b.indent()
    b.add("async with async_playwright() as p:")
    b.indent()
    b.add("browser = await p.chromium.launch(headless=False)")
    b.add("context = await browser.new_context()")
    b.add("page = await context.new_page()")
    b.add("")
    b.add("try:")
    b.indent()
    b.add('print("EVENT:navigation:Loading page", flush=True)')
    b.add(f'await page.goto({json.dumps(url)}, wait_until="networkidle")')
    b.add("await asyncio.sleep(2)")
    b.add("")
    
    b.add("# Fill form fields")
    for field in fields:
        stable_key = compute_stable_field_key(field)
        
        if field.get('field_type') == 'file':
            # Resolve file path from selected_documents (vault system)
            selected_docs = session_dict.get('selected_documents', {})
            key = field.get("name") or field.get("id_attr") or field.get("label", "file_upload")
            sel = selected_docs.get(key, [])
            
            file_path = None
            if sel:
                doc_ref = sel[0] if isinstance(sel, list) else sel
                # If it looks like a path (temp file), use directly
                if isinstance(doc_ref, str) and (os.sep in doc_ref or '/' in doc_ref):
                    file_path = doc_ref
                else:
                    # It's a document_id — resolve via vault DB synchronously
                    # At script generation time we need the path, so look it up from file_requirements
                    for req in session_dict.get('file_requirements', []):
                        if req.get("key") == key and req.get("selected_document_id") == doc_ref:
                            # Path must be resolved by the caller (orchestrator)
                            # Fallback: check matched_document for legacy compat
                            md = req.get("matched_document")
                            if md:
                                file_path = md.get("file_path")
                            break
                    
                    # Try legacy format too
                    if not file_path:
                        for req in session_dict.get('file_requirements', []):
                            if req.get("key") == key and req.get("matched_document"):
                                file_path = req["matched_document"].get("file_path")
                                break
                    
            if file_path:
                generate_fill_code(field, file_path, session_id, b)
        else:
            value = pre_filled_values.get(stable_key)
            if value:
                generate_fill_code(field, str(value), session_id, b)
    
    b.add("# Submit form")
    b.add('print("EVENT:submitting:Submitting form", flush=True)')
    b.add(f'submit_loc = page.locator({json.dumps(submit_selector)})')
    b.add("try:")
    b.indent()
    b.add("if await submit_loc.count() == 0 or not (await submit_loc.first.is_visible()):")
    b.indent()
    b.add('fallback_submit = page.locator(\'div[role="button"]:has-text("Submit"), [role="button"]:has-text("Submit"), button[type="submit"], input[type="submit"]\')')
    b.add("if await fallback_submit.count() > 0:")
    b.indent()
    b.add("submit_loc = fallback_submit.first")
    b.dedent()
    b.dedent()
    b.dedent()
    b.add("except Exception:")
    b.indent()
    b.add('submit_loc = page.locator(\'div[role="button"]:has-text("Submit"), [role="button"]:has-text("Submit"), button[type="submit"], input[type="submit"]\').first')
    b.dedent()
    b.add("print('EVENT:submission:Clicking submit', flush=True)")
    b.add("await submit_loc.click()")
    b.add("await asyncio.sleep(2.5)")
    b.add("")
    
    b.add("# Check for CAPTCHA")
    b.add("from agents.executor import detect_visible_captcha, check_resume_signal")
    b.add("captcha_info = await detect_visible_captcha(page)")
    b.add("if captcha_info['present']:")
    b.indent()
    b.add("print(f\"EVENT:captcha_detected:{captcha_info['type']}:{captcha_info['reason']}\", flush=True)")
    b.add("# Poll for resume signal")
    b.add("while True:")
    b.indent()
    b.add(f'signal = await check_resume_signal({json.dumps(session_id)})')
    b.add('if signal == "captcha_solved":')
    b.indent()
    b.add('print("EVENT:resume:Continuing after CAPTCHA", flush=True)')
    b.add("break")
    b.dedent()
    b.add("await asyncio.sleep(2)")
    b.dedent()
    b.dedent()
    b.add("else:")
    b.indent()
    b.add('print("EVENT:captcha_not_detected", flush=True)')
    b.dedent()
    b.add("")
    
    b.add("# Verify post-submit confirmation")
    b.add("verified = False")
    b.add("current_url = page.url")
    b.add("page_text = await page.evaluate('() => document.body.innerText')")
    b.add("if 'formResponse' in current_url or 'response has been recorded' in page_text.lower() or 'submitted' in page_text.lower() or 'thank you' in page_text.lower() or 'successful' in page_text.lower():")
    b.indent()
    b.add("verified = True")
    b.dedent()
    b.add("else:")
    b.indent()
    b.add("try:")
    b.indent()
    b.add("if await submit_loc.count() == 0 or not (await submit_loc.is_visible()):")
    b.indent()
    b.add("verified = True")
    b.dedent()
    b.dedent()
    b.add("except Exception:")
    b.indent()
    b.add("verified = True")
    b.dedent()
    b.dedent()
    b.add("")
    b.add("if verified:")
    b.indent()
    b.add("try:")
    b.indent()
    b.add('upload_dir = os.getenv("UPLOAD_DIR", "./uploads")')
    b.add('shots_dir = os.path.join(upload_dir, "screenshots")')
    b.add('os.makedirs(shots_dir, exist_ok=True)')
    b.add(f'shot_path = os.path.join(shots_dir, f"{session_id}_after_submit.png")')
    b.add('await page.screenshot(path=shot_path)')
    b.add('print("EVENT:screenshot:" + shot_path, flush=True)')
    b.dedent()
    b.add("except Exception:")
    b.indent()
    b.add("pass")
    b.dedent()
    b.add('print("EVENT:submission_complete:Form submitted and verified successfully", flush=True)')
    b.add("await asyncio.sleep(1)")
    b.dedent()
    b.add("else:")
    b.indent()
    b.add('print("EVENT:error:Form submission could not be verified post-click", flush=True)')
    b.add('raise RuntimeError("Form submission could not be verified post-click")')
    b.dedent()
    b.add("")
    
    b.dedent()
    b.add("except Exception as e:")
    b.indent()
    b.add("err_str = str(e)")
    b.add('if "Target page, context or browser has been closed" in err_str or "TargetClosedError" in type(e).__name__ or "BrowserClosedError" in type(e).__name__:')
    b.indent()
    b.add('print("EVENT:interrupted:Browser window closed by user", flush=True)')
    b.dedent()
    b.add("else:")
    b.indent()
    b.add('print("EVENT:error:" + err_str, flush=True)')
    b.add("raise")
    b.dedent()
    b.dedent()
    b.add("finally:")
    b.indent()
    b.add("try:")
    b.indent()
    b.add("if not page.is_closed():")
    b.indent()
    b.add("await browser.close()")
    b.dedent()
    b.dedent()
    b.add("except Exception:")
    b.indent()
    b.add("pass")
    b.dedent()
    b.level = 0
    b.add("")
    b.add('if __name__ == "__main__":')
    b.indent()
    b.add("asyncio.run(main())")
    
    return b.render()


def compute_missing_required_fields(scraped_form: dict, pre_filled_values: dict) -> list:
    """
    Compute which required fields are still missing values.
    """
    from utils.enhanced_mapper import compute_stable_field_key
    
    missing = []
    fields = scraped_form.get('fields', [])
    
    for field in fields:
        if field.get('required', False):
            stable_key = compute_stable_field_key(field)
            value = pre_filled_values.get(stable_key, '').strip()
            
            if not value:
                missing.append(stable_key)
    
    return missing
