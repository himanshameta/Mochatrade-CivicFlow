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
sys.path.insert(0, "C:\\Users\\khatr\\Downloads\\faraway-hack-main\\faraway-hack-main\\civicflow\\backend")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("EVENT:navigation:Loading page")
            await page.goto("https://demoqa.com/automation-practice-form", wait_until="networkidle")
            await asyncio.sleep(2)

            # Fill form fields
            # Fill: First Name
            print('EVENT:field_filling:First Name')
            try:
                await page.locator("#firstName").fill("mihir")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill First Name: ' + str(e))

            # Fill: Last Name
            print('EVENT:field_filling:Last Name')
            try:
                await page.locator("#lastName").fill("khatri")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Last Name: ' + str(e))

            # Fill: Name@Example.Com
            print('EVENT:field_filling:Name@Example.Com')
            try:
                await page.locator("#userEmail").fill("test@test.com")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Name@Example.Com: ' + str(e))

            # Fill: Male
            print('EVENT:field_filling:Male')
            try:
                radio = page.locator("[name=\"gender\"][value=\"Male\"]")
                await radio.check()
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Male: ' + str(e))

            # Fill: Mobile Number
            print('EVENT:field_filling:Mobile Number')
            try:
                await page.locator("#userNumber").fill("9226570903")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Mobile Number: ' + str(e))

            # Fill: Current Address
            print('EVENT:field_filling:Current Address')
            try:
                await page.locator("#currentAddress").fill("Vasai, India")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Current Address: ' + str(e))

            # Submit form
            print("EVENT:submission:Clicking submit")
            submit_btn = page.locator("#submit")
            await submit_btn.click()
            await asyncio.sleep(3)

            # Check for CAPTCHA
            from agents.executor import detect_visible_captcha, check_resume_signal
            captcha_info = await detect_visible_captcha(page)
            if captcha_info['present']:
                print(f"EVENT:captcha_detected:{captcha_info['type']}:{captcha_info['reason']}")
                # Poll for resume signal
                while True:
                    signal = await check_resume_signal("ad003ad1-7ad6-4f96-b7ba-c61aa6c6a593")
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
