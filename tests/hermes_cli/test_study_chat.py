"""Tests for hermes_cli/study.py's chat command."""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

import study_state as state
from hermes_cli.study import _build_chat_system_message, cmd_study


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "study.db"
    monkeypatch.setenv("HERMES_STUDY_DB", str(path))
    return path


def _ns(**kw):
    defaults = dict(study_command="chat", subject_id=None)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def test_build_chat_system_message_with_notes():
    subject = {"id": "s1", "title": "Physics"}
    notes = [
        {"summary_md": "**Newton's laws.**\n\nThree laws of motion.", "key_concepts": ["inertia"]},
        {"summary_md": "**Thermodynamics.**\n\nEnergy conservation.", "key_concepts": ["entropy"]},
    ]
    message = _build_chat_system_message(subject, notes)
    assert "Physics" in message
    assert "Newton's laws" in message
    assert "Thermodynamics" in message


def test_build_chat_system_message_no_notes_yet():
    subject = {"id": "s1", "title": "Physics"}
    message = _build_chat_system_message(subject, [])
    assert "Physics" in message
    assert "hermes study ingest" in message


def test_chat_rejects_unknown_subject_id(db_path):
    with pytest.raises(SystemExit):
        cmd_study(_ns(subject_id="nope"))


def test_chat_loop_persists_messages_and_exits_on_quit(db_path):
    subject_id = state.create_subject("Physics", db_path=db_path)

    fake_agent = MagicMock()
    fake_agent.run_conversation.return_value = {
        "final_response": "Inertia is the tendency to resist changes in motion.",
        "messages": [
            {"role": "user", "content": "What is inertia?"},
            {"role": "assistant", "content": "Inertia is the tendency to resist changes in motion."},
        ],
    }

    with (
        patch("hermes_cli.study.AIAgent", return_value=fake_agent) as mock_agent_cls,
        patch("hermes_cli.study.SessionDB"),
        patch("builtins.input", side_effect=["What is inertia?", "exit"]),
    ):
        cmd_study(_ns(subject_id=subject_id))

    assert mock_agent_cls.call_args.kwargs["enabled_toolsets"] == []
    assert mock_agent_cls.call_args.kwargs["platform"] == "study"

    messages = state.list_chat_messages_for_subject(subject_id, db_path=db_path)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "What is inertia?"
    assert "Inertia" in messages[1]["content"]


def test_chat_loop_passes_system_message_and_grows_history_across_turns(db_path):
    """Two turns. Verifies ``system_message`` is passed on EVERY turn (not just
    the first) and that ``conversation_history`` is replaced with the previous
    turn's ``result["messages"]`` on the next call — mirroring the real
    production caller at cli.py:13897-14109. Whether turn 2's system_message
    actually changes anything server-side is governed by
    agent/conversation_loop.py's prompt-cache reuse (see this plan's Global
    Constraints); this test only pins the CLI's own call contract, which stays
    correct regardless of that server-side behavior.
    """
    subject_id = state.create_subject("Physics", db_path=db_path)

    turn_1_result = {
        "final_response": "Inertia is the tendency to resist changes in motion.",
        "messages": [
            {"role": "user", "content": "What is inertia?"},
            {"role": "assistant", "content": "Inertia is the tendency to resist changes in motion."},
        ],
    }
    turn_2_result = {
        "final_response": "Yes — it's Newton's first law.",
        "messages": turn_1_result["messages"] + [
            {"role": "user", "content": "Is that Newton's first law?"},
            {"role": "assistant", "content": "Yes — it's Newton's first law."},
        ],
    }
    fake_agent = MagicMock()
    fake_agent.run_conversation.side_effect = [turn_1_result, turn_2_result]

    with (
        patch("hermes_cli.study.AIAgent", return_value=fake_agent),
        patch("hermes_cli.study.SessionDB"),
        patch("builtins.input", side_effect=["What is inertia?", "Is that Newton's first law?", "exit"]),
    ):
        cmd_study(_ns(subject_id=subject_id))

    first_call_kwargs = fake_agent.run_conversation.call_args_list[0].kwargs
    second_call_kwargs = fake_agent.run_conversation.call_args_list[1].kwargs

    assert first_call_kwargs["system_message"] == second_call_kwargs["system_message"]
    assert first_call_kwargs["conversation_history"] == []
    assert second_call_kwargs["conversation_history"] == turn_1_result["messages"]

    messages = state.list_chat_messages_for_subject(subject_id, db_path=db_path)
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]


def test_chat_loop_skips_persisting_failed_result(db_path, capsys):
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
        patch("builtins.input", side_effect=["What is inertia?", "exit"]),
    ):
        cmd_study(_ns(subject_id=subject_id))

    out = capsys.readouterr().out
    assert "rate limit exceeded" in out

    messages = state.list_chat_messages_for_subject(subject_id, db_path=db_path)
    # user turn is persisted (matches normal chat UX — a failed message still
    # shows in the transcript), but no assistant row was added for the failure
    assert [m["role"] for m in messages] == ["user"]


def test_chat_loop_exits_cleanly_on_eof(db_path):
    subject_id = state.create_subject("Physics", db_path=db_path)

    with (
        patch("hermes_cli.study.AIAgent") as mock_agent_cls,
        patch("hermes_cli.study.SessionDB"),
        patch("builtins.input", side_effect=EOFError),
    ):
        cmd_study(_ns(subject_id=subject_id))

    mock_agent_cls.return_value.run_conversation.assert_not_called()
