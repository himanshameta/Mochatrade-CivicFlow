"""
Universal Form Detection
=========================
Detects fillable forms on any webpage (not just government sites).
"""
import asyncio
from typing import Dict
from urllib.parse import urlparse


async def detect_form_on_page(url: str) -> Dict:
    """
    Check if a URL is reachable and contains fillable forms.
    
    Returns:
    {
        "reachable": bool,
        "has_form": bool,
        "form_count": int,
        "field_count": int,
        "site_title": str,
        "is_government_domain": bool,
        "message": str
    }
    """
    from agents.scout import scout
    from agents.scraper import scraper, score_form
    from bs4 import BeautifulSoup
    
    result = {
        "reachable": False,
        "has_form": False,
        "form_count": 0,
        "field_count": 0,
        "site_title": "",
        "is_government_domain": False,
        "message": ""
    }
    
    # Check if government domain
    result["is_government_domain"] = is_government_domain(url)
    
    # Try to fetch the page
    try:
        scout_result = await scout(url)
        
        if scout_result.get("error"):
            result["message"] = f"Could not reach this URL: {scout_result['error']}"
            return result
        
        result["reachable"] = True
        result["site_title"] = scout_result.get("title", "")
        
        html = scout_result.get("html", "")
        if not html or len(html) < 100:
            result["message"] = "Page loaded but no content found"
            return result
        
        # Try to scrape forms
        scrape_result = await scraper(html, url)
        
        if scrape_result is None:
            result["message"] = "No fillable form found on this page"
            return result
        
        # Check if warning was returned (no fields)
        if scrape_result.get("scrape_warning"):
            result["message"] = scrape_result["scrape_warning"]
            return result
        
        fields = scrape_result.get("fields", [])
        result["field_count"] = len(fields)
        
        # Count actual forms in HTML
        soup = BeautifulSoup(html, "lxml")
        forms = soup.find_all("form")
        result["form_count"] = len(forms)
        
        # Determine if this is a valid target form
        if result["field_count"] >= 2:
            result["has_form"] = True
            result["message"] = f"Form detected on this page ({result['field_count']} fillable fields)"
        elif result["field_count"] == 1:
            # Single field might be just search - check context
            field = fields[0]
            field_label = field.get("label", "").lower()
            field_name = field.get("name", "").lower()
            
            if any(term in field_label or term in field_name for term in ["search", "query", "find"]):
                result["message"] = "Only a search box found - no fillable form"
            else:
                result["has_form"] = True
                result["message"] = f"Form detected on this page (1 field)"
        else:
            result["message"] = "No fillable form found on this page"
        
        return result
        
    except Exception as e:
        result["message"] = f"Error checking page: {str(e)}"
        return result


def is_government_domain(url: str) -> bool:
    """Check if URL is a known government domain (metadata only, not blocking)."""
    try:
        parsed = urlparse(url if url.startswith("http") else f"https://{url}")
        hostname = parsed.netloc.lower()
        
        gov_patterns = [
            ".gov.in",
            ".nic.in",
            ".gov",
            ".mil",
            ".edu.in"  # Educational institutions
        ]
        
        return any(hostname.endswith(pattern) for pattern in gov_patterns)
    except:
        return False


def page_has_fillable_form(html: str) -> Dict:
    """
    Quick check if HTML contains fillable forms.
    
    Returns:
    {
        "has_form": bool,
        "form_count": int,
        "field_count": int,
        "best_form_score": int
    }
    """
    from bs4 import BeautifulSoup
    from agents.scraper import score_form, is_ignorable_field
    
    result = {
        "has_form": False,
        "form_count": 0,
        "field_count": 0,
        "best_form_score": 0
    }
    
    try:
        soup = BeautifulSoup(html, "lxml")
        forms = soup.find_all("form")
        result["form_count"] = len(forms)
        
        # Score each form
        for form in forms:
            score = score_form(form)
            if score > result["best_form_score"]:
                result["best_form_score"] = score
        
        # Count fillable fields (in forms or loose)
        all_fields = soup.find_all(["input", "select", "textarea"])
        fillable_count = 0
        
        for field in all_fields:
            if not is_ignorable_field(field):
                field_type = field.get("type", "text").lower()
                if field_type not in ["hidden", "submit", "button", "reset", "image"]:
                    fillable_count += 1
        
        result["field_count"] = fillable_count
        
        # Determine if valid target form
        if result["best_form_score"] > 0 and fillable_count >= 2:
            result["has_form"] = True
        elif fillable_count >= 3:
            # Even without form tag, 3+ fields means likely a form
            result["has_form"] = True
        
        return result
        
    except Exception as e:
        print(f"[FormDetection] Error: {e}")
        return result
