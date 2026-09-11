# PaddleOCR Initialization Fix

## Problem
PaddleOCR initialization crashed the entire backend:
```
ValueError: Unknown argument: show_log
```

The `show_log=False` parameter is not supported in current PaddleOCR versions.

## Solution

### 1. Fixed DocVaultAgent Initialization (`backend/agents/doc_vault.py`)

**Before:**
```python
def __init__(self):
    if PADDLE_AVAILABLE:
        self.ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    else:
        self.ocr = None
```

**After:**
```python
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
```

**Changes:**
- Removed unsupported `show_log=False` parameter
- Added version-safe fallback: first try with `use_angle_cls=True`, then without
- Logs success/failure with clear status indicators
- Never crashes, sets `self.ocr = None` on failure

### 2. Enhanced OCR Execution Safety (`backend/agents/doc_vault.py`)

**Added try-catch to `_run_paddle_ocr()`:**
```python
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
        # ... process blocks ...
        return blocks
    except Exception as e:
        print(f"[DocVault] ✗ PaddleOCR execution failed: {type(e).__name__}: {e}")
        return []
```

**Changes:**
- Wrapped OCR execution in try-catch
- Returns empty list on failure instead of crashing
- Logs exact error type and message

### 3. API-Level Fallback (`backend/api/documents.py`)

**Updated global state tracking:**
```python
_doc_vault: Optional[DocVaultAgent] = None
_doc_vault_error: Optional[str] = None
```

**Updated `get_doc_vault()` function:**
```python
def get_doc_vault() -> Optional[DocVaultAgent]:
    global _doc_vault, _doc_vault_error
    if _doc_vault is None and _doc_vault_error is None:
        try:
            _doc_vault = DocVaultAgent()
        except Exception as e:
            import logging
            logger = logging.getLogger("civicflow.documents")
            _doc_vault_error = f"{type(e).__name__}: {str(e)}"
            logger.error("DocVaultAgent initialization failed: %s", _doc_vault_error)
            logger.warning("Document processing will use fallback mode")
            _doc_vault = None
    return _doc_vault
```

**Changes:**
- Returns `Optional[DocVaultAgent]` instead of `DocVaultAgent`
- Caches initialization errors in `_doc_vault_error`
- Returns `None` on failure instead of raising exception
- Never crashes the API

**Updated `upload_document()` endpoint:**
```python
@router.post("/upload")
async def upload_document(...):
    agent = get_doc_vault()
    
    # Check if DocVault is available
    if agent is None:
        global _doc_vault_error
        return ok("Document upload unavailable", data={
            "doc_id": None,
            "extracted_fields": {},
            "fallback_mode": True,
            "error_reason": "docvault_unavailable",
            "message": f"Document processing is currently unavailable. Error: {_doc_vault_error or 'Unknown'}"
        })
    
    # Continue with normal processing...
```

**Changes:**
- Checks if DocVault initialization succeeded
- Returns structured fallback response with error details
- Never returns 500 error for initialization failures

## Files Modified

1. **backend/agents/doc_vault.py**
   - `__init__()`: Removed `show_log=False`, added version-safe fallback
   - `_run_paddle_ocr()`: Added try-catch wrapper

2. **backend/api/documents.py**
   - Added `_doc_vault_error` global variable
   - Updated `get_doc_vault()` to cache errors and return Optional
   - Updated `upload_document()` to check for DocVault availability

## Expected Behavior

### Scenario 1: PaddleOCR Loads Successfully
```
[DocVault] ✓ PaddleOCR initialized successfully
```
- Document upload works normally
- OCR extraction runs
- Gemini enrichment runs

### Scenario 2: PaddleOCR Needs Fallback Mode
```
[DocVault] ✓ PaddleOCR initialized (fallback mode, no angle classification)
```
- Document upload works
- OCR runs without angle classification
- Slightly reduced accuracy for rotated text

### Scenario 3: PaddleOCR Fails Completely
```
[DocVault] ✗ PaddleOCR initialization failed: ValueError: Unknown argument: show_log
```
- API continues running
- Document upload endpoint returns:
```json
{
  "success": true,
  "message": "Document upload unavailable",
  "data": {
    "doc_id": null,
    "extracted_fields": {},
    "fallback_mode": true,
    "error_reason": "docvault_unavailable",
    "message": "Document processing is currently unavailable. Error: ValueError: Unknown argument: show_log"
  }
}
```

### Scenario 4: OCR Execution Fails
```
[DocVault] ✗ PaddleOCR execution failed: RuntimeError: Some runtime error
```
- Document processing continues
- Returns empty OCR blocks
- Gemini can still extract from image if available

## Testing

### 1. Test Startup
```bash
python main.py
```
Look for `[DocVault] ✓` messages in logs.

### 2. Test Document Upload
```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.pdf" \
  -F "doc_type=aadhaar"
```

### 3. Check Fallback Response
If PaddleOCR unavailable, response includes:
- `"fallback_mode": true`
- `"error_reason": "docvault_unavailable"`
- Detailed error message

## Impact

- **Backend never crashes** due to PaddleOCR issues
- **Graceful degradation** when OCR unavailable
- **Clear error messages** for debugging
- **Structured fallback responses** for frontend handling
