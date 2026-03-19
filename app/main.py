"""FastAPI application — Community Guardian API routes."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config, database as db
from app.models import (
    FeedImportRequest,
    Incident,
    IncidentCreate,
    IncidentUpdate,
    ReanalyzeRequest,
)
from app.services import ai_pipeline, feed_service

BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(application: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Community Guardian", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ── Pages ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


# ── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    ai_available = bool(config.GROQ_API_KEY) and config.AI_ENABLED
    daily_limit = ai_pipeline._daily_limit_hit
    return {"status": "ok", "ai_available": ai_available and not daily_limit, "daily_limit_hit": daily_limit}


# ── Stats ─────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats() -> dict:
    return db.get_stats()


# ── Incidents CRUD ────────────────────────────────────────────────────────

@app.get("/api/incidents")
def list_incidents(
    search: str = Query(default=""),
    status: str = Query(default=""),
    severity: str = Query(default=""),
    category: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    incidents, total = db.get_incidents(
        search=search, status=status, severity=severity,
        category=category, limit=limit, offset=offset,
    )
    return {"incidents": incidents, "total": total}


@app.post("/api/incidents", status_code=201)
async def create_incident(payload: IncidentCreate) -> dict:
    analysis = await ai_pipeline.analyze(
        title=payload.title,
        description=payload.description,
        location=payload.location,
        use_ai=payload.use_ai,
    )
    incident = db.insert_incident(
        title=payload.title,
        description=payload.description,
        location=payload.location,
        category=analysis.category,
        severity=analysis.severity,
        confidence=analysis.confidence,
        summary=analysis.summary,
        checklist=analysis.checklist,
        source=analysis.source,
        reasoning=analysis.reasoning,
        entry_mode="manual",
    )
    return incident


@app.put("/api/incidents/{incident_id}")
def update_incident(incident_id: int, payload: IncidentUpdate) -> dict:
    existing = db.get_incident(incident_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Incident not found")

    updates = {}
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.severity is not None:
        updates["severity"] = payload.severity

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = db.update_incident(incident_id, **updates)
    return result


@app.post("/api/incidents/{incident_id}/reanalyze")
async def reanalyze_incident(incident_id: int, payload: ReanalyzeRequest = None) -> dict:
    existing = db.get_incident(incident_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Incident not found")

    use_ai = payload.use_ai if payload else None
    analysis = await ai_pipeline.analyze(
        title=existing["title"],
        description=existing["description"],
        location=existing["location"],
        use_ai=use_ai,
    )
    result = db.reanalyze_incident(
        incident_id=incident_id,
        category=analysis.category,
        severity=analysis.severity,
        confidence=analysis.confidence,
        summary=analysis.summary,
        checklist=analysis.checklist,
        source=analysis.source,
        reasoning=analysis.reasoning,
    )
    return result


# ── Feed ──────────────────────────────────────────────────────────────────

@app.get("/api/feed/preview")
def preview_feed() -> dict:
    return feed_service.get_preview()


@app.post("/api/feed/import")
async def import_feed(payload: FeedImportRequest) -> dict:
    events = feed_service.load_events()
    if not events:
        raise HTTPException(status_code=404, detail="No feed events found")

    if payload.reset_existing:
        deleted = db.delete_feed_incidents()

    # Determine if we need API pacing (Groq free-tier rate limits)
    needs_ai = payload.use_ai is not False and ai_pipeline._ai_available()

    # Reanalyze manual incidents whose source doesn't match the selected engine
    reanalyzed = 0
    if payload.use_ai is False:
        # Forced fallback — reanalyze any manual incidents that used AI
        for inc in db.get_manual_incidents_by_source("ai"):
            try:
                analysis = await ai_pipeline.analyze(
                    title=inc["title"], description=inc["description"],
                    location=inc["location"], use_ai=False,
                )
                db.reanalyze_incident(
                    incident_id=inc["id"], category=analysis.category,
                    severity=analysis.severity, confidence=analysis.confidence,
                    summary=analysis.summary, checklist=analysis.checklist,
                    source=analysis.source, reasoning=analysis.reasoning,
                )
                reanalyzed += 1
            except Exception:
                pass
    elif needs_ai:
        # AI mode or auto with AI available — reanalyze fallback manual incidents
        for inc in db.get_manual_incidents_by_source("fallback"):
            try:
                analysis = await ai_pipeline.analyze(
                    title=inc["title"], description=inc["description"],
                    location=inc["location"], use_ai=True,
                )
                db.reanalyze_incident(
                    incident_id=inc["id"], category=analysis.category,
                    severity=analysis.severity, confidence=analysis.confidence,
                    summary=analysis.summary, checklist=analysis.checklist,
                    source=analysis.source, reasoning=analysis.reasoning,
                )
                reanalyzed += 1
                await asyncio.sleep(0.5)
            except Exception:
                pass

    # Limit events
    events = events[: payload.max_items]

    imported = 0
    for ev in events:
        # Skip duplicates
        if db.check_duplicate(ev.title, ev.location):
            continue

        try:
            analysis = await ai_pipeline.analyze(
                title=ev.title,
                description=ev.description,
                location=ev.location,
                use_ai=payload.use_ai,
            )
        except Exception:
            # AI failed hard — fall back to classifier so we don't lose the event
            analysis = await ai_pipeline.analyze(
                title=ev.title, description=ev.description,
                location=ev.location, use_ai=False,
            )
        db.insert_incident(
            title=ev.title,
            description=ev.description,
            location=ev.location,
            category=analysis.category,
            severity=analysis.severity,
            confidence=analysis.confidence,
            summary=analysis.summary,
            checklist=analysis.checklist,
            source=analysis.source,
            reasoning=analysis.reasoning,
            entry_mode="feed",
            raw_event=ev.model_dump(),
            created_at=ev.reported_at or None,
        )
        imported += 1
        # Pace API calls to stay within Groq free-tier rate limits
        if needs_ai and imported < len(events):
            await asyncio.sleep(0.5)

    total = db.get_stats()["total"]
    return {"imported": imported, "reanalyzed": reanalyzed, "total_incidents": total}
