"""
CivicFlow — Government Form Finder Agent
==========================================
Given a plain-English description of what the user wants to do,
finds the most relevant Indian government portal URL.

Strategy:
1. Gemini 2.0 Flash reasons over the pre-seeded portal list
2. If AI fails → keyword matching fallback
3. Returns ranked results + full portal list for the frontend to display

Endpoint: POST /forms/search
"""
import os
import sys
import json
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Pre-seeded portal directory
# ---------------------------------------------------------------------------

KNOWN_PORTALS = [
    {
        "name": "Passport Seva Portal",
        "url": "https://passportindia.gov.in",
        "category": "travel",
        "keywords": ["passport", "travel document", "ecr", "nec", "tatkal", "police clearance"],
    },
    {
        "name": "Aadhaar Enrollment / Update (UIDAI)",
        "url": "https://uidai.gov.in",
        "category": "identity",
        "keywords": ["aadhaar", "uid", "biometric", "address update", "name correction", "aadhar"],
    },
    {
        "name": "My Aadhaar (Download / Lock)",
        "url": "https://myaadhaar.uidai.gov.in",
        "category": "identity",
        "keywords": ["download aadhaar", "e-aadhaar", "virtual id", "aadhaar lock", "otp"],
    },
    {
        "name": "DigiLocker",
        "url": "https://digilocker.gov.in",
        "category": "documents",
        "keywords": ["digilocker", "digital documents", "driving licence", "marksheet", "certificate"],
    },
    {
        "name": "PAN Card Application (NSDL / UTIITSL)",
        "url": "https://tin.tin.nsdl.com",
        "category": "tax",
        "keywords": ["pan card", "permanent account number", "pan application", "pan correction"],
    },
    {
        "name": "Voter ID / NVSP",
        "url": "https://voterportal.eci.gov.in",
        "category": "election",
        "keywords": ["voter id", "epic", "voter registration", "election", "vote", "form 6"],
    },
    {
        "name": "Driving Licence / Learner Licence (Sarathi)",
        "url": "https://sarathi.parivahan.gov.in",
        "category": "transport",
        "keywords": ["driving licence", "dl", "learner licence", "ll", "driving test"],
    },
    {
        "name": "Vehicle Registration (Vahan)",
        "url": "https://vahan.parivahan.gov.in",
        "category": "transport",
        "keywords": ["vehicle registration", "rc", "road tax", "fitness certificate", "noc"],
    },
    {
        "name": "Income Tax e-Filing Portal",
        "url": "https://eportal.incometax.gov.in",
        "category": "tax",
        "keywords": ["itr", "income tax return", "e-filing", "form 16", "refund", "tax"],
    },
    {
        "name": "EPF Member Portal (EPFO)",
        "url": "https://unifiedportal-mem.epfindia.gov.in",
        "category": "employment",
        "keywords": ["epf", "provident fund", "pf withdrawal", "uan", "passbook", "claim"],
    },
    {
        "name": "PM Kisan Samman Nidhi",
        "url": "https://pmkisan.gov.in",
        "category": "agriculture",
        "keywords": ["pm kisan", "farmer", "agricultural", "kisan", "8000"],
    },
    {
        "name": "Ayushman Bharat (PM-JAY)",
        "url": "https://pmjay.gov.in",
        "category": "health",
        "keywords": ["ayushman", "health card", "pmjay", "hospital", "5 lakh", "health insurance"],
    },
    {
        "name": "National Scholarship Portal (NSP)",
        "url": "https://scholarships.gov.in",
        "category": "education",
        "keywords": ["scholarship", "student", "nsp", "minority", "obc", "sc st scholarship"],
    },
    {
        "name": "IRCTC Train Ticket Booking",
        "url": "https://www.irctc.co.in",
        "category": "transport",
        "keywords": ["train ticket", "rail", "irctc", "reservation", "tatkal", "pnr"],
    },
    {
        "name": "GST Portal",
        "url": "https://www.gst.gov.in",
        "category": "tax",
        "keywords": ["gst", "goods and services", "gstin", "return filing", "gstr"],
    },
    {
        "name": "MCA21 Company Registration",
        "url": "https://www.mca.gov.in",
        "category": "business",
        "keywords": ["company registration", "mca", "roc", "incorporation", "llp", "pvt ltd"],
    },
    {
        "name": "e-District Portal (State Certificates)",
        "url": "https://edistrict.gov.in",
        "category": "certificates",
        "keywords": ["caste certificate", "income certificate", "domicile", "birth certificate", "death certificate"],
    },
    {
        "name": "UMANG — Unified Government Services",
        "url": "https://web.umang.gov.in",
        "category": "general",
        "keywords": ["umang", "government services", "multiple services"],
    },
    {
        "name": "Jeevan Pramaan (Digital Life Certificate)",
        "url": "https://jeevanpramaan.gov.in",
        "category": "pension",
        "keywords": ["life certificate", "pension", "pensioner", "jeevan pramaan"],
    },
    {
        "name": "PM SVANidhi (Street Vendor Loan)",
        "url": "https://pmsvanidhi.mohua.gov.in",
        "category": "loan",
        "keywords": ["street vendor", "vending", "svanidhi", "working capital loan"],
    },
    {
        "name": "Mudra Loan (PMMY)",
        "url": "https://www.mudra.org.in",
        "category": "loan",
        "keywords": ["mudra", "small business loan", "shishu", "kishor", "tarun"],
    },
    {
        "name": "MSME Udyam Registration",
        "url": "https://udyamregistration.gov.in",
        "category": "business",
        "keywords": ["udyam", "msme", "small business", "enterprise registration"],
    },
    {
        "name": "Skill India / PMKVY",
        "url": "https://www.skillindia.gov.in",
        "category": "education",
        "keywords": ["skill", "training", "pmkvy", "vocational", "certificate course"],
    },
    {
        "name": "National Career Service Portal (NCS)",
        "url": "https://www.ncs.gov.in",
        "category": "employment",
        "keywords": ["job", "employment", "ncs", "career", "resume", "job seeker"],
    },
]


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

async def find_government_portal(description: str, custom_url: Optional[str] = None) -> dict:
    """
    Find the best government portal for the user's need.

    Args:
        description: Plain-English description of what user wants to do
        custom_url: If user already knows the URL, skip search and return it

    Returns:
        {
            url, portal_name, category, confidence, reasoning,
            alternatives: [...],
            all_portals: [...]   # for frontend dropdown
        }
    """
    # If user provided a custom URL directly, validate and return
    if custom_url:
        if not custom_url.startswith(("http://", "https://")):
            raise ValueError("Custom URL must start with http:// or https://")
        return {
            "url": custom_url,
            "portal_name": "Custom URL",
            "category": "custom",
            "confidence": "high",
            "reasoning": "User-provided URL",
            "alternatives": [],
            "all_portals": KNOWN_PORTALS,
        }

    # Try AI-powered search
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            result = await _gemini_search(description, api_key)
            if result:
                result["all_portals"] = KNOWN_PORTALS
                return result
        except Exception as e:
            print(f"[FormFinder] AI search failed: {e} — falling back to keyword match")

    # Keyword fallback
    return _keyword_search(description)


async def _gemini_search(description: str, api_key: str) -> Optional[dict]:
    """Ask Gemini to pick the best portal from the known list."""
    from google import genai

    client = genai.Client(api_key=api_key)

    portals_summary = "\n".join(
        f"- {p['name']} | {p['url']} | Category: {p['category']} | Keywords: {', '.join(p['keywords'])}"
        for p in KNOWN_PORTALS
    )

    prompt = f"""You are a helpful assistant for Indian government services.

A user wants to: "{description}"

Here are the known government portals:
{portals_summary}

Find the BEST matching portal. If no portal matches well, say so honestly.

Return ONLY valid JSON (no markdown):
{{
  "url": "exact url from the list above",
  "portal_name": "exact name from the list",
  "category": "category from the list",
  "confidence": "high|medium|low|none",
  "reasoning": "one sentence explanation",
  "alternatives": [
    {{"url": "...", "portal_name": "...", "confidence": "low"}}
  ]
}}"""

    response = client.models.generate_content(model="gemini-2.0-flash-lite", contents=prompt)
    text = response.text.strip()

    # Strip markdown code blocks if present
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    result = json.loads(text)

    # Validate that the URL is in our known list (prevent hallucinated URLs)
    known_urls = {p["url"] for p in KNOWN_PORTALS}
    if result.get("url") and result["url"] not in known_urls:
        print(f"[FormFinder] AI returned unknown URL: {result['url']} — overriding with keyword match")
        return None

    return result


def _keyword_search(description: str) -> dict:
    """Simple keyword matching — always works, no AI needed."""
    desc_lower = description.lower()
    scored = []

    for portal in KNOWN_PORTALS:
        score = sum(1 for kw in portal["keywords"] if kw in desc_lower)
        if score > 0:
            scored.append((score, portal))

    scored.sort(reverse=True, key=lambda x: x[0])

    if scored:
        best_score, best = scored[0]
        alts = [
            {"url": p["url"], "portal_name": p["name"], "confidence": "low"}
            for _, p in scored[1:4]
        ]
        confidence = "high" if best_score >= 2 else "medium"
        return {
            "url": best["url"],
            "portal_name": best["name"],
            "category": best["category"],
            "confidence": confidence,
            "reasoning": f"Matched {best_score} keyword(s) in description",
            "alternatives": alts,
            "all_portals": KNOWN_PORTALS,
        }

    # No match at all
    return {
        "url": "",
        "portal_name": "No matching portal found",
        "category": "unknown",
        "confidence": "none",
        "reasoning": "No Indian government portal matched your description. Please enter the URL manually.",
        "alternatives": [],
        "all_portals": KNOWN_PORTALS,
    }
