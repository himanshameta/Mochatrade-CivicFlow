"""
URL Classification System
========================
Strict page type classification with evidence-based scoring.
"""
import re
from typing import Dict, List, Tuple
from urllib.parse import urlparse
from models.form_models import URLClassification

class URLClassifier:
    """Classifies URLs into strict categories with evidence"""
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
        
    def classify_url(self, url: str, html_content: str = "", title: str = "") -> URLClassification:
        """Main classification method"""
        # Determine source category first
        source_category = self._get_source_category(url)
        
        # Early YouTube detection
        if source_category == "youtube":
            return URLClassification(
                url=url,
                source_category="youtube",
                page_type="youtube_video",
                official_domain=False,
                automatable=False,
                confidence=0.95,
                evidence=["YouTube domain detected"],
                normalized_title=title or "YouTube Video",
                relevance_reason="Video tutorial or guidance"
            )
        
        # Classify page type based on content
        page_type, confidence, evidence = self._classify_page_type(url, html_content, title)
        
        # Determine if official domain
        official_domain = self._is_official_domain(url)
        
        # Determine if automatable (only direct_form pages)
        automatable = page_type == "direct_form" and self._has_form_elements(html_content)
        
        return URLClassification(
            url=url,
            source_category=source_category,
            page_type=page_type,
            official_domain=official_domain,
            automatable=automatable,
            confidence=confidence,
            evidence=evidence,
            normalized_title=self._normalize_title(title),
            relevance_reason=self._get_relevance_reason(page_type)
        )
    
    def _get_source_category(self, url: str) -> str:
        """Determine source category"""
        domain = urlparse(url).netloc.lower()
        
        if 'youtube.com' in domain or 'youtu.be' in domain:
            return "youtube"
        elif self._is_official_domain(url):
            return "official_portal"
        else:
            return "third_party_web"
    
    def _is_official_domain(self, url: str) -> bool:
        """Check if domain is official government/institutional"""
        domain = urlparse(url).netloc.lower()
        
        # Government domains
        gov_patterns = [
            r'\.gov\.in$', r'\.nic\.in$', r'\.gov$', r'\.ac\.in$'
        ]
        
        for pattern in gov_patterns:
            if re.search(pattern, domain):
                return True
        
        # Known official domains (can be extended)
        official_domains = [
            'epfindia.gov.in', 'nsdl.com', 'utiitsl.com', 'irctc.co.in',
            'passportindia.gov.in', 'incometaxindia.gov.in'
        ]
        
        return any(od in domain for od in official_domains)
    
    def _classify_page_type(self, url: str, html_content: str, title: str) -> Tuple[str, float, List[str]]:
        """Classify page type with evidence"""
        html_lower = html_content.lower()
        title_lower = title.lower()
        url_lower = url.lower()
        evidence = []
        
        # DIRECT FORM detection (highest priority)
        form_score = 0
        if '<form' in html_lower:
            form_score += 0.4
            evidence.append("Contains <form> tag")
        
        input_count = html_lower.count('<input')
        if input_count >= 3:
            form_score += 0.3
            evidence.append(f"Contains {input_count} input fields")
        
        if any(t in html_lower for t in ['type="file"', "file upload", "choose file"]):
            form_score += 0.2
            evidence.append("Has file upload capability")
        
        if any(t in html_lower for t in ['type="submit"', 'submit', 'apply now', 'register']):
            form_score += 0.2
            evidence.append("Has submit/apply button")
        
        if any(t in html_lower for t in ['captcha', 'recaptcha', 'hcaptcha']):
            form_score += 0.1
            evidence.append("Contains CAPTCHA")
        
        if form_score >= 0.5:
            return "direct_form", min(form_score, 1.0), evidence
        
        # LOGIN GATEWAY detection
        login_indicators = ['sign in', 'log in', 'login', 'authentication', 'user id', 'password']
        if (any(ind in html_lower for ind in login_indicators) and 
            form_score < 0.5 and '<form' in html_lower):
            evidence.append("Login/authentication page")
            return "login_gateway", 0.8, evidence
        
        # DOCUMENT CHECKLIST detection
        doc_indicators = [
            'required documents', 'document list', 'checklist', 'eligibility documents',
            'upload documents', 'file format', 'photo requirements', 'id proof', 'address proof'
        ]
        if any(ind in html_lower for ind in doc_indicators):
            evidence.append("Contains document requirements")
            return "document_checklist", 0.7, evidence
        
        # FAQ detection
        faq_indicators = ['faq', 'frequently asked', 'questions', 'q&a', 'help']
        if any(ind in title_lower or ind in html_lower for ind in faq_indicators):
            evidence.append("FAQ or help content")
            return "faq", 0.6, evidence
        
        # OFFICIAL GUIDANCE detection
        guidance_indicators = [
            'eligibility', 'benefits', 'process', 'procedure', 'instructions',
            'how to apply', 'application process', 'scheme', 'guidelines'
        ]
        if (any(ind in html_lower for ind in guidance_indicators) and 
            self._is_official_domain(url)):
            evidence.append("Official guidance content")
            return "official_guidance", 0.7, evidence
        
        # ARTICLE/BLOG detection
        article_indicators = ['article', 'blog', 'post', 'tutorial', 'guide']
        if (any(ind in html_lower for ind in article_indicators) and 
            not self._is_official_domain(url)):
            evidence.append("Third-party article/blog")
            return "article_or_blog", 0.6, evidence
        
        # NEWS detection
        news_indicators = ['news', 'press release', 'announcement', 'latest', 'breaking']
        if any(ind in html_lower for ind in news_indicators):
            evidence.append("News content")
            return "news", 0.5, evidence
        
        # DASHBOARD/PORTAL HOME detection
        if any(ind in title_lower for ind in ['dashboard', 'portal', 'home', 'welcome']):
            evidence.append("Portal homepage or dashboard")
            return "dashboard_or_portal_home", 0.4, evidence
        
        # Default
        evidence.append("Could not determine specific page type")
        return "unknown", 0.2, evidence
    
    def _has_form_elements(self, html_content: str) -> bool:
        """Check if page has actual fillable form elements"""
        html_lower = html_content.lower()
        
        # Must have form tag
        if '<form' not in html_lower:
            return False
        
        # Must have multiple inputs
        input_count = html_lower.count('<input')
        select_count = html_lower.count('<select')
        textarea_count = html_lower.count('<textarea')
        
        total_fields = input_count + select_count + textarea_count
        
        return total_fields >= 3  # Minimum threshold for a real form
    
    def _normalize_title(self, title: str) -> str:
        """Clean up page title"""
        if not title:
            return "Untitled Page"
        
        # Remove common suffixes
        title = re.sub(r'\s*[-|]\s*(Government of India|GOI|Official Website).*$', '', title, flags=re.IGNORECASE)
        title = title.strip()
        
        return title[:100] if len(title) > 100 else title
    
    def _get_relevance_reason(self, page_type: str) -> str:
        """Get human-readable relevance reason"""
        reasons = {
            "direct_form": "Direct application form",
            "official_guidance": "Official information and guidance", 
            "document_checklist": "Document requirements and checklist",
            "faq": "Frequently asked questions and help",
            "login_gateway": "Login required to access application",
            "dashboard_or_portal_home": "Portal homepage or user dashboard",
            "youtube_video": "Video tutorial or guidance",
            "article_or_blog": "Third-party guide or tutorial",
            "news": "News or announcement",
            "unknown": "Relevance unclear"
        }
        return reasons.get(page_type, "Unknown relevance")

async def classify_url_with_llm(url: str, html_snippet: str, title: str, llm_client) -> URLClassification:
    """Enhanced classification using LLM for ambiguous cases"""
    classifier = URLClassifier()
    basic_classification = classifier.classify_url(url, html_snippet, title)
    
    # Use LLM for low-confidence classifications
    if basic_classification.confidence < 0.6 and llm_client and llm_client.api_key:
        try:
            prompt = f"""
            Classify this web page strictly:
            
            URL: {url}
            Title: {title}
            HTML snippet: {html_snippet[:1500]}
            
            Return JSON with page_type (one of: direct_form, official_guidance, document_checklist, faq, login_gateway, dashboard_or_portal_home, youtube_video, article_or_blog, news, unknown) and confidence (0-1):
            
            {{"page_type": "direct_form", "confidence": 0.8}}
            """
            
            response = await llm_client.generate_content(prompt=prompt, temperature=0.0, max_tokens=100)
            
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            import json
            llm_result = json.loads(response.strip())
            
            # Update classification if LLM is more confident
            if llm_result.get("confidence", 0) > basic_classification.confidence:
                basic_classification.page_type = llm_result["page_type"]
                basic_classification.confidence = llm_result["confidence"]
                basic_classification.evidence.append("Enhanced by LLM analysis")
                
        except Exception as e:
            print(f"[Classifier] LLM enhancement failed: {e}")
    
    return basic_classification