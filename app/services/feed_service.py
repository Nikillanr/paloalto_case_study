"""Feed ingestion service — loads, normalizes, and deduplicates external events."""

from __future__ import annotations
import json
from pathlib import Path
from app.models import FeedEvent
from app import config

# Field name mappings for normalization
_TITLE_FIELDS = ("title", "headline", "subject", "name")
_DESC_FIELDS = ("description", "details", "content", "body", "text")
_LOC_FIELDS = ("location", "region", "area", "city", "place")
_SRC_FIELDS = ("source", "feed_source", "origin", "reported_by")
_TIME_FIELDS = ("reported_at", "timestamp", "date", "created_at", "time")


def _normalize_event(raw: dict) -> FeedEvent | None:
    """Normalize a raw feed event into a FeedEvent, or None if unusable."""
    title = ""
    for f in _TITLE_FIELDS:
        if f in raw and raw[f]:
            title = str(raw[f]).strip()
            break

    description = ""
    for f in _DESC_FIELDS:
        if f in raw and raw[f]:
            description = str(raw[f]).strip()
            break

    location = ""
    for f in _LOC_FIELDS:
        if f in raw and raw[f]:
            location = str(raw[f]).strip()
            break

    source = "unknown"
    for f in _SRC_FIELDS:
        if f in raw and raw[f]:
            source = str(raw[f]).strip()
            break

    reported_at = ""
    for f in _TIME_FIELDS:
        if f in raw and raw[f]:
            reported_at = str(raw[f]).strip()
            break

    if not title or not description or not location:
        return None

    return FeedEvent(
        title=title,
        description=description,
        location=location,
        source=source,
        reported_at=reported_at,
    )


def load_events(path: str | None = None) -> list[FeedEvent]:
    """Load and normalize events from the seed JSON file."""
    feed_path = Path(path or config.FEED_PATH)
    if not feed_path.exists():
        return []

    with open(feed_path, "r") as f:
        raw_list = json.load(f)

    if not isinstance(raw_list, list):
        return []

    events = []
    for raw in raw_list:
        if isinstance(raw, dict):
            ev = _normalize_event(raw)
            if ev:
                events.append(ev)
    return events


def get_preview(path: str | None = None) -> dict:
    """Return feed summary: total count and first 3 samples."""
    events = load_events(path)
    return {
        "total": len(events),
        "samples": [e.model_dump() for e in events[:3]],
    }
