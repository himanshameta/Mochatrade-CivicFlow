"""
CivicFlow — Universal Form Search Agent
========================================
Finds form URLs for ANY service or website.
Includes a curated list of government portals but works with ANY URL.
"""
import os
import sys
import json
import httpx
from typing import Optional, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.form_models import FormSearchResult, FormSearchOption
from config import settings


class FormSearchAgent:
    """
    Universal form finder - works with ANY website.
    Includes government portal knowledge base but accepts all URLs.
    """

    PORTALS_KNOWLEDGE = """
    Known Indian government portals (reference - but system works with ANY website):
    - Passport: passportindia.gov.in
    - PAN: incometaxindia.gov.in or onlineservices.nsdl.com
    - Aadhaar update: uidai.gov.in
    - GST: gst.gov.in
    - Income tax: https://www.incometax.gov.in/iec/foportal/
    - EPF: epfindia.gov.in
    - Driving licence: sarathi.parivahan.gov.in
    - Vehicle RC: vahan.parivahan.gov.in
    - DigiLocker: digilocker.gov.in
    - MSME/Udyam: udyamregistration.gov.in
    - FSSAI: foscos.fssai.gov.in
    - Birth cert: varies by state municipal corporation
    
    Note: CivicFlow works with ANY website - not limited to government sites.
    This list is just a reference for common services.
    """

    def __init__(self):
        from utils.llm import get_llm_client
        self.llm = get_llm_client()
        if not self.llm.api_key:
            print("[FormSearch] [WARNING] OpenRouter API key not configured")

    def is_valid_url(self, url: str) -> bool:
        """Sanity check to reject obvious placeholder/example URLs from LLM."""
        url_lower = url.lower()
        placeholders = [
            "your-username", "your-repo", "example.com", "placeholder", 
            "yourdomain", "yoursite", "template", "github.com/your-", 
            "github.com/username", "github.com/my-", "github.com/repo",
            "localhost", "127.0.0.1", "github.com/yourusername"
        ]
        for p in placeholders:
            if p in url_lower:
                return False
        if "." not in url:
            return False
        return True

    async def find_form_url(
        self,
        service_name: str,
        state: Optional[str] = None,
        user_provided_url: Optional[str] = None
    ) -> FormSearchResult:
        """
        If user_provided_url is given: validate and return it directly.
        Otherwise: use LLM to identify the correct portal.
        Accepts ANY URL - not limited to government sites.
        """
        # 1. User Override - accept ANY URL
        if user_provided_url:
            accessible = await self.verify_url_accessible(user_provided_url)
            
            return FormSearchResult(
                options=[FormSearchOption(
                    url=user_provided_url,
                    portal_name="User Provided URL",
                    confidence=1.0,
                    notes="Accessible" if accessible else "Warning: URL may be unreachable"
                )],
                is_user_provided=True,
                valid=True  # Always valid if user provided it
            )

        # 2. OpenRouter LLM Search
        if not self.llm.api_key:
            return FormSearchResult(
                options=[],
                valid=False,
                error_message="OpenRouter API key not configured"
            )
        
        state_context = f" in the state of {state}" if state else ""
        
        prompt = f"""
        {self.PORTALS_KNOWLEDGE}
        
        For {service_name} in India{state_context}, what is the best URL?
        
        Return ONLY valid JSON in this exact format: 
        [
          {{"url": "https://...", "portal_name": "...", "confidence": 0.9, "notes": "..."}}
        ]
        
        Rules:
        - Can suggest ANY website URL that matches the service
        - Return up to 3 options
        - Order by confidence (highest first)
        - No markdown wrapping, just raw JSON array
        """

        try:
            # Call OpenRouter via unified LLM client
            text = await self.llm.generate_content(
                prompt=prompt,
                temperature=0.1,
                max_tokens=500
            )
            
            # Clean up markdown if LLM ignores instructions
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
                    
                # Sanity check to filter bad/hallucinated URLs
                if not self.is_valid_url(url):
                    print(f"[FormSearch] Filtered out hallucinated/invalid URL: {url}")
                    continue

                # For government portal search, prefer .gov.in domains but accept all valid URLs
                options.append(FormSearchOption(
                    url=url,
                    portal_name=item.get("portal_name", "Unknown Portal"),
                    confidence=float(item.get("confidence", 0.0)),
                    notes=item.get("notes", "")
                ))

            if not options:
                return FormSearchResult(options=[], valid=False, error_message="No matching form URL found for this service.")

            # Verify the top option if it's valid
            top_option = options[0]
            await self.verify_url_accessible(top_option.url)
                
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
            
        if not self.is_valid_url(url):
            return False

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
            
        try:
            async with httpx.AsyncClient(verify=False, timeout=3.0) as client:
                response = await client.head(url, headers=headers, follow_redirects=True)
                if response.status_code >= 400 and response.status_code != 405:
                    # Sometimes HEAD is blocked, try a quick GET
                    response = await client.get(url, headers=headers, follow_redirects=True)
                return response.status_code < 400
        except Exception:
            return False
