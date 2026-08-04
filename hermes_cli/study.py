"""``hermes study`` command implementations.

Parser construction lives in ``hermes_cli/subcommands/study.py``; this
module holds the actual logic, dispatched from a single ``cmd_study()``
entry point that ``hermes_cli/main.py`` forwards into (mirrors
``hermes_cli/dashboard_register.py``'s relationship to ``main.py``).
"""

from __future__ import annotations

import asyncio
import sys
import uuid

import study_state as state
from hermes_state import SessionDB
from run_agent import AIAgent
from tools.study_ingest_tool import ingest_source


def _cmd_subject_create(args) -> None:
    subject_id = state.create_subject(args.title, args.description or "")
    print(f"Created subject {subject_id}: {args.title}")


def _cmd_subject_list(args) -> None:
    subjects = state.list_subjects()
    if not subjects:
        print("No subjects yet. Create one with: hermes study subject create <title>")
        return
    for subject in subjects:
        source_count = len(state.list_sources_for_subject(subject["id"]))
        print(f"{subject['id']}  {subject['title']}  ({source_count} source(s))")


def _require_subject(subject_id: str) -> dict:
    subject = state.get_subject(subject_id)
    if subject is None:
        print(f"No subject found with id {subject_id!r}. Run: hermes study subject list")
        sys.exit(1)
    return subject


def _cmd_ingest(args) -> None:
    _require_subject(args.subject_id)

    print(f"Ingesting {args.source_type} source: {args.origin}")
    result = asyncio.run(ingest_source(args.subject_id, args.source_type, args.origin))
    if not result["success"]:
        print(f"Ingest failed: {result['error']}")
        sys.exit(1)
    print(f"Ingested as source {result['source_id']} — note generated.")


def _cmd_notes(args) -> None:
    _require_subject(args.subject_id)

    notes = state.list_notes_for_subject(args.subject_id)
    if not notes:
        print("No notes yet for this subject.")
        return
    for note in notes:
        print(f"## Note {note['id']}\n")
        print(note["summary_md"])
        print(f"\nKey concepts: {', '.join(note['key_concepts'])}\n")
        print("-" * 40)


def _build_chat_system_message(subject: dict, notes: list[dict]) -> str:
    if not notes:
        return (
            f"You are a study assistant helping the user learn about \"{subject['title']}\". "
            "No sources have been ingested yet for this subject, so answer from general "
            "knowledge and suggest the user add one with: hermes study ingest"
        )
    parts = [
        f"You are a study assistant helping the user learn about \"{subject['title']}\". "
        "Answer questions using the study notes below, which were summarized from sources "
        "the user added to this subject. If a question falls outside these notes, say so "
        "before answering from general knowledge.",
        "",
    ]
    for i, note in enumerate(notes, start=1):
        parts.append(f"--- Note {i} ---")
        parts.append(note["summary_md"])
        parts.append("")
    return "\n".join(parts)


def _cmd_chat(args) -> None:
    subject = _require_subject(args.subject_id)
    notes = state.list_notes_for_subject(args.subject_id)
    system_message = _build_chat_system_message(subject, notes)

    agent = AIAgent(
        session_id=uuid.uuid4().hex,
        session_db=SessionDB(),
        platform="study",
        enabled_toolsets=[],
        skip_context_files=True,
        skip_memory=True,
        quiet_mode=True,
    )

    print(f"Chatting about: {subject['title']}  (type 'exit' or Ctrl-D to quit)")
    print(
        "Note: sources ingested after this chat starts won't appear in its context — "
        "restart the chat to pick them up.\n"
    )

    conversation_history: list = []
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        state.add_chat_message(args.subject_id, "user", user_input)
        # system_message is authoritative only on turn 1; conversation_loop.py's
        # _restore_or_build_system_prompt reuses the persisted prompt verbatim
        # on later turns of the same session for prefix-cache warmth, so passing
        # it here on every turn is harmless and keeps the call uniform.
        try:
            result = agent.run_conversation(
                user_message=user_input,
                system_message=system_message,
                conversation_history=conversation_history,
            )
        except KeyboardInterrupt:
            print()
            break
        except Exception as exc:
            print(f"[chat error: {exc}]")
            continue

        if result.get("failed"):
            print(f"[chat error: {result.get('error') or result.get('final_response') or 'request failed'}]")
            continue

        reply = result.get("final_response", "")
        print(reply)
        state.add_chat_message(args.subject_id, "assistant", reply)
        conversation_history = result.get("messages", conversation_history)


def cmd_study(args) -> None:
    """Dispatch ``hermes study`` subcommands to their handlers."""
    command = getattr(args, "study_command", None)
    if command == "subject":
        subject_command = getattr(args, "study_subject_command", None)
        if subject_command == "create":
            return _cmd_subject_create(args)
        if subject_command == "list":
            return _cmd_subject_list(args)
        print("Usage: hermes study subject <create|list>")
        sys.exit(1)
    if command == "ingest":
        return _cmd_ingest(args)
    if command == "notes":
        return _cmd_notes(args)
    if command == "chat":
        return _cmd_chat(args)
    print("Usage: hermes study <subject|ingest|notes|chat>")
    sys.exit(1)
