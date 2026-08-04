"""Tests for hermes_cli/study.py's subject/ingest/notes command handlers."""

from __future__ import annotations

import argparse
import json
from unittest.mock import patch

import pytest

import study_state as state
from hermes_cli.study import cmd_study


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "study.db"
    monkeypatch.setenv("HERMES_STUDY_DB", str(path))
    return path


def _ns(**kw):
    defaults = dict(
        study_command=None,
        study_subject_command=None,
        title=None,
        description=None,
        subject_id=None,
        source_type=None,
        origin=None,
        json=False,
    )
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def test_subject_create_creates_and_prints(db_path, capsys):
    cmd_study(_ns(study_command="subject", study_subject_command="create", title="Biology", description="Cells"))

    subjects = state.list_subjects(db_path=db_path)
    assert len(subjects) == 1
    assert subjects[0]["title"] == "Biology"
    assert subjects[0]["description"] == "Cells"
    out = capsys.readouterr().out
    assert subjects[0]["id"] in out


def test_subject_create_defaults_empty_description(db_path):
    cmd_study(_ns(study_command="subject", study_subject_command="create", title="Physics", description=None))

    subjects = state.list_subjects(db_path=db_path)
    assert subjects[0]["description"] == ""


def test_subject_create_json_output(db_path, capsys):
    cmd_study(_ns(study_command="subject", study_subject_command="create", title="Biology", description="Cells", json=True))

    out = json.loads(capsys.readouterr().out)
    assert out["title"] == "Biology"
    assert out["description"] == "Cells"
    assert out["id"]
    assert out["created_at"]


def test_subject_list_json_output(db_path, capsys):
    state.create_subject("Alpha", db_path=db_path)
    state.create_subject("Beta", db_path=db_path)

    cmd_study(_ns(study_command="subject", study_subject_command="list", json=True))

    out = json.loads(capsys.readouterr().out)
    assert {s["title"] for s in out} == {"Alpha", "Beta"}
    assert all(set(s.keys()) == {"id", "title", "source_count"} for s in out)


def test_subject_list_json_empty(db_path, capsys):
    cmd_study(_ns(study_command="subject", study_subject_command="list", json=True))

    out = json.loads(capsys.readouterr().out)
    assert out == []


def test_require_subject_json_error_via_ingest(db_path, capsys):
    with pytest.raises(SystemExit):
        cmd_study(_ns(study_command="ingest", subject_id="nope", source_type="url", origin="https://x.com", json=True))

    out = json.loads(capsys.readouterr().out)
    assert "error" in out
    assert "nope" in out["error"]


def test_subject_list_prints_each_subject(db_path, capsys):
    state.create_subject("Alpha", db_path=db_path)
    state.create_subject("Beta", db_path=db_path)

    cmd_study(_ns(study_command="subject", study_subject_command="list"))

    out = capsys.readouterr().out
    assert "Alpha" in out
    assert "Beta" in out


def test_subject_list_empty_prints_hint(db_path, capsys):
    cmd_study(_ns(study_command="subject", study_subject_command="list"))
    out = capsys.readouterr().out
    assert "hermes study subject create" in out


def test_ingest_rejects_unknown_subject_id(db_path, capsys):
    with pytest.raises(SystemExit):
        cmd_study(_ns(study_command="ingest", subject_id="nope", source_type="url", origin="https://x.com"))
    out = capsys.readouterr().out
    assert "No subject found" in out


def test_ingest_calls_ingest_source_and_reports_success(db_path, capsys):
    subject_id = state.create_subject("Chemistry", db_path=db_path)

    async def _fake_ingest_source(*a, **kw):
        return {"success": True, "source_id": "src-1", "error": ""}

    with patch("hermes_cli.study.ingest_source", side_effect=_fake_ingest_source):
        cmd_study(_ns(study_command="ingest", subject_id=subject_id, source_type="url", origin="https://x.com"))

    out = capsys.readouterr().out
    assert "src-1" in out


def test_ingest_reports_failure_and_exits_nonzero(db_path, capsys):
    subject_id = state.create_subject("Chemistry", db_path=db_path)

    async def _fake_ingest_source(*a, **kw):
        return {"success": False, "source_id": "src-1", "error": "extraction failed"}

    with patch("hermes_cli.study.ingest_source", side_effect=_fake_ingest_source):
        with pytest.raises(SystemExit):
            cmd_study(_ns(study_command="ingest", subject_id=subject_id, source_type="url", origin="https://x.com"))
    out = capsys.readouterr().out
    assert "extraction failed" in out


def test_notes_rejects_unknown_subject_id(db_path):
    with pytest.raises(SystemExit):
        cmd_study(_ns(study_command="notes", subject_id="nope"))


def test_notes_prints_summaries(db_path, capsys):
    subject_id = state.create_subject("History", db_path=db_path)
    source_id = state.add_source(subject_id, "url", "https://x.com", db_path=db_path)
    state.upsert_note(source_id, "**Overview**\n\nWWI began in 1914.", ["alliances", "1914"], db_path=db_path)

    cmd_study(_ns(study_command="notes", subject_id=subject_id))

    out = capsys.readouterr().out
    assert "WWI began in 1914" in out
    assert "alliances" in out


def test_notes_no_notes_prints_hint(db_path, capsys):
    subject_id = state.create_subject("History", db_path=db_path)
    cmd_study(_ns(study_command="notes", subject_id=subject_id))
    out = capsys.readouterr().out
    assert "No notes yet" in out
