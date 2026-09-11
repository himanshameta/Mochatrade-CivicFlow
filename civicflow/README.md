# CivicFlow

Multi-agent system that automates web form filling through intelligent analysis and execution.

## Overview

CivicFlow accepts any web form URL, analyzes it, collects required user information once, generates a custom Playwright automation script, and executes it to complete the form.

## Architecture

- **Scout Agent**: Visits URL and captures page HTML + screenshot
- **Scraper Agent**: Extracts all form fields from HTML
- **Analyst Agent**: Maps form fields to required user data
- **Collector Agent**: Manages user data collection
- **ScriptGen Agent**: Generates custom Playwright automation script
- **Executor Agent**: Runs the generated script
- **Notifier Agent**: Sends real-time status updates

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys
2. Run `docker-compose up`
3. Open `frontend/index.html` in your browser
4. Backend API available at `http://localhost:8000`

## Tech Stack

- Backend: FastAPI + LangGraph + Anthropic Claude
- Automation: Playwright
- Storage: Redis
- Frontend: Vanilla JavaScript
