<div align="center">
  <img src="https://raw.githubusercontent.com/team-tensors/civicflow/main/assets/logo.png" alt="CivicFlow Logo" width="120" onerror="this.style.display='none'">
  <h1>CivicFlow</h1>
  <p><strong>Private AI-Assisted Form Automation</strong></p>
  <p><em>Built by <b>Team Tensors</b> for the <b>Faraway Hackathon 2026</b></em></p>
</div>

---

## 🚀 The Vision

Government and institutional portals are notoriously complex, repetitive, and frustrating to navigate. Citizens spend countless hours repeatedly typing the same information and uploading the same documents across different platforms.

**CivicFlow** is a privacy-first, intelligent automation platform that acts as your personal digital assistant. You securely store your core identity documents and profile once. When you need to fill a form, CivicFlow's AI agents navigate the portal, extract what's needed, map your data to the form, ask for your final review, and execute the submission on your behalf—handling CAPTCHAs and OTPs interactively along the way.

## ✨ Key Features

- **🔐 Privacy-First Document Vault (DocVault):** Upload Aadhaar, PAN, Passports, or resumes. CivicFlow uses Gemini Vision and PaddleOCR to extract structured data and stores it with AES-256 encryption. Your sensitive data never leaks.
- **🤖 Intelligent Form Execution (WebPilot):** Utilizing Playwright and LLMs, our executor agent dynamically reads complex, multi-page forms, generates robust automation scripts on the fly, and bypasses anti-paste restrictions.
- **🙋‍♂️ Human-in-the-Loop Interventions:** CivicFlow is autonomous but respects boundaries. If it hits a CAPTCHA or an OTP wall, execution pauses. The user is notified (via WebSockets or Telegram), solves the challenge on the dashboard, and execution resumes seamlessly.
- **🧠 Sahayak AI Counsellor:** A built-in AI chat widget that acts as your personal guide, helping you understand complex government requirements and suggesting which documents to use.
- **🎨 "Bitcoin DeFi" Design System:** A custom, premium, dark-mode-first visual aesthetic built from scratch using pure CSS variables—signaling security, precision, and trust.

## 🛠️ Technology Stack

**Frontend**
- React 18 + Vite 5
- Custom Vanilla CSS Design System (Bitcoin DeFi aesthetic)
- React Router DOM for SPA routing

**Backend & Automation**
- Python 3.10+ & FastAPI
- Playwright (Headless Browser Automation)
- WebSockets for real-time execution tracking
- Motor (Async MongoDB Driver)

**AI & Machine Learning**
- Google Gemini 2.0 Flash (Core LLM for planning, extraction, and vision)
- PaddleOCR / Poppler (Document processing)
- LangChain / Custom Agent Architecture

**Infrastructure**
- MongoDB (Data persistence)
- Redis (Session coordination & rate limiting)
- Python-Telegram-Bot (Real-time notifications)

---

## 🏗️ Architecture Overview

```mermaid
flowchart TB
    subgraph Frontend["Frontend (React + Vite)"]
        UI["React Router\n/dashboard · /form-search\n/session/:id · /execution/:id"]
        Sahayak["Sahayak Chat Widget\n(Counsellor Agent)"]
        WS_Client["WebSocket Client\nReal-time progress"]
    end

    subgraph Backend["Backend (FastAPI — port 8000)"]
        Auth["POST /auth/login\nPOST /auth/register"]
        Docs["POST /documents/upload\n(DocVault → OCR)"]
        Search["POST /search/form\n(FormSearch → Gemini)"]
        Chat["POST /chat\nWS /ws/{session_id}"]
        Sessions["GET /sessions\n/start · /execute"]
        Telegram_API["POST /telegram/webhook\nGET /telegram/link-token"]
    end

    subgraph Agents["Autonomous Agents"]
        DocVault["DocVault\nPDF→Image→OCR→Encrypt"]
        Counsellor["CounsellorAgent\nSahayak · Gemini"]
        FormSearch["FormSearchAgent\nGemini + Portal Knowledge"]
        WebPilot["WebPilot\nAnti-paste · CAPTCHA"]
        ScriptGen["ScriptGen\nPlaywright script generator"]
        Executor["Executor\nSubprocess runner"]
        Notifier["TelegramNotifier\npython-telegram-bot"]
    end

    subgraph Storage["Storage & Infra"]
        MongoDB[("MongoDB\nusers · profiles\ndocuments · sessions")]
        Redis[("Redis\nSession coordination")]
        Uploads["./uploads/\ndocs · screenshots"]
    end

    UI -->|HTTP + JWT| Auth & Docs & Search & Chat & Sessions
    UI -->|WebSocket| WS_Client
    WS_Client -->|ws:///ws/{id}| Chat

    Sessions --> ScriptGen --> Executor
    Executor -->|Playwright| WebPilot
    WebPilot -->|Browser automation| GovPortal[("External\nGov Portals")]
    Executor -->|Events| WS_Client

    Docs --> DocVault --> Gemini[("Google Gemini 2.0")]
    Chat --> Counsellor --> Gemini
    Search --> FormSearch --> Gemini
    WebPilot --> Gemini

    Auth & Docs & Sessions --> MongoDB
    Executor --> Redis
    Notifier --> TelegramAPI[("Telegram API")]
    Sessions --> Notifier
```

---

## 🏁 Quick Start Guide

### 1. Repository Setup
```bash
git clone https://github.com/team-tensors/civicflow.git
cd civicflow
```

### 2. Environment Configuration
Create a `.env` file in the `backend/` directory:
```bash
cp backend/.env.example backend/.env
# Edit backend/.env and add your GEMINI_API_KEY
```

### 3. Backend Setup
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```
*Note: Depending on your OS, you may need to install Poppler for PDF processing (`brew install poppler` on macOS, `sudo apt install poppler-utils` on Ubuntu).*

**Run the Backend:**
```bash
# Windows
python main.py
# Mac/Linux
uvicorn main:app --reload --port 8000
```

### 4. Frontend Setup
```bash
cd ../frontend/react-app
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🎮 How to use the Demo

1. Create a new account or use the seeded demo credentials (if you ran `python scripts/seed_demo.py`).
2. **Profile Setup**: Fill in your basic details.
3. **Document Vault**: Upload a sample PDF or image (e.g., a dummy Aadhaar or PAN). Watch the OCR extract the data.
4. **Form Search**: Search for a form, e.g., "Passport Application".
5. **Review**: CivicFlow will pre-fill the form using your profile and documents. Review the mapped fields.
6. **Execution**: Click Confirm. CivicFlow will launch a headless browser and fill the form on the target site. Watch the real-time progress. If a CAPTCHA is encountered, use the intervention panel to solve it and resume!

---

## 🏆 Built by Team Tensors
**Faraway Hackathon 2026**

*Empowering citizens with secure, intelligent automation.*
