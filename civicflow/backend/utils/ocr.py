import httpx
import logging
import os
from pathlib import Path

logger = logging.getLogger("civicflow.ocr")

OCR_API_URL = os.getenv("OCR_API_URL", "http://localhost:8081")
OCR_API_ENABLED = os.getenv("OCR_API_ENABLED", "true").lower() == "true"


async def extract_text_from_document(file_bytes: bytes, filename: str, content_type: str) -> dict:
    if not OCR_API_ENABLED:
        logger.info("OCR disabled via env, returning fallback")
        return _fallback_response(filename)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OCR_API_URL}/ocr",
                files={"file": (filename, file_bytes, content_type)},
            )
            if response.status_code == 200:
                data = response.json()
                logger.info(f"OCR success for {filename}")
                return data
            else:
                logger.warning(f"OCR service returned {response.status_code}")
                return _fallback_response(filename)
    except httpx.ConnectError:
        logger.warning(f"OCR service unreachable at {OCR_API_URL}")
        return _fallback_response(filename)
    except Exception as e:
        logger.error(f"OCR call failed: {e}")
        return _fallback_response(filename)


def _fallback_response(filename: str) -> dict:
    return {
        "success": False,
        "fallback_mode": True,
        "engine": "none",
        "message": "OCR service unavailable. Manual review required.",
        "pages": [],
        "metadata": {"filename": filename, "processing_mode": "fallback"}
    }