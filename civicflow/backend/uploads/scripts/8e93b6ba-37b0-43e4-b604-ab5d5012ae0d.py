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
            page.goto("https://demoqa.com/automation-practice-form", wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(1000)

            # Field 1: First Name (text)
            print('EVENT:field_start:First Name')
            try:
                locator = page.locator("#firstName")
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

            # Field 2: Last Name (text)
            print('EVENT:field_start:Last Name')
            try:
                locator = page.locator("#lastName")
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

            # Field 3: name@example.com (text)
            print('EVENT:field_start:name@example.com')
            try:
                locator = page.locator("#userEmail")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 500))
                    locator.fill("Kaivalya Sunil Sonawane")
                    page.wait_for_timeout(random.randint(300, 700))
                    print('EVENT:field_filled:name@example.com:Kaivalya Sunil Sonaw')
                else:
                    print('EVENT:field_skipped:name@example.com:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:name@example.com:{e}')

            # Field 4: Male (radio)
            print('EVENT:field_start:Male')
            try:
                locator = page.locator("#gender-radio-1")
                if locator.count() > 0:
                    locator.check()
                    print('EVENT:field_filled:Male:checked')
            except Exception as e:
                print(f'EVENT:field_error:Male:{e}')

            # Field 5: Mobile Number (text)
            print('EVENT:field_start:Mobile Number')
            try:
                locator = page.locator("#userNumber")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("07498148196", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:Mobile Number:07498148196')
                else:
                    print('EVENT:field_skipped:Mobile Number:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:Mobile Number:{e}')

            # Field 6: dateOfBirthInput (text)
            print('EVENT:field_start:dateOfBirthInput')
            try:
                locator = page.locator("#dateOfBirthInput")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("07/07/2005", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:dateOfBirthInput:07/07/2005')
                else:
                    print('EVENT:field_skipped:dateOfBirthInput:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:dateOfBirthInput:{e}')

            # Field 7: subjectsInput (text)
            print('EVENT:field_start:subjectsInput')
            try:
                locator = page.locator("#subjectsInput")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("asdas", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:subjectsInput:asdas')
                else:
                    print('EVENT:field_skipped:subjectsInput:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:subjectsInput:{e}')

            # Field 8: Sports (checkbox)
            print('EVENT:field_start:Sports')
            try:
                locator = page.locator("#hobbies-checkbox-1")
                if locator.count() > 0:
                    locator.check()
                    print('EVENT:field_filled:Sports:checked')
            except Exception as e:
                print(f'EVENT:field_error:Sports:{e}')

            # Field 9: Reading (checkbox)
            print('EVENT:field_start:Reading')
            try:
                locator = page.locator("#hobbies-checkbox-2")
                if locator.count() > 0:
                    locator.check()
                    print('EVENT:field_filled:Reading:checked')
            except Exception as e:
                print(f'EVENT:field_error:Reading:{e}')

            # Field 10: Music (checkbox)
            print('EVENT:field_start:Music')
            try:
                locator = page.locator("#hobbies-checkbox-3")
                if locator.count() > 0:
                    locator.check()
                    print('EVENT:field_filled:Music:checked')
            except Exception as e:
                print(f'EVENT:field_error:Music:{e}')

            # Field 11: uploadPicture (file)
            print('EVENT:field_start:uploadPicture')
            print('EVENT:file_skipped:uploadPicture:no file provided')

            # Field 12: Current Address (text)
            print('EVENT:field_start:Current Address')
            try:
                locator = page.locator("#currentAddress")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 500))
                    locator.fill("205-B Sanskar society Haridwar Complex")
                    page.wait_for_timeout(random.randint(300, 700))
                    print('EVENT:field_filled:Current Address:205-B Sanskar societ')
                else:
                    print('EVENT:field_skipped:Current Address:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:Current Address:{e}')

            # Field 13: react-select-3-input (text)
            print('EVENT:field_start:react-select-3-input')
            try:
                locator = page.locator("#react-select-3-input")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("dfsdf", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:react-select-3-input:dfsdf')
                else:
                    print('EVENT:field_skipped:react-select-3-input:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:react-select-3-input:{e}')

            # Field 14: react-select-4-input (text)
            print('EVENT:field_start:react-select-4-input')
            try:
                locator = page.locator("#react-select-4-input")
                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(random.randint(200, 400))
                    locator.press_sequentially("fsdf", delay=random.randint(60, 130))
                    page.wait_for_timeout(random.randint(400, 900))
                    print('EVENT:field_filled:react-select-4-input:fsdf')
                else:
                    print('EVENT:field_skipped:react-select-4-input:selector not found')
            except Exception as e:
                print(f'EVENT:field_error:react-select-4-input:{e}')

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
                submit = page.locator("#submit")
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