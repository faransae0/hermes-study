"""Tests for study_state.py — subjects/sources/notes SQLite layer."""

from pathlib import Path

import pytest

import study_state as state


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "study.db"


def test_create_and_get_subject(db_path):
    subject_id = state.create_subject("Quantum Mechanics", "Intro course", db_path=db_path)
    assert subject_id

    subject = state.get_subject(subject_id, db_path=db_path)
    assert subject is not None
    assert subject["title"] == "Quantum Mechanics"
    assert subject["description"] == "Intro course"
    assert subject["id"] == subject_id
    assert subject["created_at"]


def test_get_subject_missing_returns_none(db_path):
    assert state.get_subject("does-not-exist", db_path=db_path) is None


def test_list_subjects_returns_all_in_creation_order(db_path):
    first_id = state.create_subject("Physics", db_path=db_path)
    second_id = state.create_subject("Chemistry", db_path=db_path)

    subjects = state.list_subjects(db_path=db_path)
    assert [s["id"] for s in subjects] == [first_id, second_id]


def test_connect_closing_actually_closes_connection(db_path):
    with state.connect_closing(db_path=db_path) as conn:
        conn.execute("SELECT 1")
    with pytest.raises(Exception):
        conn.execute("SELECT 1")  # connection is closed, must raise


def test_add_source_defaults_to_pending(db_path):
    subject_id = state.create_subject("Biology", db_path=db_path)
    source_id = state.add_source(subject_id, "url", "https://example.com/article", db_path=db_path)

    source = state.get_source(source_id, db_path=db_path)
    assert source["subject_id"] == subject_id
    assert source["type"] == "url"
    assert source["origin"] == "https://example.com/article"
    assert source["status"] == "pending"
    assert source["error_message"] is None
    assert source["raw_text_path"] is None


def test_update_source_status_sets_error_message(db_path):
    subject_id = state.create_subject("Biology", db_path=db_path)
    source_id = state.add_source(subject_id, "pdf", "/tmp/notes.pdf", db_path=db_path)

    state.update_source_status(source_id, "error", error_message="corrupt file", db_path=db_path)

    source = state.get_source(source_id, db_path=db_path)
    assert source["status"] == "error"
    assert source["error_message"] == "corrupt file"


def test_update_source_status_sets_raw_text_path(db_path):
    subject_id = state.create_subject("Biology", db_path=db_path)
    source_id = state.add_source(subject_id, "url", "https://example.com", db_path=db_path)

    state.update_source_status(source_id, "summarizing", raw_text_path="/cache/abc.txt", db_path=db_path)

    source = state.get_source(source_id, db_path=db_path)
    assert source["status"] == "summarizing"
    assert source["raw_text_path"] == "/cache/abc.txt"


def test_update_source_status_clears_error_message_on_successful_retry(db_path):
    subject_id = state.create_subject("Biology", db_path=db_path)
    source_id = state.add_source(subject_id, "pdf", "/tmp/notes.pdf", db_path=db_path)

    state.update_source_status(source_id, "error", error_message="corrupt file", db_path=db_path)
    state.update_source_status(source_id, "extracting", raw_text_path="/cache/abc.txt", db_path=db_path)
    state.update_source_status(source_id, "ready", db_path=db_path)

    source = state.get_source(source_id, db_path=db_path)
    assert source["status"] == "ready"
    assert source["error_message"] is None
    # raw_text_path keeps its existing COALESCE-preserve behavior — a retry
    # succeeding should not wipe out previously-cached raw text.
    assert source["raw_text_path"] == "/cache/abc.txt"


def test_list_sources_for_subject_only_returns_that_subjects_sources(db_path):
    subject_a = state.create_subject("Subject A", db_path=db_path)
    subject_b = state.create_subject("Subject B", db_path=db_path)
    source_a = state.add_source(subject_a, "url", "https://a.example.com", db_path=db_path)
    state.add_source(subject_b, "url", "https://b.example.com", db_path=db_path)

    sources = state.list_sources_for_subject(subject_a, db_path=db_path)
    assert [s["id"] for s in sources] == [source_a]


def test_upsert_note_then_get_note_for_source(db_path):
    subject_id = state.create_subject("Math", db_path=db_path)
    source_id = state.add_source(subject_id, "url", "https://example.com", db_path=db_path)

    note_id = state.upsert_note(
        source_id, "**Summary**\n\nDetails here.", ["derivatives", "limits"], db_path=db_path
    )
    assert note_id

    note = state.get_note_for_source(source_id, db_path=db_path)
    assert note["id"] == note_id
    assert note["source_id"] == source_id
    assert note["summary_md"] == "**Summary**\n\nDetails here."
    assert note["key_concepts"] == ["derivatives", "limits"]


def test_upsert_note_replaces_existing_note_for_same_source(db_path):
    subject_id = state.create_subject("Math", db_path=db_path)
    source_id = state.add_source(subject_id, "url", "https://example.com", db_path=db_path)

    first_id = state.upsert_note(source_id, "first draft", ["a"], db_path=db_path)
    second_id = state.upsert_note(source_id, "revised", ["a", "b"], db_path=db_path)

    note = state.get_note_for_source(source_id, db_path=db_path)
    assert note["summary_md"] == "revised"
    assert note["key_concepts"] == ["a", "b"]
    assert note["id"] == second_id
    assert first_id != second_id  # confirms the old row was replaced, not left behind


def test_list_notes_for_subject(db_path):
    subject_id = state.create_subject("Math", db_path=db_path)
    source_id = state.add_source(subject_id, "url", "https://example.com", db_path=db_path)
    state.upsert_note(source_id, "summary", ["x"], db_path=db_path)

    notes = state.list_notes_for_subject(subject_id, db_path=db_path)
    assert len(notes) == 1
    assert notes[0]["source_id"] == source_id
    assert notes[0]["summary_md"] == "summary"


def test_add_chat_message_and_list_for_subject(db_path):
    subject_id = state.create_subject("History", db_path=db_path)

    state.add_chat_message(subject_id, "user", "What caused WWI?", db_path=db_path)
    state.add_chat_message(subject_id, "assistant", "A mix of alliances and...", db_path=db_path)

    messages = state.list_chat_messages_for_subject(subject_id, db_path=db_path)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "What caused WWI?"
    assert all(m["subject_id"] == subject_id for m in messages)
    assert all(m["created_at"] for m in messages)


def test_add_chat_message_rejects_invalid_role(db_path):
    subject_id = state.create_subject("History", db_path=db_path)
    with pytest.raises(ValueError, match="invalid chat message role"):
        state.add_chat_message(subject_id, "system", "nope", db_path=db_path)


def test_list_chat_messages_isolated_per_subject(db_path):
    subject_a = state.create_subject("Subject A", db_path=db_path)
    subject_b = state.create_subject("Subject B", db_path=db_path)

    state.add_chat_message(subject_a, "user", "message for A", db_path=db_path)
    state.add_chat_message(subject_b, "user", "message for B", db_path=db_path)

    messages_a = state.list_chat_messages_for_subject(subject_a, db_path=db_path)
    assert len(messages_a) == 1
    assert messages_a[0]["content"] == "message for A"


def test_list_chat_messages_ordered_by_created_at(db_path):
    subject_id = state.create_subject("Ordering", db_path=db_path)
    for i in range(5):
        state.add_chat_message(subject_id, "user", f"msg {i}", db_path=db_path)

    messages = state.list_chat_messages_for_subject(subject_id, db_path=db_path)
    assert [m["content"] for m in messages] == [f"msg {i}" for i in range(5)]
