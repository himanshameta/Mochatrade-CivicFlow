"""
CivicFlow — Search API
======================
Endpoints for searching and verifying government form URLs.
"""
import os
import sys
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.auth import require_auth, ok
from models.form_models import SearchFormRequest, VerifyUrlRequest
from agents.form_search import FormSearchAgent

router = APIRouter(prefix="/search", tags=["Search"])

_form_search_agent: Optional[FormSearchAgent] = None

def get_search_agent() -> FormSearchAgent:
    global _form_search_agent
    if _form_search_agent is None:
        _form_search_agent = FormSearchAgent()
    return _form_search_agent


@router.post("/form", summary="Search for a government form URL")
async def search_form(request: SearchFormRequest, payload: dict = Depends(require_auth)):
    """
    Uses Gemini to identify the official portal URL for the requested service.
    If user_url is provided, it validates and returns it instead.
    """
    agent = get_search_agent()
    
    try:
        result = await agent.find_form_url(
            service_name=request.service_name,
            state=request.state,
            user_provided_url=request.user_url
        )
        
        if not result.valid:
            return {"success": False, "message": result.error_message, "data": result.model_dump()}
            
        return ok("Found form options", data=result.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e), "data": {}})


@router.post("/verify", summary="Verify a URL")
async def verify_url(request: VerifyUrlRequest, payload: dict = Depends(require_auth)):
    """
    Checks if a URL is reachable and is an official government domain.
    """
    agent = get_search_agent()
    
    url = request.url
    is_gov = agent._is_government_domain(url)
    is_reachable = await agent.verify_url_accessible(url)
    
    # Extract domain for display
    from urllib.parse import urlparse
    try:
        if not url.startswith("http"):
            domain = urlparse("https://" + url).netloc
        else:
            domain = urlparse(url).netloc
    except:
        domain = "unknown"
        
    return ok("Verification complete", data={
        "valid": is_reachable,
        "is_government": is_gov,
        "domain": domain
    })
