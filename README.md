# Community Guardian - Palo Alto Case Study

Candidate Name: Nikillan  
Scenario Chosen: Community Safety & Digital Wellness  
Estimated Time Spent: ~12 hours (MVP build + tests + documentation)

## Problem Summary

People are exposed to fragmented local safety and digital-security information. This creates alert fatigue and inconsistent responses to incidents like phishing, scams, and breach rumors. Community Guardian turns noisy reports into a calm incident digest with immediate 1-2-3 action steps.

## MVP Features

- Primary source-driven flow: ingest synthetic feed events and triage them into incidents.
- End-to-end incident flow: create/import, view, update status (`new`, `verified`, `ignored`, `resolved`).
- Search/filter by keyword, status, and severity.
- AI-powered incident analysis (category, severity, summary, checklist).
- Rule-based fallback analysis when AI is unavailable or invalid.
- Synthetic source datasets (`data/feed_events.json`, `data/incidents.json`) with no personal data.
- Palo Alto-inspired dashboard styling with animated splash entry.

## Quick Start

### Prerequisites

- Python 3.10+

### Run Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open: http://127.0.0.1:8000

### Test Commands

```bash
source .venv/bin/activate
pytest -q
```

## API Highlights

- `GET /api/feed/preview`: Preview feed size and sample events.
- `POST /api/feed/import`: Import and analyze feed events.
- `GET /api/incidents`: View searchable/filterable incident digest.
- `PUT /api/incidents/{id}`: Update incident status.

## Environment Variables

Create a local `.env` file from `.env.example`.

```bash
cp .env.example .env
```

- `AI_ENABLED=true|false` toggles AI analysis.
- `OPENAI_API_KEY` enables OpenAI call.
- Without API key or if AI output is invalid, fallback logic is used automatically.

## AI Disclosure

- Did you use an AI assistant (Copilot, ChatGPT, etc.)? **Yes**
- How did you verify the suggestions?
  - Validated API contracts through tests and manual runs.
  - Ensured deterministic fallback behavior without external services.
  - Confirmed security basics: no keys in repo, synthetic data only.
- One suggestion rejected/changed:
  - Rejected adding multiple external feeds/scrapers because requirement explicitly asks for synthetic data and a focused MVP.

## Tradeoffs & Prioritization

- What was cut to stay within a tight scope?
  - Multi-user auth and RBAC.
  - Live geolocation integrations.
  - End-to-end encryption implementation for safe circles.
  - Deployment pipeline and observability stack.
- What would be built next with more time?
  - Explainable confidence scoring and human-in-the-loop correction.
  - Trusted source verification + weighting pipeline.
  - User profiles, safe-circle controls, and notification preferences.
  - Audit logging and role-based security hardening.
- Known limitations
  - Uses file-based JSON storage (single-node, non-concurrent).
  - AI response quality depends on model/API availability.
  - Fallback is heuristic and intentionally simple.

## Responsible AI Notes

- The product always has a fallback classifier.
- The UI labels whether a result came from `ai` or `fallback`.
- Users can reanalyze and manually update status, avoiding blind automation.
- Data is synthetic and does not include sensitive personal information.

## Demo Video (5-7 mins)

Add your public video link here:

- Video Link: TODO

## Repository Structure

```text
app/
  main.py
  models.py
  services/
static/
  css/
  js/
templates/
data/
tests/
```
