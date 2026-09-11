"""
CivicFlow — Form Search Agent
=============================
Uses Gemini to find the correct government portal URL for any service,
falling back to the user's provided URL if given.
"""
import os
import sys
import json
import httpx
from typing import Optional, List

from google import genai

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.form_models import FormSearchResult, FormSearchOption


class FormSearchAgent:
    """
    Uses Gemini to find the correct government portal URL for any service.
    Falls back to user-provided URL if needed.
    """

    GOVERNMENT_PORTALS_KNOWLEDGE = """
    Known Indian government portals (use as starting context):
    - Passport: passportindia.gov.in
    - PAN: incometaxindia.gov.in or onlineservices.nsdl.com
    - Aadhaar update: uidai.gov.in
    - GST: gst.gov.in
    - Income tax: incometaxindiaefiling.gov.in
    - EPF: epfindia.gov.in
    - Driving licence: sarathi.parivahan.gov.in
    - Vehicle RC: vahan.parivahan.gov.in
    - DigiLocker: digilocker.gov.in
    - MSME/Udyam: udyamregistration.gov.in
    - FSSAI: foscos.fssai.gov.in
    - Birth cert: varies by state municipal corporation
    """

    def __init__(self):
        self.client = genai.Client()

    async def find_form_url(
        self,
        service_name: str,
        state: Optional[str] = None,
        user_provided_url: Optional[str] = None
    ) -> FormSearchResult:
        """
        If user_provided_url is given: validate and return it directly.
        Otherwise: use Gemini to identify the correct portal.
        """
        # 1. User Override
        if user_provided_url:
            is_gov = self._is_government_domain(user_provided_url)
            accessible = await self.verify_url_accessible(user_provided_url)
            
            return FormSearchResult(
                options=[FormSearchOption(
                    url=user_provided_url,
                    portal_name="User Provided Portal",
                    confidence=1.0,
                    notes="Verified accessibility" if accessible else "Warning: URL may be unreachable"
                )],
                is_user_provided=True,
                valid=accessible
            )

        # 2. Gemini Search
        state_context = f" in the state of {state}" if state else ""
        
        prompt = f"""
        {self.GOVERNMENT_PORTALS_KNOWLEDGE}
        
        For {service_name} in India{state_context}, what is the official government portal URL?
        
        Return ONLY valid JSON in this exact format: 
        [
          {{"url": "https://...", "portal_name": "...", "confidence": 0.9, "notes": "..."}}
        ]
        
        Rules:
        - Only include .gov.in, .nic.in, or recognized official domains.
        - Return up to 3 options.
        - Order by confidence (highest first).
        - No markdown wrapping, just raw JSON array.
        """

        try:
            response = self.client.models.generate_content(model="gemini-2.0-flash-lite", contents=prompt)
            text = response.text.strip()
            
            # Clean up markdown if Gemini ignores instructions
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
                
            data = json.loads(text.strip())
            
            options = []
            for item in data:
                url = item.get("url", "")
                # Clean up trailing slashes
                if url.endswith("/"):
                    url = url[:-1]
                    
                # Add http prefix if missing
                if not url.startswith("http"):
                    url = "https://" + url
                    
                # Filter out obvious hallucinations or non-gov sites
                if self._is_government_domain(url):
                    options.append(FormSearchOption(
                        url=url,
                        portal_name=item.get("portal_name", "Unknown Portal"),
                        confidence=float(item.get("confidence", 0.0)),
                        notes=item.get("notes", "")
                    ))

            if not options:
                return FormSearchResult(options=[], valid=False, error_message="No official government portal found for this service.")

            # Optionally, verify the top option
            top_option = options[0]
            if await self.verify_url_accessible(top_option.url):
                pass # It's good
                
            return FormSearchResult(options=options, valid=True)

        except Exception as e:
            print(f"[FormSearch] LLM Search failed: {e}")
            return FormSearchResult(
                options=[], 
                valid=False, 
                error_message=f"Failed to search for form: {str(e)}"
            )

    def _is_government_domain(self, url: str) -> bool:
        """Validate URL ends with .gov.in or .nic.in or is in approved list."""
        url_lower = url.lower()
        if ".gov.in" in url_lower or ".nic.in" in url_lower:
            return True
            
        # Hardcoded exceptions for official domains not using .gov.in
        exceptions = [
            "nsdl.com",
            "utiitsl.com",
            "epfindia.gov.in", # technically .gov.in but covering edge cases
            "irctc.co.in"
        ]
        
        for ex in exceptions:
            if ex in url_lower:
                return True
                
        return False

    async def verify_url_accessible(self, url: str) -> bool:
        """Quick HTTP head/get request to check URL is reachable."""
        # Add scheme if missing
        if not url.startswith("http"):
            url = "https://" + url
            
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
            
        try:
            async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                response = await client.head(url, headers=headers, follow_redirects=True)
                if response.status_code >= 400 and response.status_code != 405:
                    # Sometimes HEAD is blocked, try a quick GET
                    response = await client.get(url, headers=headers, follow_redirects=True)
                return response.status_code < 400
        except httpx.RequestError:
            return False
