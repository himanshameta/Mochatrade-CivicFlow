"""
Display Title and Reason Generator
==================================
Generates production-ready user-facing text from internal classification data.
"""
import re
from urllib.parse import urlparse
from typing import Tuple

class DisplayTextGenerator:
    """Generates clean display titles and reasons"""
    
    def generate_display_title(self, raw_title: str, url: str, page_type: str) -> str:
        """
        Generate clean display title for users
        Never returns generic "Page" - derives from URL if needed
        """
        # Try to clean raw title first
        if raw_title and raw_title not in ["Unknown Page", "Page", "Untitled Page", ""]:
            # Remove fallback markers
            cleaned = raw_title.replace(" (fallback)", "").strip()
            
            # Remove common noise
            cleaned = re.sub(r'\s*[-|]\s*(Government of India|GOI|Official Website|Home).*$', '', cleaned, flags=re.IGNORECASE)
            
            # If still meaningful, use it
            if len(cleaned) > 3 and cleaned.lower() not in ["page", "home", "index"]:
                return self._title_case_smart(cleaned[:80])
        
        # Derive from URL path
        path_title = self._derive_title_from_url(url)
        if path_title:
            return path_title
        
        # Fallback based on page type (last resort)
        return self._get_type_based_fallback(page_type)
    
    def _derive_title_from_url(self, url: str) -> str:
        """Extract meaningful title from URL path"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            
            if not path or path in ['index.html', 'home', 'index.php']:
                # Use domain name
                domain = parsed.netloc.replace('www.', '')
                # Convert domain to title
                name = domain.split('.')[0]
                return self._slug_to_title(name)
            
            # Get last meaningful segment
            segments = [s for s in path.split('/') if s and s not in ['index.html', 'home', 'index.php']]
            if segments:
                # Use last segment or combine last 2 if very short
                if len(segments) > 1 and len(segments[-1]) < 10:
                    slug = '-'.join(segments[-2:])
                else:
                    slug = segments[-1]
                
                # Remove file extensions
                slug = re.sub(r'\.(html?|php|aspx?)$', '', slug, flags=re.IGNORECASE)
                
                return self._slug_to_title(slug)
            
            return ""
            
        except Exception:
            return ""
    
    def _slug_to_title(self, slug: str) -> str:
        """Convert URL slug to readable title"""
        # Remove common prefixes/suffixes
        slug = re.sub(r'^(page|form|apply|application|online)[-_]', '', slug, flags=re.IGNORECASE)
        slug = re.sub(r'[-_](page|form|php|html)$', '', slug, flags=re.IGNORECASE)
        
        # Replace separators with spaces
        title = re.sub(r'[-_]+', ' ', slug)
        
        # Title case
        return self._title_case_smart(title)
    
    def _title_case_smart(self, text: str) -> str:
        """Smart title casing that handles acronyms"""
        # Keep known acronyms uppercase
        acronyms = ['MSBTE', 'PAN', 'GST', 'EPF', 'FAQ', 'OTP', 'PDF', 'KYC', 'UIDAI', 'RTI']
        
        words = text.split()
        result = []
        
        for word in words:
            upper_word = word.upper()
            if upper_word in acronyms:
                result.append(upper_word)
            elif len(word) > 0:
                # Regular title case
                result.append(word[0].upper() + word[1:].lower() if len(word) > 1 else word.upper())
            else:
                result.append(word)
        
        return ' '.join(result)
    
    def _get_type_based_fallback(self, page_type: str) -> str:
        """Get friendly fallback title based on page type"""
        fallbacks = {
            "direct_form": "Direct Application Form",
            "official_guidance": "Official Guidance",
            "document_checklist": "Document Checklist",
            "faq": "Frequently Asked Questions",
            "login_gateway": "Login Portal",
            "dashboard_or_portal_home": "Portal Home",
            "youtube_video": "Video Guidance",
            "article_or_blog": "Guide Article",
            "news": "News Article",
            "unknown": "Related Page"
        }
        return fallbacks.get(page_type, "Related Resource")
    
    def generate_display_reason(
        self, 
        page_type: str, 
        official_domain: bool, 
        confidence: float,
        evidence: list = None
    ) -> str:
        """
        Generate user-friendly explanation of why this result is relevant
        Never exposes "(fallback)" or internal classification details
        """
        # Base reason on type and domain
        if page_type == "direct_form":
            if official_domain:
                return "Official application form page"
            else:
                return "Application form page"
        
        elif page_type == "official_guidance":
            return "Official guidance and instructions"
        
        elif page_type == "document_checklist":
            if official_domain:
                return "Official document requirements"
            else:
                return "Document requirements list"
        
        elif page_type == "faq":
            return "Frequently asked questions and help"
        
        elif page_type == "login_gateway":
            return "Portal login or registration page"
        
        elif page_type == "youtube_video":
            return "Video tutorial and guidance"
        
        elif page_type == "article_or_blog":
            return "Guide article with instructions"
        
        elif page_type == "dashboard_or_portal_home":
            return "Portal homepage"
        
        else:
            if official_domain:
                return "Official resource page"
            else:
                return "Related resource"
    
    def clean_evidence_for_debug(self, evidence: list) -> list:
        """Clean evidence list for debug display (remove internal markers but keep info)"""
        if not evidence:
            return []
        
        cleaned = []
        for item in evidence:
            # Remove fallback markers
            clean = item.replace(" (fallback)", "")
            # Keep meaningful evidence
            if clean and clean not in ["YouTube domain", "Official domain"]:
                cleaned.append(clean)
        
        return cleaned if cleaned else ["Classification completed"]

# Global instance
_generator = DisplayTextGenerator()

def generate_display_title(raw_title: str, url: str, page_type: str) -> str:
    """Public API for generating display title"""
    return _generator.generate_display_title(raw_title, url, page_type)

def generate_display_reason(page_type: str, official_domain: bool, confidence: float, evidence: list = None) -> str:
    """Public API for generating display reason"""
    return _generator.generate_display_reason(page_type, official_domain, confidence, evidence)

def clean_evidence(evidence: list) -> list:
    """Public API for cleaning evidence"""
    return _generator.clean_evidence_for_debug(evidence)