"""SQLite database layer for incident storage."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app import config

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS incidents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL,
    location    TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    severity    TEXT    NOT NULL DEFAULT 'medium',
    confidence  REAL    NOT NULL DEFAULT 0.5,
    summary     TEXT    NOT NULL DEFAULT '',
    checklist   TEXT    NOT NULL DEFAULT '[]',
    source      TEXT    NOT NULL DEFAULT 'fallback',
    reasoning   TEXT    NOT NULL DEFAULT '',
    entry_mode  TEXT    NOT NULL DEFAULT 'manual',
    status      TEXT    NOT NULL DEFAULT 'new',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    raw_event   TEXT    NOT NULL DEFAULT '{}'
);
"""


_shared_conn: Optional[sqlite3.Connection] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    global _shared_conn
    # For :memory: databases, reuse a single connection
    if config.DATABASE_PATH == ":memory:":
        if _shared_conn is None:
            _shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            _shared_conn.row_factory = sqlite3.Row
        return _shared_conn
    Path(config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["checklist"] = json.loads(d["checklist"])
    if d.get("raw_event"):
        d["raw_event"] = json.loads(d["raw_event"])
    return d


# ---- Lifecycle ----

def init_db() -> None:
    conn = _conn()
    conn.execute(_CREATE_TABLE)
    conn.commit()


def reset_db() -> None:
    """Drop and recreate – used by tests."""
    global _shared_conn
    if config.DATABASE_PATH == ":memory:" and _shared_conn is not None:
        _shared_conn.execute("DROP TABLE IF EXISTS incidents")
        _shared_conn.execute(_CREATE_TABLE)
        _shared_conn.commit()
    else:
        _shared_conn = None
        with _conn() as conn:
            conn.execute("DROP TABLE IF EXISTS incidents")
            conn.execute(_CREATE_TABLE)


# ---- CRUD ----

def insert_incident(
    title: str,
    description: str,
    location: str,
    category: str,
    severity: str,
    confidence: float,
    summary: str,
    checklist: list[str],
    source: str,
    reasoning: str,
    entry_mode: str = "manual",
    raw_event: Optional[dict] = None,
    created_at: Optional[str] = None,
) -> dict:
    now = _now()
    conn = _conn()
    cur = conn.execute(
        """INSERT INTO incidents
           (title, description, location, category, severity, confidence,
            summary, checklist, source, reasoning, entry_mode, status,
            created_at, updated_at, raw_event)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            title, description, location, category, severity, confidence,
            summary, json.dumps(checklist), source, reasoning,
            entry_mode, "new", created_at or now, now, json.dumps(raw_event or {}),
        ),
    )
    conn.commit()
    return get_incident(cur.lastrowid)


def get_incident(incident_id: int) -> Optional[dict]:
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM incidents WHERE id = ?", (incident_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def get_incidents(
    search: str = "",
    status: str = "",
    severity: str = "",
    category: str = "",
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return (incidents_list, total_count) with filters applied."""
    clauses: list[str] = []
    params: list = []

    if search:
        clauses.append(
            "(LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(location) LIKE ?)"
        )
        q = f"%{search.lower()}%"
        params.extend([q, q, q])

    if status:
        clauses.append("status = ?")
        params.append(status)

    if severity:
        clauses.append("severity = ?")
        params.append(severity)

    if category:
        clauses.append("category = ?")
        params.append(category)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    conn = _conn()
    total = conn.execute(
        f"SELECT COUNT(*) FROM incidents {where}", params
    ).fetchone()[0]

    rows = conn.execute(
        f"""SELECT * FROM incidents {where}
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high'     THEN 2
                    WHEN 'medium'   THEN 3
                    WHEN 'low'      THEN 4
                END,
                created_at DESC
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    return [_row_to_dict(r) for r in rows], total


def update_incident(incident_id: int, **updates) -> Optional[dict]:
    allowed = {"status", "severity"}
    fields = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not fields:
        return get_incident(incident_id)

    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [incident_id]

    conn = _conn()
    conn.execute(f"UPDATE incidents SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return get_incident(incident_id)


def reanalyze_incident(
    incident_id: int,
    category: str,
    severity: str,
    confidence: float,
    summary: str,
    checklist: list[str],
    source: str,
    reasoning: str,
) -> Optional[dict]:
    now = _now()
    conn = _conn()
    conn.execute(
        """UPDATE incidents SET
            category=?, severity=?, confidence=?, summary=?,
            checklist=?, source=?, reasoning=?, updated_at=?
           WHERE id=?""",
        (
            category, severity, confidence, summary,
            json.dumps(checklist), source, reasoning, now,
            incident_id,
        ),
    )
    conn.commit()
    return get_incident(incident_id)


def get_stats() -> dict:
    conn = _conn()
    total = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]

    by_severity = {}
    for row in conn.execute(
        "SELECT severity, COUNT(*) as cnt FROM incidents GROUP BY severity"
    ):
        by_severity[row["severity"]] = row["cnt"]

    by_category = {}
    for row in conn.execute(
        "SELECT category, COUNT(*) as cnt FROM incidents GROUP BY category"
    ):
        by_category[row["category"]] = row["cnt"]

    by_source = {}
    for row in conn.execute(
        "SELECT source, COUNT(*) as cnt FROM incidents GROUP BY source"
    ):
        by_source[row["source"]] = row["cnt"]

    avg_row = conn.execute(
        "SELECT AVG(confidence) as avg_conf FROM incidents"
    ).fetchone()
    avg_confidence = round(avg_row["avg_conf"] or 0.0, 2)

    return {
        "total": total,
        "by_severity": by_severity,
        "by_category": by_category,
        "by_source": by_source,
        "avg_confidence": avg_confidence,
    }


def delete_feed_incidents() -> int:
    """Delete all feed-imported incidents, preserve manual entries."""
    conn = _conn()
    cur = conn.execute("DELETE FROM incidents WHERE entry_mode = 'feed'")
    conn.commit()
    return cur.rowcount


def check_duplicate(title: str, location: str) -> bool:
    conn = _conn()
    row = conn.execute(
        "SELECT 1 FROM incidents WHERE LOWER(title)=? AND LOWER(location)=?",
        (title.lower(), location.lower()),
    ).fetchone()
    return row is not None


def get_fallback_manual_incidents() -> list[dict]:
    """Return manual incidents that were analyzed by fallback (candidates for AI reanalysis)."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM incidents WHERE entry_mode = 'manual' AND source = 'fallback'"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_manual_incidents_by_source(source: str) -> list[dict]:
    """Return manual incidents analyzed by the given source (candidates for reanalysis)."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM incidents WHERE entry_mode = 'manual' AND source = ?",
        (source,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]
