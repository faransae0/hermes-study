"""``hermes study`` command implementations.

Parser construction lives in ``hermes_cli/subcommands/study.py``; this
module holds the actual logic, dispatched from a single ``cmd_study()``
entry point that ``hermes_cli/main.py`` forwards into (mirrors
``hermes_cli/dashboard_register.py``'s relationship to ``main.py``).
"""

from __future__ import annotations

import asyncio
import sys

import study_state as state
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


def _cmd_chat(args) -> None:
    _require_subject(args.subject_id)
    print("hermes study chat is not implemented yet.")
    sys.exit(1)


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
