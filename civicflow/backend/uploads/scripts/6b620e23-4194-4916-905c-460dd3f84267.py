import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def safe_click(page, selector, label):
    try:
        page.click(selector, force=True)
        print(f"EVENT:field_filled:{label}:clicked")
    except Exception as e:
        print(f"EVENT:error:Failed to click {label} - {e}")

def safe_fill(page, selector, label, value, use_press=False):
    try:
        if use_press:
            page.focus(selector)
            page.press_sequentially(selector, value, delay=100)
        else:
            page.fill(selector, value)
        print(f"EVENT:field_filled:{label}:{value}")
    except Exception as e:
        print(f"EVENT:error:Failed to fill {label} - {e}")

def safe_upload(page, selector, label, file_path):
    try:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        page.set_input_files(selector, file_path)
        print(f"EVENT:file_uploaded:{label}")
    except Exception as e:
        print(f"EVENT:error:Failed to upload file for {label} - {e}")

def captcha_present(page):
    # Simple heuristic: look for common captcha iframes or elements
    try:
        if page.query_selector("iframe[src*='recaptcha']") or page.query_selector("[id*='captcha']"):
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

        # Fill First Name (short)
        safe_fill(page, "#firstName", "First Name", "John", use_press=True)

        # Fill Last Name (short)
        safe_fill(page, "#lastName", "Last Name", "Doe", use_press=True)

        # Fill Email (short)
        safe_fill(page, "#userEmail", "Name@Example.Com", "john.doe@example.com", use_press=True)

        # Select Gender radio
        safe_click(page, "#gender-radio-1", "Male")

        # Fill Mobile Number (short)
        safe_fill(page, "#userNumber", "Mobile Number", "1234567890", use_press=True)

        # Fill Date of Birth (short) - using press to type date
        safe_fill(page, "#dateOfBirthInput", "Unnamed Field", "10 Jan 1990", use_press=True)

        # Fill Subjects (short) - type and press Enter
        try:
            page.click("#subjectsInput")
            page.fill("#subjectsInput", "Maths")
            page.keyboard.press("Enter")
            print("EVENT:field_filled:Unnamed Field:Maths")
        except Exception as e:
            print(f"EVENT:error:Failed to fill Subjects - {e}")

        # Check Hobbies checkboxes
        safe_click(page, "#hobbies-checkbox-1", "Sports")
        safe_click(page, "#hobbies-checkbox-2", "Reading")
        safe_click(page, "#hobbies-checkbox-3", "Music")

        # Upload picture (file)
        # Replace with an actual existing file path on your machine
        picture_path = "sample.png"
        safe_upload(page, "#uploadPicture", "Unnamed Field", picture_path)

        # Fill Current Address (long)
        safe_fill(page, "#currentAddress", "Current Address", "123 Main Street, Springfield, USA", use_press=False)

        # State and City selection (react-select)
        try:
            page.click("#state")
            page.fill("#react-select-3-input", "NCR")
            page.keyboard.press("Enter")
            print("EVENT:field_filled:Unnamed Field:NCR")
        except Exception as e:
            print(f"EVENT:error:Failed to select State - {e}")

        try:
            page.click("#city")
            page.fill("#react-select-4-input", "Delhi")
            page.keyboard.press("Enter")
            print("EVENT:field_filled:Unnamed Field:Delhi")
        except Exception as e:
            print(f"EVENT:error:Failed to select City - {e}")

        # Screenshot before submit
        try:
            page.screenshot(path="before_submit.png")
        except Exception as e:
            print(f"EVENT:error:Failed to take before submit screenshot - {e}")

        # Check for CAPTCHA
        if captcha_present(page):
            print("EVENT:captcha_detected")
        else:
            # Submit form
            try:
                page.click("#submit")
                print("EVENT:submission_complete")
            except Exception as e:
                print(f"EVENT:error:Failed to submit form - {e}")

        # Screenshot after submit
        try:
            page.screenshot(path="after_submit.png")
        except Exception as e:
            print(f"EVENT:error:Failed to take after submit screenshot - {e}")

        context.close()
        browser.close()

if __name__ == "__main__":
    main()