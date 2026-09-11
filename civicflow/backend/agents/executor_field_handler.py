"""
Executor Field Handler
=======================
Handles autofill for different field types using session.pre_filled_values.
This is the contract between the confirmation system and Playwright execution.
"""

def generate_fill_code(field: dict, value: str, session_id: str) -> str:
    """
    Generate Playwright code to fill a specific field type.
    
    Args:
        field: Field dict from scraped_form
        value: Confirmed value from session.pre_filled_values
        session_id: Session ID for logging
        
    Returns:
        Python code string for Playwright
    """
    field_type = field.get('field_type', 'text')
    selector = field.get('selector', '')
    label = field.get('label', 'Unknown')
    name = field.get('name', '')
    options = field.get('options', [])
    
    if not value or not selector:
        return f"    # Skip {label}: no value or selector\n"
    
    code = f"    # Fill: {label}\n"
    code += f"    print(f'EVENT:field_filling:{label}')\n"
    code += "    try:\n"
    
    if field_type in ['text', 'email', 'tel', 'number', 'password', 'url', 'search']:
        code += f"        await page.locator('{selector}').fill('{value}')\n"
        code += "        await asyncio.sleep(0.3)\n"
    
    elif field_type == 'textarea':
        code += f"        await page.locator('{selector}').fill('{value}')\n"
        code += "        await asyncio.sleep(0.3)\n"
    
    elif field_type == 'date':
        # Some date pickers need special handling
        code += f"        date_input = page.locator('{selector}')\n"
        code += f"        await date_input.fill('{value}')\n"
        code += "        await asyncio.sleep(0.3)\n"
    
    elif field_type == 'select':
        # Use select_option for dropdowns
        code += f"        select_elem = page.locator('{selector}')\n"
        code += f"        await select_elem.select_option(value='{value}')\n"
        code += "        await asyncio.sleep(0.3)\n"
    
    elif field_type == 'radio':
        # Find the specific radio option by value
        if name:
            code += f"        radio = page.locator('[name=\"{name}\"][value=\"{value}\"]')\n"
        else:
            code += f"        radio = page.locator('{selector}[value=\"{value}\"]')\n"
        code += "        await radio.check()\n"
        code += "        await asyncio.sleep(0.3)\n"
    
    elif field_type == 'checkbox':
        # Check or uncheck based on value
        should_check = value.lower() in ['true', 'yes', '1', 'on']
        action = 'check' if should_check else 'uncheck'
        code += f"        checkbox = page.locator('{selector}')\n"
        code += f"        await checkbox.{action}()\n"
        code += "        await asyncio.sleep(0.3)\n"
    
    elif field_type == 'file':
        # File upload - value should be file path
        code += f"        # File upload: {label}\n"
        code += f"        file_input = page.locator('{selector}')\n"
        code += f"        await file_input.set_input_files('{value}')\n"
        code += "        await asyncio.sleep(0.5)\n"
    
    else:
        # Fallback to text input
        code += f"        # Fallback fill for type {field_type}\n"
        code += f"        await page.locator('{selector}').fill('{value}')\n"
        code += "        await asyncio.sleep(0.3)\n"
    
    code += "    except Exception as e:\n"
    code += f"        print(f'EVENT:field_error:Failed to fill {label}: {{e}}')\n"
    code += "\n"
    
    return code


def generate_autofill_script(session_dict: dict, script_path: str) -> str:
    """
    Generate complete Playwright script using ONLY session.pre_filled_values.
    
    Args:
        session_dict: Complete session dict with scraped_form and pre_filled_values
        script_path: Where to save the script
        
    Returns:
        Generated script content
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
    
    # Script header
    script = '''"""
Auto-generated Playwright form filler
======================================
Generated from confirmed user data.
"""
import asyncio
from playwright.async_api import async_playwright
import sys
import os

# Add parent for executor imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print(f"EVENT:navigation:Loading page")
'''
    
    script += f'            await page.goto("{url}", wait_until="networkidle")\n'
    script += '            await asyncio.sleep(2)\n\n'
    
    # Generate fill code for each field with a value
    script += '            # Fill form fields\n'
    for field in fields:
        stable_key = compute_stable_field_key(field)
        value = pre_filled_values.get(stable_key)
        
        if value:
            script += generate_fill_code(field, str(value), session_id)
    
    # Submit handling
    script += '\n            # Submit form\n'
    script += '            print(f"EVENT:submission:Clicking submit")\n'
    script += f'            submit_btn = page.locator("{submit_selector}")\n'
    script += '            await submit_btn.click()\n'
    script += '            await asyncio.sleep(3)\n'
    script += '\n'
    
    # CAPTCHA check
    script += '            # Check for CAPTCHA\n'
    script += '            captcha_present = False\n'
    script += '            try:\n'
    script += '                # Check for common CAPTCHA indicators\n'
    script += '                recaptcha = await page.locator("iframe[src*=\\"recaptcha\\"]").count()\n'
    script += '                hcaptcha = await page.locator(".h-captcha").count()\n'
    script += '                if recaptcha > 0 or hcaptcha > 0:\n'
    script += '                    captcha_present = True\n'
    script += '            except:\n'
    script += '                pass\n'
    script += '\n'
    script += '            if captcha_present:\n'
    script += '                print("EVENT:captcha_detected:CAPTCHA found")\n'
    script += '                # Poll for resume signal\n'
    script += '                from agents.executor import check_resume_signal\n'
    script += f'                while True:\n'
    script += f'                    signal = await check_resume_signal("{session_id}")\n'
    script += '                    if signal == "captcha_solved":\n'
    script += '                        print("EVENT:resume:Continuing after CAPTCHA")\n'
    script += '                        break\n'
    script += '                    await asyncio.sleep(2)\n'
    script += '\n'
    
    # Success
    script += '            print("EVENT:submission_complete:Form submitted successfully")\n'
    script += '            await asyncio.sleep(5)\n'
    script += '\n'
    script += '        except Exception as e:\n'
    script += '            print(f"EVENT:error:{str(e)}")\n'
    script += '            raise\n'
    script += '        finally:\n'
    script += '            await browser.close()\n'
    script += '\n'
    script += 'if __name__ == "__main__":\n'
    script += '    asyncio.run(main())\n'
    
    return script


def compute_missing_required_fields(scraped_form: dict, pre_filled_values: dict) -> list:
    """
    Compute which required fields are still missing values.
    
    Args:
        scraped_form: Scraped form dict
        pre_filled_values: Dict of confirmed values
        
    Returns:
        List of missing field keys
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
