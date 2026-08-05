"""``hermes study`` subcommand parser.

Follows the cron/approvals pattern: parser construction lives here, the
handler is injected by ``main.py`` so this module never imports ``main``
(cycle avoidance). All real command logic lives in ``hermes_cli/study.py``;
this module only builds argparse structure.
"""

from __future__ import annotations

from typing import Callable

_SOURCE_TYPES = ("url", "pdf", "youtube")


def build_study_parser(subparsers, *, cmd_study: Callable, cmd_study_gui: Callable) -> None:
    """Attach the ``study`` subcommand (and its nested subcommands) to ``subparsers``."""
    study_parser = subparsers.add_parser(
        "study",
        help="Study-desktop: collect sources into Subjects, summarize, and chat over them",
        description=(
            "Manage study-desktop Subjects: ingest web pages / PDFs / YouTube videos, "
            "read the generated notes, and chat with an assistant grounded in those notes."
        ),
    )
    study_subparsers = study_parser.add_subparsers(
        dest="study_command",
        metavar="<subcommand>",
    )

    # --- subject create / list -------------------------------------------------
    subject_parser = study_subparsers.add_parser(
        "subject",
        help="Create or list study Subjects",
    )
    subject_subparsers = subject_parser.add_subparsers(
        dest="study_subject_command",
        metavar="<subcommand>",
    )

    subject_create_parser = subject_subparsers.add_parser(
        "create",
        help="Create a new Subject",
    )
    subject_create_parser.add_argument("title", help="Subject title")
    subject_create_parser.add_argument(
        "--description",
        default=None,
        help="Optional longer description of the Subject",
    )
    subject_create_parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )
    subject_create_parser.set_defaults(func=cmd_study)

    subject_list_parser = subject_subparsers.add_parser(
        "list",
        help="List all Subjects",
    )
    subject_list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )
    subject_list_parser.set_defaults(func=cmd_study)
    subject_parser.set_defaults(func=cmd_study)

    # --- ingest ------------------------------------------------------------
    ingest_parser = study_subparsers.add_parser(
        "ingest",
        help="Add and summarize a source under a Subject",
        description=(
            "Extract text from a URL, PDF, or YouTube video, then generate a study "
            "note for it via the study_summary auxiliary LLM task."
        ),
    )
    ingest_parser.add_argument("subject_id", help="Subject id (see: hermes study subject list)")
    ingest_parser.add_argument("source_type", choices=_SOURCE_TYPES, help="Type of source to ingest")
    ingest_parser.add_argument("origin", help="URL, or local file path for a PDF")
    ingest_parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )
    ingest_parser.set_defaults(func=cmd_study)

    # --- notes ---------------------------------------------------------------
    notes_parser = study_subparsers.add_parser(
        "notes",
        help="Print all generated notes for a Subject",
    )
    notes_parser.add_argument("subject_id", help="Subject id (see: hermes study subject list)")
    notes_parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )
    notes_parser.set_defaults(func=cmd_study)

    # --- chat ------------------------------------------------------------
    chat_parser = study_subparsers.add_parser(
        "chat",
        help="Interactive Q&A chat grounded in a Subject's notes",
        description=(
            "Start an interactive chat session whose context is every Note under this "
            "Subject. The context is fixed for the lifetime of this chat process — "
            "sources ingested after the chat starts will not appear until you restart it."
        ),
    )
    chat_parser.add_argument("subject_id", help="Subject id (see: hermes study subject list)")
    chat_parser.set_defaults(func=cmd_study)

    # --- chat-turn -------------------------------------------------------
    chat_turn_parser = study_subparsers.add_parser(
        "chat-turn",
        help="Non-interactive single-turn chat, for programmatic callers (e.g. the desktop app)",
        description=(
            "Send one message and get one JSON reply, grounded in a Subject's current "
            "notes: {\"reply\": str, \"error\": null} on success, or "
            "{\"reply\": null, \"error\": str} on failure. Unlike `hermes study chat`, "
            "each call rebuilds context from scratch (no frozen-until-restart behavior) "
            "and is not interactive."
        ),
    )
    chat_turn_parser.add_argument("subject_id", help="Subject id (see: hermes study subject list)")
    chat_turn_parser.add_argument("--message", required=True, help="The user's message for this turn")
    chat_turn_parser.set_defaults(json=True)
    chat_turn_parser.set_defaults(func=cmd_study)

    # --- desktop -----------------------------------------------------------
    desktop_parser = study_subparsers.add_parser(
        "desktop",
        help="Launch the study-desktop Electron app",
        description=(
            "Install dependencies (if needed) and launch apps/study-desktop, a "
            "minimal Electron app for managing Subjects, sources, notes, and chat. "
            "Developer-oriented: runs `npm run dev`, no packaged build."
        ),
    )
    desktop_parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip the npm install step even if node_modules looks missing",
    )
    desktop_parser.set_defaults(func=cmd_study_gui)

    study_parser.set_defaults(func=cmd_study)
