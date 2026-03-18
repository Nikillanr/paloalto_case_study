# Design Documentation - Community Guardian

## 1. Objective

Build a focused prototype that converts noisy community safety reports into concise, actionable guidance with transparent AI usage and a reliable fallback path.

## 2. Architecture

- **Frontend**: Server-rendered HTML + vanilla JavaScript + custom CSS.
- **Backend**: FastAPI REST API.
- **Storage**:
  - Feed source: `data/feed_events.json` (synthetic external-like event source)
  - Incident store: `data/incidents.json` (triaged digest output)
- **AI Layer**:
  - Primary: OpenAI chat completion via HTTPS.
  - Fallback: Rule-based classifier using keyword heuristics.

## 3. Core Flow

1. User triggers feed import from the dashboard.
2. Backend loads synthetic source events from `feed_events.json`.
3. Each event is normalized and deduplicated.
4. Backend attempts AI analysis (category, severity, summary, 3-step checklist).
5. If AI is unavailable/invalid, backend executes fallback rules.
6. Incidents are persisted with `source` metadata (`ai` or `fallback`).
7. User reviews digest, filters incidents, updates status, and can reanalyze.
8. Optional operator input path exists for simulation/testing.

## 4. Data Model

Incident fields:

- `id`: integer
- `title`: short text
- `description`: long text
- `location`: short text
- `category`: `phishing | data_breach | local_hazard | scam | general`
- `severity`: `low | medium | high | critical`
- `status`: `new | verified | ignored | resolved`
- `summary`: concise interpretation
- `checklist`: exactly 3 recommended actions
- `source`: `ai | fallback`

## 5. AI + Fallback Strategy

- AI is optional and gated by `OPENAI_API_KEY`.
- Fallback triggers when:
  - API key is missing,
  - external call fails,
  - output schema is invalid.
- Fallback guarantees deterministic behavior and always produces required fields.

## 6. Validation and Error Handling

- Pydantic validation enforces input constraints.
- API returns structured validation errors on malformed payloads.
- Not-found and invalid update operations return clear HTTP errors.

## 7. Testing

Implemented tests:

- **Happy path**: create incident and verify it appears in listing.
- **Edge case**: invalid short input rejected with HTTP 422.
- **Source flow**: preview + import feed events and verify incidents are created.

## 8. Security and Responsible AI

- No secrets committed; `.env.example` provided.
- Synthetic data only.
- Transparent source labeling (`ai` vs `fallback`).
- Human control retained through status updates and reanalysis.

## 9. Future Enhancements

- Confidence scoring with explainability cards.
- Source reliability ranking and stronger cross-source deduplication.
- Auth + role-based permissions.
- Notification channels (email/SMS/push) and escalation logic.
- Postgres storage with migration support.
