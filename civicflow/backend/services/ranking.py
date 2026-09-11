from typing import List, Dict, Any, Tuple
from models.form_models import ClassifiedURL, DirectFormCandidate

class RankingService:
    """Ranks candidates to strongly favor direct forms."""
    
    @staticmethod
    def rank_candidates(classified_urls: List[ClassifiedURL]) -> Tuple[DirectFormCandidate | None, List[ClassifiedURL]]:
        direct_forms = []
        others = []
        
        for item in classified_urls:
            if item.page_type == "direct_form":
                score = item.confidence
                if item.official_domain:
                    score += 0.2
                if item.automatable:
                    score += 0.2
                
                # Cap at 1.0
                score = min(score, 1.0)
                
                direct_forms.append({
                    "candidate": DirectFormCandidate(
                        url=item.url,
                        title=item.title,
                        confidence=score,
                        automatable=item.automatable,
                        evidence=item.evidence
                    ),
                    "score": score
                })
            else:
                others.append(item)
                
        # Sort direct forms
        direct_forms.sort(key=lambda x: x["score"], reverse=True)
        
        best_form = direct_forms[0]["candidate"] if direct_forms else None
        
        # We can also sort others by official domain and confidence
        others.sort(key=lambda x: (x.official_domain, x.confidence), reverse=True)
        
        return best_form, others
