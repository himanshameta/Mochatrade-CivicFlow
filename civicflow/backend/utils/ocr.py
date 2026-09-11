import os
from pathlib import Path
from typing import Optional
from PIL import Image
import pytesseract


async def extract_text_from_image(file_path: str) -> str:
    """
    Extract text from image file using Tesseract OCR.
    
    Args:
        file_path: Path to image file
        
    Returns:
        Extracted text
    """
    try:
        import pytesseract
        from PIL import Image
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except ImportError:
        print(f"[OCR] pytesseract not available — skipping OCR for {file_path}")
        return ""
    except Exception as e:
        if "tesseract" in str(e).lower() or "not installed" in str(e).lower():
            print(f"[OCR] Tesseract not installed — skipping OCR. Install from: https://github.com/UB-Mannheim/tesseract/wiki")
            return ""
        print(f"[OCR] Failed to extract text from image {file_path}: {e}")
        return ""


async def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from PDF file.
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Extracted text
    """
    try:
        # Use PyPDF2 for text extraction
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            return text.strip()
        except ImportError:
            print("[OCR] PyPDF2 not installed, cannot extract from PDF")
            return ""
            
    except Exception as e:
        print(f"[OCR] Failed to extract text from PDF {file_path}: {e}")
        return ""


async def extract_text_from_document(file_path: str) -> str:
    """
    Extract text from document (image or PDF).
    Automatically detects file type by extension.
    
    Args:
        file_path: Path to document file
        
    Returns:
        Extracted text
    """
    file_ext = Path(file_path).suffix.lower()
    
    # Image formats
    if file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif']:
        return await extract_text_from_image(file_path)
    
    # PDF format
    elif file_ext == '.pdf':
        return await extract_text_from_pdf(file_path)
    
    # Text format (no OCR needed)
    elif file_ext in ['.txt', '.text']:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read().strip()
        except Exception as e:
            print(f"[OCR] Failed to read text file {file_path}: {e}")
            return ""
    
    else:
        print(f"[OCR] Unsupported file format: {file_ext}")
        return ""


if __name__ == "__main__":
    import asyncio
    
    async def test_ocr():
        print("=" * 80)
        print("Testing OCR Utility")
        print("=" * 80)
        
        # Create test text file
        test_file = Path("test_document.txt")
        with open(test_file, "w") as f:
            f.write("John Smith\nDate of Birth: 01/15/1990\nEmail: john@example.com")
        
        print("\n[Test] Extracting text from .txt file")
        text = await extract_text_from_document(str(test_file))
        print(f"Extracted text:\n{text}")
        
        # Cleanup
        test_file.unlink()
        
        print("\n" + "=" * 80)
        print("OCR test complete!")
        print("=" * 80)
    
    asyncio.run(test_ocr())
