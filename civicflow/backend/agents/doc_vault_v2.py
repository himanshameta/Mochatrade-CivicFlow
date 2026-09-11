"""
CivicFlow — DocVault Agent (Refactored)
========================================
Handles document processing by delegating OCR to external microservice.
Pipeline: Upload → Validate → Call OCR Service → Extract → Normalise → Cross-Validate → Encrypt → Store
"""
import os
import io
import json
import uuid
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

import magic
import httpx
from PIL import Image
from rapidfuzz import fuzz

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.document_models import OCRBlock, DocumentResult, Conflict
from models.user_models import DocumentDB
from db.mongo import get_db
from utils.encryption import encrypt_field
from utils.llm_extractor import extract_fields_with_llm
from config import settings
import logging

logger = logging.getLogger("civicflow.doc_vault")


class DocVaultAgent:
    SUPPORTED_TYPES = [
      "image/jpeg", "image/png", "image/webp",
      "application/pdf", "image/tiff"
    ]
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

    def __init__(self):
        self.ocr_api_url = settings.ocr_api_url
        self.ocr_enabled = settings.ocr_api_enabled
        self.uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
        os.makedirs(self.uploads_dir, exist_ok=True)
        
        print(f"[DocVault] OCR Service: {self.ocr_api_url} ({'enabled' if self.ocr_enabled else 'disabled'})")

    async def check_ocr_health(self) -> bool:
        """Check if OCR service is available."""
        if not self.ocr_enabled:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ocr_api_url}/health")
                return response.status_code == 200
        except Exception as e:
            print(f"[DocVault] OCR health check failed: {e}")
            return False

    async def call_ocr_service(self, file_bytes: bytes, filename: str) -> Dict:
        """Call external OCR microservice."""
        if not self.ocr_enabled:
            raise RuntimeError("OCR service is disabled")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {"file": (filename, file_bytes)}
                response = await client.post(f"{self.ocr_api_url}/ocr", files=files)
                
                if response.status_code != 200:
                    raise RuntimeError(f"OCR service returned {response.status_code}: {response.text}")
                
                return response.json()
        
        except httpx.TimeoutException:
            raise RuntimeError("OCR service timeout - file too large or service overloaded")
        except httpx.ConnectError:
            raise RuntimeError("Cannot connect to OCR service - ensure it's running on " + self.ocr_api_url)
        except Exception as e:
            raise RuntimeError(f"OCR service error: {str(e)}")

    async def process_document(
        self, 
        file_bytes: bytes,
        filename: str,
        mime_type_hint: str,
        doc_type: str,
        user_id: str,
        session_id: str
    ) -> DocumentResult:
        """
        Main pipeline to process an uploaded document.
        """
        # 1. Validate file size and type
        if len(file_bytes) > self.MAX_FILE_SIZE_BYTES:
            raise ValueError("File exceeds maximum allowed size of 10MB.")

        try:
            mime_type = magic.from_buffer(file_bytes, mime=True)
        except Exception:
            mime_type = mime_type_hint

        if mime_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported file type detected: {mime_type}")

        # 2. Save raw document to disk
        doc_id = str(uuid.uuid4())
        ext = os.path.splitext(filename)[1] or ".bin"
        storage_filename = f"{doc_id}{ext}"
        storage_path = os.path.join(self.uploads_dir, storage_filename)
        
        with open(storage_path, "wb") as f:
            f.write(file_bytes)

        # Initialize the DocumentDB record (pending)
        db = await get_db()
        doc_db = DocumentDB(
            doc_id=doc_id,
            user_id=user_id,
            original_filename=filename,
            mime_type=mime_type,
            storage_path=storage_path,
            file_size_bytes=len(file_bytes),
            ocr_status="processing"
        )
        if db is not None:
            await db.documents.insert_one(doc_db.model_dump())

        # 3. Call OCR service
        try:
            ocr_result = await self.call_ocr_service(file_bytes, filename)
            
            if not ocr_result.get("success"):
                raise RuntimeError("OCR service returned failure")
            
            # Extract text from pages
            all_text_lines = []
            for page in ocr_result.get("pages", []):
                lines = page.get("lines", [])
                all_text_lines.extend(lines)
            
            raw_text = "\n".join(all_text_lines)
            
            # Convert to OCRBlock format for compatibility with fallback
            all_ocr_blocks = [
                OCRBlock(text=line, confidence=0.8, bbox=[], center_y=0)
                for line in all_text_lines
            ]

            # 4. Extract structured fields using LLM (with regex fallback)
            extracted = await extract_fields_with_llm(
                ocr_text=raw_text,
                doc_type=doc_type,
                openrouter_api_key=settings.openrouter_api_key
            )
            
            # If LLM failed, fall back to regex
            if not extracted.get("extraction_success"):
                logger.warning("LLM extraction failed, falling back to regex")
                regex_extracted = self._extract_structured_fields(all_ocr_blocks, doc_type)
                extracted = self._normalize_fields(regex_extracted)
                extracted["extraction_engine"] = "regex-fallback"
            else:
                # LLM already returns normalized fields, just remove metadata keys
                normalized = {k: v for k, v in extracted.items() 
                             if k not in ["extraction_success", "extraction_engine", "reasoning_used"]}
                extracted = normalized
                extracted["extraction_engine"] = "nemotron-llm"

            # 5. Cross-validate with existing profile (if available)
            conflicts = await self._cross_validate_with_db(user_id, extracted)

            # Update DB with success
            if db is not None:
                await db.documents.update_one(
                    {"doc_id": doc_id},
                    {"$set": {
                        "ocr_status": "done",
                        "ocr_results": extracted
                    }}
                )

            return DocumentResult(
                doc_id=doc_id,
                doc_type=doc_type,
                original_filename=filename,
                mime_type=mime_type,
                extracted_fields=extracted,
                conflicts=conflicts,
                raw_ocr_text=raw_text
            )

        except Exception as e:
            # Mark failed in DB
            if db is not None:
                await db.documents.update_one(
                    {"doc_id": doc_id},
                    {"$set": {"ocr_status": "failed", "ocr_results": {"error": str(e)}}}
                )
            raise

    def _extract_structured_fields(
        self, 
        ocr_blocks: List[OCRBlock], 
        doc_type: str
    ) -> dict:
        """Extract structured fields from OCR text using regex patterns."""
        
        # Prepare the OCR text
        ocr_text = "\n".join([b.text for b in ocr_blocks])
        
        # Basic regex-based extraction for common document types
        extracted = {}
        
        if doc_type.lower() == "aadhaar":
            # Extract Aadhaar last 4 digits
            aadhaar_match = re.search(r'\b(\d{4})\s*(\d{4})\s*(\d{4})\b', ocr_text)
            if aadhaar_match:
                extracted["aadhaar_number_last4"] = {"value": aadhaar_match.group(3), "confidence": 0.8}
            
            # Extract DOB
            dob_match = re.search(r'\b(\d{2}[/-]\d{2}[/-]\d{4})\b', ocr_text)
            if dob_match:
                extracted["dob"] = {"value": dob_match.group(1), "confidence": 0.7}
                
        elif doc_type.lower() == "pan":
            # Extract PAN number
            pan_match = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b', ocr_text)
            if pan_match:
                extracted["pan_number"] = {"value": pan_match.group(1), "confidence": 0.9}
                
        # Extract name (first line that looks like a name)
        lines = ocr_text.split('\n')
        for line in lines:
            if len(line.strip()) > 3 and re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)+$', line.strip()):
                extracted["name"] = {"value": line.strip(), "confidence": 0.6}
                break
        
        print(f"[DocVault] Basic extraction completed, found {len(extracted)} fields")
        return extracted

    def _normalize_fields(self, extracted: dict) -> dict:
        """Normalize formats for names, dates, phones, etc."""
        normalized = {}
        
        # Titles to strip from names
        titles = r"^(Mr\.|Mrs\.|Dr\.|Shri|Smt\.|Ms\.|Miss)\s*"
        
        for k, v_obj in extracted.items():
            if not isinstance(v_obj, dict) or "value" not in v_obj:
                continue
                
            val = str(v_obj["value"]).strip()
            if not val:
                continue
                
            # Name normalization
            if "name" in k.lower():
                val = re.sub(titles, "", val, flags=re.IGNORECASE).title()
                
            # Date normalization (very basic attempt to reach YYYY-MM-DD)
            if "dob" in k.lower() or "date" in k.lower():
                # Extract digits
                parts = re.split(r'[-/.]', val)
                if len(parts) == 3:
                    # heuristic: if part[2] is 4 digits, it's DD-MM-YYYY
                    if len(parts[2]) == 4:
                        val = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    elif len(parts[0]) == 4:
                        val = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                        
            # Phone normalization
            if "phone" in k.lower() or "mobile" in k.lower():
                digits = re.sub(r'\D', '', val)
                if len(digits) >= 10:
                    val = digits[-10:]
                    
            # Pincode
            if "pin" in k.lower():
                digits = re.sub(r'\D', '', val)
                if len(digits) == 6:
                    val = digits
                    
            # Aadhaar last 4
            if "aadhaar" in k.lower():
                digits = re.sub(r'\D', '', val)
                if len(digits) >= 4:
                    val = digits[-4:]

            normalized[k] = val
            
        return normalized

    async def _cross_validate_with_db(self, user_id: str, new_fields: dict) -> List[Conflict]:
        """Fetch existing profile and run _cross_validate_documents."""
        db = await get_db()
        if db is None:
            return []
            
        doc = await db.user_profiles.find_one({"user_id": user_id})
        if not doc:
            return []
            
        # We need to decrypt the profile to compare
        from utils.encryption import decrypt_profile
        profile = decrypt_profile(doc, user_id)
        
        return self._cross_validate_documents(profile, new_fields)

    def _cross_validate_documents(self, existing_profile: dict, new_doc_fields: dict) -> List[Conflict]:
        """Flag conflicts using Levenshtein similarity."""
        conflicts = []
        
        # Flatten existing profile for easier checking
        flat_profile = {}
        for section in ["basic_info", "contact", "identity", "education"]:
            if section in existing_profile and isinstance(existing_profile[section], dict):
                for k, v in existing_profile[section].items():
                    if v:
                        flat_profile[k] = str(v).lower()
        
        for k, new_val in new_doc_fields.items():
            new_val_lower = str(new_val).lower()
            
            # Find matching key in profile (heuristic)
            prof_key = None
            if k in flat_profile:
                prof_key = k
            elif "name" in k and "full_name" in flat_profile:
                prof_key = "full_name"
            elif "aadhaar" in k and "aadhaar_last4" in flat_profile:
                prof_key = "aadhaar_last4"
            elif "pan" in k and "pan_number" in flat_profile:
                prof_key = "pan_number"
                
            if prof_key:
                existing_val = flat_profile[prof_key]
                
                # Direct match
                if existing_val == new_val_lower:
                    continue
                    
                # Levenshtein similarity
                # ratio is 0 to 100
                similarity = fuzz.ratio(existing_val, new_val_lower) / 100.0
                
                if "name" in k and similarity < 0.85:
                    conflicts.append(Conflict(
                        field=k,
                        existing_value=existing_val.title(),
                        new_value=str(new_val).title(),
                        similarity=similarity,
                        message="Name spelling differs significantly."
                    ))
                elif "dob" in k and similarity < 1.0:
                    conflicts.append(Conflict(
                        field=k,
                        existing_value=existing_val,
                        new_value=str(new_val),
                        similarity=similarity,
                        message="Date of birth mismatch."
                    ))
                elif similarity < 0.70:  # General catch-all
                     conflicts.append(Conflict(
                        field=k,
                        existing_value=existing_val,
                        new_value=str(new_val),
                        similarity=similarity,
                        message="Field mismatch detected."
                    ))
                     
        return conflicts
