import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from models.form_models import PageType, SourceCategory

class ClassifierService:
    """Classifies web pages using strong heuristics."""
    
    @staticmethod
    def is_official_domain(url: str) -> bool:
        url_lower = url.lower()
        if ".gov.in" in url_lower or ".nic.in" in url_lower:
            return True
        exceptions = ["nsdl.com", "utiitsl.com", "epfindia.gov.in", "irctc.co.in", "passportindia.gov.in"]
        for ex in exceptions:
            if ex in url_lower:
                return True
        return False

    @staticmethod
    def get_source_category(url: str) -> SourceCategory:
        url_lower = url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return SourceCategory.youtube
        if ClassifierService.is_official_domain(url):
            return SourceCategory.official_portal
        return SourceCategory.third_party_web

    @staticmethod
    def classify_page(url: str, html: str, title: str) -> Dict[str, Any]:
        """Returns a dict containing page_type, automatable, confidence, evidence."""
        source_category = ClassifierService.get_source_category(url)
        official_domain = ClassifierService.is_official_domain(url)
        
        # 1. YouTube check
        if source_category == SourceCategory.youtube:
            return {
                "page_type": PageType.youtube_video,
                "automatable": False,
                "confidence": 1.0,
                "evidence": ["YouTube domain matched"]
            }

        if not html:
            return {
                "page_type": PageType.unknown,
                "automatable": False,
                "confidence": 0.0,
                "evidence": ["No HTML provided"]
            }

        # Use BeautifulSoup for deterministic heuristics
        soup = BeautifulSoup(html, "html.parser")
        html_text_lower = soup.get_text().lower()
        
        evidence = []
        
        # 2. Form Check
        forms = soup.find_all("form")
        inputs = soup.find_all(["input", "select", "textarea"])
        
        # Exclude simple search forms
        valid_forms = 0
        has_upload = False
        for form in forms:
            form_text = form.get_text().lower()
            if "search" not in form_text:
                valid_forms += 1
            if form.find("input", type="file"):
                has_upload = True

        if valid_forms > 0 and len(inputs) > 3:
            evidence.append(f"Found {valid_forms} valid forms and {len(inputs)} inputs")
            if has_upload:
                evidence.append("Found file upload field")
            
            # Additional form markers
            if "captcha" in html_text_lower:
                evidence.append("Captcha marker found")
            if "otp" in html_text_lower:
                evidence.append("OTP marker found")
                
            return {
                "page_type": PageType.direct_form,
                "automatable": True,
                "confidence": 0.9 + (0.1 if has_upload else 0.0),
                "evidence": evidence
            }
            
        # 3. Login Gateway Check
        if "sign in" in html_text_lower or "login" in html_text_lower:
            login_inputs = [i for i in inputs if i.get('type') in ['password', 'email', 'text']]
            if len(login_inputs) <= 3 and len(inputs) > 0:
                evidence.append("Found login keywords and few inputs")
                return {
                    "page_type": PageType.login_gateway,
                    "automatable": False, # Needs login first
                    "confidence": 0.8,
                    "evidence": evidence
                }

        # 4. Document Checklist / FAQ
        doc_keywords = ["required documents", "upload size", "file format", "address proof", "id proof"]
        faq_keywords = ["frequently asked questions", "faq"]
        
        if any(k in html_text_lower for k in doc_keywords):
            evidence.append("Document checklist keywords found")
            return {
                "page_type": PageType.document_checklist,
                "automatable": False,
                "confidence": 0.8,
                "evidence": evidence
            }
            
        if any(k in html_text_lower for k in faq_keywords):
            evidence.append("FAQ keywords found")
            return {
                "page_type": PageType.faq,
                "automatable": False,
                "confidence": 0.8,
                "evidence": evidence
            }

        # 5. Official Guidance
        guidance_keywords = ["eligibility", "benefits", "instructions", "process", "who can apply", "how to apply"]
        if official_domain and any(k in html_text_lower for k in guidance_keywords):
            evidence.append("Official domain with guidance keywords")
            return {
                "page_type": PageType.official_guidance,
                "automatable": False,
                "confidence": 0.85,
                "evidence": evidence
            }
            
        # 6. Article/Blog
        if not official_domain and len(soup.find_all("p")) > 10:
            evidence.append("Third-party domain with large amount of text paragraphs")
            return {
                "page_type": PageType.article_or_blog,
                "automatable": False,
                "confidence": 0.7,
                "evidence": evidence
            }
            
        # Default
        evidence.append("No strong heuristics matched")
        return {
            "page_type": PageType.unknown,
            "automatable": False,
            "confidence": 0.3,
            "evidence": evidence
        }
