import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Sample data to fill the form
DATA = {
    "First Name": "John",
    "Last Name": "Doe",
    "Name@Example.Com": "john.doe@example.com",
    "Male": None,  # radio, just click
    "Mobile Number": "1234567890",
    "Unnamed Field": {  # Date of Birth
        "selector": "#dateOfBirthInput",
        "value": "10 Jan 1990"
    },
    "Subjects": "Maths",
    "Sports": None,
    "Reading": None,
    "Music": None,
    "Unnamed Field_file": {  # picture upload
        "selector": "#uploadPicture",
        "path": "sample.png"
    },
    "Current Address": "123 Main Street, Springfield",
    "StateCity": {"state": "NCR", "city": "Delhi"}
}

def safe_click(page, selector, label):
    try:
        page.locator(selector).click(force=True)
        print(f"EVENT:field_filled:{label}:clicked")
    except PlaywrightTimeoutError:
        print(f"EVENT:error:Selector not found for {label}")

def safe_fill(page, selector, value, label):
    try:
        page.locator(selector).fill(value)
        print(f"EVENT:field_filled:{label}:{value}")
    except PlaywrightTimeoutError:
        print(f"EVENT:error:Selector not found for {label}")

def safe_type(page, selector, value, label):
    try:
        page.locator(selector).click()
        page.locator(selector).press_sequentially(value, delay=100)
        print(f"EVENT:field_filled:{label}:{value}")
    except PlaywrightTimeoutError:
        print(f"EVENT:error:Selector not found for {label}")

def upload_file(page, selector, file_path, label):
    try:
        path = Path(file_path)
        if not path.is_file():
            print(f"EVENT:error:File not found {file_path}")
            return
        page.locator(selector).set_input_files(str(path))
        print(f"EVENT:file_uploaded:{label}")
    except PlaywrightTimeoutError:
        print(f"EVENT:error:Selector not found for {label}")

def detect_captcha(page):
    # Simple heuristic: look for common captcha iframes or elements
    try:
        if page.locator("iframe[title*='captcha']").first.is_visible():
            print("EVENT:captcha_detected")
            return True
        if page.locator("div.g-recaptcha").first.is_visible():
            print("EVENT:captcha_detected")
            return True
    except Exception:
        pass
    return False

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://demoqa.com/automation-practice-form")
        page.wait_for_load_state("domcontentloaded")

        # First Name
        safe_type(page, "#firstName", DATA["First Name"], "First Name")

        # Last Name
        safe_type(page, "#lastName", DATA["Last Name"], "Last Name")

        # Email
        safe_type(page, "#userEmail", DATA["Name@Example.Com"], "Name@Example.Com")

        # Gender Radio - Male
        safe_click(page, "#gender-radio-1", "Male")

        # Mobile Number (short, use press_sequentially)
        safe_type(page, "#userNumber", DATA["Mobile Number"], "Mobile Number")

        # Date of Birth (use fill because it's a date picker)
        safe_fill(page, "#dateOfBirthInput", DATA["Unnamed Field"]["value"], "Date of Birth")
        # close date picker overlay if present
        page.keyboard.press("Escape")

        # Subjects (type and press Enter)
        try:
            subjects_input = page.locator("#subjectsInput")
            subjects_input.click()
            subjects_input.fill(DATA["Subjects"])
            subjects_input.press("Enter")
            print(f"EVENT:field_filled:Subjects:{DATA['Subjects']}")
        except PlaywrightTimeoutError:
            print("EVENT:error:Selector not found for Subjects")

        # Hobbies checkboxes
        safe_click(page, "#hobbies-checkbox-1", "Sports")
        safe_click(page, "#hobbies-checkbox-2", "Reading")
        safe_click(page, "#hobbies-checkbox-3", "Music")

        # Upload picture
        upload_file(page, "#uploadPicture", DATA["Unnamed Field_file"]["path"], "Picture")

        # Current Address (long text -> fill)
        safe_fill(page, "#currentAddress", DATA["Current Address"], "Current Address")

        # State selection (react-select)
        try:
            page.locator("#state").click()
            page.locator("div[id^='react-select-3-option-']").filter(has_text=DATA["StateCity"]["state"]).click()
            print(f"EVENT:field_filled:State:{DATA['StateCity']['state']}")
        except PlaywrightTimeoutError:
            print("EVENT:error:Selector not found for State")

        # City selection (react-select)
        try:
            page.locator("#city").click()
            page.locator("div[id^='react-select-4-option-']").filter(has_text=DATA["StateCity"]["city"]).click()
            print(f"EVENT:field_filled:City:{DATA['StateCity']['city']}")
        except PlaywrightTimeoutError:
            print("EVENT:error:Selector not found for City")

        # Screenshot before submit
        page.screenshot(path="before_submit.png")

        # Check for CAPTCHA
        if detect_captcha(page):
            print("EVENT:error:CAPTCHA present, aborting submission")
        else:
            # Submit
            try:
                page.locator("#submit").click()
                print("EVENT:submission_complete")
            except PlaywrightTimeoutError:
                print("EVENT:error:Submit button not found")

        # Screenshot after submit
        page.screenshot(path="after_submit.png")

        # Keep browser open for a short while to observe result
        time.sleep(5)
        context.close()
        browser.close()

if __name__ == "__main__":
    main()