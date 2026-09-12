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


def normalize_field_type(raw_type: str, tag_name: str) -> str:
    """Normalize any HTML input type to our supported set."""
    raw = (raw_type or "").strip().lower()
    tag = (tag_name or "").strip().lower()

    # Handle non-input tags
    if tag == "textarea":
        return "textarea"
    if tag == "select":
        return "select"

    # If no type specified, default to text
    if not raw:
        return "text"

    # Direct supported types
    direct = {
        "text", "email", "tel", "date", "number", "radio",
        "checkbox", "file", "password", "search", "url",
        "hidden", "time", "month", "week", "datetime-local", "textarea"
    }
    if raw in direct:
        return raw

    # Map unsupported types to equivalents
    fallback_map = {
        "submit": "hidden",
        "button": "hidden",
        "reset": "hidden",
        "image": "hidden",
        "color": "text",
        "range": "number"
    }
    return fallback_map.get(raw, "text")


def is_security_field(name: str, field_id: str) -> bool:
    """Check if field is a security/spam field that should be filtered out."""
    security_terms = ['csrf', 'token', '_method', 'honeypot', 'authenticity', 'captcha-response']
    name_lower = (name or "").lower()
    id_lower = (field_id or "").lower()
    
    return any(term in name_lower or term in id_lower for term in security_terms)


def is_ignorable_field(element: Tag) -> bool:
    """Check if field should be ignored (not user-fillable)."""
    # Skip disabled fields
    if element.has_attr("disabled"):
        return True
    
    # Skip readonly fields (unless required for review)
    if element.has_attr("readonly") and not element.has_attr("required"):
        return True
    
    # Skip submit/button/reset types
    input_type = (element.get("type", "") or "").lower()
    if input_type in ["submit", "button", "reset", "image"]:
        return True
    
    return False


def is_search_form(form: Tag) -> bool:
    """Detect if form is just a site search box (should be skipped)."""
    inputs = form.find_all(["input", "select", "textarea"])
    
    # Only 1-2 fields = likely search
    if len(inputs) > 2:
        return False
    
    for inp in inputs:
        name = (inp.get("name", "") or "").lower()
        field_id = (inp.get("id", "") or "").lower()
        placeholder = (inp.get("placeholder", "") or "").lower()
        field_type = (inp.get("type", "") or "").lower()
        
        # Check for search-related attributes
        if field_type == "search":
            return True
        
        search_terms = ["search", "query", "q", "keyword", "find"]
        if any(term in name or term in field_id or term in placeholder for term in search_terms):
            return True
    
    return False


def score_form(form: Tag) -> int:
    """Score a form to determine if it's a real user form vs search/nav."""
    score = 0
    inputs = form.find_all(["input", "select", "textarea"])
    
    # Check if it's a search form (heavily penalize)
    if is_search_form(form):
        return -100
    
    for element in inputs:
        tag_name = element.name
        input_type = (element.get("type", "text") or "text").lower()
        
        # Skip non-user fields
        if is_ignorable_field(element):
            continue
        
        # Score by field type (higher = more likely real form)
        if input_type in ["text", "email", "tel"]:
            score += 3
        elif input_type == "email":
            score += 3
        elif input_type == "tel":
            score += 2
        elif input_type == "file":
            score += 2
        elif tag_name == "textarea":
            score += 2
        elif tag_name == "select" or input_type in ["radio", "checkbox"]:
            score += 1
    
    # Bonus for submit button with form-like text
    submit = form.find("button") or form.find("input", {"type": "submit"})
    if submit:
        submit_text = (submit.get_text() or submit.get("value", "")).lower()
        form_keywords = ["submit", "register", "apply", "send", "continue", "next", "save"]
        if any(kw in submit_text for kw in form_keywords):
            score += 5
    
    return score


def normalize_label(text: str) -> str:
    """Normalize label text: strip whitespace, remove asterisks, title case."""
    if not text:
        return ""
    text = text.strip()
    text = text.replace("*", "").replace(":", "")
    text = " ".join(text.split())
    return text.title() if text else ""


def get_label_for_element(element: Tag, soup: BeautifulSoup) -> str:
    """Extract label text for an input element with priority strategy."""
    # 1. Try id-matching label
    element_id = element.get("id", "")
    if element_id:
        label = soup.find("label", {"for": element_id})
        if label:
            return normalize_label(label.get_text())
    
    # 2. Try parent label
    parent = element.parent
    if parent and parent.name == "label":
        return normalize_label(parent.get_text())
    
    # 3. Try aria-label
    aria_label = element.get("aria-label", "")
    if aria_label:
        return normalize_label(aria_label)
    
    # 4. Try aria-labelledby
    aria_labelledby = element.get("aria-labelledby", "")
    if aria_labelledby:
        ref_elem = soup.find(id=aria_labelledby)
        if ref_elem:
            return normalize_label(ref_elem.get_text())
    
    # 5. Try Google Forms / ARIA question container heading or .M7eMe
    container = element.find_parent(attrs={"role": "listitem"}) or element.find_parent(class_=re.compile(r"(geFormPage|QrShBc|freebirdFormviewerViewItemsItemItem)", re.I))
    if container:
        heading = container.find(attrs={"role": "heading"}) or container.find(class_=re.compile(r"M7eMe", re.I))
        if heading:
            txt = heading.get_text(strip=True)
            if txt:
                return normalize_label(txt)
        c_aria = container.get("aria-label", "")
        if c_aria:
            return normalize_label(c_aria)

    # 6. Try previous label sibling
    prev_label = element.find_previous_sibling("label")
    if prev_label:
        return normalize_label(prev_label.get_text())
    
    # 7. Try preceding sibling text node
    prev = element.find_previous_sibling(string=True)
    if prev and prev.strip():
        return normalize_label(prev.strip())
    
    # 8. Try fieldset legend (for radio groups)
    fieldset = element.find_parent("fieldset")
    if fieldset:
        legend = fieldset.find("legend")
        if legend:
            return normalize_label(legend.get_text())
    
    # 9. Try nearby span/div text
    for tag in ['span', 'div', 'p']:
        prev_elem = element.find_previous_sibling(tag)
        if prev_elem:
            text = prev_elem.get_text(strip=True)
            if text and len(text) < 50:
                return normalize_label(text)
    
    # 10. Fallback to placeholder
    placeholder = element.get("placeholder", "")
    if placeholder:
        return normalize_label(placeholder)
    
    # 11. Fallback to name
    name = element.get("name", "")
    if name:
        return normalize_label(name)
    
    # 12. Final fallback
    return "Unnamed Field"


def extract_aria_and_google_forms_fields(soup: BeautifulSoup, target_form: Tag) -> list:
    """Extract fields from Google Forms and ARIA-based form structures."""
    import uuid
    fields = []
    seen_keys = set()

    # Find question containers or listitems
    containers = target_form.find_all(attrs={"role": "listitem"})
    if not containers:
        containers = target_form.find_all(class_=re.compile(r"(geFormPage|QrShBc|freebirdFormviewerViewItemsItemItem)", re.I))

    # Fallback: if no listitem containers, check if target_form itself has form controls
    if not containers:
        containers = [target_form]

    for container in containers:
        # Extract label / question text
        heading = (
            container.find(attrs={"role": "heading"}) or
            container.find(class_=re.compile(r"M7eMe", re.I)) or
            container.find(class_=re.compile(r"(title|question-title|label)", re.I))
        )
        label_text = ""
        if heading:
            label_text = normalize_label(heading.get_text())
        if not label_text:
            label_text = normalize_label(container.get("aria-label", ""))

        # Find hidden entry inputs associated with this question container
        entry_inputs = container.find_all("input", attrs={"name": re.compile(r"^entry\.", re.I)})
        entry_names = [inp.get("name") for inp in entry_inputs if inp.get("name")]

        # Determine required status
        required = (
            "*" in container.get_text() or
            container.find(attrs={"aria-required": "true"}) is not None or
            container.find(class_=re.compile(r"required", re.I)) is not None
        )

        # 1. Radio Group Check
        radio_group = container.find(attrs={"role": "radiogroup"})
        radio_elems = container.find_all(attrs={"role": "radio"})
        if radio_group or radio_elems:
            radios = radio_elems or (radio_group.find_all(attrs={"role": "radio"}) if radio_group else [])
            options = []
            for r in radios:
                opt_val = r.get("data-value") or r.get_text(strip=True)
                opt_lbl = r.get("aria-label") or r.get_text(strip=True) or opt_val
                if opt_val or opt_lbl:
                    options.append({"value": opt_val or opt_lbl, "label": normalize_label(opt_lbl or opt_val)})

            name = entry_names[0] if entry_names else ""
            dedup_key = name or label_text or f"radio_group_{len(fields)}"
            if dedup_key not in seen_keys and label_text:
                seen_keys.add(dedup_key)
                primary_selector = f"[name='{name}']" if name else "[role='radiogroup']"
                selector_priority = []
                if label_text:
                    selector_priority.append(f"getByLabel('{label_text}')")
                if name:
                    selector_priority.append(f"[name='{name}']")
                selector_priority.append("[role='radiogroup']")

                fields.append({
                    "field_id": str(uuid.uuid4()),
                    "label": label_text,
                    "field_type": "radio",
                    "name": name,
                    "id_attr": "",
                    "placeholder": "",
                    "required": required,
                    "options": options,
                    "selector": primary_selector,
                    "selector_priority": selector_priority,
                    "section": get_section_name(container),
                    "accept": None,
                    "multiple": False,
                    "order": len(fields)
                })
                continue

        # 2. Checkbox Group Check
        checkbox_elems = container.find_all(attrs={"role": "checkbox"})
        if checkbox_elems:
            options = []
            for c in checkbox_elems:
                opt_val = c.get("data-value") or c.get_text(strip=True)
                opt_lbl = c.get("aria-label") or c.get_text(strip=True) or opt_val
                if opt_val or opt_lbl:
                    options.append({"value": opt_val or opt_lbl, "label": normalize_label(opt_lbl or opt_val)})

            name = entry_names[0] if entry_names else ""
            dedup_key = name or label_text or f"checkbox_group_{len(fields)}"
            if dedup_key not in seen_keys and label_text:
                seen_keys.add(dedup_key)
                primary_selector = f"[name='{name}']" if name else "[role='checkbox']"
                selector_priority = []
                if label_text:
                    selector_priority.append(f"getByLabel('{label_text}')")
                if name:
                    selector_priority.append(f"[name='{name}']")
                selector_priority.append("[role='checkbox']")

                fields.append({
                    "field_id": str(uuid.uuid4()),
                    "label": label_text,
                    "field_type": "checkbox",
                    "name": name,
                    "id_attr": "",
                    "placeholder": "",
                    "required": required,
                    "options": options,
                    "selector": primary_selector,
                    "selector_priority": selector_priority,
                    "section": get_section_name(container),
                    "accept": None,
                    "multiple": True,
                    "order": len(fields)
                })
                continue

        # 3. Dropdown / Listbox Check
        listbox = container.find(attrs={"role": "listbox"})
        if listbox:
            opt_elems = listbox.find_all(attrs={"role": "option"})
            options = []
            for o in opt_elems:
                opt_val = o.get("data-value") or o.get_text(strip=True)
                opt_lbl = o.get_text(strip=True) or opt_val
                if opt_val or opt_lbl:
                    options.append({"value": opt_val or opt_lbl, "label": normalize_label(opt_lbl or opt_val)})

            name = entry_names[0] if entry_names else ""
            dedup_key = name or label_text or f"listbox_{len(fields)}"
            if dedup_key not in seen_keys and label_text:
                seen_keys.add(dedup_key)
                primary_selector = f"[name='{name}']" if name else "[role='listbox']"
                selector_priority = []
                if label_text:
                    selector_priority.append(f"getByLabel('{label_text}')")
                if name:
                    selector_priority.append(f"[name='{name}']")
                selector_priority.append("[role='listbox']")

                fields.append({
                    "field_id": str(uuid.uuid4()),
                    "label": label_text,
                    "field_type": "select",
                    "name": name,
                    "id_attr": "",
                    "placeholder": "",
                    "required": required,
                    "options": options,
                    "selector": primary_selector,
                    "selector_priority": selector_priority,
                    "section": get_section_name(container),
                    "accept": None,
                    "multiple": False,
                    "order": len(fields)
                })
                continue

        # 4. Text / Textarea / Date Check
        textarea = container.find("textarea") or container.find(class_=re.compile(r"KHwjSy|SPErbc", re.I))
        if textarea:
            name = textarea.get("name") or (entry_names[0] if entry_names else "")
            jsname = textarea.get("jsname", "")
            elem_id = textarea.get("id", "")
            aria_lbl = textarea.get("aria-label", "") or label_text
            dedup_key = name or elem_id or label_text or f"textarea_{len(fields)}"
            if dedup_key not in seen_keys and label_text:
                seen_keys.add(dedup_key)
                if aria_lbl:
                    primary_selector = f"textarea[aria-label='{aria_lbl}']"
                elif name:
                    primary_selector = f"[name='{name}']"
                elif jsname and textarea.name == "textarea":
                    primary_selector = f"textarea[jsname='{jsname}']"
                else:
                    primary_selector = f"div[role='listitem']:has-text('{label_text}') textarea" if label_text else "textarea"

                selector_priority = []
                if aria_lbl:
                    selector_priority.append(f"textarea[aria-label='{aria_lbl}']")
                if label_text:
                    selector_priority.append(f"getByLabel('{label_text}')")
                if name:
                    selector_priority.append(f"[name='{name}']")

                fields.append({
                    "field_id": str(uuid.uuid4()),
                    "label": label_text,
                    "field_type": "textarea",
                    "name": name,
                    "id_attr": elem_id,
                    "placeholder": textarea.get("placeholder", ""),
                    "required": required,
                    "options": [],
                    "selector": primary_selector,
                    "selector_priority": selector_priority,
                    "section": get_section_name(container),
                    "accept": None,
                    "multiple": False,
                    "order": len(fields)
                })
                continue

        text_input = (
            container.find("input", attrs={"type": re.compile(r"^(text|email|tel|number|date)$", re.I)}) or
            container.find("input", attrs={"jsname": True}) or
            container.find("input") or
            container.find(class_=re.compile(r"whsOnd|zWSnvd", re.I)) or
            container.find(attrs={"contenteditable": "true"})
        )
        if text_input or entry_names:
            name = ""
            elem_id = ""
            jsname = ""
            placeholder = ""
            aria_lbl = ""
            input_type = "text"
            
            if text_input:
                name = text_input.get("name", "")
                elem_id = text_input.get("id", "")
                jsname = text_input.get("jsname", "")
                placeholder = text_input.get("placeholder", "")
                aria_lbl = text_input.get("aria-label", "")
                raw_type = text_input.get("type", "text").lower()
                if raw_type in ["email", "tel", "number", "date"]:
                    input_type = raw_type

            if not name and entry_names:
                name = entry_names[0]

            dedup_key = name or elem_id or label_text or f"text_{len(fields)}"
            if dedup_key not in seen_keys and label_text:
                seen_keys.add(dedup_key)
                
                # Priority 1: name if specific entry or emailAddress
                if name and (name.startswith("entry.") or name == "emailAddress"):
                    primary_selector = f"input[name='{name}']"
                # Priority 2: explicit aria-label on input
                elif aria_lbl:
                    primary_selector = f"input[aria-label='{aria_lbl}']"
                # Priority 3: element id
                elif elem_id:
                    primary_selector = f"#{elem_id}"
                # Priority 4: jsname ONLY if tag is input
                elif jsname and text_input and text_input.name == "input":
                    primary_selector = f"input[jsname='{jsname}']"
                # Priority 5: listitem container anchor
                elif label_text:
                    primary_selector = f"div[role='listitem']:has-text('{label_text}') input"
                else:
                    primary_selector = "input[type='text']"

                selector_priority = []
                if aria_lbl:
                    selector_priority.append(f"input[aria-label='{aria_lbl}']")
                if label_text:
                    selector_priority.append(f"getByLabel('{label_text}')")
                if name:
                    selector_priority.append(f"input[name='{name}']")

                fields.append({
                    "field_id": str(uuid.uuid4()),
                    "label": label_text,
                    "field_type": input_type,
                    "name": name,
                    "id_attr": elem_id,
                    "placeholder": placeholder,
                    "required": required,
                    "options": [],
                    "selector": primary_selector,
                    "selector_priority": selector_priority,
                    "section": get_section_name(container),
                    "accept": None,
                    "multiple": False,
                    "order": len(fields)
                })
                continue


    return fields



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
    """Detect CAPTCHA presence and type (stricter rules to avoid false positives)."""
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html, "lxml")
    
    # Check for reCAPTCHA iframe
    recaptcha_iframe = soup.find("iframe", src=re.compile(r"recaptcha", re.I))
    if recaptcha_iframe:
        return True, "recaptcha"
    
    # Check for reCAPTCHA response textarea or g-recaptcha div
    recaptcha_response = soup.find("textarea", {"name": "g-recaptcha-response"})
    if recaptcha_response:
        return True, "recaptcha"
    
    recaptcha_div = soup.find(attrs={"class": re.compile(r"\bg-recaptcha\b", re.I)})
    if recaptcha_div:
        return True, "recaptcha"
    
    # Check for hCaptcha
    hcaptcha_div = soup.find("div", {"class": re.compile(r"h-captcha", re.I)})
    if hcaptcha_div:
        return True, "hcaptcha"
    
    # Check for hCaptcha response
    hcaptcha_response = soup.find("textarea", {"name": "h-captcha-response"})
    if hcaptcha_response:
        return True, "hcaptcha"
    
    # Check for explicit CAPTCHA-related IDs/classes (but not just the word "captcha")
    captcha_container = soup.find(attrs={"id": re.compile(r"captcha[-_](?:container|box|field|image)", re.I)})
    if captcha_container:
        return True, "image"
    
    captcha_class = soup.find(attrs={"class": re.compile(r"captcha[-_](?:container|box|field|image)", re.I)})
    if captcha_class:
        return True, "image"
    
    # No CAPTCHA detected
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
        print(f"[Scraper] [FAIL] HTML too short: {len(html.strip())} chars")
        return None
    
    print(f"[Scraper] [OK] Processing HTML of length {len(html)}")
    
    try:
        soup = BeautifulSoup(html, "lxml")
        
        # Find all forms and score them
        all_forms = soup.find_all("form")
        print(f"[Scraper] Found {len(all_forms)} form(s) in HTML")
        
        target_form = None
        
        if all_forms:
            # Score each form and pick the best
            scored_forms = [(form, score_form(form)) for form in all_forms]
            scored_forms.sort(key=lambda x: x[1], reverse=True)
            
            # Log scores for debugging
            for i, (form, score) in enumerate(scored_forms[:3], 1):
                print(f"[Scraper] Form {i} score: {score}")
            
            # Pick highest scoring form with positive score
            if scored_forms[0][1] > 0:
                target_form = scored_forms[0][0]
            else:
                print("[Scraper] All forms scored negative (likely search forms)")
        
        # Fallback: if no <form> tag, treat whole page as form
        if not target_form:
            print("[Scraper] No valid <form> tag found, searching for loose inputs...")
            all_inputs = soup.find_all(["input", "select", "textarea"])
            print(f"[Scraper] Found {len(all_inputs)} loose input elements")
            if not all_inputs:
                print("[Scraper] ✗ No form fields found anywhere on page")
                return None
            target_form = soup
        
        fields = []
        seen_names = set()
        
        for element in target_form.find_all(["input", "select", "textarea"]):
            # Skip ignorable fields
            if is_ignorable_field(element):
                continue
            
            tag_name = element.name
            raw_field_type = element.get("type", "text").lower()
            field_type = normalize_field_type(raw_field_type, tag_name)
            
            # Skip hidden fields
            if field_type == "hidden":
                continue
            
            name = element.get("name", "")
            elem_id = element.get("id", "")
            
            # Fallback to container entry.XXXXXXXX input name for Google Forms inputs
            if not name or not name.startswith("entry."):
                container = element.find_parent(attrs={"role": "listitem"}) or element.find_parent(class_=re.compile(r"(geFormPage|QrShBc|freebirdFormviewerViewItemsItemItem)", re.I))
                if container:
                    entry_inp = container.find("input", attrs={"name": re.compile(r"^entry\.", re.I)})
                    if entry_inp and entry_inp.get("name"):
                        name = entry_inp.get("name")

            # Skip security/spam fields
            if is_security_field(name, elem_id):
                continue

            
            placeholder = element.get("placeholder", "")
            required = element.has_attr("required") or element.get("required") == "required"
            
            accept = element.get("accept", "") if field_type == "file" else None
            multiple = element.has_attr("multiple") or element.get("multiple") == "multiple" if field_type == "file" else False
            
            # Get label text — try multiple strategies
            label_text = get_label_for_element(element, soup)
            
            # Skip duplicate names (e.g. same radio group counted once)
            dedup_key = name or elem_id or label_text
            if dedup_key and dedup_key in seen_names and field_type in ("radio",):
                continue
            seen_names.add(dedup_key)
            
            # Build selector priority list
            selector_priority = []
            if label_text:
                selector_priority.append(f"getByLabel('{label_text}')")
            if name:
                selector_priority.append(f"[name='{name}']")
            if elem_id:
                selector_priority.append(f"#{elem_id}")
            if placeholder:
                selector_priority.append(f"[placeholder='{placeholder}']")
            
            # Primary selector (first priority)
            if elem_id:
                selector = f"#{elem_id}"
            elif name:
                selector = f"[name='{name}']"
            elif placeholder:
                selector = f"[placeholder='{placeholder}']"
            else:
                selector = element.name
            
            # Get options for select/radio
            options = []
            if tag_name == "select":
                for opt in element.find_all("option"):
                    opt_val = opt.get("value", "")
                    opt_text = opt.get_text(strip=True)
                    if opt_val and opt_val not in ("", "0", "select", "choose"):
                        options.append({"value": opt_val, "label": opt_text or opt_val})
            elif field_type == "radio":
                # For radio, collect all options with same name
                radio_group = target_form.find_all("input", {"name": name, "type": "radio"})
                for radio in radio_group:
                    radio_val = radio.get("value", "")
                    radio_label = get_label_for_element(radio, soup)
                    if radio_val:
                        options.append({"value": radio_val, "label": radio_label})
            
            import uuid
            fields.append({
                "field_id": str(uuid.uuid4()),
                "label": label_text,
                "field_type": field_type,
                "name": name,
                "id_attr": elem_id,
                "placeholder": placeholder,
                "required": required,
                "options": options,
                "selector": selector,
                "selector_priority": selector_priority,
                "section": get_section_name(element),
                "accept": accept,
                "multiple": multiple,
                "order": len(fields)  # Preserve order
            })
        
        # Also extract fields from Google Forms / ARIA controls if standard fields are incomplete or 0
        aria_fields = extract_aria_and_google_forms_fields(soup, target_form)
        if aria_fields:
            existing_labels = {f["label"].lower() for f in fields if f.get("label")}
            existing_names = {f["name"] for f in fields if f.get("name")}
            for af in aria_fields:
                a_name = af.get("name")
                a_label = af.get("label", "").lower()
                if (a_name and a_name in existing_names) or (a_label and a_label in existing_labels):
                    continue
                af["order"] = len(fields)
                fields.append(af)
                if a_name:
                    existing_names.add(a_name)
                if a_label:
                    existing_labels.add(a_label)

        if not fields:
            print("[Scraper] ✗ Found form tag but extracted 0 fields")
            # Return structured warning instead of None
            return {
                "url": url,
                "page_title": soup.title.string if soup.title else "",
                "form_html": "",
                "fields": [],
                "submit_button_selector": "button[type='submit']",
                "has_captcha": False,
                "has_file_upload": False,
                "captcha_type": None,
                "scraped_at": datetime.now().isoformat(),
                "scrape_warning": "No fillable user fields found"
            }

        
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
        
        # Detect CAPTCHA with stricter rules
        has_captcha, captcha_type = detect_captcha(html)
        
        has_file_upload = any(f["field_type"] == "file" for f in fields)
        
        print(f"[Scraper] [OK] Extracted {len(fields)} fields | Submit: {submit_selector} | CAPTCHA: {has_captcha}")
        
        from datetime import datetime
        return {
            "url": url,
            "page_title": soup.title.string if soup.title else "",
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
