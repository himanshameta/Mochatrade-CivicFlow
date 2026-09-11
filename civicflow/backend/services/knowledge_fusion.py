import json
from typing import List, Dict, Any
from utils.llm import get_llm_client
from models.form_models import ProcessInsightsNode

class KnowledgeFusionService:
    """Fuses knowledge from multiple sources to create a unified process insight."""
    
    @staticmethod
    async def generate_insights(query: str, sources_text: List[str]) -> ProcessInsightsNode:
        if not sources_text:
            return ProcessInsightsNode(
                summary="No official guidance or transcripts available to generate insights.",
                notes="Requires manual research."
            )
            
        combined_text = "\n\n---\n\n".join(sources_text)[:12000] # Limit tokens
        
        llm = get_llm_client()
        if not llm.api_key:
            return ProcessInsightsNode(summary="LLM not configured, cannot generate insights.")
            
        prompt = f"""
        You are a government services expert. The user wants to "{query}".
        I have gathered text from official guidance pages, FAQs, and video transcripts.
        
        Sources:
        {combined_text}
        
        Generate a unified process insight. If sources disagree, mention uncertainty.
        Return ONLY valid JSON:
        {{
            "summary": "1-2 paragraph overview",
            "likely_required_documents": ["doc1", "doc2"],
            "likely_steps": ["step1", "step2"],
            "likely_blockers": ["common issue 1", "prerequisite"],
            "automation_readiness": "High/Medium/Low with reason",
            "notes": "Any other context or warnings"
        }}
        """
        
        try:
            text = await llm.generate_content(prompt=prompt, temperature=0.1, max_tokens=600)
            if text.startswith("```json"): text = text[7:]
            if text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
            data = json.loads(text.strip())
            return ProcessInsightsNode(**data)
        except Exception as e:
            print(f"[KnowledgeFusion] Failed: {e}")
            return ProcessInsightsNode(summary="Failed to parse insights from LLM.")
