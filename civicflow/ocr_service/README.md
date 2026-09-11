# CivicFlow OCR Microservice

Privacy-first, CPU-only OCR service for document processing.

## Architecture

This service runs **separately** from the main CivicFlow backend to:
- Isolate heavy OCR dependencies
- Prevent dependency conflicts
- Enable independent scaling
- Keep documents on-premises (never sent to third-party APIs)

## Features

- ✅ CPU-only processing (no GPU required)
- ✅ Privacy-first (all processing local)
- ✅ Supports images (JPEG, PNG, WebP, TIFF)
- ✅ Supports PDFs (first 3 pages)
- ✅ Structured JSON output
- ✅ Health check endpoint
- ✅ Graceful error handling

## Installation

### Option 1: Local Development (Recommended for Windows)

1. **Create isolated virtual environment:**
```powershell
cd civicflow\ocr_service
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. **Install dependencies:**
```powershell
pip install -r requirements.txt
```

3. **Configure (optional):**
```powershell
copy .env.example .env
# Edit .env if needed (e.g., POPPLER_PATH for PDF support)
```

4. **Run the service:**
```powershell
python app.py
```

Service will start on `http://localhost:8081`

### Option 2: Docker

```bash
cd civicflow/ocr_service
docker build -t civicflow-ocr .
docker run -p 8081:8081 civicflow-ocr
```

## API Endpoints

### Health Check
```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "CivicFlow OCR Service",
  "version": "1.0.0",
  "ocr_engine": "paddleocr-cpu",
  "pdf_support": true,
  "mode": "cpu-local"
}
```

### OCR Processing
```
POST /ocr
Content-Type: multipart/form-data
```

**Request:**
```bash
curl -X POST http://localhost:8081/ocr \
  -F "file=@document.jpg"
```

**Response:**
```json
{
  "success": true,
  "engine": "paddleocr-cpu",
  "pages": [
    {
      "page": 1,
      "text": "Full extracted text here...",
      "lines": ["Line 1", "Line 2", "Line 3"]
    }
  ],
  "metadata": {
    "filename": "document.jpg",
    "content_type": "image/jpeg",
    "processing_mode": "cpu-local",
    "total_pages": 1
  }
}
```

## Integration with Main Backend

The main CivicFlow backend calls this service via HTTP:

```python
import httpx

async def get_ocr_results(file_bytes: bytes, filename: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8081/ocr",
            files={"file": (filename, file_bytes)}
        )
        return response.json()
```

## Performance

- **Image processing:** ~2-5 seconds per page (CPU)
- **PDF processing:** ~3-8 seconds per page (CPU)
- **Memory usage:** ~500MB-1GB during processing
- **Max file size:** 10MB (configurable)

## Troubleshooting

### PaddleOCR Import Error
```
RuntimeError: PDX has already been initialized
```
**Solution:** This is a known issue with PaddleOCR 3.x. Use version 2.7.3 as specified in requirements.txt.

### PDF Processing Fails
```
RuntimeError: PDF conversion failed
```
**Solution:** Install Poppler and set `POPPLER_PATH` in `.env`:
- Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases/
- Extract and set path to `bin` folder

### Out of Memory
**Solution:** Reduce PDF page limit in `convert_pdf_to_images()` or process smaller files.

## Why Separate Service?

1. **Dependency Isolation:** OCR libraries (PaddleOCR, PyTorch) have complex dependencies that conflict with other packages
2. **Resource Management:** OCR is CPU/memory intensive - can run on separate machine if needed
3. **Independent Updates:** Update OCR engine without touching main backend
4. **Fault Isolation:** OCR crashes don't bring down main backend
5. **Scalability:** Run multiple OCR workers behind load balancer

## Privacy & Security

- ✅ All processing happens locally (CPU-only)
- ✅ No data sent to external APIs
- ✅ Files not persisted after processing
- ✅ No logging of sensitive content
- ✅ Can run in air-gapped environments

## Development

To modify the OCR engine behavior:

1. Edit `get_ocr_engine()` in `app.py`
2. Adjust confidence thresholds in `process_image_ocr()`
3. Change PDF page limit in `convert_pdf_to_images()`

## Testing

```bash
# Health check
curl http://localhost:8081/health

# Test with image
curl -X POST http://localhost:8081/ocr \
  -F "file=@test.jpg"

# Test with PDF
curl -X POST http://localhost:8081/ocr \
  -F "file=@test.pdf"
```

## License

Part of CivicFlow project.
