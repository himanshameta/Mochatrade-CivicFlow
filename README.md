<div align="center">

  <h1>CivicFlow</h1>
  <p><strong>Private AI-Assisted Form Automation</strong></p>
  <p><em>Built by <b>Team Tensors</b> for the <b>Faraway Hackathon 2026</b></em></p>
</div>

***

## Overview

Government and institutional portals are often complex, repetitive, and frustrating to navigate. People spend a large amount of time re-entering the same information and repeatedly uploading the same documents across different services.

**CivicFlow** is a privacy-first, intelligent form automation platform that acts as a personal digital assistant. Users securely store their core profile and documents once, and CivicFlow helps scrape forms, map saved data to fields, request final user review, and execute submissions with human-in-the-loop support for CAPTCHA and OTP steps.

## Key Features

- **Privacy-First Document Vault (DocVault):** Upload Aadhaar, PAN, passports, resumes, and other documents. CivicFlow uses OCR and vision models to extract structured data and store it securely.
- **Intelligent Form Execution (WebPilot):** Uses Playwright and LLM-assisted planning to understand complex forms, generate automation steps dynamically, and handle real-world field behavior.
- **Human-in-the-Loop Interventions:** If CivicFlow encounters a CAPTCHA, OTP, or another manual checkpoint, execution pauses and resumes after user action.
- **AI Counsellor (Sahayak):** An embedded assistant that helps users understand form requirements and decide which profile data or documents to use.
- **Custom Design System:** A premium dark-mode-first interface based on the “Bitcoin DeFi” visual language, focused on trust, clarity, and technical precision.

## Technology Stack

### Frontend

- React 18
- Vite 5
- React Router DOM
- Custom CSS design system

### Backend and Automation

- Python 3.10+
- FastAPI
- Playwright
- WebSockets for real-time execution tracking
- Motor (async MongoDB driver)

### AI and Document Intelligence

- Google Gemini 2.0 Flash
- PaddleOCR
- Poppler for PDF processing
- LangChain and custom agent orchestration

### Infrastructure

- MongoDB
- Redis
- Python Telegram Bot

## Architecture Overview

```mermaid
flowchart TB
    subgraph Frontend["Frontend (React + Vite)"]
        UI["React Router\n/dashboard · /form-search\n/session/:id · /execution/:id"]
        Sahayak["Sahayak Chat Widget\n(Counsellor Agent)"]
        WS_Client["WebSocket Client\nReal-time progress"]
    end

    subgraph Backend["Backend (FastAPI)"]
        Auth["POST /auth/login\nPOST /auth/register"]
        Docs["POST /documents/upload\n(DocVault → OCR)"]
        Search["POST /search/form\n(FormSearch → Gemini)"]
        Chat["POST /chat\nWS /ws/{session_id}"]
        Sessions["GET /sessions\n/start · /execute"]
        TelegramHook["POST /telegram/webhook\nGET /telegram/link-token"]
    end

    subgraph Agents["Autonomous Agents"]
        DocVault["DocVault\nPDF → Image → OCR → Encrypt"]
        Counsellor["CounsellorAgent\nSahayak · Gemini"]
        FormSearch["FormSearchAgent\nGemini + Portal Knowledge"]
        WebPilot["WebPilot\nForm Interaction Agent"]
        ScriptGen["ScriptGen\nPlaywright Script Generator"]
        Executor["Executor\nSubprocess Runner"]
        Notifier["TelegramNotifier\npython-telegram-bot"]
    end

    subgraph Storage["Storage and Infra"]
        MongoDB[("MongoDB\nusers · profiles\nsessions")]
        Redis[("Redis\nSession coordination")]
        Uploads["./uploads/\ndocs · screenshots"]
    end

    UI -->|HTTP + JWT| Auth
    UI -->|HTTP + JWT| Docs
    UI -->|HTTP + JWT| Search
    UI -->|HTTP + JWT| Chat
    UI -->|HTTP + JWT| Sessions
    UI -->|WebSocket| WS_Client
    WS_Client -->|ws:///ws/{session_id}| Chat

    Sessions --> ScriptGen --> Executor
    Executor -->|Playwright| WebPilot
    WebPilot -->|Browser automation| GovPortal[("External Portals")]
    Executor -->|Events| WS_Client

    Docs --> DocVault --> Gemini[("Google Gemini 2.0")]
    Chat --> Counsellor --> Gemini
    Search --> FormSearch --> Gemini
    WebPilot --> Gemini

    Auth --> MongoDB
    Docs --> MongoDB
    Sessions --> MongoDB
    Executor --> Redis
    Sessions --> Notifier
    Notifier --> TelegramAPI[("Telegram API")]
```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/team-tensors/civicflow.git
cd civicflow
```

### 2. Configure Environment Variables

Create a `.env` file inside the `backend/` directory:

```bash
cp backend/.env.example backend/.env
```

Then edit `backend/.env` and add the required secrets such as your `GEMINI_API_KEY`.

### 3. Backend Setup

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```

Depending on your operating system, you may also need Poppler for PDF processing:

- macOS: `brew install poppler`
- Ubuntu: `sudo apt install poppler-utils`

Run the backend:

```bash
# Windows
python main.py

# macOS / Linux
uvicorn main:app --reload --port 8000
```

### 4. Frontend Setup

```bash
cd ../frontend/react-app
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

## Demo Flow

1. Create a new account or use seeded demo credentials.
2. Complete **Profile Setup** with your basic information.
3. Upload sample documents in **Document Vault** and review extracted OCR data.
4. Use **Form Search** to look for a target workflow, such as a passport application.
5. Review mapped fields in the **Review Before Filing** screen.
6. Confirm execution and let CivicFlow automate the form.
7. If a CAPTCHA or OTP is encountered, complete it and resume execution.

## Notes

- CivicFlow is designed to be privacy-first and human-reviewed.
- Users remain in control before any final submission.
- Document extraction, field mapping, and execution can be improved incrementally as agents evolve.

## Team

**Team Tensors**  
Built for **Faraway Hackathon 2026**

*Empowering citizens with secure, intelligent automation.*
