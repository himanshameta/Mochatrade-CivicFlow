import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def safe_click(page, selector, label):
    try:
        page.locator(selector).click(force=True)
        print(f"EVENT:field_filled:{label}:clicked")
    except Exception as e:
        print(f"EVENT:error:Failed to click {label} ({selector}): {e}")

def safe_fill(page, selector, label, value, use_press=False):
    try:
        if use_press:
            page.locator(selector).click()
            page.locator(selector).press_sequentially(value, delay=100)
        else:
            page.locator(selector).fill(value)
        print(f"EVENT:field_filled:{label}:{value}")
    except Exception as e:
        print(f"EVENT:error:Failed to fill {label} ({selector}): {e}")

def safe_upload(page, selector, label, file_path):
    try:
        if not Path(file_path).is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        page.locator(selector).set_input_files(file_path)
        print(f"EVENT:file_uploaded:{label}")
    except Exception as e:
        print(f"EVENT:error:Failed to upload {label} ({selector}): {e}")

def detect_captcha(page):
    # Simple heuristic: look for common captcha iframes or elements
    try:
        if page.locator("iframe[src*='recaptcha']").first.is_visible():
            return True
        if page.locator("text=CAPTCHA").first.is_visible():
            return True
    except Exception:
        pass
    return False

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto("https://demoqa.com/automation-practice-form", timeout=60000)
        except PlaywrightTimeoutError:
            print("EVENT:error:Page load timeout")
            return

        # Fill short text fields using press_sequentially (under 20 chars)
        short_fields = [
            ("#firstName", "First Name", "John"),
            ("#lastName", "Last Name", "Doe"),
            ("#userEmail", "Name@Example.Com", "john.doe@example.com"),
            ("#userNumber", "Mobile Number", "1234567890"),
        ]
        for selector, label, value in short_fields:
            safe_fill(page, selector, label, value, use_press=True)

        # Gender radio
        safe_click(page, "#gender-radio-1", "Male")

        # Date of Birth (click to open picker, then type)
        try:
            page.locator("#dateOfBirthInput").click()
            page.locator("#dateOfBirthInput").fill("10 Jan 1990")
            print("EVENT:field_filled:Unnamed Field:10 Jan 1990")
        except Exception as e:
            print(f"EVENT:error:Failed to set date of birth: {e}")

        # Subjects (type and press Enter)
        try:
            subjects_input = page.locator("#subjectsInput")
            subjects_input.click()
            subjects_input.fill("Maths")
            subjects_input.press("Enter")
            print("EVENT:field_filled:Unnamed Field:Maths")
        except Exception as e:
            print(f"EVENT:error:Failed to fill subjects: {e}")

        # Hobbies checkboxes
        safe_click(page, "#hobbies-checkbox-1", "Sports")
        safe_click(page, "#hobbies-checkbox-2", "Reading")
        safe_click(page, "#hobbies-checkbox-3", "Music")

        # Upload picture (use a placeholder image path)
        upload_path = "sample_picture.png"
        # Create a dummy file if it doesn't exist
        if not Path(upload_path).exists():
            Path(upload_path).write_bytes(b"\x89PNG\r\n\x1a\n")
        safe_upload(page, "#uploadPicture", "Unnamed Field", upload_path)

        # Current Address (long text, use fill)
        safe_fill(page, "#currentAddress", "Current Address",
                  "123 Main Street\nCityville\nCountryland", use_press=False)

        # State and City (react-select inputs)
        try:
            page.locator("#react-select-3-input").click()
            page.locator("#react-select-3-input").fill("NCR")
            page.locator("#react-select-3-input").press("Enter")
            print("EVENT:field_filled:Unnamed Field:NCR")
        except Exception as e:
            print(f"EVENT:error:Failed to select State: {e}")

        try:
            page.locator("#react-select-4-input").click()
            page.locator("#react-select-4-input").fill("Delhi")
            page.locator("#react-select-4-input").press("Enter")
            print("EVENT:field_filled:Unnamed Field:Delhi")
        except Exception as e:
            print(f"EVENT:error:Failed to select City: {e}")

        # Screenshot before submit
        try:
            page.screenshot(path="before_submit.png")
        except Exception as e:
            print(f"EVENT:error:Failed to take before-submit screenshot: {e}")

        # CAPTCHA detection
        if detect_captcha(page):
            print("EVENT:captcha_detected")
        else:
            # Submit form
            try:
                page.locator("#submit").click()
                print("EVENT:submission_complete")
            except Exception as e:
                print(f"EVENT:error:Failed to click submit: {e}")

        # Screenshot after submit
        try:
            page.screenshot(path="after_submit.png")
        except Exception as e:
            print(f"EVENT:error:Failed to take after-submit screenshot: {e}")

        context.close()
        browser.close()

if __name__ == "__main__":
    main()