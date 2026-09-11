"""
URL Normalization and Validation
================================
Handles URL cleaning, validation, and normalization with detailed logging.
"""
import re
import logging
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse, parse_qs, urlunparse, urljoin
from models.form_models import URLClassification

logger = logging.getLogger(__name__)

class URLNormalizer:
    """Normalizes and validates URLs with fallback classification"""
    
    def __init__(self):
        self.youtube_id_pattern = re.compile(r'^[a-zA-Z0-9_-]{11}$')
    
    def normalize_url(self, url: str, search_id: str = "unknown") -> Optional[str]:
        """Normalize URL with logging"""
        if not url or not isinstance(url, str):
            logger.warning(f"[{search_id}] Invalid URL type: {type(url)}")
            return None
        
        # Strip whitespace and quotes
        url = url.strip().strip('"').strip("'")
        
        # Remove markdown wrapping
        url = re.sub(r'^\[.*?\]\((.*?)\)$', r'\1', url)
        
        # Strip trailing punctuation
        url = url.rstrip('.,;:!?')
        
        # Ensure scheme
        if not url.startswith(('http://', 'https://')):
            if url.startswith('//'):
                url = 'https:' + url
            elif not url.startswith('/'):
                url = 'https://' + url
        
        # Validate basic structure
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                logger.warning(f"[{search_id}] No netloc in URL: {url}")
                return None
            
            # Canonicalize
            url = urlunparse((
                parsed.scheme or 'https',
                parsed.netloc.lower(),
                parsed.path,
                parsed.params,
                parsed.query,
                ''  # Remove fragment
            ))
            
            logger.info(f"[{search_id}] Normalized URL: {url}")
            return url
            
        except Exception as e:
            logger.error(f"[{search_id}] URL parse failed for {url}: {e}")
            return None
    
    def normalize_youtube_url(self, url: str, search_id: str = "unknown") -> Tuple[Optional[str], Optional[str]]:
        """
        Normalize YouTube URL and extract video ID
        Returns: (normalized_url, video_id)
        """
        if not url:
            return None, None
        
        try:
            parsed = urlparse(url)
            video_id = None
            
            # Extract video ID from various formats
            if 'youtu.be' in parsed.netloc:
                video_id = parsed.path.strip('/')
            elif 'youtube.com' in parsed.netloc:
                if '/watch' in parsed.path:
                    query = parse_qs(parsed.query)
                    video_id = query.get('v', [None])[0]
                elif '/embed/' in parsed.path:
                    video_id = parsed.path.split('/embed/')[-1].split('/')[0]
                elif '/v/' in parsed.path:
                    video_id = parsed.path.split('/v/')[-1].split('/')[0]
            
            # Validate video ID format
            if video_id and self.youtube_id_pattern.match(video_id):
                canonical_url = f"https://www.youtube.com/watch?v={video_id}"
                logger.info(f"[{search_id}] YouTube normalized: {canonical_url} (ID: {video_id})")
                return canonical_url, video_id
            else:
                logger.warning(f"[{search_id}] Invalid YouTube ID extracted from: {url}")
                return None, None
                
        except Exception as e:
            logger.error(f"[{search_id}] YouTube URL normalization failed for {url}: {e}")
            return None, None
    
    def is_youtube_url(self, url: str) -> bool:
        """Quick check if URL is YouTube"""
        if not url:
            return False
        url_lower = url.lower()
        return 'youtube.com' in url_lower or 'youtu.be' in url_lower
    
    def validate_hostname(self, url: str, search_id: str = "unknown") -> bool:
        """Validate hostname structure"""
        try:
            parsed = urlparse(url)
            hostname = parsed.netloc.split(':')[0]  # Remove port
            
            # Basic validation
            if not hostname or len(hostname) < 3:
                return False
            
            # Check for invalid patterns
            invalid_patterns = [
                'example.com', 'placeholder', 'yourdomain', 'yoursite',
                'localhost', '127.0.0.1', 'test.com', 'sample.com'
            ]
            
            hostname_lower = hostname.lower()
            if any(pattern in hostname_lower for pattern in invalid_patterns):
                logger.warning(f"[{search_id}] Invalid hostname pattern: {hostname}")
                return False
            
            # Must have at least one dot
            if '.' not in hostname:
                return False
            
            # Check TLD exists
            parts = hostname.split('.')
            if len(parts[-1]) < 2:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"[{search_id}] Hostname validation failed for {url}: {e}")
            return False
    
    def get_fallback_classification(
        self, 
        url: str, 
        title: str = "", 
        search_id: str = "unknown"
    ) -> URLClassification:
        """
        Provide heuristic-based classification when LLM times out
        """
        logger.info(f"[{search_id}] Using fallback classification for: {url}")
        
        url_lower = url.lower()
        path_lower = urlparse(url).path.lower()
        title_lower = title.lower()
        
        # Determine source category
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            source_category = "youtube"
            page_type = "youtube_video"
            confidence = 0.9
            evidence = ["YouTube domain (fallback)"]
            official_domain = False
        elif self._is_official_domain(url):
            source_category = "official_portal"
            # Classify based on path keywords
            if any(kw in path_lower for kw in ['form', 'apply', 'application', 'register', 'fill']):
                page_type = "direct_form"
                confidence = 0.6
                evidence = ["Official domain + form path (fallback)"]
            elif any(kw in path_lower for kw in ['faq', 'help', 'questions']):
                page_type = "faq"
                confidence = 0.7
                evidence = ["Official domain + FAQ path (fallback)"]
            elif any(kw in path_lower for kw in ['document', 'checklist', 'requirement']):
                page_type = "document_checklist"
                confidence = 0.7
                evidence = ["Official domain + documents path (fallback)"]
            elif any(kw in path_lower or kw in title_lower for kw in ['guideline', 'instruction', 'process']):
                page_type = "official_guidance"
                confidence = 0.65
                evidence = ["Official domain + guidance keywords (fallback)"]
            else:
                page_type = "official_guidance"
                confidence = 0.5
                evidence = ["Official domain (fallback)"]
            official_domain = True
        else:
            source_category = "third_party_web"
            page_type = "article_or_blog"
            confidence = 0.4
            evidence = ["Third-party domain (fallback)"]
            official_domain = False
        
        return URLClassification(
            url=url,
            source_category=source_category,
            page_type=page_type,
            official_domain=official_domain,
            automatable=(page_type == "direct_form" and official_domain),
            confidence=confidence,
            evidence=evidence,
            normalized_title=title or "Page (fallback)",
            relevance_reason=f"Fallback classification: {page_type}"
        )
    
    def _is_official_domain(self, url: str) -> bool:
        """Check if domain is official"""
        domain = urlparse(url).netloc.lower()
        
        gov_patterns = [
            r'\.gov\.in$', r'\.nic\.in$', r'\.gov$', r'\.ac\.in$', r'\.edu$'
        ]
        
        for pattern in gov_patterns:
            if re.search(pattern, domain):
                return True
        
        # Known official domains
        official = [
            'epfindia.gov.in', 'nsdl.com', 'utiitsl.com', 'passportindia.gov.in',
            'incometaxindia.gov.in', 'uidai.gov.in', 'msbte.org.in', 'msbte.com'
        ]
        
        return any(od in domain for od in official)