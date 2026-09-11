"""
Auto-generated Playwright form filler
======================================
Generated from confirmed user data.
"""
import asyncio
from playwright.async_api import async_playwright
import sys
import os

# Add parent for executor imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("EVENT:navigation:Loading page")
            await page.goto("https://testing.qaautomationlabs.com/form.php", wait_until="networkidle")
            await asyncio.sleep(2)

            # Fill form fields
            # Fill: First Name
            print('EVENT:field_filling:First Name')
            try:
                await page.locator("#firstname").fill("Elon")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill First Name: ' + str(e))

            # Fill: Middle Name
            print('EVENT:field_filling:Middle Name')
            try:
                await page.locator("#middlename").fill("Sunil")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Middle Name: ' + str(e))

            # Fill: Last Name
            print('EVENT:field_filling:Last Name')
            try:
                await page.locator("#lastname").fill("Musk")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Last Name: ' + str(e))

            # Fill: Email
            print('EVENT:field_filling:Email')
            try:
                await page.locator("#email").fill("kaivalya775@gmail.com")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Email: ' + str(e))

            # Fill: Password
            print('EVENT:field_filling:Password')
            try:
                await page.locator("#password").fill("onepiece")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Password: ' + str(e))

            # Fill: Address
            print('EVENT:field_filling:Address')
            try:
                await page.locator("#address").fill("789, Space, Colony")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Address: ' + str(e))

            # Fill: City
            print('EVENT:field_filling:City')
            try:
                await page.locator("#city").fill("Badlapur")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill City: ' + str(e))

            # Fill: State
            print('EVENT:field_filling:State')
            try:
                await page.locator("#states").fill("Maharashtra")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill State: ' + str(e))

            # Fill: Pin Code
            print('EVENT:field_filling:Pin Code')
            try:
                await page.locator("#pincode").fill("421503")
                await asyncio.sleep(0.3)
            except Exception as e:
                print('EVENT:field_error:Failed to fill Pin Code: ' + str(e))

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
                    signal = await check_resume_signal("63175841-539a-4182-b664-f763e8627954")
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
