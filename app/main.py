import os
import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import FeedImportRequest, Incident, IncidentCreate, IncidentUpdate
from app.services.classifier import analyze_incident
from app.services.datastore import DataStore
from app.services.feed_ingest import import_feed_events

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "incidents.json"
FEED_PATH = BASE_DIR / "data" / "feed_events.json"

app = FastAPI(title="Community Guardian")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
store = DataStore(str(DATA_PATH))


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/feed/preview")
def preview_feed() -> dict:
    if not FEED_PATH.exists():
        raise HTTPException(status_code=404, detail="Feed file not found")

    rows = json.loads(FEED_PATH.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise HTTPException(status_code=500, detail="Feed file format is invalid")

    return {
        "events_available": len(rows),
        "sample": rows[:2],
    }


@app.post("/api/feed/import")
def import_feed(payload: FeedImportRequest) -> dict:
    ai_enabled = os.getenv("AI_ENABLED", "true").lower() == "true"
    existing = store.list_incidents()

    try:
        updated, imported = import_feed_events(
            feed_path=FEED_PATH,
            existing_incidents=existing,
            ai_enabled=ai_enabled,
            max_items=payload.max_items,
            reset_existing=payload.reset_existing,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store.save_incidents(updated)
    return {
        "imported": imported,
        "total_incidents": len(updated),
    }


@app.get("/api/incidents", response_model=list[Incident])
def list_incidents(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
) -> list[Incident]:
    incidents = store.list_incidents()

    if q:
        q_lower = q.lower()
        incidents = [
            i
            for i in incidents
            if q_lower in i.title.lower()
            or q_lower in i.description.lower()
            or q_lower in i.location.lower()
        ]

    if status:
        incidents = [i for i in incidents if i.status == status]

    if severity:
        incidents = [i for i in incidents if i.severity == severity]

    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    incidents.sort(key=lambda i: severity_rank[i.severity], reverse=True)
    return incidents


@app.post("/api/incidents", response_model=Incident, status_code=201)
def create_incident(payload: IncidentCreate) -> Incident:
    incidents = store.list_incidents()
    next_id = max([i.id for i in incidents], default=0) + 1

    ai_enabled = os.getenv("AI_ENABLED", "true").lower() == "true"
    analysis = analyze_incident(
        title=payload.title,
        description=payload.description,
        ai_enabled=ai_enabled,
    )

    incident = Incident(
        id=next_id,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        category=analysis["category"],
        severity=analysis["severity"],
        status="new",
        summary=analysis["summary"],
        checklist=analysis["checklist"],
        source=analysis["source"],
        entry_mode="manual",
    )

    incidents.append(incident)
    store.save_incidents(incidents)
    return incident


@app.put("/api/incidents/{incident_id}", response_model=Incident)
def update_incident(incident_id: int, payload: IncidentUpdate) -> Incident:
    incidents = store.list_incidents()

    if payload.status is None and payload.severity is None:
        raise HTTPException(status_code=400, detail="At least one field must be updated")

    for idx, incident in enumerate(incidents):
        if incident.id == incident_id:
            updates: dict = {}
            if payload.status is not None:
                updates["status"] = payload.status
            if payload.severity is not None:
                updates["severity"] = payload.severity

            updated = incident.model_copy(update=updates)
            incidents[idx] = updated
            store.save_incidents(incidents)
            return updated

    raise HTTPException(status_code=404, detail="Incident not found")


@app.post("/api/incidents/{incident_id}/reanalyze", response_model=Incident)
def reanalyze_incident(incident_id: int) -> Incident:
    incidents = store.list_incidents()
    ai_enabled = os.getenv("AI_ENABLED", "true").lower() == "true"

    for idx, incident in enumerate(incidents):
        if incident.id == incident_id:
            analysis = analyze_incident(
                title=incident.title,
                description=incident.description,
                ai_enabled=ai_enabled,
            )
            updated = incident.model_copy(
                update={
                    "category": analysis["category"],
                    "severity": analysis["severity"],
                    "summary": analysis["summary"],
                    "checklist": analysis["checklist"],
                    "source": analysis["source"],
                }
            )
            incidents[idx] = updated
            store.save_incidents(incidents)
            return updated

    raise HTTPException(status_code=404, detail="Incident not found")
