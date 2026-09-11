"""
CivicFlow — Enhanced Search API
=================================
Endpoints for multi-source form search with strict classification.
"""
import os
import sys
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.auth import require_auth, ok
from models.form_models import SearchFormRequest, VerifyUrlRequest, EnhancedFormSearchResult
from agents.form_search import FormSearchAgent  # Legacy agent
from agents.enhanced_form_search import EnhancedFormSearchAgent  # New agent
from agents.fixed_enhanced_form_search import FixedEnhancedFormSearchAgent  # Fixed agent
from utils.form_detection import detect_form_on_page

router = APIRouter(prefix="/search", tags=["Search"])

_form_search_agent: Optional[FormSearchAgent] = None
_enhanced_search_agent: Optional[EnhancedFormSearchAgent] = None
_fixed_search_agent: Optional[FixedEnhancedFormSearchAgent] = None

def get_search_agent() -> FormSearchAgent:
    global _form_search_agent
    if _form_search_agent is None:
        _form_search_agent = FormSearchAgent()
    return _form_search_agent

def get_enhanced_search_agent() -> EnhancedFormSearchAgent:
    global _enhanced_search_agent
    if _enhanced_search_agent is None:
        _enhanced_search_agent = EnhancedFormSearchAgent()
    return _enhanced_search_agent

def get_fixed_search_agent() -> FixedEnhancedFormSearchAgent:
    global _fixed_search_agent
    if _fixed_search_agent is None:
        _fixed_search_agent = FixedEnhancedFormSearchAgent()
    return _fixed_search_agent

class SearchModeRequest(BaseModel):
    service_name: str
    state: Optional[str] = None
    user_url: Optional[str] = None
    mode: Optional[str] = "enhanced"  # "legacy" or "enhanced"

@router.post("/form", summary="Search for a form URL")
async def search_form(request: SearchFormRequest, payload: dict = Depends(require_auth)):
    """
    Legacy search endpoint - maintained for backward compatibility.
    Uses the original search agent with categorized results.
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
            
        response_data = result.model_dump()
        response_data["search_metadata"] = {
            "total_direct_forms": len(result.direct_forms),
            "total_guidance_pages": len(result.guidance_pages),
            "total_context_pages": len(result.context_pages),
            "total_insights": len(result.process_insights),
            "has_crawled_results": any("Found via Crawler" in item.badges for item in result.direct_forms),
            "search_mode": "legacy"
        }
            
        return ok("Found form options", data=response_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e), "data": {}})

@router.post("/form/enhanced", summary="Enhanced multi-source form search")
async def search_form_enhanced(request: SearchModeRequest, payload: dict = Depends(require_auth)):
    """
    FIXED Enhanced search with robust error handling.
    
    Features:
    - Full request tracing with search_id
    - Fallback classification on timeout
    - YouTube video validation
    - URL normalization
    - Comprehensive debug output
    
    Response time: 30-60 seconds due to comprehensive analysis.
    """
    agent = get_fixed_search_agent()  # Use fixed agent
    
    try:
        result = await agent.find_form_enhanced(
            service_name=request.service_name,
            state=request.state,
            user_provided_url=request.user_url
        )
        
        if not result.valid:
            return {"success": False, "message": result.error_message, "data": result.model_dump()}
        
        response_data = result.model_dump()
        
        # Add search metadata
        response_data["search_metadata"] = {
            "search_mode": "enhanced_fixed",
            "has_direct_form": result.direct_form is not None,
            "automatable": result.direct_form.automatable if result.direct_form else False,
            "total_guidance_sources": len(result.official_guidance) + len(result.document_checklists),
            "youtube_videos_found": len(result.youtube_videos),
            "youtube_with_transcripts": sum(1 for v in result.youtube_videos if v.transcript_available),
            "automation_readiness": result.insights.automation_readiness,
            "total_classified_candidates": result.debug.get("classified_candidates_count", 0),
            "total_dropped_candidates": result.debug.get("dropped_candidates_count", 0),
            "search_id": result.debug.get("search_id", "unknown")
        }
        
        return ok("Enhanced search completed", data=response_data)
        
    except Exception as e:
        import traceback
        error_detail = {
            "success": False, 
            "message": str(e), 
            "traceback": traceback.format_exc(),
            "data": {}
        }
        raise HTTPException(status_code=500, detail=error_detail)


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
