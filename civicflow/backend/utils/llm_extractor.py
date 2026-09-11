"""
CivicFlow — LLM Field Extractor
================================
Uses OpenRouter's Nemotron 3 Ultra to extract structured fields from OCR text.
Replaces regex-based extraction with LLM reasoning for better accuracy.
"""
import os
import json
import re
import time
import logging
from typing import Dict, List

import httpx

logger = logging.getLogger("civicflow.llm_extractor")


async def call_openrouter(messages: List[Dict], api_key: str) -> Dict:
    """
    Call OpenRouter API with Nemotron 3 Ultra model.
    
    Args:
        messages: List of message dicts with role and content
        api_key: OpenRouter API key
    
    Returns:
        API response JSON dict
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://civicflow.app",
                "X-Title": "CivicFlow"
            },
            content=json.dumps({
                "model": "openai/gpt-oss-120b:free",
                "messages": messages,
                "reasoning": {"enabled": True},
                "temperature": 0.1,
                "max_tokens": 800
            })
        )
        return response.json()


async def extract_fields_with_llm(
    ocr_text: str,
    doc_type: str,
    openrouter_api_key: str
) -> dict:
    """
    Extract structured fields from OCR text using LLM reasoning.
    
    Args:
        ocr_text: Raw text extracted from document by OCR
        doc_type: Type of document (e.g., "aadhaar", "pan", "passport")
        openrouter_api_key: OpenRouter API key
    
    Returns:
        Dict with extracted fields and metadata. Always returns a dict, never raises.
    """
    start_time = time.time()
    
    logger.info("LLM extraction started for doc_type=%s", doc_type)
    
    # Validate inputs
    if not openrouter_api_key:
        logger.warning("OpenRouter API key not configured")
        return {
            "extraction_success": False,
            "extraction_engine": "failed",
            "fallback_mode": True,
            "error_reason": "api_key_missing"
        }
    
    if not ocr_text or not ocr_text.strip():
        logger.warning("Empty OCR text provided")
        return {
            "extraction_success": False,
            "extraction_engine": "failed",
            "fallback_mode": True,
            "error_reason": "empty_ocr_text"
        }
    
    # STEP 1: Build messages
    system_message = {
        "role": "system",
        "content": """You are a precise document field extraction engine for Indian government documents.
You receive raw OCR text extracted from a scanned document and must extract structured fields.

CRITICAL: Respond ONLY with a valid JSON object. No explanation. No markdown. No code blocks. No extra text.
Just the raw JSON.

Extract these fields if present in the OCR text:
- name: Full name of the person (string, title case, strip titles like Mr/Mrs/Dr/Shri/Smt/Ms)
- dob: Date of birth in YYYY-MM-DD format only
- gender: "M" or "F" only
- aadhaar_last4: ONLY the last 4 digits of Aadhaar number (string, never full number)
- pan_number: PAN in format AAAAA9999A (5 uppercase letters, 4 digits, 1 uppercase letter)
- passport_number: Passport number (letter followed by 7 digits, e.g. A1234567)
- address: Complete address as one string
- pincode: 6-digit Indian PIN code as string
- phone: Exactly 10-digit Indian mobile number, no country code
- father_name: Father's name if explicitly mentioned
- expiry_date: Document expiry in YYYY-MM-DD format

Rules:
- Only include fields that are clearly present in the text
- Omit fields entirely if not found — never use null
- aadhaar_last4: if you see 1234 5678 9012, return "9012" not the full number
- All dates must be YYYY-MM-DD format regardless of input format
- name must be Title Case
- Return empty object {} if nothing can be extracted
- Never invent or guess values not in the OCR text"""
    }
    
    user_message = {
        "role": "user",
        "content": f"Document type: {doc_type}\n\nOCR extracted text:\n{ocr_text}\n\nExtract all available fields from this document."
    }
    
    messages = [system_message, user_message]
    
    try:
        # STEP 2: First API call with reasoning enabled
        result = await call_openrouter(messages, openrouter_api_key)
        
        # Check for API errors
        if "error" in result:
            error_msg = result.get("error", {}).get("message", "Unknown error")
            logger.warning("OpenRouter API error: %s", error_msg)
            return {
                "extraction_success": False,
                "extraction_engine": "failed",
                "fallback_mode": True,
                "error_reason": "api_error",
                "raw_text_preview": ocr_text[:300]
            }
        
        # STEP 3: Parse the response
        response_message = result.get("choices", [{}])[0].get("message", {})
        raw_content = response_message.get("content", "").strip()
        
        if not raw_content:
            logger.warning("Empty response from LLM")
            return {
                "extraction_success": False,
                "extraction_engine": "failed",
                "fallback_mode": True,
                "error_reason": "empty_response",
                "raw_text_preview": ocr_text[:300]
            }
        
        # Try direct JSON parse
        extracted_json = None
        try:
            extracted_json = json.loads(raw_content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown or text
            json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
            if json_match:
                try:
                    extracted_json = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        
        # If parsing failed, return fallback
        if extracted_json is None or not isinstance(extracted_json, dict):
            logger.warning("Failed to parse LLM response as JSON")
            return {
                "extraction_success": False,
                "extraction_engine": "failed",
                "fallback_mode": True,
                "error_reason": "json_parse_failed",
                "raw_text_preview": ocr_text[:300]
            }
        
        # STEP 4: Build return dict
        elapsed_ms = (time.time() - start_time) * 1000
        num_fields = len([k for k in extracted_json.keys() if k not in ["extraction_success", "extraction_engine", "reasoning_used"]])
        
        logger.info("LLM extraction completed in %.0f ms, extracted %d fields", elapsed_ms, num_fields)
        
        return {
            **extracted_json,
            "extraction_success": True,
            "extraction_engine": "openai/gpt-oss-120b:free",
            "reasoning_used": True
        }
    
    except httpx.ConnectError as e:
        logger.warning("Cannot connect to OpenRouter: %s", str(e))
        return {
            "extraction_success": False,
            "extraction_engine": "failed",
            "fallback_mode": True,
            "error_reason": "connection_error",
            "raw_text_preview": ocr_text[:300]
        }
    
    except httpx.TimeoutException as e:
        logger.warning("OpenRouter request timeout: %s", str(e))
        return {
            "extraction_success": False,
            "extraction_engine": "failed",
            "fallback_mode": True,
            "error_reason": "timeout",
            "raw_text_preview": ocr_text[:300]
        }
    
    except KeyError as e:
        logger.warning("Unexpected API response structure: %s", str(e))
        return {
            "extraction_success": False,
            "extraction_engine": "failed",
            "fallback_mode": True,
            "error_reason": "response_parse_error",
            "raw_text_preview": ocr_text[:300]
        }
    
    except Exception as e:
        logger.error("Unexpected error in LLM extraction: %s: %s", type(e).__name__, str(e))
        return {
            "extraction_success": False,
            "extraction_engine": "failed",
            "fallback_mode": True,
            "error_reason": f"{type(e).__name__}",
            "raw_text_preview": ocr_text[:300]
        }


# STEP 6: Test function
async def _test_extraction():
    """Quick test — run: python utils/llm_extractor.py"""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    test_cases = [
        {
            "doc_type": "aadhaar",
            "text": """GOVERNMENT OF INDIA
Unique Identification Authority of India
Aadhaar
1234 5678 9012
RAMESH KUMAR
DOB: 05/01/1990
MALE
123 MG Road, Bandra West
Mumbai 400051 Maharashtra"""
        },
        {
            "doc_type": "pan",
            "text": """INCOME TAX DEPARTMENT
GOVT. OF INDIA
Permanent Account Number Card
ABCDE1234F
Name: Suresh Sharma
Father's Name: Rajesh Sharma
Date of Birth: 15/08/1985"""
        }
    ]
    
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set in .env")
        return
    
    for case in test_cases:
        print(f"\n--- Testing {case['doc_type']} ---")
        result = await extract_fields_with_llm(
            ocr_text=case["text"],
            doc_type=case["doc_type"],
            openrouter_api_key=api_key
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test_extraction())
