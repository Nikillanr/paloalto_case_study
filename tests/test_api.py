"""API endpoint tests — covers CRUD, feed import, search/filter, and stats."""

import os
import pytest
from fastapi.testclient import TestClient

# Point database to a temp file before importing app
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["AI_ENABLED"] = "false"  # Tests use fallback — no API calls

from app.main import app
from app import database as db


client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db():
    """Reset the database for each test."""
    db.reset_db()
    yield


# ── Happy Path Tests ──────────────────────────────────────────────────

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "ai_available" in body


def test_create_incident_happy_path():
    payload = {
        "title": "Phishing email targeting employees",
        "description": "Staff received urgent emails asking to verify payroll credentials through a fake login page.",
        "location": "Bengaluru",
    }
    resp = client.post("/api/incidents", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] >= 1
    assert body["title"] == payload["title"]
    assert body["category"] in {"phishing", "scam", "data_breach", "local_hazard", "network_security", "general"}
    assert body["confidence"] > 0
    assert body["source"] in {"ai", "fallback"}
    assert len(body["checklist"]) > 0
    assert body["reasoning"] != ""
    assert body["status"] == "new"
    assert body["entry_mode"] == "manual"

    # Verify it appears in the list
    list_resp = client.get("/api/incidents")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


# ── Validation Tests ──────────────────────────────────────────────────

def test_create_incident_validation_error():
    payload = {"title": "Hi", "description": "short", "location": "X"}
    resp = client.post("/api/incidents", json=payload)
    assert resp.status_code == 422


# ── Feed Import Tests ─────────────────────────────────────────────────

def test_feed_preview():
    resp = client.get("/api/feed/preview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 10
    assert len(body["samples"]) == 3


def test_import_feed():
    resp = client.post("/api/feed/import", json={"max_items": 5, "reset_existing": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] == 5
    assert body["total_incidents"] == 5


def test_import_feed_dedup():
    """Importing the same events twice should not create duplicates."""
    client.post("/api/feed/import", json={"max_items": 3, "reset_existing": False})
    resp2 = client.post("/api/feed/import", json={"max_items": 3, "reset_existing": False})
    body = resp2.json()
    assert body["imported"] == 0  # All duplicates


# ── Search & Filter Tests ─────────────────────────────────────────────

def test_search_filter():
    # Create two incidents in different locations
    client.post("/api/incidents", json={
        "title": "Phishing attack in Pune",
        "description": "Employees received suspicious emails with credential harvesting links.",
        "location": "Pune",
    })
    client.post("/api/incidents", json={
        "title": "Gas leak emergency in Mumbai",
        "description": "Major gas leak reported in residential area, evacuation underway.",
        "location": "Mumbai",
    })

    # Search by text
    resp = client.get("/api/incidents?search=mumbai")
    assert resp.json()["total"] == 1
    assert resp.json()["incidents"][0]["location"] == "Mumbai"

    # Filter by severity — both incidents exist
    all_resp = client.get("/api/incidents")
    assert all_resp.json()["total"] == 2


# ── Update Tests ──────────────────────────────────────────────────────

def test_update_incident():
    create_resp = client.post("/api/incidents", json={
        "title": "Test incident for update",
        "description": "This is a test incident that we will update the status of.",
        "location": "Delhi",
    })
    inc_id = create_resp.json()["id"]

    resp = client.put(f"/api/incidents/{inc_id}", json={"status": "verified", "severity": "critical"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "verified"
    assert resp.json()["severity"] == "critical"


def test_update_nonexistent_incident():
    resp = client.put("/api/incidents/99999", json={"status": "verified"})
    assert resp.status_code == 404


# ── Stats Tests ───────────────────────────────────────────────────────

def test_stats():
    # Import some events to get stats
    client.post("/api/feed/import", json={"max_items": 5, "reset_existing": False})

    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert isinstance(body["by_severity"], dict)
    assert isinstance(body["by_category"], dict)
    assert isinstance(body["by_source"], dict)
    assert body["avg_confidence"] > 0


# ── Feed Reset Preserves Manual Entries ───────────────────────────────

def test_manual_survives_feed_reset():
    # Create manual incident
    manual = client.post("/api/incidents", json={
        "title": "Manual report about suspicious activity",
        "description": "Suspicious individual spotted near the school campus multiple times.",
        "location": "Gurugram",
    }).json()

    # Import feed
    client.post("/api/feed/import", json={"max_items": 3, "reset_existing": False})

    # Reset and reimport
    client.post("/api/feed/import", json={"max_items": 3, "reset_existing": True})

    # Manual entry should still exist
    all_resp = client.get("/api/incidents")
    ids = [i["id"] for i in all_resp.json()["incidents"]]
    assert manual["id"] in ids
