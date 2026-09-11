import re
import asyncio
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup, Tag
from uuid import uuid4
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.form_models import FormField, ScrapedForm


def normalize_label(text: str) -> str:
    """Normalize label text: strip whitespace, remove asterisks, title case."""
    if not text:
        return ""
    text = text.strip()
    text = text.replace("*", "").replace(":", "")
    text = " ".join(text.split())
    return text.title() if text else ""


def get_label_for_element(element: Tag, soup: BeautifulSoup) -> str:
    """Extract label text for an input element."""
    # Try id-matching label
    element_id = element.get("id", "")
    if element_id:
        label = soup.find("label", {"for": element_id})
        if label:
            return normalize_label(label.get_text())
    
    # Try parent label
    parent = element.parent
    if parent and parent.name == "label":
        return normalize_label(parent.get_text())
    
    # Try aria-label
    aria_label = element.get("aria-label", "")
    if aria_label:
        return normalize_label(aria_label)
    
    # Try preceding sibling text
    prev = element.find_previous_sibling(string=True)
    if prev and prev.strip():
        return normalize_label(prev.strip())
    
    # Try previous label sibling
    prev_label = element.find_previous_sibling("label")
    if prev_label:
        return normalize_label(prev_label.get_text())
    
    # Fallback to name or placeholder
    name = element.get("name", "")
    placeholder = element.get("placeholder", "")
    return normalize_label(placeholder or name or "Unnamed Field")


def generate_selector(element: Tag, form: Tag) -> str:
    """Generate best CSS selector for an element."""
    element_id = element.get("id", "")
    if element_id:
        return f"#{element_id}"
    
    name = element.get("name", "")
    if name:
        element_type = element.get("type", "")
        if element_type:
            return f"[name='{name}'][type='{element_type}']"
        return f"[name='{name}']"
    
    placeholder = element.get("placeholder", "")
    if placeholder:
        return f"[placeholder='{placeholder}']"
    
    # Generate nth-of-type selector
    tag_name = element.name
    siblings = form.find_all(tag_name)
    if element in siblings:
        index = siblings.index(element) + 1
        return f"{tag_name}:nth-of-type({index})"
    
    return tag_name


def map_input_type(element: Tag) -> str:
    """Map HTML input type to our FormField type."""
    tag_name = element.name
    
    if tag_name == "textarea":
        return "textarea"
    elif tag_name == "select":
        return "select"
    
    input_type = element.get("type", "text").lower()
    
    type_mapping = {
        "text": "text",
        "email": "email",
        "tel": "tel",
        "date": "date",
        "number": "number",
        "password": "password",
        "radio": "radio",
        "checkbox": "checkbox",
        "file": "file",
        "hidden": "text",  # Treat hidden as text
        "url": "text",
        "search": "text",
        "time": "text",
        "datetime-local": "date",
    }
    
    return type_mapping.get(input_type, "text")


def detect_captcha(html: str) -> tuple[bool, Optional[str]]:
    """Detect CAPTCHA presence and type."""
    html_lower = html.lower()
    
    if "recaptcha" in html_lower:
        return True, "recaptcha"
    elif "hcaptcha" in html_lower:
        return True, "hcaptcha"
    elif "captcha" in html_lower:
        return True, "image"
    
    return False, None


def find_submit_button(form: Tag) -> str:
    """Find and generate selector for submit button."""
    # Look for input[type=submit]
    submit_input = form.find("input", {"type": "submit"})
    if submit_input:
        return generate_selector(submit_input, form)
    
    # Look for button[type=submit]
    submit_button = form.find("button", {"type": "submit"})
    if submit_button:
        return generate_selector(submit_button, form)
    
    # Look for button with submit-like text
    buttons = form.find_all("button")
    submit_keywords = ["submit", "apply", "register", "send", "next", "continue"]
    
    for button in buttons:
        button_text = button.get_text().lower().strip()
        if any(keyword in button_text for keyword in submit_keywords):
            return generate_selector(button, form)
    
    # Fallback to any button
    if buttons:
        return generate_selector(buttons[0], form)
    
    return "button[type='submit']"


def get_section_name(element: Tag) -> str:
    """Determine which section/fieldset this element belongs to."""
    fieldset = element.find_parent("fieldset")
    if fieldset:
        legend = fieldset.find("legend")
        if legend:
            return normalize_label(legend.get_text())
    return ""


async def scraper(html: str, url: str) -> Optional[dict]:
    """
    Extract all form fields from HTML with precision.
    
    Args:
        html: Raw HTML content
        url: Original URL
        
    Returns:
        dict representation of ScrapedForm, or None if scraping fails
    """
    if not html:
        print("[Scraper] ✗ HTML is None or empty")
        return None
    
    if len(html.strip()) < 100:
        print(f"[Scraper] ✗ HTML too short: {len(html.strip())} chars")
        return None
    
    print(f"[Scraper] ✓ Processing HTML of length {len(html)}")
    
    try:
        soup = BeautifulSoup(html, "lxml")
        
        # Strategy 1: Find largest form element
        all_forms = soup.find_all("form")
        print(f"[Scraper] Found {len(all_forms)} form(s) in HTML")
        
        # Strategy 2: If no <form> tag, look for inputs anywhere on the page
        # (some sites put inputs outside a form tag)
        if not all_forms:
            print("[Scraper] No <form> tag found, searching for loose inputs...")
            all_inputs = soup.find_all(["input", "select", "textarea"])
            print(f"[Scraper] Found {len(all_inputs)} loose input elements")
            if not all_inputs:
                print("[Scraper] ✗ No form fields found anywhere on page")
                return None
            # Treat the whole page as one form
            target_form = soup
        else:
            # Pick the form with the most inputs
            target_form = max(
                all_forms,
                key=lambda f: len(f.find_all(["input", "select", "textarea"]))
            )
            form_inputs = target_form.find_all(["input", "select", "textarea"])
            print(f"[Scraper] Selected form with {len(form_inputs)} fields")
        
        fields = []
        seen_names = set()
        
        for element in target_form.find_all(["input", "select", "textarea"]):
            field_type = element.get("type", "text").lower()
            
            # Skip hidden, submit, reset, button types
            if field_type in ("submit", "reset", "button", "image"):
                continue
            
            name = element.get("name", "")
            elem_id = element.get("id", "")
            placeholder = element.get("placeholder", "")
            required = element.has_attr("required") or element.get("required") == "required"
            
            # Get label text — try multiple strategies
            label_text = ""
            
            # Strategy 1: <label for="id">
            if elem_id:
                label_tag = soup.find("label", attrs={"for": elem_id})
                if label_tag:
                    label_text = label_tag.get_text(strip=True)
            
            # Strategy 2: parent <label>
            if not label_text:
                parent = element.find_parent("label")
                if parent:
                    label_text = parent.get_text(strip=True)
            
            # Strategy 3: preceding sibling text or label
            if not label_text:
                for sibling in element.find_previous_siblings():
                    if sibling.name == "label":
                        label_text = sibling.get_text(strip=True)
                        break
                    elif sibling.name in ("p", "div", "span", "td", "th"):
                        text = sibling.get_text(strip=True)
                        if text and len(text) < 100:
                            label_text = text
                            break
            
            # Strategy 4: aria-label attribute
            if not label_text:
                label_text = element.get("aria-label", "")
            
            # Strategy 5: fallback to name or placeholder
            if not label_text:
                label_text = name or placeholder or elem_id or f"field_{len(fields)+1}"
            
            # Clean label
            label_text = label_text.strip().rstrip("*:").strip()
            
            # Skip duplicate names (e.g. same radio group counted once)
            dedup_key = name or elem_id or label_text
            if dedup_key and dedup_key in seen_names and field_type in ("radio",):
                continue
            seen_names.add(dedup_key)
            
            # Build selector — priority: id > name > placeholder
            if elem_id:
                selector = f"#{elem_id}"
            elif name:
                selector = f"[name='{name}']"
            elif placeholder:
                selector = f"[placeholder='{placeholder}']"
            else:
                selector = element.name  # Last resort
            
            # Get options for select
            options = []
            if element.name == "select":
                options = [
                    opt.get("value", opt.get_text(strip=True))
                    for opt in element.find_all("option")
                    if opt.get("value") and opt.get("value") not in ("", "0", "select", "choose")
                ]
            
            import uuid
            fields.append({
                "field_id": str(uuid.uuid4()),
                "label": label_text,
                "field_type": field_type if element.name != "select" else "select",
                "name": name,
                "id_attr": elem_id,
                "placeholder": placeholder,
                "required": required,
                "options": options,
                "selector": selector,
                "section": ""
            })
        
        if not fields:
            print("[Scraper] ✗ Found form tag but extracted 0 fields")
            return None
        
        # Find submit button
        submit_button = (
            target_form.find("input", attrs={"type": "submit"}) or
            target_form.find("button", attrs={"type": "submit"}) or
            target_form.find("button") or
            soup.find("input", attrs={"type": "submit"}) or
            soup.find("button")
        )
        
        if submit_button:
            btn_id = submit_button.get("id", "")
            btn_name = submit_button.get("name", "")
            submit_selector = f"#{btn_id}" if btn_id else (f"[name='{btn_name}']" if btn_name else "button[type='submit']")
        else:
            submit_selector = "button[type='submit']"
        
        # Detect CAPTCHA
        html_lower = html.lower()
        has_captcha = any(word in html_lower for word in ["recaptcha", "hcaptcha", "captcha"])
        if "recaptcha" in html_lower:
            captcha_type = "recaptcha"
        elif "hcaptcha" in html_lower:
            captcha_type = "hcaptcha"
        elif has_captcha:
            captcha_type = "image"
        else:
            captcha_type = None
        
        has_file_upload = any(f["field_type"] == "file" for f in fields)
        
        print(f"[Scraper] ✓ Extracted {len(fields)} fields | Submit: {submit_selector} | CAPTCHA: {has_captcha}")
        
        from datetime import datetime
        return {
            "url": url,
            "page_title": BeautifulSoup(html, "lxml").title.string if BeautifulSoup(html, "lxml").title else "",
            "form_html": str(target_form)[:5000],  # Truncate for storage
            "fields": fields,
            "submit_button_selector": submit_selector,
            "has_captcha": has_captcha,
            "has_file_upload": has_file_upload,
            "captcha_type": captcha_type,
            "scraped_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"[Scraper] ✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    async def test_full_pipeline():
        print("=" * 80)
        print("Testing Scout + Scraper Pipeline")
        print("=" * 80)
        
        # Import scout
        from scout import scout
        
        test_url = "https://httpbin.org/forms/post"
        
        # Test Scout
        print(f"\n[1] Scouting URL: {test_url}")
        scout_result = await scout(test_url)
        
        if "error" in scout_result:
            print(f"Scout Error: {scout_result['error']}")
            return
        
        print(f"✓ Page Title: {scout_result['title']}")
        print(f"✓ Screenshot saved: {scout_result['screenshot_path']}")
        print(f"✓ HTML captured: {len(scout_result['html'])} chars")
        
        # Test Scraper
        print(f"\n[2] Scraping form fields...")
        scraped_form = await scraper(scout_result['html'], scout_result['url'])
        
        print(f"✓ Found {len(scraped_form.fields)} fields")
        print(f"✓ Submit button: {scraped_form.submit_button_selector}")
        print(f"✓ Has CAPTCHA: {scraped_form.has_captcha}")
        print(f"✓ Has file upload: {scraped_form.has_file_upload}")
        
        print("\n" + "=" * 80)
        print("Scraped Form as JSON:")
        print("=" * 80)
        print(scraped_form.model_dump_json(indent=2))
        
        print("\n" + "=" * 80)
        print("Field Details:")
        print("=" * 80)
        for i, field in enumerate(scraped_form.fields, 1):
            print(f"\n[Field {i}]")
            print(f"  Label: {field.label}")
            print(f"  Type: {field.field_type}")
            print(f"  Name: {field.name}")
            print(f"  Required: {field.required}")
            print(f"  Selector: {field.selector}")
            if field.options:
                print(f"  Options: {field.options}")
    
    asyncio.run(test_full_pipeline())
