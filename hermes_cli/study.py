"""``hermes study`` command implementations.

Parser construction lives in ``hermes_cli/subcommands/study.py``; this
module holds the actual logic, dispatched from a single ``cmd_study()``
entry point that ``hermes_cli/main.py`` forwards into (mirrors
``hermes_cli/dashboard_register.py``'s relationship to ``main.py``).
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

import study_state as state
from hermes_state import SessionDB
from run_agent import AIAgent
from tools.study_ingest_tool import ingest_source


def _cmd_subject_create(args) -> None:
    subject_id = state.create_subject(args.title, args.description or "")
    if args.json:
        print(json.dumps(state.get_subject(subject_id)))
        return
    print(f"Created subject {subject_id}: {args.title}")


def _cmd_subject_list(args) -> None:
    subjects = state.list_subjects()
    if args.json:
        print(json.dumps([
            {
                "id": s["id"],
                "title": s["title"],
                "source_count": len(state.list_sources_for_subject(s["id"])),
            }
            for s in subjects
        ]))
        return
    if not subjects:
        print("No subjects yet. Create one with: hermes study subject create <title>")
        return
    for subject in subjects:
        source_count = len(state.list_sources_for_subject(subject["id"]))
        print(f"{subject['id']}  {subject['title']}  ({source_count} source(s))")


def _require_subject(args) -> dict:
    subject = state.get_subject(args.subject_id)
    if subject is None:
        if getattr(args, "json", False):
            print(json.dumps({"error": f"No subject found with id {args.subject_id!r}"}))
        else:
            print(f"No subject found with id {args.subject_id!r}. Run: hermes study subject list")
        sys.exit(1)
    return subject


def _cmd_ingest(args) -> None:
    _require_subject(args)

    if not args.json:
        print(f"Ingesting {args.source_type} source: {args.origin}")
    result = asyncio.run(ingest_source(args.subject_id, args.source_type, args.origin))

    if args.json:
        print(json.dumps(result))
        if not result["success"]:
            sys.exit(1)
        return

    if not result["success"]:
        print(f"Ingest failed: {result['error']}")
        sys.exit(1)
    print(f"Ingested as source {result['source_id']} — note generated.")


def _cmd_notes(args) -> None:
    _require_subject(args)

    notes = state.list_notes_for_subject(args.subject_id)
    if args.json:
        print(json.dumps([
            {
                "id": n["id"],
                "summary_md": n["summary_md"],
                "key_concepts": n["key_concepts"],
                "generated_at": n["generated_at"],
            }
            for n in notes
        ]))
        return

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
    from hermes_cli.main import _require_tty

    _require_tty("study chat")

    subject = _require_subject(args)
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

        if result.get("failed") or result.get("error"):
            print(f"[chat error: {result.get('error') or 'request failed'}]")
            continue

        reply = result.get("final_response") or ""
        if not reply:
            print("[chat error: empty response from model]")
            continue

        print(reply)
        state.add_chat_message(args.subject_id, "assistant", reply)
        conversation_history = result.get("messages", conversation_history)


def _cmd_chat_turn(args) -> None:
    """Non-interactive single-turn chat: one message in, one JSON reply out.

    Unlike the interactive `chat` REPL, this rebuilds the system message from
    the Subject's CURRENT notes and uses a brand-new session on every call —
    no session reuse, no frozen-context caveat to explain to a caller. Both
    chat_messages rows are persisted together, only after a successful
    run_conversation() call — persisting only the user turn on a failed call
    would leave the next call's history reconstruction with two consecutive
    "user" entries and no assistant reply between them.
    """
    subject = _require_subject(args)

    try:
        notes = state.list_notes_for_subject(args.subject_id)
        system_message = _build_chat_system_message(subject, notes)

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in state.list_chat_messages_for_subject(args.subject_id)
        ]

        agent = AIAgent(
            session_id=uuid.uuid4().hex,
            session_db=SessionDB(),
            platform="study",
            enabled_toolsets=[],
            skip_context_files=True,
            skip_memory=True,
            quiet_mode=True,
        )

        result = agent.run_conversation(
            user_message=args.message,
            system_message=system_message,
            conversation_history=history,
        )
    except Exception as exc:
        print(json.dumps({"reply": None, "error": str(exc) or type(exc).__name__}))
        return

    if result.get("failed") or result.get("error"):
        print(json.dumps({"reply": None, "error": result.get("error") or "request failed"}))
        return

    reply = result.get("final_response") or ""
    if not reply:
        print(json.dumps({"reply": None, "error": "empty response from model"}))
        return

    try:
        state.add_chat_message(args.subject_id, "user", args.message)
        state.add_chat_message(args.subject_id, "assistant", reply)
    except Exception as exc:
        print(json.dumps({"reply": None, "error": str(exc) or type(exc).__name__}))
        return

    print(json.dumps({"reply": reply, "error": None}))


def cmd_study(args) -> None:
    """Dispatch ``hermes study`` subcommands to their handlers."""
    command = getattr(args, "study_command", None)
    try:
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
        if command == "chat-turn":
            return _cmd_chat_turn(args)
        print("Usage: hermes study <subject|ingest|notes|chat>")
        sys.exit(1)
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(exc) or type(exc).__name__}))
            sys.exit(1)
        raise
