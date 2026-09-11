import asyncio
import re
from typing import List, Dict, Any
from urllib.parse import urljoin

from duckduckgo_search import DDGS
from agents.scout import scout

from models.form_models import (
    FormSearchResultV2, 
    ClassifiedURL, 
    YouTubeVideoNode, 
    ProcessInsightsNode,
    PageType
)
from services.classifier import ClassifierService
from services.ranking import RankingService
from services.youtube_provider import YouTubeProvider
from services.knowledge_fusion import KnowledgeFusionService

class SearchPipeline:
    
    @staticmethod
    async def run(service_name: str, state: str = None) -> FormSearchResultV2:
        query = f"{service_name} {'in ' + state if state else ''} official portal apply online"
        
        # Stage A & B: Query Understanding & Candidate Retrieval via DDGS
        candidates = SearchPipeline._retrieve_candidates(query)
        if not candidates:
            return FormSearchResultV2(query=query, valid=False, error_message="No candidates found from search.")

        # Limit to top 5 to manage latency
        candidates = candidates[:5]
        
        # Stage C: URL Classification
        tasks = [SearchPipeline._fetch_and_classify(url) for url in candidates]
        classified_results = await asyncio.gather(*tasks)
        
        # We might also do 1 level crawl if it's a portal/guidance
        expanded_results = []
        for res in classified_results:
            if not res:
                continue
            expanded_results.append(res)
            
            # Intelligent Crawler (Stage C extension)
            if res.page_type in [PageType.dashboard_or_portal_home, PageType.official_guidance, PageType.login_gateway]:
                apply_links = SearchPipeline._find_apply_links(res._html, res.url)
                # Fetch up to 2 discovered links
                crawl_tasks = [SearchPipeline._fetch_and_classify(l) for l in apply_links[:2]]
                crawled = await asyncio.gather(*crawl_tasks)
                expanded_results.extend([c for c in crawled if c])

        # Stage D: Target Selection & Ranking
        best_form, others = RankingService.rank_candidates(expanded_results)
        
        # Separate others
        guidance = []
        checklists = []
        youtube_videos = []
        sources_text = [] # For fusion
        
        for item in others:
            if item.page_type == PageType.youtube_video:
                youtube_videos.append(item)
            elif item.page_type == PageType.document_checklist:
                checklists.append(item)
                if hasattr(item, '_text_snippet'): sources_text.append(item._text_snippet)
            elif item.page_type in [PageType.official_guidance, PageType.faq]:
                guidance.append(item)
                if hasattr(item, '_text_snippet'): sources_text.append(item._text_snippet)

        # Stage E: Enrichment (YouTube)
        enriched_videos = []
        for vid in youtube_videos[:3]:
            video_id = YouTubeProvider.extract_video_id(vid.url)
            if video_id:
                transcript_res = YouTubeProvider.get_transcript(video_id)
                enriched_vid = YouTubeVideoNode(
                    url=vid.url,
                    title=vid.title,
                    transcript_available=transcript_res["available"],
                    transcript_summary="Transcript fetched." if transcript_res["available"] else "Transcript unavailable.",
                )
                enriched_videos.append(enriched_vid)
                if transcript_res["available"]:
                    # Take first 3000 chars of transcript for fusion
                    sources_text.append(f"Video Transcript: {transcript_res['text'][:3000]}")
            else:
                enriched_videos.append(YouTubeVideoNode(url=vid.url, title=vid.title))

        # Stage E: Knowledge Fusion
        insights = await KnowledgeFusionService.generate_insights(query, sources_text)

        # Stage F: UI Packaging
        debug_info = {
            "total_candidates_evaluated": len(expanded_results),
            "classified_urls": [c.model_dump() for c in expanded_results if not hasattr(c, '_html')] # Exclude hidden attrs in dump
        }
        
        return FormSearchResultV2(
            query=query,
            direct_form=best_form,
            official_guidance=guidance[:3],
            document_checklists=checklists[:3],
            youtube_videos=enriched_videos,
            insights=insights,
            debug=debug_info
        )

    @staticmethod
    def _retrieve_candidates(query: str) -> List[str]:
        urls = []
        try:
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(query, max_results=8)]
                for r in results:
                    urls.append(r["href"])
        except Exception as e:
            print(f"[SearchPipeline] DDGS failed: {e}")
        return urls

    @staticmethod
    async def _fetch_and_classify(url: str) -> ClassifiedURL | None:
        try:
            scout_res = await scout(url)
            if scout_res.get("error") or not scout_res.get("html"):
                # Handle YouTube without playwright since it might fail or we don't need its HTML for basic classification
                if "youtube.com" in url or "youtu.be" in url:
                    return ClassifiedURL(
                        url=url,
                        title="YouTube Video",
                        source_category="youtube",
                        page_type=PageType.youtube_video,
                        official_domain=False,
                        automatable=False,
                        confidence=1.0,
                        evidence=["YouTube URL pattern"]
                    )
                return None
            
            html = scout_res["html"]
            title = scout_res.get("title", "Unknown")
            
            cls_result = ClassifierService.classify_page(url, html, title)
            
            obj = ClassifiedURL(
                url=url,
                title=title,
                source_category=ClassifierService.get_source_category(url),
                page_type=cls_result["page_type"],
                official_domain=ClassifierService.is_official_domain(url),
                automatable=cls_result["automatable"],
                confidence=cls_result["confidence"],
                evidence=cls_result["evidence"],
                normalized_title=title.strip()
            )
            # Attach temporary hidden attributes for downstream stages
            obj._html = html
            obj._text_snippet = html[:4000] # for fusion
            return obj
            
        except Exception as e:
            print(f"[SearchPipeline] Fetch failed for {url}: {e}")
            return None

    @staticmethod
    def _find_apply_links(html: str, base_url: str) -> List[str]:
        apply_urls = []
        soup_links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE)
        for href, link_text in soup_links:
            text_lower = link_text.lower()
            if "apply" in text_lower or "register" in text_lower or "login" in text_lower or "signup" in text_lower or "click here" in text_lower:
                if href.startswith("http"):
                    apply_urls.append(href)
                elif href.startswith("/"):
                    apply_urls.append(urljoin(base_url, href))
                elif not href.startswith("#") and not href.startswith("javascript"):
                    apply_urls.append(urljoin(base_url, href))
        return list(dict.fromkeys(apply_urls))
