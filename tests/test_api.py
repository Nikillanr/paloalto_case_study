from fastapi.testclient import TestClient
import pytest

from app.main import app, store


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_store(tmp_path):
    original_path = store.path
    temp_data = tmp_path / "incidents.json"
    temp_data.write_text("[]", encoding="utf-8")
    store.path = temp_data
    yield
    store.path = original_path


def test_create_incident_happy_path() -> None:
    payload = {
        "title": "Phishing text alert",
        "description": "User received a message asking for bank OTP and password verification.",
        "location": "Pune",
    }

    response = client.post("/api/incidents", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["category"] in {"phishing", "scam", "general", "data_breach", "local_hazard"}

    list_response = client.get("/api/incidents")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_create_incident_validation_edge_case() -> None:
    payload = {
        "title": "Hi",
        "description": "short",
        "location": "X",
    }

    response = client.post("/api/incidents", json=payload)
    assert response.status_code == 422


def test_import_feed_data_source_flow() -> None:
    preview_response = client.get("/api/feed/preview")
    assert preview_response.status_code == 200
    preview_body = preview_response.json()
    assert preview_body["events_available"] >= 1

    import_response = client.post(
        "/api/feed/import",
        json={"reset_existing": True, "max_items": 3},
    )
    assert import_response.status_code == 200
    import_body = import_response.json()
    assert import_body["imported"] >= 1
    assert import_body["total_incidents"] >= 1

    list_response = client.get("/api/incidents")
    assert list_response.status_code == 200
    assert len(list_response.json()) == import_body["total_incidents"]


def test_manual_entry_survives_feed_reset_and_severity_override() -> None:
    manual_response = client.post(
        "/api/incidents",
        json={
            "title": "Manual suspicious call report",
            "description": "Caller claimed to be from tax office and requested immediate UPI payment.",
            "location": "Delhi",
        },
    )
    assert manual_response.status_code == 201
    manual_body = manual_response.json()
    assert manual_body["entry_mode"] == "manual"

    update_response = client.put(
        f"/api/incidents/{manual_body['id']}",
        json={"status": "verified", "severity": "critical"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "verified"
    assert updated["severity"] == "critical"

    import_response = client.post(
        "/api/feed/import",
        json={"reset_existing": True, "max_items": 2},
    )
    assert import_response.status_code == 200

    all_incidents = client.get("/api/incidents").json()
    manual_ids = [i["id"] for i in all_incidents if i["entry_mode"] == "manual"]
    assert manual_body["id"] in manual_ids
