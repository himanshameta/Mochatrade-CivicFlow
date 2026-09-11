"""
CivicFlow — DocVault Agent
==========================
Handles all document processing.
Pipeline: Upload → Validate → Convert → OCR → Extract → Normalise → Cross-Validate → Encrypt → Store
"""
import os
import io
import json
import base64
import uuid
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

import magic
from PIL import Image
from rapidfuzz import fuzz

try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    import logging as paddle_logging
    # Suppress PaddleOCR verbose logs
    paddle_logging.getLogger("ppocr").setLevel(paddle_logging.ERROR)
    PADDLE_AVAILABLE = True
except Exception:
    PADDLE_AVAILABLE = False
    PaddleOCR = None

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.document_models import OCRBlock, DocumentResult, Conflict
from models.user_models import DocumentDB, UserProfileData, BasicInfo, IdentityInfo
from db.mongo import get_db
from utils.encryption import encrypt_field

class DocVaultAgent:
    SUPPORTED_TYPES = [
      "image/jpeg", "image/png", "image/webp",
      "application/pdf", "image/tiff"
    ]
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

    def __init__(self):
        if PADDLE_AVAILABLE:
            try:
                # Try modern PaddleOCR initialization (no show_log parameter)
                self.ocr = PaddleOCR(use_angle_cls=True, lang='en')
                print("[DocVault] ✓ PaddleOCR initialized successfully")
            except Exception as e1:
                # Fallback: try without use_angle_cls
                try:
                    self.ocr = PaddleOCR(lang='en')
                    print("[DocVault] ✓ PaddleOCR initialized (fallback mode, no angle classification)")
                except Exception as e2:
                    self.ocr = None
                    print(f"[DocVault] ✗ PaddleOCR initialization failed: {type(e2).__name__}: {e2}")
        else:
            self.ocr = None
            print("[DocVault] ⚠ PaddleOCR not available. Run: pip install paddleocr paddlepaddle")
        
        self.uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
        os.makedirs(self.uploads_dir, exist_ok=True)

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

        # 3. Convert to images
        try:
            if mime_type == "application/pdf":
                images = self._convert_pdf_to_images(file_bytes)
            else:
                images = [Image.open(io.BytesIO(file_bytes))]
            
            # Combine OCR blocks from all pages
            all_ocr_blocks = []
            for img in images:
                blocks = self._run_paddle_ocr(img)
                all_ocr_blocks.extend(blocks)
                
            raw_text = "\n".join([b.text for b in all_ocr_blocks])

            # We'll use the first page image for Gemini to extract context visually
            primary_image = images[0]

            # 4. Extract structured fields
            extracted = self._extract_structured_fields(all_ocr_blocks, primary_image, doc_type)
            
            # 5. Normalize
            normalized = self._normalize_fields(extracted)

            # 6. Cross-validate with existing profile (if available)
            conflicts = await self._cross_validate_with_db(user_id, normalized)

            # Update DB with success
            if db is not None:
                await db.documents.update_one(
                    {"doc_id": doc_id},
                    {"$set": {
                        "ocr_status": "done",
                        "ocr_results": normalized
                    }}
                )

            return DocumentResult(
                doc_id=doc_id,
                doc_type=doc_type,
                original_filename=filename,
                mime_type=mime_type,
                extracted_fields=normalized,
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

    def _convert_pdf_to_images(self, pdf_bytes: bytes) -> List[Image.Image]:
        """Convert PDF to PIL Images."""
        if not PDF2IMAGE_AVAILABLE:
            raise RuntimeError("pdf2image package is missing.")
            
        poppler_path = os.getenv("POPPLER_PATH")
        try:
            if poppler_path:
                images = convert_from_bytes(pdf_bytes, dpi=200, poppler_path=poppler_path)
            else:
                images = convert_from_bytes(pdf_bytes, dpi=200)
            return images
        except Exception as e:
            raise RuntimeError(f"Failed to convert PDF. Ensure Poppler is installed. Error: {e}")

    def _run_paddle_ocr(self, image: Image.Image) -> List[OCRBlock]:
        """Run PaddleOCR and return sorted, filtered blocks."""
        if not self.ocr:
            print("[DocVault] ⚠ OCR not available, returning empty blocks")
            return []

        try:
            # Convert PIL to numpy for PaddleOCR
            import numpy as np
            img_np = np.array(image.convert("RGB"))
            
            result = self.ocr.ocr(img_np, cls=True)
            blocks = []
            
            if not result or not result[0]:
                return blocks

            for line in result[0]:
                bbox = line[0]
                text = line[1][0]
                confidence = float(line[1][1])
                
                if confidence >= 0.6:
                    # Calculate center_y for top-to-bottom sorting
                    center_y = sum([point[1] for point in bbox]) / 4.0
                    blocks.append(OCRBlock(
                        text=text,
                        confidence=confidence,
                        bbox=bbox,
                        center_y=center_y
                    ))
                    
            # Sort blocks vertically (top to bottom)
            blocks.sort(key=lambda b: b.center_y)
            return blocks
        except Exception as e:
            print(f"[DocVault] ✗ PaddleOCR execution failed: {type(e).__name__}: {e}")
            return []

    def _extract_structured_fields(
        self, 
        ocr_blocks: List[OCRBlock], 
        image: Image.Image,
        doc_type: str
    ) -> dict:
        """Extract structured fields from OCR text only (no LLM enrichment)."""
        
        # Prepare the OCR text
        ocr_text = "\n".join([f"{b.text}" for b in ocr_blocks])
        
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
        
        print(f"[DocVault] Basic extraction completed (no LLM), found {len(extracted)} fields")
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
