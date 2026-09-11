# Enhanced Form Search - Fixed Implementation

## Overview

This document describes the comprehensive fix for CivicFlow's enhanced form search end-to-end flow.

## Problems Fixed

### 1. Classification Timeout Loss
**Problem**: When LLM classification timed out, URLs were dropped completely (returned `None`)
**Fix**: Implemented fallback heuristic classification based on domain and path patterns

### 2. Scout Failure Loss  
**Problem**: Any Playwright/scout exception dropped the URL
**Fix**: Catch exceptions and use fallback classification instead of dropping URLs

### 3. Invalid YouTube Links
**Problem**: YouTube URLs shown without validation, leading to 404s
**Fix**: Added YouTube oEmbed validation before displaying videos in UI

### 4. URL Malformation
**Problem**: Malformed URLs from LLM caused DNS errors
**Fix**: Comprehensive URL normalization with hostname validation

### 5. No Request Tracing
**Problem**: Impossible to debug where URLs were lost
**Fix**: Added search_id tracking through entire pipeline with detailed logging

### 6. Silent Failures
**Problem**: 200 response even when classification failed
**Fix**: Enhanced debug output showing dropped candidates with reasons

## New Components

### utils/url_normalizer.py
- `URLNormalizer` class handles:
  - URL cleaning (whitespace, markdown, punctuation)
  - Scheme canonicalization
  - YouTube URL normalization
  - Hostname validation
  - Fallback classification based on heuristics

### utils/youtube_validator.py
- `YouTubeValidator` class validates videos using YouTube oEmbed API
- Checks video availability before showing in UI
- Returns detailed availability status (available, not_found, private, timeout)

### agents/fixed_enhanced_form_search.py
- `FixedEnhancedFormSearchAgent` - Complete rewrite with:
  - Search ID generation for tracing
  - Comprehensive logging at every stage
  - Fallback classification on timeout/error
  - YouTube validation
  - Robust error handling
  - Enhanced debug output

## Pipeline Flow

### Stage A: Query Understanding
- Parse service name and state
- Generate search variants
- Log: search_id, query, variants

### Stage B: Candidate Retrieval
- Call LLM for candidate URLs
- Log: raw candidates count, URLs

### Stage B.5: Normalization & Deduplication
- Normalize URLs (clean, validate hostname)
- Special handling for YouTube URLs
- Deduplicate
- Log: normalized count, invalid URLs

### Stage C: Classification (Robust)
- For each candidate:
  1. Try YouTube fast path
  2. Scout page (12s timeout)
  3. Try LLM classification (8s timeout)
  4. **Fallback**: Use heuristic classification if timeout/error
- Log: classification result, confidence, evidence
- **Never drop URLs** - always provide fallback

### Stage D: Target Selection
- Group by page_type
- Sort by confidence
- Select top N per category
- Log: selected counts

### Stage E: Enrichment
- **Validate YouTube videos** using oEmbed API
- Fetch transcripts for valid videos only
- Summarize transcripts
- Log: validation results

### Stage F: UI Packaging
- Build response with validated data
- Enhanced debug object with:
  - search_id
  - Raw, normalized, classified, dropped counts
  - Full list of dropped candidates with reasons
  - Classified candidates with evidence

## Debug Output

The `debug` field in API response now contains:

```json
{
  "search_id": "a1b2c3d4",
  "raw_candidates_count": 8,
  "normalized_candidates_count": 7,
  "classified_candidates_count": 6,
  "dropped_candidates_count": 1,
  "final_direct_forms": 1,
  "final_guidance": 2,
  "final_youtube": 2,
  "raw_candidates": ["https://...", ...],
  "dropped_candidates": [
    {
      "url": "https://invalid.com",
      "reason": "Hostname validation failed"
    }
  ],
  "classified_candidates": [
    {
      "url": "https://example.com",
      "page_type": "direct_form",
      "confidence": 0.85,
      "evidence": ["Contains <form> tag", "Has submit button"]
    }
  ]
}
```

## Fallback Classification Logic

When LLM classification times out or fails:

### YouTube URLs
- Always classified as `youtube_video`
- Confidence: 0.9
- Evidence: "YouTube domain (fallback)"

### Official Domains (.gov.in, .nic.in, known portals)
- Path contains "form/apply/register" → `direct_form` (0.6 confidence)
- Path contains "faq/help" → `faq` (0.7 confidence)
- Path contains "document/checklist" → `document_checklist` (0.7 confidence)
- Path contains "guideline/instruction" → `official_guidance` (0.65 confidence)
- Default → `official_guidance` (0.5 confidence)

### Third-Party Domains
- Default → `article_or_blog` (0.4 confidence)
- Evidence: "Third-party domain (fallback)"

## Frontend Changes

### FormSearch.jsx

Added:
- Debug info banner showing search_id and counts
- Console logging of full response
- Better error handling with specific error messages
- Detection of `enhanced_fixed` search mode

### Console Logging

```javascript
console.log('[FormSearch] Full response:', response.data.data)
console.log('[FormSearch] Metadata:', metadata)
console.log('[FormSearch] Debug:', response.data.data.debug)
```

## Testing

### MSBTE Test Script

Run:
```bash
cd backend
python tests/test_msbte_search.py
```

Output:
- Console: Detailed search flow
- File: `msbte_test_result.json` with complete result

### Expected Behavior

For query "msbte migration certificate":
1. LLM returns 8 candidates including msbte.org.in URLs
2. All URLs normalized and validated
3. Classification with fallback if timeouts occur
4. MSBTE URLs classified as `official_guidance` or `direct_form`
5. Results visible in frontend with proper categorization

### Logs to Check

Search for: `[{search_id}]` in logs to trace specific request:
- `STAGE A: Query Understanding`
- `Raw candidates: N`
- `Normalized candidates: N`
- `Classifying: {url}`
- `LLM classified {url} as {type}` OR `using fallback`
- `Classified: N, Dropped: N`
- `Selected targets: direct=N, guidance=N, youtube=N`

## API Changes

### Endpoint: POST /search/form/enhanced

Now uses `FixedEnhancedFormSearchAgent`

### Response additions:

```json
{
  "search_metadata": {
    "search_mode": "enhanced_fixed",  // Changed from "enhanced"
    "search_id": "a1b2c3d4",          // NEW
    "total_dropped_candidates": 1      // NEW
  }
}
```

### Error responses:

Now include traceback for debugging:
```json
{
  "success": false,
  "message": "Error message",
  "traceback": "Full Python traceback",
  "data": {}
}
```

## Configuration

No environment variable changes needed. Uses existing:
- `OPENROUTER_API_KEY` for LLM
- `GEMINI_API_KEY` (if used)

## Performance

### Timeouts:
- Individual scout: 12s
- LLM classification: 8s  
- YouTube validation: 5s
- Overall search: ~30-60s

### Concurrency:
- Max 3 concurrent classifications (semaphore)
- YouTube validations run in parallel

## Monitoring

Key metrics to track:
- `raw_candidates_count` - Should be 5-8
- `dropped_candidates_count` - Should be 0-2
- `classified_candidates_count` - Should be ≥ raw - 2
- Fallback classification rate (check logs for "fallback")

## Troubleshooting

### No results shown

1. Check browser console for `[FormSearch]` logs
2. Check `debug.search_id` in response
3. Search backend logs for that search_id
4. Check `debug.dropped_candidates` for reasons

### YouTube videos not showing

1. Check if `youtube_videos_found` > 0 in metadata
2. Check console for validation failures
3. Videos with `valid: false` are filtered out

### Classification timeout

1. Check logs for "using fallback"
2. Fallback classification preserves URL
3. May have lower confidence but still usable

## Migration

The fixed agent is backwards compatible:
- Same request format
- Enhanced response format (superset)
- Frontend handles both old and new formats

To switch back to old agent:
```python
# In api/search.py
agent = get_enhanced_search_agent()  # Old
agent = get_fixed_search_agent()     # New (current)
```

## Future Improvements

1. Cache LLM classifications (Redis)
2. Pre-validate YouTube IDs before LLM call
3. Add DNS pre-check before scout
4. Implement circuit breaker for failing domains
5. Add classification confidence threshold tuning