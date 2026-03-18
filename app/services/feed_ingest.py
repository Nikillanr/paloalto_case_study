import json
from pathlib import Path

from app.models import Incident
from app.services.classifier import analyze_incident


def _normalize_feed_event(row: dict) -> tuple[str, str, str] | None:
    title = str(row.get("headline") or row.get("title") or "").strip()
    description = str(
        row.get("details") or row.get("description") or row.get("content") or ""
    ).strip()
    location = str(row.get("region") or row.get("location") or "Unknown").strip()

    if len(title) < 3 or len(description) < 10 or len(location) < 2:
        return None

    return title[:120], description[:2000], location[:120]


def import_feed_events(
    *,
    feed_path: Path,
    existing_incidents: list[Incident],
    ai_enabled: bool,
    max_items: int | None,
    reset_existing: bool,
) -> tuple[list[Incident], int]:
    if not feed_path.exists():
        raise FileNotFoundError(f"Feed file not found at {feed_path}")

    rows = json.loads(feed_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Feed file must contain a JSON list")

    if reset_existing:
        # Keep manual entries while rebuilding feed-derived incidents.
        current = [i for i in existing_incidents if i.entry_mode == "manual"]
    else:
        current = list(existing_incidents)
    seen = {(i.title.lower(), i.description.lower(), i.location.lower()) for i in current}
    next_id = max((i.id for i in current), default=0) + 1
    imported = 0

    candidates = rows if max_items is None else rows[:max_items]
    for row in candidates:
        if not isinstance(row, dict):
            continue

        normalized = _normalize_feed_event(row)
        if not normalized:
            continue

        title, description, location = normalized
        sig = (title.lower(), description.lower(), location.lower())
        if sig in seen:
            continue

        analysis = analyze_incident(title=title, description=description, ai_enabled=ai_enabled)
        current.append(
            Incident(
                id=next_id,
                title=title,
                description=description,
                location=location,
                category=analysis["category"],
                severity=analysis["severity"],
                status="new",
                summary=analysis["summary"],
                checklist=analysis["checklist"],
                source=analysis["source"],
                entry_mode="feed",
            )
        )
        seen.add(sig)
        imported += 1
        next_id += 1

    return current, imported
