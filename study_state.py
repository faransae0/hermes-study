"""SQLite-backed state for study-desktop: subjects, sources, notes.

A deliberately simple, single-user-desktop-scoped sibling to
hermes_cli/kanban_db.py — no multi-board routing, no cross-process init
lock, because study.db has exactly one writer (the local `hermes study`
process) instead of a multi-worker dispatcher's concurrent claimers.

The one safety property borrowed unchanged from kanban_db.py:
sqlite3's own `with conn:` context manager only commits/rolls back a
transaction, it does NOT close the file descriptor. Every connection
opened here MUST go through connect_closing() (or be closed manually) —
see relatorio-issue-69678-sqlite-fd-leaks.md for the incident this
pattern exists to prevent.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS subjects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    type TEXT NOT NULL CHECK(type IN ('url','pdf','youtube')),
    origin TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','extracting','summarizing','ready','error')),
    error_message TEXT,
    raw_text_path TEXT,
    added_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sources_subject_id ON sources(subject_id);

CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL UNIQUE REFERENCES sources(id),
    summary_md TEXT NOT NULL,
    key_concepts TEXT NOT NULL,
    generated_at TEXT NOT NULL
);
"""

_INITIALIZED_PATHS: set[str] = set()


def study_db_path() -> Path:
    """Resolve the study.db path: HERMES_STUDY_DB env override, else <hermes home>/study.db."""
    override = os.environ.get("HERMES_STUDY_DB", "").strip()
    if override:
        return Path(override).expanduser()
    from hermes_constants import get_hermes_home

    return get_hermes_home() / "study.db"


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open (and initialize if needed) the study DB. Caller MUST close it (prefer connect_closing)."""
    path = db_path if db_path is not None else study_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    try:
        conn.row_factory = sqlite3.Row
        from hermes_state import apply_wal_with_fallback

        apply_wal_with_fallback(conn, db_label=f"study.db ({path.name})")
        conn.execute("PRAGMA foreign_keys=ON")

        resolved = str(path.resolve())
        if resolved not in _INITIALIZED_PATHS:
            conn.executescript(SCHEMA_SQL)
            _INITIALIZED_PATHS.add(resolved)
    except Exception:
        conn.close()
        raise
    return conn


@contextlib.contextmanager
def connect_closing(db_path: Optional[Path] = None):
    """Open a study DB connection and guarantee it is closed on exit.

    Use this instead of raw connect() for any short-lived operation —
    sqlite3's built-in connection context manager does not close the file
    descriptor. See module docstring.
    """
    conn = connect(db_path=db_path)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_subject(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "created_at": row["created_at"],
    }


def create_subject(title: str, description: str = "", *, db_path: Optional[Path] = None) -> str:
    subject_id = uuid.uuid4().hex
    with connect_closing(db_path) as conn:
        conn.execute(
            "INSERT INTO subjects (id, title, description, created_at) VALUES (?, ?, ?, ?)",
            (subject_id, title, description, _now()),
        )
        conn.commit()
    return subject_id


def get_subject(subject_id: str, *, db_path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    with connect_closing(db_path) as conn:
        row = conn.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone()
    return _row_to_subject(row) if row is not None else None


def list_subjects(*, db_path: Optional[Path] = None) -> list[dict[str, Any]]:
    with connect_closing(db_path) as conn:
        rows = conn.execute("SELECT * FROM subjects ORDER BY created_at ASC").fetchall()
    return [_row_to_subject(row) for row in rows]
