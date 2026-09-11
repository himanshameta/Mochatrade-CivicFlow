"""
CivicFlow — Portal URL Registry
================================
Centralized registry of verified Indian government portal URLs.
Updated: 2024 - All URLs verified as current.
"""

PORTAL_URLS = {
    # Tax Services
    "income_tax": "https://www.incometax.gov.in/iec/foportal/",
    "pan_nsdl": "https://www.onlineservices.nsdl.com/paam/endUserRegisterContact.html",
    "pan_utiitsl": "https://www.pan.utiitsl.com/PAN/",
    "gst": "https://www.gst.gov.in/",
    
    # Identity Documents
    "passport": "https://passportindia.gov.in/",
    "aadhaar_update": "https://ssup.uidai.gov.in/",
    "aadhaar_download": "https://myaadhaar.uidai.gov.in/",
    "voter_id": "https://voters.eci.gov.in/",
    "digilocker": "https://www.digilocker.gov.in/",
    
    # Employment & Benefits
    "epf": "https://unifiedportal-mem.epfindia.gov.in/",
    "ncs_jobs": "https://www.ncs.gov.in/",
    "esic": "https://www.esic.in/",
    
    # Transport
    "driving_license": "https://parivahan.gov.in/parivahan/",
    "vehicle_registration": "https://vahan.parivahan.gov.in/",
    "irctc": "https://www.irctc.co.in/",
    
    # Business Registration
    "udyam_msme": "https://udyamregistration.gov.in/",
    "mca_company": "https://www.mca.gov.in/",
    "fssai": "https://foscos.fssai.gov.in/",
    
    # Social Welfare
    "pm_kisan": "https://pmkisan.gov.in/",
    "ayushman_bharat": "https://pmjay.gov.in/",
    "scholarship_nsp": "https://scholarships.gov.in/",
    "jeevan_pramaan": "https://jeevanpramaan.gov.in/",
    "pm_svanidhi": "https://pmsvanidhi.mohua.gov.in/",
    "mudra_loan": "https://www.mudra.org.in/",
    
    # Skills & Education
    "skill_india": "https://www.skillindia.gov.in/",
    "swayam_courses": "https://swayam.gov.in/",
    
    # State Services (No central URL)
    "ration_card": None,  # State-specific, no central URL
    "birth_certificate": None,  # State municipal corporation
    "caste_certificate": None,  # State e-District portals
    
    # Multi-service Platforms
    "umang": "https://web.umang.gov.in/",
}


def get_portal_url(service_type: str) -> str:
    """
    Get the verified portal URL for a given service.
    
    Args:
        service_type: Service identifier (e.g., "income_tax", "passport")
        
    Returns:
        Portal URL string
        
    Raises:
        ValueError: If service not found or URL not available
    """
    url = PORTAL_URLS.get(service_type.lower())
    if url is None:
        raise ValueError(
            f"No portal URL configured for: {service_type}. "
            f"This may be a state-specific service requiring manual URL entry."
        )
    return url


def list_all_portals() -> dict:
    """Return all portal URLs as a dictionary."""
    return {k: v for k, v in PORTAL_URLS.items() if v is not None}


def search_portal(query: str) -> list:
    """
    Search for portals matching a keyword query.
    
    Args:
        query: Search term (e.g., "tax", "passport")
        
    Returns:
        List of (service_key, url) tuples matching the query
    """
    query_lower = query.lower()
    matches = []
    
    for key, url in PORTAL_URLS.items():
        if url and query_lower in key.lower():
            matches.append((key, url))
    
    return matches


# Deprecated URLs - DO NOT USE
DEPRECATED_URLS = {
    "incometaxindiaefiling.gov.in": {
        "status": "DEAD - No DNS record",
        "replacement": "https://www.incometax.gov.in/iec/foportal/",
        "deprecated_since": "2021"
    },
    "eportal.incometax.gov.in": {
        "status": "Redirects to new portal",
        "replacement": "https://www.incometax.gov.in/iec/foportal/",
        "deprecated_since": "2022"
    }
}


if __name__ == "__main__":
    # Test the module
    print("=== Portal URL Registry ===\n")
    
    print("Total portals registered:", len(PORTAL_URLS))
    print("Active portals:", len([u for u in PORTAL_URLS.values() if u]))
    print("State-specific (no URL):", len([u for u in PORTAL_URLS.values() if u is None]))
    
    print("\n=== Sample Lookups ===")
    
    test_keys = ["income_tax", "passport", "ration_card"]
    for key in test_keys:
        try:
            url = get_portal_url(key)
            print(f"OK {key}: {url}")
        except ValueError as e:
            print(f"SKIP {key}: {e}")
    
    print("\n=== Search Test ===")
    results = search_portal("tax")
    print(f"Found {len(results)} portals matching 'tax':")
    for key, url in results:
        print(f"  - {key}: {url}")
