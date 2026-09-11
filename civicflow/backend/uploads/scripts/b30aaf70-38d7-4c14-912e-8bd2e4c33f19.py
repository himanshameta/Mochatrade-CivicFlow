"""
Auto-generated Playwright form filler
======================================
Generated from confirmed user data.
"""
import asyncio
from playwright.async_api import async_playwright
import sys
import os

# Add backend directory to path so 'agents', 'utils', 'models' are importable
sys.path.insert(0, "D:\\my stuff\\faraway3\\civicflow\\backend")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("EVENT:navigation:Loading page")
            await page.goto("https://aaplesarkar.mahaonline.gov.in/en/Login/Login", wait_until="networkidle")
            await asyncio.sleep(2)

            # Fill form fields
            # Fill: First Name
            print('EVENT:field_filling:First Name')
            try:
                await page.locator("#txtFirstName").fill("kaivalya")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill First Name: ' + str(e))

            # Fill: Last Name
            print('EVENT:field_filling:Last Name')
            try:
                await page.locator("#txtLastName").fill("sonawane")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Last Name: ' + str(e))

            # Fill: Age
            print('EVENT:field_filling:Age')
            try:
                await page.locator("#txtAge").fill("20")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Age: ' + str(e))

            # Fill: Contact Number
            print('EVENT:field_filling:Contact Number')
            try:
                await page.locator("#txtContact").fill("07498148196")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Contact Number: ' + str(e))

            # Submit form
            print("EVENT:submission:Clicking submit")
            submit_btn = page.locator("button[type='submit']")
            await submit_btn.click()
            await asyncio.sleep(3)

            # Check for CAPTCHA
            from agents.executor import detect_visible_captcha, check_resume_signal
            captcha_info = await detect_visible_captcha(page)
            if captcha_info['present']:
                print(f"EVENT:captcha_detected:{captcha_info['type']}:{captcha_info['reason']}")
                # Poll for resume signal
                while True:
                    signal = await check_resume_signal("b30aaf70-38d7-4c14-912e-8bd2e4c33f19")
                    if signal == "captcha_solved":
                        print("EVENT:resume:Continuing after CAPTCHA")
                        break
                    await asyncio.sleep(2)
            else:
                print("EVENT:captcha_not_detected")

            print("EVENT:submission_complete:Form submitted successfully")
            await asyncio.sleep(5)

        except Exception as e:
            print("EVENT:error:" + str(e))
            raise
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
