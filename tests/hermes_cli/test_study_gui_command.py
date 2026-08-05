"""Tests for ``hermes study desktop`` launcher wiring."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from hermes_cli import main as cli_main


def _ns(**kw):
    defaults = dict(skip_install=False)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def _make_study_desktop_tree(tmp_path: Path) -> Path:
    root = tmp_path / "hermes-agent"
    study_desktop_dir = root / "apps" / "study-desktop"
    study_desktop_dir.mkdir(parents=True)
    (study_desktop_dir / "package.json").write_text("{}", encoding="utf-8")
    return root


def test_study_gui_exits_cleanly_when_source_missing(tmp_path, monkeypatch, capsys):
    root = tmp_path / "hermes-agent"
    root.mkdir()
    monkeypatch.setattr(cli_main, "PROJECT_ROOT", root)

    with pytest.raises(SystemExit):
        cli_main.cmd_study_gui(_ns())

    out = capsys.readouterr().out
    assert "study-desktop" in out.lower()


def test_study_gui_requires_npm(tmp_path, monkeypatch, capsys):
    root = _make_study_desktop_tree(tmp_path)
    monkeypatch.setattr(cli_main, "PROJECT_ROOT", root)
    monkeypatch.setattr(cli_main, "_resolve_node_runtime_npm", lambda: None)

    with pytest.raises(SystemExit):
        cli_main.cmd_study_gui(_ns())

    out = capsys.readouterr().out
    assert "npm" in out.lower()


def test_study_gui_installs_when_node_modules_missing_then_runs_dev(tmp_path, monkeypatch):
    root = _make_study_desktop_tree(tmp_path)
    monkeypatch.setattr(cli_main, "PROJECT_ROOT", root)
    monkeypatch.setattr(cli_main, "_resolve_node_runtime_npm", lambda: "npm")

    install_calls = []
    run_calls = []

    def _fake_install(npm, cwd, *, extra_args=(), capture_output=True, env=None):
        install_calls.append((npm, cwd, extra_args))
        return subprocess.CompletedProcess([npm], 0)

    def _fake_run(cmd, cwd=None, env=None, check=False):
        run_calls.append((cmd, cwd, env))
        return subprocess.CompletedProcess(cmd, 0)

    with (
        patch.object(cli_main, "_run_npm_install_deterministic", side_effect=_fake_install),
        patch.object(cli_main.subprocess, "run", side_effect=_fake_run),
    ):
        cli_main.cmd_study_gui(_ns())

    assert install_calls == [("npm", root, ("--workspace", "apps/study-desktop"))]
    assert len(run_calls) == 1
    cmd, cwd, env = run_calls[0]
    assert cmd == ["npm", "run", "dev"]
    assert cwd == root / "apps" / "study-desktop"
    assert env["HERMES_STUDY_PYTHON"] == cli_main.sys.executable


def test_study_gui_skips_install_when_node_modules_present(tmp_path, monkeypatch):
    root = _make_study_desktop_tree(tmp_path)
    (root / "node_modules" / "electron").mkdir(parents=True)
    monkeypatch.setattr(cli_main, "PROJECT_ROOT", root)
    monkeypatch.setattr(cli_main, "_resolve_node_runtime_npm", lambda: "npm")

    install_calls = []

    def _fake_install(npm, cwd, *, extra_args=(), capture_output=True, env=None):
        install_calls.append((npm, cwd, extra_args))
        return subprocess.CompletedProcess([npm], 0)

    with (
        patch.object(cli_main, "_run_npm_install_deterministic", side_effect=_fake_install),
        patch.object(cli_main.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)),
    ):
        cli_main.cmd_study_gui(_ns())

    assert install_calls == []


def test_study_gui_skip_install_flag_forces_skip(tmp_path, monkeypatch):
    root = _make_study_desktop_tree(tmp_path)
    monkeypatch.setattr(cli_main, "PROJECT_ROOT", root)
    monkeypatch.setattr(cli_main, "_resolve_node_runtime_npm", lambda: "npm")

    install_calls = []

    def _fake_install(npm, cwd, *, extra_args=(), capture_output=True, env=None):
        install_calls.append((npm, cwd, extra_args))
        return subprocess.CompletedProcess([npm], 0)

    with (
        patch.object(cli_main, "_run_npm_install_deterministic", side_effect=_fake_install),
        patch.object(cli_main.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)),
    ):
        cli_main.cmd_study_gui(_ns(skip_install=True))

    assert install_calls == []


def test_study_gui_install_failure_exits_nonzero(tmp_path, monkeypatch, capsys):
    root = _make_study_desktop_tree(tmp_path)
    monkeypatch.setattr(cli_main, "PROJECT_ROOT", root)
    monkeypatch.setattr(cli_main, "_resolve_node_runtime_npm", lambda: "npm")

    def _fake_install(npm, cwd, *, extra_args=(), capture_output=True, env=None):
        return subprocess.CompletedProcess([npm], 1)

    with patch.object(cli_main, "_run_npm_install_deterministic", side_effect=_fake_install):
        with pytest.raises(SystemExit):
            cli_main.cmd_study_gui(_ns())

    out = capsys.readouterr().out
    assert "install" in out.lower()
