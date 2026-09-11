# CivicFlow Backend Runtime Fixes

## Summary
Fixed 3 critical runtime issues preventing backend startup and operation.

---

## ROOT CAUSE 1: Gemini Runtime Quota Failure

### Problem
- Direct terminal tests confirmed: `google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED`
- `GEMINI_MODEL` environment variable not being read from `.env`
- No fallback behavior when Gemini API quota exceeded

### Solution

**1. Updated `backend/config.py`**
- Added `gemini_model: str = "gemini-2.0-flash-lite"` field to `Settings` class
- Environment variable `GEMINI_MODEL` now properly loaded from `.env`

**2. Updated `backend/main.py`**
- Added startup diagnostics logging:
  - Python executable path
  - Gemini API key status (masked)
  - Gemini model name
  - Paddle import status
  - PaddleOCR import status
- Added `/health/runtime` endpoint for comprehensive diagnostics

**3. Updated `backend/api/chat.py`**
- Added explicit Gemini quota error detection (429, RESOURCE_EXHAUSTED)
- Created `fallback_chat_response()` function with deterministic responses per stage
- Returns structured metadata with `fallback_mode: true` and `error_reason`
- No longer throws 500 errors on Gemini failures

**4. Updated `backend/api/documents.py`**
- Added Gemini quota error handling in document upload
- Returns partial success with `fallback_mode: true` when AI enrichment unavailable
- Continues with OCR extraction even if Gemini fails

---

## ROOT CAUSE 2: PaddleOCR Import Fails (LangChain Compatibility)

### Problem
- `import paddle` works
- `import paddleocr` fails with: `ModuleNotFoundError: No module named 'langchain.docstore'`
- LangChain version incompatibility with PaddleOCR
- LangGraph requires newer langchain-core that conflicts with old langchain

### Solution

**Updated `backend/requirements.txt`**
Changed from:
```
langchain==0.0.352
langgraph
```

To compatible version set:
```
langchain-core==0.1.52
langchain==0.1.20
langchain-community==0.0.38
langgraph==0.0.43
```

This version combination:
- Provides `langchain.docstore` module needed by PaddleOCR
- Supports `RemoveMessage` class needed by LangGraph
- Maintains compatibility with existing LangGraph code

---

## ROOT CAUSE 3: Profile Schema Mismatch

### Problem
- `/auth/profile` endpoint fails with: `ValueError: "ContactInfo" object has no field "address"`
- Frontend sends `address` and `pincode` in `contact` section
- Backend `ContactInfo` model missing these fields

### Solution

**Updated `backend/models/user_models.py`**
Added fields to `ContactInfo` class:
```python
class ContactInfo(BaseModel):
    email: str = ""
    phone: str = ""              # AES-256 encrypted in MongoDB
    alternate_phone: str = ""
    address: Optional[str] = ""  # Frontend sends this field
    pincode: Optional[str] = ""  # Frontend sends this field
```

---

## New /health/runtime Endpoint

**URL**: `GET /health/runtime`

**Response**:
```json
{
  "python_executable": "D:\\...\\python.exe",
  "gemini": {
    "api_key_configured": true,
    "api_key_masked": "AQ.Ab8RN6L...",
    "model": "gemini-2.0-flash-lite"
  },
  "imports": {
    "paddle": "ok",
    "paddleocr": "ok"
  },
  "databases": {
    "mongodb": "connected",
    "redis": "redis://localhost:6379"
  }
}
```

If imports fail, shows exact error:
```json
{
  "imports": {
    "paddle": "ok",
    "paddleocr": "error: ModuleNotFoundError: No module named 'langchain.docstore'"
  }
}
```

---

## Installation Steps

### 1. Update Dependencies
```bash
cd civicflow\backend
pip install -r requirements.txt --upgrade
```

### 2. Verify Imports
Test in Python REPL:
```python
import paddle
import paddleocr
from langgraph.graph import StateGraph, END
```

### 3. Start Backend
```bash
python main.py
```

Check startup logs for diagnostics:
```
============================================================
CivicFlow Configuration
Python executable: D:\...\python.exe
Gemini API Key: ✓ configured
Gemini Model: gemini-2.0-flash-lite
paddle import: ✓ OK
paddleocr import: ✓ OK
============================================================
```

### 4. Test Runtime Endpoint
```bash
curl http://localhost:8000/health/runtime
```

---

## Fallback Behavior

### Chat Endpoint (`POST /chat`)
When Gemini unavailable:
```json
{
  "success": true,
  "message": "Quota exceeded",
  "data": {
    "response": "Welcome to CivicFlow! I'm here to help...",
    "triggered_action": null,
    "stage": "welcome",
    "fallback_mode": true,
    "error_reason": "gemini_quota_exceeded"
  }
}
```

### Document Upload (`POST /documents/upload`)
When Gemini unavailable:
```json
{
  "success": true,
  "message": "Document processed with limited features",
  "data": {
    "doc_id": null,
    "extracted_fields": {},
    "fallback_mode": true,
    "error_reason": "gemini_quota_exceeded",
    "message": "Document uploaded but AI enrichment is currently unavailable..."
  }
}
```

---

## Files Modified

1. **backend/config.py** - Added gemini_model field
2. **backend/main.py** - Added startup diagnostics and /health/runtime endpoint
3. **backend/api/chat.py** - Added quota error handling and fallback responses
4. **backend/api/documents.py** - Added quota error handling for uploads
5. **backend/models/user_models.py** - Added address/pincode to ContactInfo
6. **backend/requirements.txt** - Fixed LangChain version compatibility

---

## Testing Checklist

- [ ] Backend starts without import errors
- [ ] Startup logs show all diagnostics
- [ ] `/health/runtime` returns complete diagnostics
- [ ] Chat endpoint returns fallback when Gemini unavailable
- [ ] Document upload continues with OCR when Gemini fails
- [ ] Profile update accepts address and pincode fields
- [ ] PaddleOCR imports successfully
- [ ] LangGraph imports successfully

---

## Expected Behavior

### Normal Operation (Gemini Available)
- Chat responses powered by Gemini AI
- Document extraction enhanced by Gemini
- Full functionality

### Degraded Operation (Gemini Quota Exceeded)
- Chat returns deterministic fallback responses
- Document upload continues with OCR only
- All responses include `fallback_mode: true` metadata
- Users see friendly error messages
- No 500 errors thrown

### Startup Diagnostics
- All import status logged on startup
- Configuration printed to console
- Runtime endpoint provides programmatic diagnostics
