import os
import sys
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.form_models import FormSearchResultV2
from services.search_pipeline import SearchPipeline


class FormSearchAgent:
    """
    Universal form finder - works with ANY website.
    Delegates to the multi-stage SearchPipeline for strict retrieval and classification.
    """

    def __init__(self):
        pass

    async def find_form_url(
        self,
        service_name: str,
        state: Optional[str] = None,
        user_provided_url: Optional[str] = None
    ) -> FormSearchResultV2:
        
        # User Provided URL logic remains simple override
        if user_provided_url:
            from models.form_models import DirectFormCandidate
            return FormSearchResultV2(
                query=user_provided_url,
                direct_form=DirectFormCandidate(
                    url=user_provided_url,
                    title="User Provided URL",
                    confidence=1.0,
                    automatable=True,
                    evidence=["Provided directly by user"]
                ),
                valid=True
            )

        # Delegate to the new Search Pipeline
        return await SearchPipeline.run(service_name, state)

    async def verify_url_accessible(self, url: str) -> bool:
        import httpx
        if not url.startswith("http"):
            url = "https://" + url
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            async with httpx.AsyncClient(verify=False, timeout=3.0) as client:
                response = await client.head(url, headers=headers, follow_redirects=True)
                if response.status_code >= 400 and response.status_code != 405:
                    response = await client.get(url, headers=headers, follow_redirects=True)
                return response.status_code < 400
        except Exception:
            return False
