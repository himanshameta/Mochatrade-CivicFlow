"""
FIXED Enhanced Form Search Agent
=================================
Multi-stage pipeline with comprehensive logging and fallback handling.
"""
import os
import sys
import json
import asyncio
import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.form_models import (
    EnhancedFormSearchResult, DirectFormResult, GuidanceSource, 
    YouTubeVideoResult, ProcessInsights, URLClassification
)
from utils.url_classifier import URLClassifier, classify_url_with_llm
from utils.url_normalizer import URLNormalizer
from utils.youtube_validator import YouTubeValidator
from utils.youtube_providers import YouTubeMetadataProvider, YouTubeTranscriptProvider, GuidanceSummarizer
from utils.display_text_generator import generate_display_title, generate_display_reason, clean_evidence
from agents.scout import scout

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FixedEnhancedFormSearchAgent:
    """Enhanced search with full tracing and fallback handling"""
    
    def __init__(self):
        from utils.llm import get_llm_client
        self.llm = get_llm_client()
        self.classifier = URLClassifier(self.llm)
        self.normalizer = URLNormalizer()
        self.youtube_validator = YouTubeValidator()
        self.youtube_metadata = YouTubeMetadataProvider()
        self.youtube_transcript = YouTubeTranscriptProvider()
        self.guidance_summarizer = GuidanceSummarizer(self.llm)
        
        self.PORTAL_KNOWLEDGE = """
        Known portals: passportindia.gov.in, incometaxindia.gov.in, uidai.gov.in,
        msbte.org.in, msbte.com, epfindia.gov.in, sarathi.parivahan.gov.in
        """
    
    async def find_form_enhanced(
        self, 
        service_name: str, 
        state: Optional[str] = None,
        user_provided_url: Optional[str] = None
    ) -> EnhancedFormSearchResult:
        """Main search pipeline with full tracing"""
        
        # Generate search ID for tracing
        search_id = str(uuid.uuid4())[:8]
        logger.info(f"[{search_id}] === SEARCH START ===")
        logger.info(f"[{search_id}] Query: {service_name}, State: {state}")
        
        # Handle user URL
        if user_provided_url:
            logger.info(f"[{search_id}] User provided URL: {user_provided_url}")
            return await self._handle_user_provided_url(user_provided_url, service_name, search_id)
        
        if not self.llm.api_key:
            logger.error(f"[{search_id}] OpenRouter API key not configured")
            return EnhancedFormSearchResult(
                query=service_name,
                insights=ProcessInsights(summary="API key not configured"),
                valid=False,
                error_message="OpenRouter API key not configured"
            )
        
        # STAGE A: Query Understanding
        logger.info(f"[{search_id}] STAGE A: Query Understanding")
        query_variants = self._parse_query_intent(service_name, state, search_id)
        
        # STAGE B: Candidate Retrieval
        logger.info(f"[{search_id}] STAGE B: Candidate Retrieval")
        raw_candidates = await self._retrieve_candidates(query_variants, search_id)
        logger.info(f"[{search_id}] Raw candidates: {len(raw_candidates)}")
        logger.info(f"[{search_id}] Raw URLs: {json.dumps(raw_candidates, indent=2)}")
        
        # STAGE B.5: Normalize and Deduplicate
        logger.info(f"[{search_id}] STAGE B.5: Normalization")
        normalized_candidates = self._normalize_candidates(raw_candidates, search_id)
        logger.info(f"[{search_id}] Normalized candidates: {len(normalized_candidates)}")
        
        # STAGE C: URL Classification
        logger.info(f"[{search_id}] STAGE C: Classification")
        classified_results, dropped_candidates = await self._classify_candidates_robust(
            normalized_candidates, service_name, search_id
        )
        logger.info(f"[{search_id}] Classified: {len(classified_results)}, Dropped: {len(dropped_candidates)}")
        
        # STAGE D: Target Selection
        logger.info(f"[{search_id}] STAGE D: Target Selection")
        selected_targets = self._select_targets(classified_results, search_id)
        
        # STAGE E: Enrichment
        logger.info(f"[{search_id}] STAGE E: Enrichment")
        enriched_data = await self._enrich_guidance(selected_targets, service_name, state, search_id)
        
        # STAGE F: UI Packaging
        logger.info(f"[{search_id}] STAGE F: Packaging")
        result = self._package_for_ui(
            service_name, selected_targets, enriched_data, 
            classified_results, raw_candidates, normalized_candidates, dropped_candidates, search_id
        )
        
        logger.info(f"[{search_id}] === SEARCH COMPLETE ===")
        logger.info(f"[{search_id}] Final: direct_form={result.direct_form is not None}, " +
                   f"guidance={len(result.official_guidance)}, youtube={len(result.youtube_videos)}")
        
        return result
    
    def _parse_query_intent(self, service_name: str, state: Optional[str], search_id: str) -> Dict[str, Any]:
        """Stage A"""
        variants = [
            service_name,
            f"{service_name} application",
            f"{service_name} form",
            f"apply for {service_name}",
            f"online {service_name}"
        ]
        
        if state:
            variants.extend([f"{service_name} {state}", f"{service_name} in {state}"])
        
        logger.info(f"[{search_id}] Query variants: {variants}")
        
        return {
            "original_query": service_name,
            "search_variants": variants,
            "state": state
        }
    
    async def _retrieve_candidates(self, query_variants: Dict[str, Any], search_id: str) -> List[str]:
        """Stage B"""
        prompt = f"""
        {self.PORTAL_KNOWLEDGE}
        
        For "{query_variants['original_query']}", find 8 diverse URLs including:
        - Direct application forms
        - Official guidance pages
        - Document requirement pages
        - FAQ pages
        - YouTube tutorial videos
        
        Return ONLY a JSON array of URLs:
        ["https://example.com/url1", "https://youtube.com/watch?v=xxx"]
        """
        
        try:
            response = await self.llm.generate_content(prompt=prompt, temperature=0.2, max_tokens=600)
            
            # Clean response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            candidates = json.loads(response)
            logger.info(f"[{search_id}] LLM returned {len(candidates)} candidates")
            return candidates if isinstance(candidates, list) else []
            
        except Exception as e:
            logger.error(f"[{search_id}] Candidate retrieval failed: {e}")
            return []
    
    def _normalize_candidates(self, raw_urls: List[str], search_id: str) -> List[Dict[str, Any]]:
        """Stage B.5: Normalize and deduplicate"""
        normalized = []
        seen_urls = set()
        
        for i, raw_url in enumerate(raw_urls):
            logger.info(f"[{search_id}] Normalizing candidate {i+1}: {raw_url}")
            
            # Normalize based on type
            if self.normalizer.is_youtube_url(raw_url):
                norm_url, video_id = self.normalizer.normalize_youtube_url(raw_url, search_id)
                if norm_url and video_id and norm_url not in seen_urls:
                    normalized.append({
                        'raw_url': raw_url,
                        'normalized_url': norm_url,
                        'video_id': video_id,
                        'type': 'youtube'
                    })
                    seen_urls.add(norm_url)
                else:
                    logger.warning(f"[{search_id}] Invalid YouTube URL: {raw_url}")
            else:
                norm_url = self.normalizer.normalize_url(raw_url, search_id)
                if norm_url and self.normalizer.validate_hostname(norm_url, search_id):
                    if norm_url not in seen_urls:
                        normalized.append({
                            'raw_url': raw_url,
                            'normalized_url': norm_url,
                            'type': 'web'
                        })
                        seen_urls.add(norm_url)
                else:
                    logger.warning(f"[{search_id}] Invalid URL: {raw_url}")
        
        return normalized
    
    async def _classify_candidates_robust(
        self, 
        candidates: List[Dict[str, Any]], 
        service_name: str, 
        search_id: str
    ) -> tuple:
        """Stage C: Classification with robust fallback"""
        
        classifications = []
        dropped = []
        semaphore = asyncio.Semaphore(3)
        
        async def classify_single(candidate: Dict[str, Any]) -> Optional[URLClassification]:
            url = candidate['normalized_url']
            cand_type = candidate['type']
            
            async with semaphore:
                logger.info(f"[{search_id}] Classifying: {url}")
                
                try:
                    # YouTube fast path
                    if cand_type == 'youtube':
                        logger.info(f"[{search_id}] YouTube URL detected: {url}")
                        return URLClassification(
                            url=url,
                            source_category="youtube",
                            page_type="youtube_video",
                            official_domain=False,
                            automatable=False,
                            confidence=0.95,
                            evidence=["YouTube domain"],
                            normalized_title=f"YouTube Video {candidate.get('video_id', '')}",
                            relevance_reason="Video guidance"
                        )
                    
                    # Scout the page
                    try:
                        scout_result = await asyncio.wait_for(scout(url), timeout=12.0)
                        
                        if scout_result.get("error"):
                            logger.warning(f"[{search_id}] Scout error for {url}: {scout_result['error']}")
                            # Use fallback on scout failure
                            return self.normalizer.get_fallback_classification(url, "", search_id)
                        
                        if not scout_result.get("html"):
                            logger.warning(f"[{search_id}] Empty HTML for {url}")
                            # Use fallback
                            return self.normalizer.get_fallback_classification(url, "", search_id)
                        
                        html = scout_result["html"]
                        title = scout_result.get("title", "")
                        
                        logger.info(f"[{search_id}] Scout success for {url}, HTML length: {len(html)}")
                        
                        # Try LLM classification with timeout
                        try:
                            classification = await asyncio.wait_for(
                                classify_url_with_llm(url, html[:2000], title, self.llm),
                                timeout=8.0
                            )
                            logger.info(f"[{search_id}] LLM classified {url} as {classification.page_type}")
                            return classification
                            
                        except asyncio.TimeoutError:
                            logger.warning(f"[{search_id}] LLM classification timeout for {url}, using fallback")
                            return self.normalizer.get_fallback_classification(url, title, search_id)
                        
                    except asyncio.TimeoutError:
                        logger.warning(f"[{search_id}] Scout timeout for {url}, using fallback")
                        return self.normalizer.get_fallback_classification(url, "", search_id)
                        
                except Exception as e:
                    logger.error(f"[{search_id}] Classification exception for {url}: {e}")
                    # Still try fallback
                    return self.normalizer.get_fallback_classification(url, "", search_id)
        
        # Classify all
        tasks = [classify_single(cand) for cand in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            url = candidates[i]['normalized_url']
            if isinstance(result, Exception):
                logger.error(f"[{search_id}] Exception classifying {url}: {result}")
                dropped.append({'url': url, 'reason': f'Exception: {result}'})
            elif result is None:
                logger.warning(f"[{search_id}] No classification for {url}")
                dropped.append({'url': url, 'reason': 'No classification returned'})
            else:
                classifications.append(result)
                logger.info(f"[{search_id}] Classified {url} as {result.page_type} (conf: {result.confidence})")
        
        return classifications, dropped
    
    def _select_targets(self, classifications: List[URLClassification], search_id: str) -> Dict[str, List[URLClassification]]:
        """Stage D"""
        by_type = {}
        for cls in classifications:
            page_type = cls.page_type
            if page_type not in by_type:
                by_type[page_type] = []
            by_type[page_type].append(cls)
        
        # Sort by confidence
        for page_type in by_type:
            by_type[page_type].sort(key=lambda x: x.confidence, reverse=True)
        
        selected = {
            "direct_forms": by_type.get("direct_form", [])[:1],
            "official_guidance": by_type.get("official_guidance", [])[:3],
            "document_checklists": by_type.get("document_checklist", [])[:3],
            "faqs": by_type.get("faq", [])[:2],
            "youtube_videos": by_type.get("youtube_video", [])[:5],  # Increased to 5, will validate
            "login_gateways": by_type.get("login_gateway", [])[:1]
        }
        
        logger.info(f"[{search_id}] Selected targets: " +
                   f"direct={len(selected['direct_forms'])}, " +
                   f"guidance={len(selected['official_guidance'])}, " +
                   f"youtube={len(selected['youtube_videos'])}")
        
        return selected
    
    async def _enrich_guidance(
        self, 
        targets: Dict[str, List[URLClassification]], 
        service_name: str,
        state: Optional[str],
        search_id: str
    ) -> Dict[str, Any]:
        """Stage E"""
        enrichment = {
            "youtube_enriched": [],
            "guidance_text": []
        }
        
        # Validate and enrich YouTube videos
        youtube_videos = targets.get("youtube_videos", [])
        if youtube_videos:
            logger.info(f"[{search_id}] Enriching {len(youtube_videos)} YouTube videos")
            
            # Prepare for validation
            video_data = []
            for yt_cls in youtube_videos:
                video_id = self.youtube_metadata.extract_video_id(yt_cls.url)
                if video_id:
                    video_data.append({'url': yt_cls.url, 'video_id': video_id, 'classification': yt_cls})
            
            # Validate all videos
            validations = await self.youtube_validator.validate_multiple(video_data, search_id)
            
            # Process valid videos
            for i, validation in enumerate(validations):
                if validation.get('valid'):
                    yt_cls = video_data[i]['classification']
                    video_id = video_data[i]['video_id']
                    
                    # Get transcript
                    transcript_data = await self.youtube_transcript.get_transcript(video_id)
                    
                    # Summarize if available
                    summary_data = {}
                    if transcript_data.get("transcript_available"):
                        summary_data = await self.guidance_summarizer.summarize_transcript(
                            transcript_data["transcript_text"], 
                            service_name
                        )
                    
                    enrichment["youtube_enriched"].append({
                        "classification": yt_cls,
                        "video_id": video_id,
                        "validation": validation,
                        "transcript_data": transcript_data,
                        "summary_data": summary_data
                    })
                else:
                    logger.warning(f"[{search_id}] Skipping invalid YouTube video: {video_data[i]['video_id']}")
        
        return enrichment
    
    def _package_for_ui(
        self, 
        service_name: str,
        targets: Dict[str, List[URLClassification]],
        enrichment: Dict[str, Any],
        all_classifications: List[URLClassification],
        raw_candidates: List[str],
        normalized_candidates: List[Dict],
        dropped_candidates: List[Dict],
        search_id: str
    ) -> EnhancedFormSearchResult:
        """Stage F"""
        
        # Direct form
        direct_form = None
        direct_forms = targets.get("direct_forms", [])
        if direct_forms:
            cls = direct_forms[0]
            
            # Generate clean display text
            display_title = generate_display_title(cls.normalized_title, cls.url, cls.page_type)
            display_reason = generate_display_reason(cls.page_type, cls.official_domain, cls.confidence, cls.evidence)
            
            direct_form = DirectFormResult(
                url=cls.url,
                title=cls.normalized_title,
                display_title=display_title,
                display_reason=display_reason,
                confidence=cls.confidence,
                automatable=cls.automatable,
                evidence=clean_evidence(cls.evidence),
                form_indicators=clean_evidence(cls.evidence)
            )
        
        # Official guidance
        official_guidance = [
            GuidanceSource(
                url=cls.url,
                title=cls.normalized_title,
                display_title=generate_display_title(cls.normalized_title, cls.url, cls.page_type),
                display_reason=generate_display_reason(cls.page_type, cls.official_domain, cls.confidence, cls.evidence),
                page_type="official_guidance",
                official_domain=cls.official_domain,
                confidence=cls.confidence
            )
            for cls in targets.get("official_guidance", [])
        ]
        
        # Document checklists
        document_checklists = [
            GuidanceSource(
                url=cls.url,
                title=cls.normalized_title,
                display_title=generate_display_title(cls.normalized_title, cls.url, cls.page_type),
                display_reason=generate_display_reason(cls.page_type, cls.official_domain, cls.confidence, cls.evidence),
                page_type="document_checklist",
                official_domain=cls.official_domain,
                confidence=cls.confidence
            )
            for cls in targets.get("document_checklists", [])
        ]
        
        # YouTube videos (only validated ones)
        youtube_videos = []
        for enriched in enrichment.get("youtube_enriched", []):
            validation = enriched['validation']
            transcript_data = enriched["transcript_data"]
            summary_data = enriched["summary_data"]
            
            # Clean title from validation or derive from video ID
            yt_title = validation.get('title', f'YouTube Video {enriched["video_id"]}')
            if not yt_title or yt_title.startswith('Video '):
                yt_title = generate_display_title(yt_title, enriched["classification"].url, "youtube_video")
            
            youtube_videos.append(YouTubeVideoResult(
                url=enriched["classification"].url,
                video_id=enriched["video_id"],
                title=yt_title,
                channel=validation.get('author_name', ''),
                transcript_available=transcript_data.get("transcript_available", False),
                transcript_summary=summary_data.get("transcript_summary"),
                key_steps=summary_data.get("key_steps", []),
                mentioned_documents=summary_data.get("mentioned_documents", []),
                confidence=enriched["classification"].confidence
            ))
        
        # Process insights
        insights = self._generate_process_insights(service_name, targets, enrichment, direct_form is not None)
        
        # Enhanced debug info
        debug = {
            "search_id": search_id,
            "raw_candidates_count": len(raw_candidates),
            "normalized_candidates_count": len(normalized_candidates),
            "classified_candidates_count": len(all_classifications),
            "dropped_candidates_count": len(dropped_candidates),
            "final_direct_forms": len(targets.get("direct_forms", [])),
            "final_guidance": len(targets.get("official_guidance", [])),
            "final_youtube": len(youtube_videos),
            "raw_candidates": raw_candidates,
            "dropped_candidates": dropped_candidates,
            "classified_candidates": [
                {
                    "url": cls.url,
                    "page_type": cls.page_type,
                    "confidence": cls.confidence,
                    "evidence": cls.evidence
                } for cls in all_classifications
            ]
        }
        
        return EnhancedFormSearchResult(
            query=service_name,
            direct_form=direct_form,
            official_guidance=official_guidance,
            document_checklists=document_checklists,
            youtube_videos=youtube_videos,
            insights=insights,
            debug=debug,
            valid=True
        )
    
    def _generate_process_insights(
        self, 
        service_name: str,
        targets: Dict[str, List[URLClassification]],
        enrichment: Dict[str, Any],
        has_direct_form: bool
    ) -> ProcessInsights:
        """Generate insights"""
        
        all_steps = []
        all_documents = []
        
        for enriched in enrichment.get("youtube_enriched", []):
            summary = enriched.get("summary_data", {})
            all_steps.extend(summary.get("key_steps", []))
            all_documents.extend(summary.get("mentioned_documents", []))
        
        all_steps = list(dict.fromkeys(all_steps))
        all_documents = list(dict.fromkeys(all_documents))
        
        automation_readiness = "high" if has_direct_form else "medium"
        if not has_direct_form and not targets.get("official_guidance"):
            automation_readiness = "low"
        
        summary_parts = [f"Found guidance for {service_name}."]
        if has_direct_form:
            summary_parts.append("Direct application form available for automation.")
        else:
            summary_parts.append("No direct form found - manual navigation may be required.")
        
        return ProcessInsights(
            summary=" ".join(summary_parts),
            likely_required_documents=all_documents,
            likely_steps=all_steps,
            automation_readiness=automation_readiness
        )
    
    async def _handle_user_provided_url(self, url: str, service_name: str, search_id: str) -> EnhancedFormSearchResult:
        """Handle user URL"""
        logger.info(f"[{search_id}] Processing user-provided URL")
        
        norm_url = self.normalizer.normalize_url(url, search_id)
        if not norm_url:
            return EnhancedFormSearchResult(
                query=service_name,
                insights=ProcessInsights(summary="Invalid URL provided"),
                valid=False,
                error_message="Invalid URL format"
            )
        
        try:
            classification = await classify_url_with_llm(norm_url, "", "", self.llm)
            
            direct_form = None
            if classification.page_type == "direct_form":
                direct_form = DirectFormResult(
                    url=norm_url,
                    title="User Provided Form",
                    confidence=1.0,
                    automatable=classification.automatable,
                    evidence=["User provided URL"],
                    form_indicators=classification.evidence
                )
            
            return EnhancedFormSearchResult(
                query=service_name,
                direct_form=direct_form,
                insights=ProcessInsights(
                    summary=f"User provided URL for {service_name}",
                    automation_readiness="high" if direct_form else "unknown"
                ),
                valid=True
            )
            
        except Exception as e:
            logger.error(f"[{search_id}] Error handling user URL: {e}")
            return EnhancedFormSearchResult(
                query=service_name,
                insights=ProcessInsights(summary="Failed to analyze provided URL"),
                valid=False,
                error_message=str(e)
            )