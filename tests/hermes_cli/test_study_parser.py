"""Tests for ``hermes study`` argparse wiring."""

from __future__ import annotations

import argparse

from hermes_cli.subcommands.study import build_study_parser


def _build_root_parser():
    root = argparse.ArgumentParser(prog="hermes")
    subparsers = root.add_subparsers(dest="command")
    calls = []
    build_study_parser(subparsers, cmd_study=lambda args: calls.append(args))
    return root, calls


def test_subject_create_parses_title_and_description():
    root, _ = _build_root_parser()
    args = root.parse_args(["study", "subject", "create", "Quantum Mechanics", "--description", "Intro course"])
    assert args.study_command == "subject"
    assert args.study_subject_command == "create"
    assert args.title == "Quantum Mechanics"
    assert args.description == "Intro course"


def test_subject_create_description_defaults_to_none():
    root, _ = _build_root_parser()
    args = root.parse_args(["study", "subject", "create", "Biology"])
    assert args.description is None


def test_subject_list_parses():
    root, _ = _build_root_parser()
    args = root.parse_args(["study", "subject", "list"])
    assert args.study_command == "subject"
    assert args.study_subject_command == "list"


def test_ingest_parses_subject_id_type_and_origin():
    root, _ = _build_root_parser()
    args = root.parse_args(["study", "ingest", "abc123", "url", "https://example.com/article"])
    assert args.study_command == "ingest"
    assert args.subject_id == "abc123"
    assert args.source_type == "url"
    assert args.origin == "https://example.com/article"


def test_ingest_rejects_unknown_source_type():
    root, _ = _build_root_parser()
    try:
        root.parse_args(["study", "ingest", "abc123", "carrier-pigeon", "origin"])
        assert False, "expected SystemExit for invalid choice"
    except SystemExit:
        pass


def test_notes_parses_subject_id():
    root, _ = _build_root_parser()
    args = root.parse_args(["study", "notes", "abc123"])
    assert args.study_command == "notes"
    assert args.subject_id == "abc123"


def test_chat_parses_subject_id():
    root, _ = _build_root_parser()
    args = root.parse_args(["study", "chat", "abc123"])
    assert args.study_command == "chat"
    assert args.subject_id == "abc123"


def test_all_leaf_commands_set_func_to_cmd_study():
    root, _ = _build_root_parser()
    for argv in (
        ["study", "subject", "create", "T"],
        ["study", "subject", "list"],
        ["study", "ingest", "s1", "pdf", "/tmp/x.pdf"],
        ["study", "notes", "s1"],
        ["study", "chat", "s1"],
    ):
        args = root.parse_args(argv)
        assert callable(args.func)
