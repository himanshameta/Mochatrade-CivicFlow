import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def safe_click(page, selector, label):
    try:
        page.locator(selector).click(force=True)
        print(f'EVENT:field_filled:{label}:clicked')
    except Exception as e:
        print(f'EVENT:error:Failed to click {label} - {e}')

def safe_fill(page, selector, value, label):
    try:
        if len(value) < 20:
            page.locator(selector).press_sequentially(value, delay=100)
        else:
            page.locator(selector).fill(value)
        print(f'EVENT:field_filled:{label}:{value}')
    except Exception as e:
        print(f'EVENT:error:Failed to fill {label} - {e}')

def safe_check(page, selector, label):
    try:
        page.locator(selector).check(force=True)
        print(f'EVENT:field_filled:{label}:checked')
    except Exception as e:
        print(f'EVENT:error:Failed to check {label} - {e}')

def safe_upload(page, selector, file_path, label):
    try:
        if file_path and os.path.isfile(file_path):
            page.locator(selector).set_input_files(file_path)
            print(f'EVENT:file_uploaded:{label}')
        else:
            print(f'EVENT:error:File not found for {label}')
    except Exception as e:
        print(f'EVENT:error:Failed to upload file for {label} - {e}')

def detect_captcha(page):
    # Simple heuristic: look for common captcha iframes or elements
    try:
        if page.locator('iframe[src*="recaptcha"]').first.is_visible():
            return True
        if page.locator('text=CAPTCHA').first.is_visible():
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

        # Fill First Name
        safe_fill(page, "#firstName", "mihir", "First Name")
        # Fill Last Name
        safe_fill(page, "#lastName", "khatri", "Last Name")
        # Email (empty as per input)
        safe_fill(page, "#userEmail", "", "Name@Example.Com")
        # Gender Radio
        safe_click(page, "#gender-radio-1", "Male")
        # Mobile Number
        safe_fill(page, "#userNumber", "9226570903", "Mobile Number")
        # Date of Birth (leave as default, just click to open and close)
        try:
            page.locator("#dateOfBirthInput").click()
            page.locator("#dateOfBirthInput").press("Escape")
            print("EVENT:field_filled:Unnamed Field:dateOfBirthInput:opened")
        except Exception as e:
            print(f"EVENT:error:Failed to interact with date picker - {e}")
        # Subjects (leave empty)
        try:
            page.locator("#subjectsInput").click()
            print("EVENT:field_filled:Unnamed Field:subjectsInput:clicked")
        except Exception as e:
            print(f"EVENT:error:Failed to click subjects input - {e}")
        # Hobbies checkboxes
        safe_check(page, "#hobbies-checkbox-1", "Sports")
        safe_check(page, "#hobbies-checkbox-2", "Reading")
        safe_check(page, "#hobbies-checkbox-3", "Music")
        # Upload picture (no file provided)
        safe_upload(page, "#uploadPicture", None, "Upload Picture")
        # Current Address
        safe_fill(page, "#currentAddress", "tfygbjjj, yfuyg", "Current Address")
        # State/City (react-select, leave empty)
        try:
            page.locator("#react-select-3-input").click()
            print("EVENT:field_filled:Unnamed Field:react-select-3-input:clicked")
        except Exception as e:
            print(f"EVENT:error:Failed to interact with state/city selector - {e}")

        # Screenshot before submit
        page.screenshot(path="before_submit.png")
        print("EVENT:field_filled:Screenshot:before_submit.png")

        # CAPTCHA detection
        if detect_captcha(page):
            print("EVENT:captcha_detected")
        else:
            # Submit form
            try:
                page.locator("#submit").click()
                print("EVENT:field_filled:Submit:clicked")
            except Exception as e:
                print(f"EVENT:error:Failed to click submit - {e}")

        # Screenshot after submit
        page.screenshot(path="after_submit.png")
        print("EVENT:field_filled:Screenshot:after_submit.png")
        print("EVENT:submission_complete")

        context.close()
        browser.close()

if __name__ == "__main__":
    main()