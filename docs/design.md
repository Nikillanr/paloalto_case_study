# Design Documentation — Community Guardian

## 1. Problem Analysis

Community safety information is fragmented across news sites, social media, and local channels. This fragmentation creates two failure modes:

1. **Alert fatigue**: Too many unfiltered reports cause people to disengage
2. **Missed signals**: Critical threats get lost in noise

Community Guardian addresses this by acting as a **noise-to-signal filter** — ingesting raw community reports, applying AI analysis to classify and prioritize them, and presenting **calm, actionable safety digests** with clear next steps.

This problem is architecturally identical to what Palo Alto Networks' Cortex XSIAM solves at enterprise scale: converting raw security telemetry into prioritized incidents with automated response recommendations.

## 2. Architecture

### Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Backend | FastAPI (Python) | Modern async framework, auto-generated OpenAPI docs, Pydantic validation |
| Database | SQLite | Zero-config, ACID-compliant, proper SQL querying — better than file-based JSON |
| AI | Groq Llama 3.1 8B Instant | Free tier with 500K daily tokens, fast inference (~0.5s), OpenAI-compatible API |
| Fallback | Weighted keyword classifier | Deterministic, always available, no external dependencies |
| Frontend | Vanilla JS + CSS | Zero build step, easy to clone and run, no framework overhead |
| Testing | Pytest + FastAPI TestClient | Standard Python testing with in-memory SQLite isolation |

### Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│                  Dashboard UI                     │
│    Stats | Feed Import | Incident List | Detail   │
└───────────────────┬─────────────────────────────┘
                    │ REST API (JSON)
┌───────────────────┴─────────────────────────────┐
│               FastAPI Application                 │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Feed     │  │ AI       │  │ Incident      │  │
│  │ Service  │→ │ Pipeline │→ │ Service (DB)  │  │
│  └──────────┘  └────┬─────┘  └───────────────┘  │
│                     │                             │
│              ┌──────┴──────┐                     │
│              │  Groq API?  │                     │
│              │  ↓Yes  ↓No  │                     │
│              │  AI   Fallback│                    │
│              └─────────────┘                     │
└──────────────────────────────────────────────────┘
```

## 3. Core Flow

1. User triggers feed import from the dashboard
2. Feed service loads 12 synthetic events from `seed_events.json`
3. Events are deduplicated (title + location match check)
4. Each event passes through the AI pipeline:
   - If Groq API is available → structured JSON analysis with confidence score
   - If not → weighted keyword classifier produces deterministic result
5. Analysis result includes: category, severity, confidence (0-1), summary, checklist, reasoning
6. Incident is stored in SQLite with full metadata and original reported timestamp
7. Dashboard updates: stats, incident list, filters
8. User can review, search/filter, update status, override severity, or trigger reanalysis

## 4. Data Model

### Incident Schema

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Auto-incrementing primary key |
| title | TEXT | Short incident title |
| description | TEXT | Full incident description |
| location | TEXT | Geographic area |
| category | TEXT | phishing, data_breach, scam, local_hazard, network_security, general |
| severity | TEXT | critical, high, medium, low |
| confidence | REAL | 0.0-1.0 analysis confidence score |
| summary | TEXT | AI/fallback-generated summary |
| checklist | TEXT (JSON) | 3-5 actionable steps |
| source | TEXT | "ai" or "fallback" |
| reasoning | TEXT | Explanation of classification logic |
| entry_mode | TEXT | "feed" or "manual" |
| status | TEXT | new, verified, resolved, dismissed |
| created_at | TEXT | ISO 8601 timestamp (preserved from source for feed events) |
| updated_at | TEXT | ISO 8601 timestamp |

## 5. AI Pipeline + Fallback Strategy

### AI Path (Groq / Llama 3.1 8B Instant)
- OpenAI-compatible API via Groq (free tier: 500K tokens/day, 30 RPM)
- Structured system prompt requesting JSON with specific fields
- Uses `response_format: json_object` for reliable parsing
- Temperature 0.3 for consistent, factual output
- 20-second timeout to prevent blocking
- Retry logic: 3 attempts on HTTP 429, respects `retry-after` header
- **Daily limit detection**: if Groq returns a "tokens per day" error, the app immediately stops retrying and falls back to classifier. The UI shows "AI Quota Exhausted" status
- Response validation: checks all required fields present, clamps confidence to 0-1

### Fallback Path (Weighted Keyword Classifier)
- **Category detection**: Weighted keyword dictionaries per category (17+ keywords each). Score = sum of matched keyword weights. Highest-scoring category wins.
- **Severity detection**: Priority-ordered keyword sets (critical → high → medium → low). First level with matches wins.
- **Confidence calculation**: `min(0.95, max(0.3, score / max_possible * 2.5))` — ensures confidence stays in a realistic range.
- **Summary generation**: Category-specific templates incorporating key details (location, first sentence of description).
- **Checklist**: Pre-written, category-specific 3-5 step action plans.
- **Reasoning**: Auto-generated text explaining which keywords triggered the classification.

### Fallback Triggers
1. No GROQ_API_KEY configured
2. AI_ENABLED set to false
3. User selects "Fallback Only" mode in UI
4. Groq API returns an error or times out
5. Daily token limit exhausted
6. Response fails schema validation

### Global Engine Toggle
The dashboard header includes a global analysis engine selector (Auto / AI Only / Fallback Only) that affects all operations:
- Feed imports: all events analyzed with selected engine
- Manual reports: submitted with selected engine
- Reanalysis: individual incidents re-processed with selected engine
- On mode switch + reimport: existing manual entries are reanalyzed to match the new mode (e.g. switching from AI to Fallback reanalyzes AI-sourced manual entries with fallback)

## 6. Confidence Scoring Design

Confidence is a key differentiator for responsible AI:

- **AI source**: Confidence is self-reported by the LLM (0-1), clamped to valid range
- **Fallback source**: Computed as keyword match density relative to maximum possible score
- **UI representation**: Colored progress bar + percentage (green ≥80%, yellow ≥60%, orange ≥40%, red <40%)
- **Purpose**: Users can quickly assess how much to trust the automated analysis and whether to reanalyze or manually override

## 7. Security Considerations

- API keys stored in `.env` (not committed to repo)
- `.env.example` provided for setup guidance
- All data is synthetic — no real personal information
- Input validation via Pydantic with min/max length constraints
- Text escaping in frontend to prevent XSS
- SQLite with parameterized queries to prevent SQL injection

## 8. Testing Strategy

- **21 tests total** (11 API + 10 classifier)
- **In-memory SQLite** for test isolation (no file cleanup needed)
- **AI disabled in tests** (`AI_ENABLED=false`) — tests use fallback only, no API calls needed
- **API tests**: CRUD operations, validation, feed import, dedup, search, stats, manual entry survival on reset
- **Classifier tests**: Category detection, severity detection, confidence range, reasoning, edge cases

## 9. Future Enhancements

| Priority | Enhancement | Effort |
|----------|------------|--------|
| High | PostgreSQL migration for production scale | Medium |
| High | User authentication and role-based access | Medium |
| Medium | Real-time WebSocket updates for live feeds | Medium |
| Medium | Source reliability scoring and weighting | Low |
| Medium | Confidence threshold alerts (auto-flag for human review) | Low |
| Low | Notification channels (email, SMS, push) | High |
| Low | Geographic visualization (map view) | Medium |
| Low | Larger AI model (70B) on paid Groq tier for higher quality | Low |
