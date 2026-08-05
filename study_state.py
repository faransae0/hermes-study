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
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
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

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_subject_id ON chat_messages(subject_id);

CREATE TABLE IF NOT EXISTS flashcards (
    id TEXT PRIMARY KEY,
    note_id TEXT NOT NULL REFERENCES notes(id),
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 0,
    repetitions INTEGER NOT NULL DEFAULT 0,
    next_review_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_flashcards_note_id ON flashcards(note_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_next_review_at ON flashcards(next_review_at);
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


def _row_to_source(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "subject_id": row["subject_id"],
        "type": row["type"],
        "origin": row["origin"],
        "status": row["status"],
        "error_message": row["error_message"],
        "raw_text_path": row["raw_text_path"],
        "added_at": row["added_at"],
    }


def add_source(subject_id: str, source_type: str, origin: str, *, db_path: Optional[Path] = None) -> str:
    source_id = uuid.uuid4().hex
    with connect_closing(db_path) as conn:
        conn.execute(
            "INSERT INTO sources (id, subject_id, type, origin, status, added_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (source_id, subject_id, source_type, origin, _now()),
        )
        conn.commit()
    return source_id


def update_source_status(
    source_id: str,
    status: str,
    *,
    error_message: Optional[str] = None,
    raw_text_path: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    with connect_closing(db_path) as conn:
        conn.execute(
            "UPDATE sources SET status = :status, "
            "error_message = CASE "
            "    WHEN :error_message IS NOT NULL THEN :error_message "
            "    WHEN :status = 'error' THEN error_message "
            "    ELSE NULL "
            "END, "
            "raw_text_path = COALESCE(:raw_text_path, raw_text_path) "
            "WHERE id = :source_id",
            {
                "status": status,
                "error_message": error_message,
                "raw_text_path": raw_text_path,
                "source_id": source_id,
            },
        )
        conn.commit()


def get_source(source_id: str, *, db_path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    with connect_closing(db_path) as conn:
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    return _row_to_source(row) if row is not None else None


def list_sources_for_subject(subject_id: str, *, db_path: Optional[Path] = None) -> list[dict[str, Any]]:
    with connect_closing(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM sources WHERE subject_id = ? ORDER BY added_at ASC", (subject_id,)
        ).fetchall()
    return [_row_to_source(row) for row in rows]


def _row_to_note(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source_id": row["source_id"],
        "summary_md": row["summary_md"],
        "key_concepts": json.loads(row["key_concepts"]),
        "generated_at": row["generated_at"],
    }


def upsert_note(
    source_id: str, summary_md: str, key_concepts: list[str], *, db_path: Optional[Path] = None
) -> str:
    note_id = uuid.uuid4().hex
    with connect_closing(db_path) as conn:
        conn.execute("DELETE FROM notes WHERE source_id = ?", (source_id,))
        conn.execute(
            "INSERT INTO notes (id, source_id, summary_md, key_concepts, generated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (note_id, source_id, summary_md, json.dumps(key_concepts), _now()),
        )
        conn.commit()
    return note_id


def get_note_for_source(source_id: str, *, db_path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    with connect_closing(db_path) as conn:
        row = conn.execute("SELECT * FROM notes WHERE source_id = ?", (source_id,)).fetchone()
    return _row_to_note(row) if row is not None else None


def list_notes_for_subject(subject_id: str, *, db_path: Optional[Path] = None) -> list[dict[str, Any]]:
    with connect_closing(db_path) as conn:
        rows = conn.execute(
            "SELECT notes.* FROM notes "
            "JOIN sources ON sources.id = notes.source_id "
            "WHERE sources.subject_id = ? "
            "ORDER BY notes.generated_at ASC",
            (subject_id,),
        ).fetchall()
    return [_row_to_note(row) for row in rows]


def _row_to_chat_message(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "subject_id": row["subject_id"],
        "role": row["role"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def add_chat_message(
    subject_id: str, role: str, content: str, *, db_path: Optional[Path] = None
) -> str:
    if role not in ("user", "assistant"):
        raise ValueError(f"invalid chat message role: {role!r}")
    message_id = uuid.uuid4().hex
    with connect_closing(db_path) as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, subject_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (message_id, subject_id, role, content, _now()),
        )
        conn.commit()
    return message_id


def list_chat_messages_for_subject(
    subject_id: str, *, db_path: Optional[Path] = None
) -> list[dict[str, Any]]:
    with connect_closing(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE subject_id = ? ORDER BY created_at ASC",
            (subject_id,),
        ).fetchall()
    return [_row_to_chat_message(row) for row in rows]


def _row_to_flashcard(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "note_id": row["note_id"],
        "front": row["front"],
        "back": row["back"],
        "ease_factor": row["ease_factor"],
        "interval_days": row["interval_days"],
        "repetitions": row["repetitions"],
        "next_review_at": row["next_review_at"],
        "created_at": row["created_at"],
    }


def create_flashcards(
    note_id: str, cards: list[dict[str, str]], *, db_path: Optional[Path] = None
) -> list[str]:
    card_ids = [uuid.uuid4().hex for _ in cards]
    now = _now()
    with connect_closing(db_path) as conn:
        conn.execute("DELETE FROM flashcards WHERE note_id = ?", (note_id,))
        conn.executemany(
            "INSERT INTO flashcards "
            "(id, note_id, front, back, ease_factor, interval_days, repetitions, next_review_at, created_at) "
            "VALUES (?, ?, ?, ?, 2.5, 0, 0, ?, ?)",
            [
                (card_id, note_id, card["front"], card["back"], now, now)
                for card_id, card in zip(card_ids, cards)
            ],
        )
        conn.commit()
    return card_ids


def list_flashcards_for_note(note_id: str, *, db_path: Optional[Path] = None) -> list[dict[str, Any]]:
    with connect_closing(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM flashcards WHERE note_id = ? ORDER BY created_at ASC", (note_id,)
        ).fetchall()
    return [_row_to_flashcard(row) for row in rows]


def list_due_flashcards(
    subject_id: str, *, now: Optional[str] = None, db_path: Optional[Path] = None
) -> list[dict[str, Any]]:
    cutoff = now if now is not None else _now()
    with connect_closing(db_path) as conn:
        rows = conn.execute(
            "SELECT flashcards.* FROM flashcards "
            "JOIN notes ON notes.id = flashcards.note_id "
            "JOIN sources ON sources.id = notes.source_id "
            "WHERE sources.subject_id = ? AND flashcards.next_review_at <= ? "
            "ORDER BY flashcards.next_review_at ASC",
            (subject_id, cutoff),
        ).fetchall()
    return [_row_to_flashcard(row) for row in rows]


def record_review(
    flashcard_id: str, quality: int, *, db_path: Optional[Path] = None
) -> Optional[dict[str, Any]]:
    from study_sm2 import compute_sm2_update

    with connect_closing(db_path) as conn:
        row = conn.execute("SELECT * FROM flashcards WHERE id = ?", (flashcard_id,)).fetchone()
        if row is None:
            return None

        new_ease_factor, new_interval_days, new_repetitions = compute_sm2_update(
            row["ease_factor"], row["interval_days"], row["repetitions"], quality
        )
        next_review_at = (datetime.now(timezone.utc) + timedelta(days=new_interval_days)).isoformat()

        conn.execute(
            "UPDATE flashcards SET ease_factor = ?, interval_days = ?, repetitions = ?, next_review_at = ? "
            "WHERE id = ?",
            (new_ease_factor, new_interval_days, new_repetitions, next_review_at, flashcard_id),
        )
        conn.commit()

        updated = conn.execute("SELECT * FROM flashcards WHERE id = ?", (flashcard_id,)).fetchone()
    return _row_to_flashcard(updated)
