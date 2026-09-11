"""
CivicFlow — Search API
======================
Endpoints for searching and verifying form URLs on any website.
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
from utils.form_detection import detect_form_on_page

router = APIRouter(prefix="/search", tags=["Search"])

_form_search_agent: Optional[FormSearchAgent] = None

def get_search_agent() -> FormSearchAgent:
    global _form_search_agent
    if _form_search_agent is None:
        _form_search_agent = FormSearchAgent()
    return _form_search_agent


@router.post("/form", summary="Search for a form URL")
async def search_form(request: SearchFormRequest, payload: dict = Depends(require_auth)):
    """
    Uses AI to identify portal URLs for the requested service.
    Works with any website - government, private, registration forms, etc.
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


@router.post("/verify", summary="Verify a form URL")
async def verify_url(request: VerifyUrlRequest, payload: dict = Depends(require_auth)):
    """
    Checks if a URL is reachable and contains a fillable form.
    Works with any website - not restricted to government domains.
    """
    url = request.url
    
    # Detect form on the page
    detection_result = await detect_form_on_page(url)
    
    return ok("Verification complete", data={
        "url": url,
        "reachable": detection_result["reachable"],
        "has_form": detection_result["has_form"],
        "form_count": detection_result["form_count"],
        "field_count": detection_result["field_count"],
        "site_title": detection_result["site_title"],
        "is_government_domain": detection_result["is_government_domain"],
        "message": detection_result["message"]
    })
