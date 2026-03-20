# Community Guardian - Palo Alto Networks Case Study

**Candidate Name:** Nikillan
**Scenario Chosen:** 3 - Community Safety & Digital Wellness
**Estimated Time Spent:** ~6 hours

## Problem Summary

As digital and physical security threats grow more complex, individuals face fragmented safety information scattered across news sites and social media. This creates **alert fatigue** — too much noise, not enough signal. Community Guardian solves this by aggregating community safety reports and using AI to filter noise, classify threats, and deliver **calm, actionable safety digests** with confidence-scored analysis.

This problem directly mirrors what Palo Alto Networks solves at enterprise scale with Cortex XSIAM: converting thousands of raw alerts into prioritized, actionable incidents.

## MVP Features

- **End-to-end incident flow**: Create, View, Update, Search/Filter incidents
- **AI-powered analysis**: Categorization, severity scoring, summary generation, and actionable checklists via Groq (Llama 3.1)
- **Intelligent fallback**: Weighted keyword scoring with confidence metrics when AI is unavailable or incorrect
- **Confidence scoring**: Every analysis includes a 0-1 confidence score with reasoning explanation
- **Dual-engine toggle**: Switch between AI, Fallback, or Auto mode application-wide — affects imports, manual reports, and reanalysis
- **6 threat categories**: phishing, data_breach, scam, local_hazard, network_security, general
- **12 synthetic events**: Diverse, realistic feed data across Indian cities
- **SQLite database**: ACID-compliant storage with querying and pagination
- **21 automated tests**: API endpoints + classifier unit tests

## Quick Start

### Prerequisites

- Python 3.9+

### Run Commands

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env to add your Groq API key (free at console.groq.com)
./start.sh
```

Open: http://127.0.0.1:8000

### Test Commands

```bash
pytest -v
```

## Architecture

```
Frontend (Security Dashboard)
    ↓↑ REST API (JSON)
FastAPI Application
    ├── SQLite Database (ACID, querying, pagination)
    ├── AI Analysis Pipeline
    │   ├── Groq Llama 3.1 8B (structured JSON, confidence scores)
    │   └── Weighted Keyword Classifier (deterministic fallback)
    ├── Feed Ingestion Service (normalize, deduplicate)
    └── Stats Aggregation (real-time dashboard metrics)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check + AI availability + daily limit status |
| GET | `/api/stats` | Dashboard statistics (totals, breakdowns, avg confidence) |
| GET | `/api/incidents` | List incidents with search, status/severity/category filters, pagination |
| POST | `/api/incidents` | Create and analyze a new incident |
| PUT | `/api/incidents/{id}` | Update status or severity |
| POST | `/api/incidents/{id}/reanalyze` | Re-run AI/fallback analysis |
| GET | `/api/feed/preview` | Preview available feed events |
| POST | `/api/feed/import` | Import and analyze feed events |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | _(empty)_ | Groq API key for AI analysis (free at console.groq.com) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq model to use |
| `AI_ENABLED` | `true` | Toggle AI analysis on/off |
| `DATABASE_PATH` | `data/guardian.db` | SQLite database file path |

## AI Disclosure

- **Did you use an AI assistant?** Yes — Claude Code (Anthropic) for development assistance.
- **How did you verify the suggestions?**
  - Ran all 21 tests to validate correctness
  - Manually tested the full flow (import → triage → search → update → reanalyze)
  - Verified fallback classifier produces reasonable categorization across all event types
  - Confirmed no API keys or secrets in repository
- **One suggestion rejected/changed:**
  - Rejected suggestion to use async SQLite (aiosqlite) — synchronous sqlite3 is simpler and perfectly adequate for a demo-scale prototype. Over-engineering async DB for a single-user demo adds complexity without benefit.

## Tradeoffs & Prioritization

- **What was cut to stay within the time limit?**
  - Multi-user authentication and RBAC
  - End-to-end encryption for "safe circles" feature
  - Live data feeds and geolocation integration
  - Deployment pipeline (Docker, CI/CD)
  - Drag-and-drop incident workflow
- **What would you build next with more time?**
  - User profiles with personalized alert preferences
  - Source reliability scoring and cross-source deduplication
  - Real-time WebSocket updates for live feed ingestion
  - Confidence threshold alerts (flag low-confidence AI results for human review)
  - Notification channels (email, SMS, push)
  - PostgreSQL migration for production scale
- **Known limitations:**
  - SQLite is single-writer (fine for demo, not for production)
  - Fallback classifier confidence is heuristic-based (keyword density)
  - AI analysis quality depends on Groq API availability and daily token quota
  - No rate limiting on API endpoints
  - Groq free tier has daily token limits — the app detects exhaustion and shows status in UI

## Responsible AI

- **Transparent sourcing**: Every analysis is labeled "ai" or "fallback" so users know what generated it
- **Confidence scoring**: 0-1 confidence score with visual indicator — users can see how certain the system is
- **Reasoning explanation**: Each classification includes a text explanation of why it was categorized that way
- **Human control**: Users can override severity, update status, and trigger reanalysis at any time. Global engine toggle lets users force AI or fallback mode
- **Graceful degradation**: If AI fails or quota is exhausted, the fallback classifier ensures the system never breaks — it always produces a usable result. Daily limit detection prevents hanging
- **Synthetic data only**: No real personal information; all events are fabricated for demonstration
- **No secrets in repo**: API keys managed via .env (not committed)

## Demo Video (5-7 mins)

Video Link: TODO

## Repository Structure

```
app/
  config.py              # Centralized settings from .env
  database.py            # SQLite database layer
  main.py                # FastAPI routes and app setup
  models.py              # Pydantic request/response schemas
  services/
    ai_pipeline.py       # Groq LLM integration with fallback
    classifier.py        # Weighted keyword fallback classifier
    feed_service.py      # Feed ingestion and normalization
data/
  seed_events.json       # 12 synthetic community safety events
docs/
  design.md              # Design documentation
static/
  css/styles.css         # Dashboard styles
  js/app.js              # Dashboard logic (vanilla JS)
templates/
  index.html             # Dashboard HTML shell
tests/
  test_api.py            # API endpoint tests (11 tests)
  test_classifier.py     # Classifier unit tests (10 tests)
start.sh                 # One-shot launcher (clean DB + start server)
CONTEXT.md               # Full project context for LLM assistants
```
