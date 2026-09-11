"""
Enhanced Form Search Agent - Multi-Source Classification Pipeline
===============================================================
Implements strict multi-stage retrieval with typed classification.
"""
import os
import sys
import json
import asyncio
import re
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urljoin

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.form_models import (
    EnhancedFormSearchResult, DirectFormResult, GuidanceSource, 
    YouTubeVideoResult, ProcessInsights, URLClassification
)
from utils.url_classifier import URLClassifier, classify_url_with_llm
from utils.youtube_providers import YouTubeMetadataProvider, YouTubeTranscriptProvider, GuidanceSummarizer
from agents.scout import scout
from config import settings

class EnhancedFormSearchAgent:
    """Multi-stage form search with strict classification"""
    
    def __init__(self):
        from utils.llm import get_llm_client
        self.llm = get_llm_client()
        self.classifier = URLClassifier(self.llm)
        self.youtube_metadata = YouTubeMetadataProvider()
        self.youtube_transcript = YouTubeTranscriptProvider()
        self.guidance_summarizer = GuidanceSummarizer(self.llm)
        
        self.PORTAL_KNOWLEDGE = """
        Known Indian portals (reference - system works with ANY website):
        - Passport: passportindia.gov.in
        - PAN: incometaxindia.gov.in, onlineservices.nsdl.com
        - Aadhaar: uidai.gov.in
        - GST: gst.gov.in
        - EPF: epfindia.gov.in
        - Driving licence: sarathi.parivahan.gov.in
        - DigiLocker: digilocker.gov.in
        """

    async def find_form_enhanced(
        self, 
        service_name: str, 
        state: Optional[str] = None,
        user_provided_url: Optional[str] = None
    ) -> EnhancedFormSearchResult:
        """Main enhanced search pipeline"""
        
        # Handle user provided URL
        if user_provided_url:
            return await self._handle_user_provided_url(user_provided_url, service_name)
        
        if not self.llm.api_key:
            return EnhancedFormSearchResult(
                query=service_name,
                insights=ProcessInsights(summary="OpenRouter API key not configured"),
                valid=False,
                error_message="OpenRouter API key not configured"
            )
        
        # STAGE A: Query Understanding
        query_variants = self._parse_query_intent(service_name, state)
        
        # STAGE B: Candidate Retrieval
        candidates = await self._retrieve_candidates(query_variants)
        
        # STAGE C: URL Classification
        classified_results = await self._classify_candidates(candidates, service_name)
        
        # STAGE D: Target Selection
        selected_targets = self._select_targets(classified_results)
        
        # STAGE E: Enrichment
        enriched_data = await self._enrich_guidance(selected_targets, service_name, state)
        
        # STAGE F: UI Packaging
        return self._package_for_ui(service_name, selected_targets, enriched_data, classified_results)

    def _parse_query_intent(self, service_name: str, state: Optional[str]) -> Dict[str, Any]:
        """Stage A: Parse user intent and create search variants"""
        variants = [
            service_name,
            f"{service_name} application",
            f"{service_name} form",
            f"apply for {service_name}",
            f"online {service_name}"
        ]
        
        if state:
            variants.extend([
                f"{service_name} {state}",
                f"{service_name} in {state}"
            ])
        
        return {
            "original_query": service_name,
            "search_variants": variants,
            "state": state,
            "intent_type": self._classify_intent(service_name)
        }

    def _classify_intent(self, service_name: str) -> str:
        """Classify user intent type"""
        service_lower = service_name.lower()
        
        if any(word in service_lower for word in ['passport', 'visa', 'license', 'certificate']):
            return "document_application"
        elif any(word in service_lower for word in ['job', 'employment', 'career']):
            return "job_application" 
        elif any(word in service_lower for word in ['admission', 'college', 'university']):
            return "education_application"
        else:
            return "general_service"

    async def _retrieve_candidates(self, query_variants: Dict[str, Any]) -> List[str]:
        """Stage B: Retrieve candidate URLs"""
        if not self.llm.api_key:
            return []
        
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
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            candidates = json.loads(response.strip())
            
            # Filter valid URLs
            return [url for url in candidates if self._is_valid_url(url)]
            
        except Exception as e:
            print(f"[EnhancedFormSearch] Candidate retrieval failed: {e}")
            return []

    async def _classify_candidates(self, candidates: List[str], service_name: str) -> List[URLClassification]:
        """Stage C: Classify each candidate URL"""
        classifications = []
        
        # Limit concurrent classifications
        semaphore = asyncio.Semaphore(3)
        
        async def classify_single(url: str) -> Optional[URLClassification]:
            async with semaphore:
                try:
                    # Handle YouTube URLs immediately
                    if self.youtube_metadata.is_youtube_url(url):
                        metadata = self.youtube_metadata.get_basic_metadata(url)
                        return URLClassification(
                            url=url,
                            source_category="youtube",
                            page_type="youtube_video",
                            official_domain=False,
                            automatable=False,
                            confidence=0.95,
                            evidence=["YouTube domain"],
                            normalized_title=metadata.get("title", "YouTube Video"),
                            relevance_reason="Video guidance"
                        )
                    
                    # Scout the page
                    scout_result = await asyncio.wait_for(scout(url), timeout=10.0)
                    
                    if scout_result.get("error") or not scout_result.get("html"):
                        return None
                    
                    html = scout_result["html"]
                    title = scout_result.get("title", "")
                    
                    # Use enhanced classification
                    return await classify_url_with_llm(url, html[:2000], title, self.llm)
                    
                except asyncio.TimeoutError:
                    print(f"[EnhancedFormSearch] Classification timeout: {url}")
                    return None
                except Exception as e:
                    print(f"[EnhancedFormSearch] Classification failed for {url}: {e}")
                    return None
        
        # Classify all candidates
        tasks = [classify_single(url) for url in candidates]
        results = await asyncio.gather(*tasks)
        
        # Filter successful classifications
        return [result for result in results if result is not None]

    def _select_targets(self, classifications: List[URLClassification]) -> Dict[str, List[URLClassification]]:
        """Stage D: Select best targets by type"""
        
        # Group by page type
        by_type = {}
        for cls in classifications:
            page_type = cls.page_type
            if page_type not in by_type:
                by_type[page_type] = []
            by_type[page_type].append(cls)
        
        # Sort each type by confidence
        for page_type in by_type:
            by_type[page_type].sort(key=lambda x: x.confidence, reverse=True)
        
        # Select targets
        selected = {
            "direct_forms": by_type.get("direct_form", [])[:1],  # Best direct form only
            "official_guidance": by_type.get("official_guidance", [])[:3],
            "document_checklists": by_type.get("document_checklist", [])[:3], 
            "faqs": by_type.get("faq", [])[:2],
            "youtube_videos": by_type.get("youtube_video", [])[:3],
            "login_gateways": by_type.get("login_gateway", [])[:1],
            "other": []
        }
        
        # Include other high-confidence results
        for cls in classifications:
            if (cls.page_type not in ["direct_form", "official_guidance", "document_checklist", 
                                    "faq", "youtube_video", "login_gateway"] and 
                cls.confidence > 0.6):
                selected["other"].append(cls)
        
        return selected

    async def _enrich_guidance(
        self, 
        targets: Dict[str, List[URLClassification]], 
        service_name: str,
        state: Optional[str]
    ) -> Dict[str, Any]:
        """Stage E: Enrich with guidance data"""
        
        enrichment = {
            "youtube_enriched": [],
            "guidance_text": [],
            "process_steps": [],
            "document_requirements": []
        }
        
        # Enrich YouTube videos
        for youtube_cls in targets.get("youtube_videos", []):
            video_id = self.youtube_metadata.extract_video_id(youtube_cls.url)
            if video_id:
                # Get transcript
                transcript_data = await self.youtube_transcript.get_transcript(video_id)
                
                # Summarize if available
                summary_data = {}
                if transcript_data.get("transcript_available"):
                    summary_data = await self.guidance_summarizer.summarize_transcript(
                        transcript_data["transcript_text"], 
                        service_name
                    )
                
                enriched_video = {
                    "classification": youtube_cls,
                    "video_id": video_id,
                    "transcript_data": transcript_data,
                    "summary_data": summary_data
                }
                enrichment["youtube_enriched"].append(enriched_video)
        
        # Extract guidance from official pages
        guidance_sources = (targets.get("official_guidance", []) + 
                          targets.get("document_checklists", []) + 
                          targets.get("faqs", []))
        
        for guide_cls in guidance_sources:
            enrichment["guidance_text"].append({
                "url": guide_cls.url,
                "title": guide_cls.normalized_title,
                "page_type": guide_cls.page_type,
                "confidence": guide_cls.confidence
            })
        
        return enrichment

    def _package_for_ui(
        self, 
        service_name: str,
        targets: Dict[str, List[URLClassification]],
        enrichment: Dict[str, Any],
        all_classifications: List[URLClassification]
    ) -> EnhancedFormSearchResult:
        """Stage F: Package for frontend"""
        
        # Best direct form
        direct_form = None
        direct_forms = targets.get("direct_forms", [])
        if direct_forms:
            cls = direct_forms[0]
            direct_form = DirectFormResult(
                url=cls.url,
                title=cls.normalized_title,
                confidence=cls.confidence,
                automatable=cls.automatable,
                evidence=cls.evidence,
                form_indicators=self._extract_form_indicators(cls)
            )
        
        # Official guidance
        official_guidance = []
        for cls in targets.get("official_guidance", []):
            official_guidance.append(GuidanceSource(
                url=cls.url,
                title=cls.normalized_title,
                page_type="official_guidance",
                official_domain=cls.official_domain,
                confidence=cls.confidence
            ))
        
        # Document checklists
        document_checklists = []
        for cls in targets.get("document_checklists", []):
            document_checklists.append(GuidanceSource(
                url=cls.url,
                title=cls.normalized_title,
                page_type="document_checklist", 
                official_domain=cls.official_domain,
                confidence=cls.confidence
            ))
        
        # YouTube videos
        youtube_videos = []
        for enriched in enrichment.get("youtube_enriched", []):
            cls = enriched["classification"]
            transcript_data = enriched["transcript_data"]
            summary_data = enriched["summary_data"]
            
            youtube_videos.append(YouTubeVideoResult(
                url=cls.url,
                video_id=enriched["video_id"],
                title=cls.normalized_title,
                transcript_available=transcript_data.get("transcript_available", False),
                transcript_source=transcript_data.get("transcript_source"),
                transcript_summary=summary_data.get("transcript_summary"),
                key_steps=summary_data.get("key_steps", []),
                mentioned_documents=summary_data.get("mentioned_documents", []),
                mentioned_warnings=summary_data.get("mentioned_warnings", []),
                confidence=cls.confidence
            ))
        
        # Process insights
        insights = self._generate_process_insights(
            service_name, targets, enrichment, direct_form is not None
        )
        
        # Debug info
        debug = {
            "classified_candidates": [
                {
                    "url": cls.url,
                    "page_type": cls.page_type,
                    "confidence": cls.confidence,
                    "evidence": cls.evidence
                } for cls in all_classifications
            ],
            "total_candidates": len(all_classifications),
            "direct_forms_found": len(targets.get("direct_forms", [])),
            "guidance_pages_found": len(targets.get("official_guidance", [])),
            "youtube_videos_found": len(targets.get("youtube_videos", []))
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

    def _extract_form_indicators(self, classification: URLClassification) -> List[str]:
        """Extract form-specific indicators"""
        indicators = []
        for evidence in classification.evidence:
            if any(word in evidence.lower() for word in ['form', 'input', 'submit', 'upload', 'captcha']):
                indicators.append(evidence)
        return indicators

    def _generate_process_insights(
        self, 
        service_name: str,
        targets: Dict[str, List[URLClassification]],
        enrichment: Dict[str, Any],
        has_direct_form: bool
    ) -> ProcessInsights:
        """Generate unified process insights"""
        
        # Aggregate steps from YouTube summaries
        all_steps = []
        all_documents = []
        all_warnings = []
        
        for enriched in enrichment.get("youtube_enriched", []):
            summary = enriched.get("summary_data", {})
            all_steps.extend(summary.get("key_steps", []))
            all_documents.extend(summary.get("mentioned_documents", []))
            all_warnings.extend(summary.get("mentioned_warnings", []))
        
        # Remove duplicates
        all_steps = list(dict.fromkeys(all_steps))
        all_documents = list(dict.fromkeys(all_documents))
        all_warnings = list(dict.fromkeys(all_warnings))
        
        # Determine automation readiness
        automation_readiness = "high" if has_direct_form else "medium"
        if targets.get("login_gateways"):
            automation_readiness = "medium"
        if not has_direct_form and not targets.get("official_guidance"):
            automation_readiness = "low"
        
        # Build summary
        summary_parts = [f"Found guidance for {service_name}."]
        if has_direct_form:
            summary_parts.append("Direct application form available for automation.")
        else:
            summary_parts.append("No direct form found - manual navigation may be required.")
        
        sources = []
        sources.extend([cls.url for cls in targets.get("official_guidance", [])])
        sources.extend([cls.url for cls in targets.get("youtube_videos", [])])
        
        return ProcessInsights(
            summary=" ".join(summary_parts),
            likely_required_documents=all_documents,
            likely_steps=all_steps,
            likely_blockers=all_warnings,
            automation_readiness=automation_readiness,
            sources=sources
        )

    async def _handle_user_provided_url(self, url: str, service_name: str) -> EnhancedFormSearchResult:
        """Handle user-provided URL"""
        try:
            classification = await classify_url_with_llm(url, "", "", self.llm)
            
            direct_form = None
            if classification.page_type == "direct_form":
                direct_form = DirectFormResult(
                    url=url,
                    title="User Provided Form",
                    confidence=1.0,
                    automatable=classification.automatable,
                    evidence=["User provided URL"],
                    form_indicators=classification.evidence
                )
            
            insights = ProcessInsights(
                summary=f"User provided URL for {service_name}",
                automation_readiness="high" if direct_form else "unknown"
            )
            
            return EnhancedFormSearchResult(
                query=service_name,
                direct_form=direct_form,
                insights=insights,
                valid=True
            )
            
        except Exception as e:
            return EnhancedFormSearchResult(
                query=service_name,
                insights=ProcessInsights(summary="Failed to analyze provided URL"),
                valid=False,
                error_message=str(e)
            )

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid"""
        if not url or not isinstance(url, str):
            return False
        
        url_lower = url.lower()
        
        # Invalid patterns
        invalid_patterns = [
            "example.com", "placeholder", "yourdomain", "localhost", "127.0.0.1"
        ]
        
        for pattern in invalid_patterns:
            if pattern in url_lower:
                return False
        
        return "." in url and (url.startswith("http") or not url.startswith("/"))