"""
MSBTE Migration Certificate Test
================================
Reproduces the search flow for debugging
"""
import asyncio
import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.fixed_enhanced_form_search import FixedEnhancedFormSearchAgent

async def test_msbte_search():
    """Test MSBTE migration certificate search"""
    
    print("="*60)
    print("MSBTE MIGRATION CERTIFICATE SEARCH TEST")
    print("="*60)
    
    agent = FixedEnhancedFormSearchAgent()
    
    query = "msbte migration certificate"
    state = None
    
    print(f"\nQuery: {query}")
    print(f"State: {state}")
    print("\nStarting search...\n")
    
    result = await agent.find_form_enhanced(query, state)
    
    print("\n" + "="*60)
    print("SEARCH RESULTS")
    print("="*60)
    
    print(f"\nValid: {result.valid}")
    
    if result.direct_form:
        print(f"\nDIRECT FORM FOUND:")
        print(f"  URL: {result.direct_form.url}")
        print(f"  Title: {result.direct_form.title}")
        print(f"  Confidence: {result.direct_form.confidence}")
        print(f"  Automatable: {result.direct_form.automatable}")
        print(f"  Evidence: {result.direct_form.evidence}")
    else:
        print("\nNO DIRECT FORM FOUND")
    
    print(f"\nOfficial Guidance: {len(result.official_guidance)} pages")
    for i, guide in enumerate(result.official_guidance, 1):
        print(f"  {i}. {guide.title}")
        print(f"     URL: {guide.url}")
        print(f"     Confidence: {guide.confidence}")
    
    print(f"\nDocument Checklists: {len(result.document_checklists)} pages")
    for i, doc in enumerate(result.document_checklists, 1):
        print(f"  {i}. {doc.title}")
        print(f"     URL: {doc.url}")
    
    print(f"\nYouTube Videos: {len(result.youtube_videos)} videos")
    for i, video in enumerate(result.youtube_videos, 1):
        print(f"  {i}. {video.title}")
        print(f"     URL: {video.url}")
        print(f"     Video ID: {video.video_id}")
        print(f"     Transcript: {video.transcript_available}")
    
    print(f"\nInsights:")
    print(f"  Summary: {result.insights.summary}")
    print(f"  Automation Readiness: {result.insights.automation_readiness}")
    print(f"  Steps: {len(result.insights.likely_steps)}")
    print(f"  Documents: {len(result.insights.likely_required_documents)}")
    
    print(f"\nDebug Info:")
    print(f"  Search ID: {result.debug.get('search_id', 'N/A')}")
    print(f"  Raw Candidates: {result.debug.get('raw_candidates_count', 0)}")
    print(f"  Normalized: {result.debug.get('normalized_candidates_count', 0)}")
    print(f"  Classified: {result.debug.get('classified_candidates_count', 0)}")
    print(f"  Dropped: {result.debug.get('dropped_candidates_count', 0)}")
    
    if result.debug.get('dropped_candidates'):
        print(f"\nDropped Candidates:")
        for dropped in result.debug['dropped_candidates']:
            print(f"  - {dropped['url']}")
            print(f"    Reason: {dropped['reason']}")
    
    if result.debug.get('raw_candidates'):
        print(f"\nRaw Candidates from LLM:")
        for url in result.debug['raw_candidates']:
            print(f"  - {url}")
    
    # Save full result to file
    output_file = "msbte_test_result.json"
    with open(output_file, 'w') as f:
        json.dump(result.model_dump(), f, indent=2, default=str)
    
    print(f"\nFull result saved to: {output_file}")
    print("\n" + "="*60)

if __name__ == "__main__":
    asyncio.run(test_msbte_search())