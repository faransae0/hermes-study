"""Tests for hermes_cli/study.py's chat-turn command (non-interactive, single-turn)."""

from __future__ import annotations

import argparse
import json
from unittest.mock import MagicMock, patch

import pytest

import study_state as state
from hermes_cli.study import cmd_study


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "study.db"
    monkeypatch.setenv("HERMES_STUDY_DB", str(path))
    return path


def _ns(**kw):
    defaults = dict(study_command="chat-turn", subject_id=None, message=None, json=True)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def test_chat_turn_rejects_unknown_subject_id(db_path, capsys):
    with pytest.raises(SystemExit):
        cmd_study(_ns(subject_id="nope", message="hi"))

    out = json.loads(capsys.readouterr().out)
    assert "error" in out


def test_chat_turn_success_persists_both_turns_and_prints_reply(db_path, capsys):
    subject_id = state.create_subject("Physics", db_path=db_path)

    fake_agent = MagicMock()
    fake_agent.run_conversation.return_value = {
        "final_response": "Inertia is the tendency to resist changes in motion.",
        "messages": [],
    }

    with (
        patch("hermes_cli.study.AIAgent", return_value=fake_agent) as mock_agent_cls,
        patch("hermes_cli.study.SessionDB"),
    ):
        cmd_study(_ns(subject_id=subject_id, message="What is inertia?"))

    out = json.loads(capsys.readouterr().out)
    assert out == {"reply": "Inertia is the tendency to resist changes in motion.", "error": None}

    messages = state.list_chat_messages_for_subject(subject_id, db_path=db_path)
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "What is inertia?"),
        ("assistant", "Inertia is the tendency to resist changes in motion."),
    ]

    # A fresh session every call — never reused across turns.
    assert mock_agent_cls.call_args.kwargs["enabled_toolsets"] == []
    assert mock_agent_cls.call_args.kwargs["platform"] == "study"


def test_chat_turn_failure_persists_nothing(db_path, capsys):
    subject_id = state.create_subject("Physics", db_path=db_path)

    fake_agent = MagicMock()
    fake_agent.run_conversation.return_value = {
        "failed": True,
        "error": "rate limit exceeded",
        "final_response": "",
        "messages": [],
    }

    with (
        patch("hermes_cli.study.AIAgent", return_value=fake_agent),
        patch("hermes_cli.study.SessionDB"),
    ):
        cmd_study(_ns(subject_id=subject_id, message="What is inertia?"))

    out = json.loads(capsys.readouterr().out)
    assert out == {"reply": None, "error": "rate limit exceeded"}

    messages = state.list_chat_messages_for_subject(subject_id, db_path=db_path)
    assert messages == []


def test_chat_turn_exception_persists_nothing(db_path, capsys):
    subject_id = state.create_subject("Physics", db_path=db_path)

    fake_agent = MagicMock()
    fake_agent.run_conversation.side_effect = RuntimeError("network error")

    with (
        patch("hermes_cli.study.AIAgent", return_value=fake_agent),
        patch("hermes_cli.study.SessionDB"),
    ):
        cmd_study(_ns(subject_id=subject_id, message="What is inertia?"))

    out = json.loads(capsys.readouterr().out)
    assert out == {"reply": None, "error": "network error"}

    messages = state.list_chat_messages_for_subject(subject_id, db_path=db_path)
    assert messages == []


def test_chat_turn_reconstructs_history_from_prior_messages(db_path):
    subject_id = state.create_subject("Physics", db_path=db_path)
    state.add_chat_message(subject_id, "user", "What is inertia?", db_path=db_path)
    state.add_chat_message(subject_id, "assistant", "Resistance to changes in motion.", db_path=db_path)

    fake_agent = MagicMock()
    fake_agent.run_conversation.return_value = {
        "final_response": "Yes — it's Newton's first law.",
        "messages": [],
    }

    with (
        patch("hermes_cli.study.AIAgent", return_value=fake_agent),
        patch("hermes_cli.study.SessionDB"),
    ):
        cmd_study(_ns(subject_id=subject_id, message="Is that Newton's first law?"))

    call_kwargs = fake_agent.run_conversation.call_args.kwargs
    assert call_kwargs["conversation_history"] == [
        {"role": "user", "content": "What is inertia?"},
        {"role": "assistant", "content": "Resistance to changes in motion."},
    ]
    assert call_kwargs["user_message"] == "Is that Newton's first law?"
