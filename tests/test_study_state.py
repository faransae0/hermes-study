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
