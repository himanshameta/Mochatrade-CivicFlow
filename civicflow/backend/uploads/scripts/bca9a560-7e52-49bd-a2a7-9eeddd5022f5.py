import asyncio
import random
import os
import sys
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        page = browser.new_page()
        try:
            print('EVENT:status:Navigating to form...')
            page.goto("https://testing.qaautomationlabs.com/form.php", wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(1000)

            # Field 1: First Name (text)
            print('EVENT:field_start:First Name')
            try:
                locator = page.locator("#firstname")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("Kaivalya", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:First Name:Kaivalya')
                else:
                    print('EVENT:field_skipped:First Name:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:First Name:{e}')

            # Field 2: Middle Name (text)
            print('EVENT:field_start:Middle Name')
            try:
                locator = page.locator("#middlename")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("Sunil", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:Middle Name:Sunil')
                else:
                    print('EVENT:field_skipped:Middle Name:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:Middle Name:{e}')

            # Field 3: Last Name (text)
            print('EVENT:field_start:Last Name')
            try:
                locator = page.locator("#lastname")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("Sonawane", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:Last Name:Sonawane')
                else:
                    print('EVENT:field_skipped:Last Name:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:Last Name:{e}')

            # Field 4: Email (email)
            print('EVENT:field_start:Email')
            try:
                locator = page.locator("#email")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 500))
                    locator.fill("kaivalya775@gmail.com")
                    page.wait_for_timeout(random.randint(300, 700))
                    print('EVENT:field_filled:Email:kaivalya775@gmail.co')
                else:
                    print('EVENT:field_skipped:Email:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:Email:{e}')

            # Field 5: Password (password)
            print('EVENT:field_start:Password')
            try:
                locator = page.locator("#password")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("onepiecE@123", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:Password:onepiecE@123')
                else:
                    print('EVENT:field_skipped:Password:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:Password:{e}')

            # Field 6: Address (text)
            print('EVENT:field_start:Address')
            try:
                locator = page.locator("#address")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 500))
                    locator.fill("205-B Sanskar society Haridwar Complex")
                    page.wait_for_timeout(random.randint(300, 700))
                    print('EVENT:field_filled:Address:205-B Sanskar societ')
                else:
                    print('EVENT:field_skipped:Address:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:Address:{e}')

            # Field 7: City (text)
            print('EVENT:field_start:City')
            try:
                locator = page.locator("#city")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("Badlapur", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:City:Badlapur')
                else:
                    print('EVENT:field_skipped:City:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:City:{e}')

            # Field 8: State (text)
            print('EVENT:field_start:State')
            try:
                locator = page.locator("#states")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("Maharashtra", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:State:Maharashtra')
                else:
                    print('EVENT:field_skipped:State:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:State:{e}')

            # Field 9: Pin Code (number)
            print('EVENT:field_start:Pin Code')
            try:
                locator = page.locator("#pincode")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("421503", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:Pin Code:421503')
                else:
                    print('EVENT:field_skipped:Pin Code:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:Pin Code:{e}')

            # Check for CAPTCHA before submitting
            captcha_found = (
                page.query_selector('iframe[src*="recaptcha"]') or
                page.query_selector('.h-captcha') or
                page.query_selector('[class*="captcha"]') or
                page.query_selector('#captcha')
            )
            if captcha_found:
                print('EVENT:captcha_detected')
                print('Please solve the CAPTCHA in the browser window, then press Enter here...')
                input()  # Wait for user

            # Take screenshot before submitting
            page.wait_for_timeout(random.randint(1500, 2500))
            page.screenshot(path='before_submit.png')
            print('EVENT:status:Submitting form...')

            # Click submit button
            try:
                submit = page.locator("button[type='submit']")
                if submit.count() == 0:
                    # Try fallback selectors
                    submit = page.locator('button[type=submit], input[type=submit], button:has-text("Submit"), button:has-text("Apply")')
                submit.first.click()
                page.wait_for_timeout(3000)
                page.screenshot(path='after_submit.png')
                print('EVENT:submission_complete')
            except Exception as e:
                print(f'EVENT:error:Submit failed: {e}')

            input('Press Enter to close browser...')
            browser.close()

        except Exception as e:
            print(f'EVENT:error:{e}')
            browser.close()

if __name__ == '__main__':
    main()