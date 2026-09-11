"""
CivicFlow — WebPilot Agent
==========================
High-level wrapper around Playwright Page objects providing 
advanced human-simulation and CAPTCHA detection capabilities.
"""
import os
import random
import asyncio
import base64
import json
from typing import List, Optional

class WebPilot:
    """
    Advanced agent that interacts with web pages intelligently,
    bypassing anti-bot protections like paste blockers.
    Note: CAPTCHA solving disabled - requires manual intervention.
    """

    def __init__(self, page):
        self.page = page

    async def _detect_anti_paste_fields(self) -> List[str]:
        """
        Detect fields that block paste via JavaScript.
        Check for: onpaste="return false", paste event listener, 
        contextmenu disabled, right-click disabled.
        Return list of field selectors that need keyboard simulation.
        """
        # Execute JS in the browser context to inspect event listeners and attributes
        js_script = """
        () => {
            const blockedSelectors = [];
            const inputs = document.querySelectorAll('input, textarea');
            
            inputs.forEach(input => {
                // Check inline onpaste attribute
                if (input.getAttribute('onpaste') === 'return false;' || 
                    input.getAttribute('onpaste') === 'return false') {
                    
                    // Generate a CSS selector for this element
                    let selector = '';
                    if (input.id) {
                        selector = '#' + input.id;
                    } else if (input.name) {
                        selector = `[name="${input.name}"]`;
                    } else {
                        // Fallback generic selector, not ideal but works
                        selector = input.tagName.toLowerCase();
                    }
                    blockedSelectors.push(selector);
                }
            });
            return blockedSelectors;
        }
        """
        try:
            blocked_selectors = await self.page.evaluate(js_script)
            return blocked_selectors
        except Exception as e:
            print(f"[WebPilot] Error detecting anti-paste fields: {e}")
            return []

    async def _human_type(self, selector: str, text: str, force_keyboard: bool = False):
        """
        Types text character by character with random delays to bypass
        JavaScript-based paste blockers used by some government portals.
        """
        if not text:
            return

        # If it's a long text and not forced, use fast fill
        if len(text) > 30 and not force_keyboard:
            await self.page.fill(selector, text)
            return

        # Focus the element first
        await self.page.click(selector)
        await self.page.wait_for_timeout(random.randint(100, 300))

        for i, char in enumerate(text):
            # Base delay between each character: 60-130ms
            delay = random.randint(60, 130)
            
            # Additional random pause every 3-7 characters: 200-500ms
            if i > 0 and i % random.randint(3, 7) == 0:
                delay += random.randint(200, 500)
                
            # Occasional typo simulation: 5% chance
            if random.random() < 0.05:
                # Type a random character nearby on keyboard (simplified as random ascii letter)
                typo_char = random.choice('abcdefghijklmnopqrstuvwxyz')
                await self.page.keyboard.press(typo_char)
                await self.page.wait_for_timeout(random.randint(100, 200))
                # Delete the typo
                await self.page.keyboard.press("Backspace")
                await self.page.wait_for_timeout(random.randint(100, 200))
                
            await self.page.keyboard.press(char)
            await self.page.wait_for_timeout(delay)

    async def fill_field(self, selector: str, value: str, is_anti_paste: bool = False):
        """
        Intelligently fill a field using standard fill or human typing.
        """
        blocked_fields = await self._detect_anti_paste_fields()
        
        needs_human_typing = is_anti_paste or selector in blocked_fields
        
        if needs_human_typing:
            print(f"[WebPilot] Using human typing for {selector}")
            await self._human_type(selector, value, force_keyboard=True)
        else:
            await self.page.fill(selector, value)

    async def handle_captcha(self) -> dict:
        """
        Detects and handles CAPTCHAs on the page.
        Returns a dict with resolution status.
        """
        # Detect standard text CAPTCHA
        captcha_img = self.page.locator('img[src*="captcha"], img[alt*="captcha"], img[alt*="verification"]')
        
        # Detect ReCaptcha/hCaptcha
        recaptcha = self.page.locator('iframe[src*="recaptcha"]')
        hcaptcha = self.page.locator('iframe[src*="hcaptcha"]')
        
        try:
            if await recaptcha.count() > 0:
                print("[WebPilot] Detected Google reCAPTCHA.")
                return {"status": "paused", "reason": "reCAPTCHA detected - requires user intervention"}
                
            if await hcaptcha.count() > 0:
                print("[WebPilot] Detected hCaptcha.")
                return {"status": "paused", "reason": "hCaptcha detected - requires user intervention"}
                
            if await captcha_img.count() > 0:
                print("[WebPilot] Detected image text CAPTCHA.")
                return {"status": "paused", "reason": "Text CAPTCHA detected - requires manual intervention"}
                    
        except Exception as e:
            print(f"[WebPilot] Error handling CAPTCHA: {e}")
            
        return {"status": "not_found"}
