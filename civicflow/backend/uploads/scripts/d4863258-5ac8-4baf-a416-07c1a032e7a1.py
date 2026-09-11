from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import os
import sys
import time

URL = "https://demoqa.com/automation-practice-form"
SUBMIT_SELECTOR = "#submit"
SCREENSHOT_BEFORE = "form_before.png"
SCREENSHOT_AFTER = "form_after.png"

# Helper to safely click hidden radio/checkbox labels
def safe_click(page, selector, label):
    try:
        # The actual input is hidden; click the associated label via for attribute
        page.locator(f"label[for='{selector.split('-')[-1]}']").click(force=True)
        print(f"EVENT:field_filled:{label}:checked")
    except Exception as e:
        print(f"EVENT:error:Failed to click {label} ({selector}): {e}")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(URL, wait_until="load")
        except PlaywrightTimeoutError:
            print("EVENT:error:Page load timeout")
            return

        # ---------- Fill Text Fields ----------
        fields = [
            {"label": "First Name", "selector": "#firstName", "value": "John"},
            {"label": "Last Name", "selector": "#lastName", "value": "Doe"},
            {"label": "Name@Example.Com", "selector": "#userEmail", "value": "john.doe@example.com"},
            {"label": "Mobile Number", "selector": "#userNumber", "value": "1234567890"},
            {"label": "Current Address", "selector": "#currentAddress", "value": "123 Main St, Springfield"},
        ]

        for f in fields:
            try:
                el = page.locator(f["selector"])
                if len(f["value"]) < 20:
                    el.click()
                    el.press_sequentially(f["value"])
                else:
                    el.fill(f["value"])
                print(f"EVENT:field_filled:{f['label']}:{f['value']}")
            except Exception as e:
                print(f"EVENT:error:Failed to fill {f['label']} ({f['selector']}): {e}")

        # ---------- Date of Birth ----------
        try:
            dob_input = page.locator("#dateOfBirthInput")
            dob_input.click()
            # Example: set to 10 Sep 1990
            dob_input.fill("10 Sep 1990")
            print("EVENT:field_filled:Date of Birth:10 Sep 1990")
        except Exception as e:
            print(f"EVENT:error:Failed to set Date of Birth: {e}")

        # ---------- Subjects ----------
        try:
            subjects = page.locator("#subjectsInput")
            subjects.click()
            subjects.fill("Maths")
            subjects.press("Enter")
            print("EVENT:field_filled:Subjects:Maths")
        except Exception as e:
            print(f"EVENT:error:Failed to fill Subjects: {e}")

        # ---------- Gender Radio ----------
        safe_click(page, "#gender-radio-1", "Male")

        # ---------- Hobbies Checkboxes ----------
        hobbies = [
            {"label": "Sports", "selector": "#hobbies-checkbox-1"},
            {"label": "Reading", "selector": "#hobbies-checkbox-2"},
            {"label": "Music", "selector": "#hobbies-checkbox-3"},
        ]
        for h in hobbies:
            safe_click(page, h["selector"], h["label"])

        # ---------- File Upload ----------
        try:
            file_path = os.path.abspath("sample.png")  # ensure a file exists at this path
            if not os.path.isfile(file_path):
                # create a dummy file
                with open(file_path, "wb") as f:
                    f.write(b"\x89PNG\r\n\x1a\n")
            page.set_input_files("#uploadPicture", file_path)
            print("EVENT:file_uploaded:Picture")
        except Exception as e:
            print(f"EVENT:error:File upload failed: {e}")

        # ---------- State / City (react-select) ----------
        try:
            # Click state dropdown
            page.locator("#state").click()
            page.locator("div[id^='react-select-3-option']").filter(has_text="NCR").click()
            print("EVENT:field_filled:State:NCR")
            # Click city dropdown
            page.locator("#city").click()
            page.locator("div[id^='react-select-4-option']").filter(has_text="Delhi").click()
            print("EVENT:field_filled:City:Delhi")
        except Exception as e:
            print(f"EVENT:error:Failed to select State/City: {e}")

        # ---------- Screenshot before submit ----------
        try:
            page.screenshot(path=SCREENSHOT_BEFORE, full_page=True)
        except Exception as e:
            print(f"EVENT:error:Screenshot before submit failed: {e}")

        # ---------- CAPTCHA detection ----------
        try:
            # DemoQA does not have a CAPTCHA, but we check for common patterns
            if page.locator("iframe[title*='captcha']").first.is_visible():
                print("EVENT:captcha_detected")
                # abort submission
                browser.close()
                return
        except Exception:
            # ignore if selector not found
            pass

        # ---------- Submit ----------
        try:
            page.locator(SUBMIT_SELECTOR).scroll_into_view_if_needed()
            page.locator(SUBMIT_SELECTOR).click()
            print("EVENT:submission_complete")
        except Exception as e:
            print(f"EVENT:error:Submit failed: {e}")

        # ---------- Screenshot after submit ----------
        try:
            page.screenshot(path=SCREENSHOT_AFTER, full_page=True)
        except Exception as e:
            print(f"EVENT:error:Screenshot after submit failed: {e}")

        # Keep browser open for a short while to view result
        time.sleep(5)
        context.close()
        browser.close()

if __name__ == "__main__":
    main()