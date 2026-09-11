# CivicFlow

> AI-powered government form filling for Indian citizens. Upload your Aadhaar, PAN, or Passport — let Sahayak guide you through any government portal automatically.

---

## Architecture

```mermaid
flowchart TB
    subgraph Frontend["Frontend (SPA — index.html)"]
        UI["Hash Router\n#login · #dashboard\n#form-search · #execution"]
        Sahayak["Sahayak Chat Widget\n(Counsellor Agent)"]
        WS_Client["WebSocket Client\nReal-time progress"]
    end

    subgraph Backend["Backend (FastAPI — port 8000)"]
        Auth["POST /auth/login\nPOST /auth/register"]
        Docs["POST /documents/upload\n(DocVault → PaddleOCR)"]
        Search["POST /search/form\n(FormSearch → Gemini)"]
        Chat["POST /chat\nWS /ws/{session_id}"]
        Sessions["GET /sessions\n/start · /execute"]
        Telegram_API["POST /telegram/webhook\nGET /telegram/link-token"]
    end

    subgraph Agents["Agents"]
        DocVault["DocVault\nPDF→Image→OCR→Encrypt"]
        Counsellor["CounsellorAgent\nSahayak · Gemini 2.0"]
        FormSearch["FormSearchAgent\nGemini + Portal Knowledge"]
        WebPilot["WebPilot\nAnti-paste · CAPTCHA"]
        ScriptGen["ScriptGen\nPlaywright script generator"]
        Executor["Executor\nSubprocess runner"]
        Notifier["TelegramNotifier\npython-telegram-bot"]
    end

    subgraph Storage["Storage"]
        MongoDB[("MongoDB\nusers · profiles\ndocuments · sessions")]
        Redis[("Redis\nSession coordination\nRate limiting")]
        Uploads["./uploads/\ndocs · scripts · screenshots"]
    end

    subgraph External["External"]
        Gemini["Google Gemini 2.0 Flash\nOCR · LLM · Vision"]
        TelegramAPI["Telegram Bot API"]
        GovPortal["Government Portals\npassportindia.gov.in etc."]
    end

    UI -->|HTTP + JWT| Auth & Docs & Search & Chat & Sessions
    UI -->|WebSocket| WS_Client
    WS_Client -->|ws:///ws/{id}| Chat

    Sessions --> ScriptGen --> Executor
    Executor -->|Playwright| WebPilot
    WebPilot -->|Browser automation| GovPortal
    Executor -->|Events| WS_Client

    Docs --> DocVault --> Gemini
    Chat --> Counsellor --> Gemini
    Search --> FormSearch --> Gemini
    WebPilot --> Gemini

    Auth & Docs & Sessions --> MongoDB
    Executor --> Redis
    Notifier --> TelegramAPI
    Sessions --> Notifier

    DocVault --> Uploads
    Executor --> Uploads
```

---

## Quick Start

### 1. Clone & enter directory
```bash
git clone https://github.com/your-org/civicflow.git
cd civicflow
```

### 2. Configure environment
```bash
cp .env.example backend/.env
# Edit backend/.env — fill in GEMINI_API_KEY at minimum
```

### 3. Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```

### 4. Run the backend
```bash
uvicorn main:app --reload --port 8000
# Windows: python main.py  (required for Playwright subprocess on Windows)
```

### 5. Open the frontend
Open `frontend/index.html` in any browser (no build step needed).

### 6. (Optional) Start the mock portal for testing
```bash
python mock_portal/server.py
# Runs on http://localhost:5001
```

---

## Poppler Installation

`pdf2image` requires Poppler to convert PDFs to images.

### Windows
1. Download from: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to `C:\poppler\`
3. Add to `.env`:
   ```
   POPPLER_PATH=C:/poppler/Library/bin
   ```

### macOS
```bash
brew install poppler
# Leave POPPLER_PATH empty in .env
```

### Ubuntu / Debian
```bash
sudo apt install poppler-utils
# Leave POPPLER_PATH empty in .env
```

---

## Telegram Bot Setup

1. Open Telegram and search for **@BotFather**: https://t.me/BotFather
2. Send `/newbot` and follow the prompts
3. Copy the token and add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC-your-token-here
   TELEGRAM_BOT_USERNAME=YourBotName
   TELEGRAM_WEBHOOK_SECRET=any_random_string
   ```
4. To receive notifications, users must link their account:
   - In the CivicFlow app → Dashboard → **Link Telegram**
   - Copy the generated token and send to your bot: `/start YOUR_TOKEN`

---

## Demo Credentials

After running the seed script (`python scripts/seed_demo.py`):

| Field    | Value                 |
|----------|-----------------------|
| Email    | `demo@civicflow.in`  |
| Password | `Demo@1234`           |

The demo account includes a pre-filled profile (Aadhaar + PAN), one completed passport application, and one active session in the `paused_captcha` state.

---

## OS-Specific Setup Notes

### Windows
- Run `python main.py` instead of `uvicorn --reload` (Playwright requires `ProactorEventLoop`)
- Set `POPPLER_PATH` in `.env`
- Use `pip install python-magic-bin` (instead of `python-magic`) for file type detection

### macOS
```bash
brew install poppler
pip install -r requirements.txt
playwright install chromium
```

### Linux (Ubuntu/Debian)
```bash
sudo apt install poppler-utils libmagic1
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
```

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | — | Create account |
| POST | `/auth/login` | — | Login, get JWT |
| GET | `/auth/me` | ✓ | Current user + profile |
| POST | `/documents/upload` | ✓ | Upload + OCR document |
| GET | `/documents/{id}` | ✓ | Document detail |
| POST | `/documents/{id}/confirm` | ✓ | Link to profile |
| POST | `/search/form` | ✓ | LLM portal search |
| POST | `/search/verify` | ✓ | Verify URL is gov domain |
| POST | `/chat` | ✓ | Message Sahayak |
| WS | `/ws/{session_id}` | — | Live execution events |
| POST | `/start` | ✓ | Start scraping session |
| GET | `/sessions` | ✓ | List user sessions |
| GET | `/sessions/{id}` | ✓ | Session detail |
| POST | `/sessions/{id}/fill` | ✓ | Submit field values |
| POST | `/sessions/{id}/execute` | ✓ | Start Playwright automation |
| POST | `/sessions/{id}/resume` | ✓ | Resume after CAPTCHA |
| POST | `/sessions/{id}/otp` | ✓ | Submit OTP |
| POST | `/sessions/{id}/correct` | ✓ | Submit field correction |
| GET | `/telegram/link-token` | ✓ | Generate link token |
| POST | `/telegram/webhook` | — | Telegram Bot webhook |
| GET | `/health` | — | Service health check |

All authenticated endpoints require: `Authorization: Bearer <jwt_token>`

All responses follow the format:
```json
{ "success": true, "message": "...", "data": { ... } }
```

---

## Verification & Tests

### Check all services are configured
```bash
python scripts/verify_setup.py
```

### Seed demo data
```bash
python scripts/seed_demo.py
```

### Run end-to-end tests
```bash
# Requires backend + mock portal running
cd backend
pytest tests/test_e2e_full_flow.py -v
```

### Run all unit tests
```bash
cd backend
pytest tests/ -v
```

---

## Troubleshooting

### `playwright install` fails
```bash
pip install playwright
playwright install chromium
# Linux only:
playwright install-deps chromium
```

### `PaddleOCR` import error
```bash
pip install paddlepaddle paddleocr
# If still fails on Windows:
pip install paddlepaddle-gpu  # if CUDA available
```

### `ModuleNotFoundError: jose`
```bash
pip install python-jose[cryptography]
```

### MongoDB connection refused
- Ensure MongoDB is running: `mongod --dbpath ./data`
- Or use MongoDB Atlas: set `MONGODB_URI=mongodb+srv://...` in `.env`

### Telegram webhook not firing
- Use [ngrok](https://ngrok.com/) to expose localhost: `ngrok http 8000`
- Call `POST /telegram/setup-webhook` with your ngrok URL

### Windows: `OSError: [WinError 87]` during Playwright
- Make sure you're running `python main.py`, **not** `uvicorn --reload`
- `reload=True` forks processes incompatibly with Playwright on Windows

---

## Project Structure

```
civicflow/
├── backend/
│   ├── agents/
│   │   ├── analyst.py          # Form data analyst
│   │   ├── collector.py        # Data collection agent
│   │   ├── counsellor.py       # Sahayak LLM agent
│   │   ├── doc_vault.py        # Document OCR pipeline
│   │   ├── executor.py         # Playwright script runner
│   │   ├── form_finder.py      # Form discovery
│   │   ├── form_search.py      # LLM portal search
│   │   ├── notifier.py         # Telegram notifier
│   │   ├── scraper.py          # Form scraper
│   │   ├── scriptgen.py        # Playwright script generator
│   │   └── web_pilot.py        # Anti-paste + CAPTCHA agent
│   ├── api/
│   │   ├── auth.py             # /auth routes
│   │   ├── chat.py             # /chat + WebSocket
│   │   ├── documents.py        # /documents routes
│   │   ├── routes.py           # /start /sessions legacy routes
│   │   ├── search.py           # /search routes
│   │   ├── telegram.py         # /telegram routes
│   │   └── websocket.py        # WebSocket handler
│   ├── db/
│   │   └── mongo.py            # Async Motor client
│   ├── models/
│   │   ├── chat_models.py
│   │   ├── form_models.py
│   │   └── session_models.py
│   ├── tests/
│   │   └── test_e2e_full_flow.py
│   ├── utils/
│   │   ├── auth.py             # JWT + password utils
│   │   ├── encryption.py       # AES-256 field encryption
│   │   ├── ocr.py
│   │   └── storage.py
│   ├── config.py
│   ├── main.py                 # FastAPI app entry point
│   └── requirements.txt
├── frontend/
│   ├── css/
│   │   └── styles.css          # Sage-green glassmorphism design
│   ├── js/
│   │   └── app.js              # SPA router + all view logic
│   └── index.html              # Single HTML shell
├── mock_portal/
│   └── server.py               # Flask test portal (port 5001)
├── scripts/
│   ├── seed_demo.py            # Seed demo data into MongoDB
│   └── verify_setup.py         # Verify all services + config
├── .env.example
├── docker-compose.yml
└── README.md
```
