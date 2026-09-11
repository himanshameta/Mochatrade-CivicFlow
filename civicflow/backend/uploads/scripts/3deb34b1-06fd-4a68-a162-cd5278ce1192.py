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
            print(f"EVENT:navigation:Loading page")
            await page.goto("https://demoqa.com/automation-practice-form", wait_until="networkidle")
            await asyncio.sleep(2)

            # Fill form fields
    # Fill: First Name
    print(f'EVENT:field_filling:{ "First Name" }')
    try:
        await page.locator("#firstName").fill("Kaivalya")
        await asyncio.sleep(0.3)
    except Exception as e:
        print(f'EVENT:field_error:Failed to fill { "First Name" }: {e}')

    # Fill: Last Name
    print(f'EVENT:field_filling:{ "Last Name" }')
    try:
        await page.locator("#lastName").fill("Sunil Sonawane")
        await asyncio.sleep(0.3)
    except Exception as e:
        print(f'EVENT:field_error:Failed to fill { "Last Name" }: {e}')

    # Fill: Male
    print(f'EVENT:field_filling:{ "Male" }')
    try:
        radio = page.locator("[name=\"gender\"][value=\"Male\"]")
        await radio.check()
        await asyncio.sleep(0.3)
    except Exception as e:
        print(f'EVENT:field_error:Failed to fill { "Male" }: {e}')

    # Fill: Current Address
    print(f'EVENT:field_filling:{ "Current Address" }')
    try:
        await page.locator("#currentAddress").fill("205-B Sanskar society Haridwar Complex\nHendrepada")
        await asyncio.sleep(0.3)
    except Exception as e:
        print(f'EVENT:field_error:Failed to fill { "Current Address" }: {e}')


            # Submit form
            print(f"EVENT:submission:Clicking submit")
            submit_btn = page.locator("#submit")
            await submit_btn.click()
            await asyncio.sleep(3)

            # Check for CAPTCHA
            captcha_present = False
            try:
                # Check for common CAPTCHA indicators
                recaptcha = await page.locator("iframe[src*=\"recaptcha\"]").count()
                hcaptcha = await page.locator(".h-captcha").count()
                if recaptcha > 0 or hcaptcha > 0:
                    captcha_present = True
            except:
                pass

            if captcha_present:
                print("EVENT:captcha_detected:CAPTCHA found")
                # Poll for resume signal
                from agents.executor import check_resume_signal
                while True:
                    signal = await check_resume_signal("3deb34b1-06fd-4a68-a162-cd5278ce1192")
                    if signal == "captcha_solved":
                        print("EVENT:resume:Continuing after CAPTCHA")
                        break
                    await asyncio.sleep(2)

            print("EVENT:submission_complete:Form submitted successfully")
            await asyncio.sleep(5)

        except Exception as e:
            print(f"EVENT:error:{str(e)}")
            raise
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
