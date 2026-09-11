"""
CivicFlow OCR Microservice
===========================
Lightweight CPU-only OCR service using PaddleOCR.
Runs separately from main backend to isolate dependencies.
"""
import os
import io
import logging
from typing import List, Dict, Optional
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
import magic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ocr_service")

# Try to import PaddleOCR
try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
    logger.info("✓ PaddleOCR import successful")
except Exception as e:
    PADDLE_AVAILABLE = False
    logger.error("✗ PaddleOCR import failed: %s", str(e))

# Try to import PDF processing
try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
    logger.info("✓ pdf2image import successful")
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logger.warning("⚠ pdf2image not available - PDF processing disabled")

app = FastAPI(
    title="CivicFlow OCR Service",
    description="Privacy-first CPU-only OCR microservice",
    version="1.0.0"
)

# Global OCR engine instance
_ocr_engine: Optional[PaddleOCR] = None

def get_ocr_engine() -> Optional[PaddleOCR]:
    """Lazy initialization of PaddleOCR engine."""
    global _ocr_engine
    
    if _ocr_engine is not None:
        return _ocr_engine
    
    if not PADDLE_AVAILABLE:
        logger.error("PaddleOCR not available")
        return None
    
    try:
        # CPU-only configuration with lightweight model
        logger.info("Initializing PaddleOCR (CPU mode, lightweight)...")
        _ocr_engine = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            use_gpu=False,  # Force CPU mode
            show_log=False
        )
        logger.info("✓ PaddleOCR initialized successfully")
        return _ocr_engine
    except TypeError:
        # Fallback: show_log parameter not supported in some versions
        try:
            logger.info("Retrying PaddleOCR init without show_log parameter...")
            _ocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang='en',
                use_gpu=False
            )
            logger.info("✓ PaddleOCR initialized (fallback mode)")
            return _ocr_engine
        except Exception as e2:
            logger.error("✗ PaddleOCR initialization failed: %s", str(e2))
            return None
    except Exception as e:
        logger.error("✗ PaddleOCR initialization failed: %s", str(e))
        return None


def process_image_ocr(image: Image.Image, page_num: int = 1) -> Dict:
    """Run OCR on a PIL Image and return structured results."""
    ocr = get_ocr_engine()
    
    if ocr is None:
        return {
            "page": page_num,
            "text": "",
            "lines": [],
            "error": "OCR engine unavailable"
        }
    
    try:
        import numpy as np
        img_np = np.array(image.convert("RGB"))
        
        result = ocr.ocr(img_np, cls=True)
        
        if not result or not result[0]:
            return {
                "page": page_num,
                "text": "",
                "lines": []
            }
        
        lines = []
        for line in result[0]:
            text = line[1][0]
            confidence = float(line[1][1])
            
            if confidence >= 0.5:  # Lower threshold for better recall
                lines.append(text)
        
        full_text = "\n".join(lines)
        
        return {
            "page": page_num,
            "text": full_text,
            "lines": lines
        }
    
    except Exception as e:
        logger.error("OCR processing error: %s", str(e))
        return {
            "page": page_num,
            "text": "",
            "lines": [],
            "error": str(e)
        }


def convert_pdf_to_images(pdf_bytes: bytes, max_pages: int = 3) -> List[Image.Image]:
    """Convert PDF to list of PIL Images (first N pages only)."""
    if not PDF2IMAGE_AVAILABLE:
        raise RuntimeError("pdf2image not available - install with: pip install pdf2image")
    
    poppler_path = os.getenv("POPPLER_PATH")
    
    try:
        if poppler_path and Path(poppler_path).exists():
            images = convert_from_bytes(
                pdf_bytes,
                dpi=200,
                poppler_path=poppler_path,
                first_page=1,
                last_page=max_pages
            )
        else:
            images = convert_from_bytes(
                pdf_bytes,
                dpi=200,
                first_page=1,
                last_page=max_pages
            )
        
        return images
    
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    ocr = get_ocr_engine()
    
    return {
        "status": "healthy",
        "service": "CivicFlow OCR Service",
        "version": "1.0.0",
        "ocr_engine": "paddleocr-cpu" if ocr else "unavailable",
        "pdf_support": PDF2IMAGE_AVAILABLE,
        "mode": "cpu-local"
    }


@app.post("/ocr")
async def ocr_document(file: UploadFile = File(...)):
    """
    OCR endpoint for images and PDFs.
    
    Accepts:
    - Images: JPEG, PNG, WebP, TIFF
    - PDFs (if pdf2image available)
    
    Returns structured OCR results.
    """
    try:
        # Read file bytes
        file_bytes = await file.read()
        
        # Detect MIME type
        try:
            mime_type = magic.from_buffer(file_bytes, mime=True)
        except Exception:
            mime_type = file.content_type or "application/octet-stream"
        
        logger.info("Processing file: %s (type: %s, size: %d bytes)", 
                   file.filename, mime_type, len(file_bytes))
        
        pages_data = []
        
        # Handle PDF
        if mime_type == "application/pdf":
            if not PDF2IMAGE_AVAILABLE:
                raise HTTPException(
                    status_code=400,
                    detail="PDF processing not available. Install pdf2image and poppler."
                )
            
            try:
                images = convert_pdf_to_images(file_bytes, max_pages=3)
                logger.info("Converted PDF to %d images", len(images))
                
                for idx, img in enumerate(images, start=1):
                    page_result = process_image_ocr(img, page_num=idx)
                    pages_data.append(page_result)
            
            except Exception as e:
                logger.error("PDF processing failed: %s", str(e))
                raise HTTPException(status_code=500, detail=f"PDF processing failed: {str(e)}")
        
        # Handle images
        elif mime_type.startswith("image/"):
            try:
                image = Image.open(io.BytesIO(file_bytes))
                page_result = process_image_ocr(image, page_num=1)
                pages_data.append(page_result)
            
            except Exception as e:
                logger.error("Image processing failed: %s", str(e))
                raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {mime_type}"
            )
        
        # Build response
        response = {
            "success": True,
            "engine": "paddleocr-cpu",
            "pages": pages_data,
            "metadata": {
                "filename": file.filename,
                "content_type": mime_type,
                "processing_mode": "cpu-local",
                "total_pages": len(pages_data)
            }
        }
        
        logger.info("OCR completed: %d pages processed", len(pages_data))
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """Warm up OCR engine on startup."""
    logger.info("=" * 60)
    logger.info("CivicFlow OCR Service starting...")
    logger.info("Mode: CPU-only, privacy-first")
    logger.info("PaddleOCR: %s", "available" if PADDLE_AVAILABLE else "unavailable")
    logger.info("PDF support: %s", "available" if PDF2IMAGE_AVAILABLE else "unavailable")
    
    # Warm up engine
    ocr = get_ocr_engine()
    if ocr:
        logger.info("OCR engine ready")
    else:
        logger.warning("OCR engine failed to initialize - service will return errors")
    
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("OCR_PORT", "8081"))
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
