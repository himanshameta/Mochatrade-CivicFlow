import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Configuration
URL = "https://demoqa.com/automation-practice-form"
SUBMIT_SELECTOR = "#submit"
HEADLESS = False
SLOW_MO = 50
SCREENSHOT_BEFORE = "before_submit.png"
SCREENSHOT_AFTER = "after_submit.png"

# Sample data to fill (replace with real data as needed)
DATA = {
    "First Name": "John",
    "Last Name": "Doe",
    "Name@Example.Com": "john.doe@example.com",
    "Male": "M",
    "Mobile Number": "1234567890",
    "Unnamed Field": {  # date of birth
        "#dateOfBirthInput": "10 Jan 1990"
    },
    "Subjects": "Maths",
    "Sports": True,
    "Reading": True,
    "Music": True,
    "Unnamed Field_file": "sample.png",  # path to upload picture
    "Current Address": "123 Main St, Springfield",
    "StateCity": {"state": "NCR", "city": "Delhi"}  # for react-select inputs
}

def safe_click(page, selector, label):
    try:
        page.click(selector, force=True)
        print(f"EVENT:field_filled:{label}:clicked")
    except PlaywrightTimeoutError:
        print(f"EVENT:error:Selector not found for {label} ({selector})")
    except Exception as e:
        print(f"EVENT:error:{str(e)}")

def fill_text(page, selector, label, value):
    try:
        if len(value) < 20:
            page.focus(selector)
            page.press_sequentially(selector, value, delay=100)
        else:
            page.fill(selector, value)
        print(f"EVENT:field_filled:{label}:{value}")
    except PlaywrightTimeoutError:
        print(f"EVENT:error:Selector not found for {label} ({selector})")
    except Exception as e:
        print(f"EVENT:error:{str(e)}")

def upload_file(page, selector, label, file_path):
    try:
        path = Path(file_path)
        if not path.is_file():
            print(f"EVENT:error:File not found {file_path}")
            return
        page.set_input_files(selector, str(path))
        print(f"EVENT:file_uploaded:{label}")
    except PlaywrightTimeoutError:
        print(f"EVENT:error:Selector not found for {label} ({selector})")
    except Exception as e:
        print(f"EVENT:error:{str(e)}")

def detect_captcha(page):
    # Simple heuristic: look for common captcha iframes or elements
    try:
        if page.query_selector("iframe[src*='recaptcha']") or page.query_selector("[class*='captcha']"):
            print("EVENT:captcha_detected")
            return True
    except Exception:
        pass
    return False

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(URL, wait_until="networkidle")
        except Exception as e:
            print(f"EVENT:error:Failed to load page - {e}")
            return

        # First Name
        fill_text(page, "#firstName", "First Name", DATA["First Name"])

        # Last Name
        fill_text(page, "#lastName", "Last Name", DATA["Last Name"])

        # Email
        fill_text(page, "#userEmail", "Name@Example.Com", DATA["Name@Example.Com"])

        # Gender Radio
        safe_click(page, "#gender-radio-1", "Male")

        # Mobile Number
        fill_text(page, "#userNumber", "Mobile Number", DATA["Mobile Number"])

        # Date of Birth (use click to open picker then type)
        try:
            page.click("#dateOfBirthInput", force=True)
            page.fill("#dateOfBirthInput", DATA["Unnamed Field"]["#dateOfBirthInput"])
            print(f"EVENT:field_filled:Unnamed Field:{DATA['Unnamed Field']['#dateOfBirthInput']}")
        except Exception as e:
            print(f"EVENT:error:{str(e)}")

        # Subjects (auto-complete)
        try:
            page.fill("#subjectsInput", DATA["Subjects"])
            page.keyboard.press("Enter")
            print(f"EVENT:field_filled:Subjects:{DATA['Subjects']}")
        except Exception as e:
            print(f"EVENT:error:{str(e)}")

        # Hobbies checkboxes
        for hobby_label, selector in [("Sports", "#hobbies-checkbox-1"),
                                      ("Reading", "#hobbies-checkbox-2"),
                                      ("Music", "#hobbies-checkbox-3")]:
            if DATA.get(hobby_label):
                safe_click(page, selector, hobby_label)

        # Upload picture
        upload_file(page, "#uploadPicture", "Unnamed Field", DATA["Unnamed Field_file"])

        # Current Address (long text -> use fill)
        fill_text(page, "#currentAddress", "Current Address", DATA["Current Address"])

        # State selection (react-select)
        try:
            page.click("#state")
            page.fill("#react-select-3-input", DATA["StateCity"]["state"])
            page.keyboard.press("Enter")
            print(f"EVENT:field_filled:State:{DATA['StateCity']['state']}")
        except Exception as e:
            print(f"EVENT:error:{str(e)}")

        # City selection (react-select)
        try:
            page.click("#city")
            page.fill("#react-select-4-input", DATA["StateCity"]["city"])
            page.keyboard.press("Enter")
            print(f"EVENT:field_filled:City:{DATA['StateCity']['city']}")
        except Exception as e:
            print(f"EVENT:error:{str(e)}")

        # Screenshot before submit
        try:
            page.screenshot(path=SCREENSHOT_BEFORE)
        except Exception as e:
            print(f"EVENT:error:Failed to take before screenshot - {e}")

        # Check CAPTCHA
        if detect_captcha(page):
            print("EVENT:captcha_detected")
            # Optionally pause for manual solving
            page.pause()
        else:
            # Submit form
            try:
                page.click(SUBMIT_SELECTOR, force=True)
                print("EVENT:submission_complete")
            except Exception as e:
                print(f"EVENT:error:Failed to submit - {e}")

        # Screenshot after submit
        try:
            page.screenshot(path=SCREENSHOT_AFTER)
        except Exception as e:
            print(f"EVENT:error:Failed to take after screenshot - {e}")

        context.close()
        browser.close()

if __name__ == "__main__":
    main()