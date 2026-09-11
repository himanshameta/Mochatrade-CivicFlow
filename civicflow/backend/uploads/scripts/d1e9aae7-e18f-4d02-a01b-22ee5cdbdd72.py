import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def safe_click(page, selector, label):
    try:
        page.locator(selector).click(force=True)
        print(f'EVENT:field_filled:{label}:clicked')
    except Exception as e:
        print(f'EVENT:error:Could not click {label} ({selector}): {e}')

def safe_fill(page, selector, value, label):
    try:
        if len(value) < 20:
            page.locator(selector).press_sequentially(value, delay=100)
        else:
            page.locator(selector).fill(value)
        print(f'EVENT:field_filled:{label}:{value}')
    except Exception as e:
        print(f'EVENT:error:Could not fill {label} ({selector}): {e}')

def safe_check(page, selector, label):
    try:
        page.locator(selector).check(force=True)
        print(f'EVENT:field_filled:{label}:true')
    except Exception as e:
        print(f'EVENT:error:Could not check {label} ({selector}): {e}')

def safe_upload(page, selector, file_path, label):
    try:
        if file_path and Path(file_path).exists():
            page.locator(selector).set_input_files(file_path)
            print(f'EVENT:file_uploaded:{label}')
        else:
            print(f'EVENT:error:File not found for {label}')
    except Exception as e:
        print(f'EVENT:error:Could not upload file for {label}: {e}')

def detect_captcha(page):
    # Simple heuristic: look for common captcha iframes or elements
    try:
        if page.locator('iframe[title*="captcha"], .g-recaptcha').first.is_visible():
            print('EVENT:captcha_detected')
            return True
    except Exception:
        pass
    return False

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context()
        page = context.new_page()
        page.goto('https://demoqa.com/automation-practice-form')
        page.wait_for_load_state('networkidle')

        # Fill text fields
        safe_fill(page, '#firstName', 'mihir', 'First Name')
        safe_fill(page, '#lastName', 'khatri', 'Last Name')
        safe_fill(page, '#userEmail', '', 'Name@Example.Com')
        safe_click(page, '#gender-radio-1', 'Male')
        safe_fill(page, '#userNumber', '9226570903', 'Mobile Number')
        safe_fill(page, '#dateOfBirthInput', '', 'Unnamed Field')
        safe_fill(page, '#subjectsInput', '', 'Unnamed Field')
        safe_check(page, '#hobbies-checkbox-1', 'Sports')
        safe_check(page, '#hobbies-checkbox-2', 'Reading')
        safe_check(page, '#hobbies-checkbox-3', 'Music')
        safe_upload(page, '#uploadPicture', None, 'Unnamed Field')
        safe_fill(page, '#currentAddress', 'tfygbjjj, yfuyg', 'Current Address')
        safe_fill(page, '#react-select-3-input', '', 'Unnamed Field')

        # Screenshot before submit
        page.screenshot(path='before_submit.png')

        # CAPTCHA detection
        if detect_captcha(page):
            print('EVENT:error:CAPTCHA present, cannot submit automatically')
        else:
            # Submit form
            try:
                page.locator('#submit').click()
                print('EVENT:submission_complete')
            except Exception as e:
                print(f'EVENT:error:Failed to click submit: {e}')

        # Screenshot after submit
        page.screenshot(path='after_submit.png')

        # Keep browser open for a short while to observe result
        time.sleep(5)
        context.close()
        browser.close()

if __name__ == '__main__':
    main()