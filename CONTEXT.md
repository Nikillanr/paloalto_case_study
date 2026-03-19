# Community Guardian — LLM Context File

> This file provides full project context for any LLM-based coding assistant (Claude, Cursor, Copilot, Windsurf, etc.). Read this before making changes.

## What This Project Is

A **Community Safety Threat Intelligence Dashboard** built for a Palo Alto Networks case study. It ingests community safety reports (feed import or manual entry), runs them through an AI analysis pipeline (Groq Llama 3.1) or a weighted keyword fallback classifier, and presents triaged incidents with severity, confidence scores, summaries, and actionable checklists.

Inspired by Palo Alto's **Cortex XSIAM** — converting raw security telemetry into prioritized, actionable incidents.

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | FastAPI | 0.115.6 |
| Server | Uvicorn | 0.34.0 |
| Database | SQLite (sync sqlite3) | stdlib |
| AI | Groq API (Llama 3.1 8B Instant) | via httpx |
| Fallback | Weighted keyword classifier | custom |
| Frontend | Vanilla JS + CSS | no framework |
| Templating | Jinja2 | 3.1.5 |
| Config | python-dotenv | 1.0.1 |
| Testing | Pytest + FastAPI TestClient | 8.3.4 |

## Project Structure

```
app/
  __init__.py
  config.py              # Environment variables (GROQ_API_KEY, AI_ENABLED, DATABASE_PATH, FEED_PATH, GROQ_MODEL)
  database.py            # SQLite layer — init_db, CRUD, stats, dedup, filtering
  main.py                # FastAPI routes (8 endpoints) + lifespan + static/template mounts
  models.py              # Pydantic schemas (IncidentCreate, IncidentUpdate, AnalysisResult, FeedEvent, Stats, etc.)
  services/
    __init__.py
    ai_pipeline.py       # Groq LLM integration — structured JSON prompting, retry, daily limit detection, fallback
    classifier.py        # Weighted keyword classifier — 6 categories, severity detection, entity extraction, checklists
    feed_service.py      # Feed ingestion — JSON loading, field normalization, preview
data/
  seed_events.json       # 12 synthetic community safety events (2 per category, Indian cities)
docs/
  design.md              # Architecture decisions, data model, AI pipeline design, future roadmap
static/
  css/styles.css         # Dark security dashboard theme (CSS custom properties)
  js/app.js              # Dashboard logic — state management, API calls, rendering, filters, engine toggle
templates/
  index.html             # Three-column layout: sidebar (feed + manual form) | incident list | detail panel
tests/
  test_api.py            # 11 API tests (CRUD, feed import, dedup, search, stats, validation)
  test_classifier.py     # 10 classifier tests (category detection, severity, confidence range, edge cases)
```

## Environment Variables

Defined in `.env` (never committed), with `.env.example` as template:

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | `""` | Groq API key (free at console.groq.com) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq model (500K tokens/day on free tier) |
| `AI_ENABLED` | `true` | Toggle AI on/off |
| `DATABASE_PATH` | `data/guardian.db` | SQLite file path |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve dashboard HTML |
| `GET` | `/health` | Health check + AI status + daily limit flag |
| `GET` | `/api/stats` | Aggregated stats (total, by_severity, by_category, by_source, avg_confidence) |
| `GET` | `/api/incidents` | List incidents — query params: `search`, `status`, `severity`, `category`, `limit`, `offset` |
| `POST` | `/api/incidents` | Create + analyze incident (body: IncidentCreate) |
| `PUT` | `/api/incidents/{id}` | Update status/severity (body: IncidentUpdate) |
| `POST` | `/api/incidents/{id}/reanalyze` | Re-run AI/fallback analysis (body: ReanalyzeRequest) |
| `GET` | `/api/feed/preview` | Preview available feed events (count + 3 samples) |
| `POST` | `/api/feed/import` | Import feed events with analysis (body: FeedImportRequest) |

## Database Schema (SQLite)

Table: `incidents`

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | auto | Primary key |
| title | TEXT | — | Incident title |
| description | TEXT | — | Full description |
| location | TEXT | — | Geographic area |
| category | TEXT | — | phishing, data_breach, scam, local_hazard, network_security, general |
| severity | TEXT | "medium" | critical, high, medium, low |
| confidence | REAL | 0.5 | 0.0–1.0 analysis confidence |
| summary | TEXT | — | AI/fallback-generated summary |
| checklist | TEXT | — | JSON array of 3-5 action steps |
| source | TEXT | "fallback" | "ai" or "fallback" |
| reasoning | TEXT | — | Why this classification was chosen |
| entry_mode | TEXT | "manual" | "feed" or "manual" |
| status | TEXT | "new" | new, verified, resolved, dismissed |
| created_at | TEXT | — | ISO 8601 |
| updated_at | TEXT | — | ISO 8601 |
| raw_event | TEXT | — | Original feed event JSON (nullable) |

## AI Pipeline (`ai_pipeline.py`)

### Flow
1. `analyze()` is the entry point — accepts `use_ai` param (True/False/None for auto)
2. If AI available → calls `_call_groq()` with structured JSON prompt
3. Groq returns: `{category, severity, confidence, summary, checklist, reasoning}`
4. Response validated, confidence clamped to 0.0–1.0
5. On failure → falls back to `classifier.classify()`

### Daily Limit Detection
- Module-level `_daily_limit_hit` flag
- On 429 response: if error message contains "per day" or "tpd", flag is set to True
- `_ai_available()` checks this flag — prevents further API calls
- Health endpoint exposes `daily_limit_hit` to frontend
- Frontend shows "AI Quota Exhausted" status when flag is true

### Retry Logic
- Max 3 attempts on 429 (rate limit)
- Respects `Retry-After` header
- 20-second timeout per request

## Fallback Classifier (`classifier.py`)

### Categories (6)
Each has a weighted keyword dictionary (17+ keywords, weights 3–10):
- `phishing` — credential theft, fake logins, OTP interception
- `data_breach` — leaked records, exposed databases, password dumps
- `scam` — fraud, impersonation, lottery, fake job offers
- `local_hazard` — fire, chemical spill, gas leak, flooding
- `network_security` — malware, ransomware, DDoS, WiFi attacks
- `general` — fallback for unmatched input

### How It Works
1. `_score_text()` — matches keywords against combined title+description+location, sums weights
2. `_detect_category()` — highest scoring category wins; confidence = `min(0.95, max(0.3, score/max_possible * 2.5))`
3. `_detect_severity()` — priority-ordered keyword check (critical → high → medium → low)
4. `_extract_entities()` — regex extraction of targets, methods, assets
5. `_generate_summary()` — category-specific template with extracted entities
6. Returns `AnalysisResult` with source="fallback", pre-written checklist per category

## Frontend (`app.js`)

### Key Patterns
- `$()` helper for `document.querySelector`
- `api()` wrapper for all fetch calls — adds AbortController timeout (120s), JSON parsing
- State: `incidents[]`, `selectedId`, `keyboardIdx`, `debounceTimer`
- Engine toggle (`#engine-select`) sends `use_ai` param on all operations
- `checkAiStatus()` polls `/health` to show AI/Fallback/Quota status
- Filters: search (debounced 250ms), status, severity, category — all trigger `loadIncidents()`
- Text escaping via `esc()` function to prevent XSS

### CSS Custom Properties (defined in `:root`)
- `--bg`, `--bg-card`, `--border` — dark theme backgrounds
- `--text`, `--text-secondary`, `--text-dim` — text hierarchy
- `--accent` (#3B82F6) — primary blue
- `--severity-critical` (#EF4444), `--severity-high` (#F97316), `--severity-medium` (#EAB308), `--severity-low` (#22C55E)

## Running the Project

```bash
pip install -r requirements.txt
cp .env.example .env        # Add your GROQ_API_KEY
uvicorn app.main:app        # http://127.0.0.1:8000
pytest -v                   # 21 tests
```

**Important**: Do NOT use `--reload` flag — it causes `init_db()` to not re-run after module reload, resulting in "no such table" errors.

## Key Gotchas

1. **No `--reload`**: Uvicorn `--reload` breaks DB initialization via lifespan context manager
2. **`.env` overrides `config.py` defaults**: If GROQ_MODEL is set in `.env`, it takes precedence over the default in config.py
3. **`_daily_limit_hit` persists until restart**: The flag is module-level; restarting uvicorn clears it
4. **Checklist is stored as JSON string**: `json.dumps(list)` on insert, `json.loads(str)` on read
5. **Feed dedup**: Based on exact match of `LOWER(title)` + `LOWER(location)`
6. **Severity ordering in queries**: critical=1, high=2, medium=3, low=4 via CASE expression
7. **Tests use in-memory SQLite**: `AI_ENABLED=false` in tests, no API calls needed
