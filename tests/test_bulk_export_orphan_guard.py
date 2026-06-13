"""Tests for the orphan-process guard wiring in scripts/bulk_export_for_flythrough.py.

Covers:
- The --force-orphan-guard flag is recognized on every subcommand
- The bypass set includes the read-only subcommands and excludes the
  long-running ones that actually spawn RiftAssetDumper.exe
- main() invokes the guard for 'run' and 'scene-graph-only' subcommands
- main() bypasses the guard for 'status', 'verify', 'clean' subcommands
- The guard exits (code 2) when orphans are detected and --force-orphan-guard
  is not set
- --force-orphan-guard is forwarded to the guard as force=True
- The guard is NOT called when the subcommand is in the bypass set
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the scripts package is importable when tests are run in isolation
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.bulk_export_for_flythrough import (  # noqa: E402
    _BULK_ORPHAN_GUARD_BYPASS_COMMANDS,
    _build_parser,
    main,
)

# ---------------------------------------------------------------------------
# Parser wiring
# ---------------------------------------------------------------------------


def test_force_orphan_guard_flag_recognized_on_run():
    parser = _build_parser()
    args = parser.parse_args(["run", "--force-orphan-guard", "--limit", "1"])
    assert args.force_orphan_guard is True


def test_force_orphan_guard_flag_recognized_on_status():
    parser = _build_parser()
    args = parser.parse_args(["status", "--force-orphan-guard"])
    assert args.force_orphan_guard is True


def test_force_orphan_guard_flag_recognized_on_scene_graph_only():
    parser = _build_parser()
    args = parser.parse_args(["scene-graph-only", "--force-orphan-guard"])
    assert args.force_orphan_guard is True


def test_force_orphan_guard_default_false():
    parser = _build_parser()
    args = parser.parse_args(["run", "--limit", "1"])
    assert args.force_orphan_guard is False


# ---------------------------------------------------------------------------
# Bypass set membership
# ---------------------------------------------------------------------------


def test_bypass_set_includes_read_only_commands():
    assert "status" in _BULK_ORPHAN_GUARD_BYPASS_COMMANDS
    assert "verify" in _BULK_ORPHAN_GUARD_BYPASS_COMMANDS
    assert "clean" in _BULK_ORPHAN_GUARD_BYPASS_COMMANDS


def test_bypass_set_excludes_long_running_commands():
    assert "run" not in _BULK_ORPHAN_GUARD_BYPASS_COMMANDS
    assert "scene-graph-only" not in _BULK_ORPHAN_GUARD_BYPASS_COMMANDS


# ---------------------------------------------------------------------------
# main() guard invocation
# ---------------------------------------------------------------------------


def test_main_runs_guard_for_run_subcommand(monkeypatch):
    """run subcommand must invoke the guard (since it spawns RiftAssetDumper)."""
    monkeypatch.setattr(sys, "argv", ["bulk_export_for_flythrough.py", "run", "--limit", "1"])
    with patch("scripts.bulk_export_for_flythrough._orphan_process_guard", return_value=0) as mock_guard:
        with patch("scripts.bulk_export_for_flythrough._cmd_run", return_value=0):
            rc = main()
    assert rc == 0
    mock_guard.assert_called_once()
    # Without --force-orphan-guard, force should be False
    assert mock_guard.call_args.kwargs.get("force") is False


def test_main_runs_guard_for_scene_graph_only(monkeypatch):
    """scene-graph-only spawns dotnet run probe-nif-scene-graph — must be guarded."""
    monkeypatch.setattr(sys, "argv", ["bulk_export_for_flythrough.py", "scene-graph-only", "--limit", "1"])
    with patch("scripts.bulk_export_for_flythrough._orphan_process_guard", return_value=0) as mock_guard:
        with patch("scripts.bulk_export_for_flythrough._cmd_scene_graph_only", return_value=0):
            rc = main()
    assert rc == 0
    mock_guard.assert_called_once()
    assert mock_guard.call_args.kwargs.get("force") is False


def test_main_bypasses_guard_for_status(monkeypatch):
    """status is read-only and must not invoke the guard."""
    monkeypatch.setattr(sys, "argv", ["bulk_export_for_flythrough.py", "status"])
    with patch("scripts.bulk_export_for_flythrough._orphan_process_guard") as mock_guard:
        with patch("scripts.bulk_export_for_flythrough._cmd_status", return_value=0):
            rc = main()
    assert rc == 0
    mock_guard.assert_not_called()


def test_main_bypasses_guard_for_verify(monkeypatch):
    """verify is read-only (just SHA1s existing OBJs) and must not invoke the guard."""
    monkeypatch.setattr(sys, "argv", ["bulk_export_for_flythrough.py", "verify"])
    with patch("scripts.bulk_export_for_flythrough._orphan_process_guard") as mock_guard:
        with patch("scripts.bulk_export_for_flythrough._cmd_verify", return_value=0):
            rc = main()
    assert rc == 0
    mock_guard.assert_not_called()


def test_main_bypasses_guard_for_clean(monkeypatch):
    """clean is local-only filesystem deletion and must not invoke the guard."""
    monkeypatch.setattr(sys, "argv", ["bulk_export_for_flythrough.py", "clean", "--yes"])
    with patch("scripts.bulk_export_for_flythrough._orphan_process_guard") as mock_guard:
        with patch("scripts.bulk_export_for_flythrough._cmd_clean", return_value=0):
            rc = main()
    assert rc == 0
    mock_guard.assert_not_called()


def test_main_propagates_system_exit_when_guard_refuses(monkeypatch):
    """If the guard calls sys.exit(2), main() must propagate that exit code."""
    monkeypatch.setattr(sys, "argv", ["bulk_export_for_flythrough.py", "run", "--limit", "1"])
    with patch("scripts.bulk_export_for_flythrough._orphan_process_guard", side_effect=SystemExit(2)):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 2


def test_main_force_orphan_guard_forwards_force_true(monkeypatch):
    """--force-orphan-guard must be forwarded to the guard as force=True."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["bulk_export_for_flythrough.py", "run", "--force-orphan-guard", "--limit", "1"],
    )
    with patch("scripts.bulk_export_for_flythrough._orphan_process_guard", return_value=1) as mock_guard:
        with patch("scripts.bulk_export_for_flythrough._cmd_run", return_value=0):
            rc = main()
    assert rc == 0
    mock_guard.assert_called_once_with(force=True)


# ---------------------------------------------------------------------------
# Regression: no RiftAssetDumper process is spawned for any bypass command
# ---------------------------------------------------------------------------


_BULK_FAKE_SUBPROCESS_CALLS: list[str] = []


def _bulk_record_subprocess_call(*args, **kwargs):
    """Record every subprocess.run call and return a benign CompletedProcess."""
    cmd_list = list(args[0]) if args else list(kwargs.get("args", []))
    cmd_text = " ".join(str(part) for part in cmd_list).lower()
    _BULK_FAKE_SUBPROCESS_CALLS.append(cmd_text)
    import subprocess as _sp

    return _sp.CompletedProcess(args=cmd_list, returncode=0, stdout="", stderr="")


@pytest.mark.parametrize("command", sorted(_BULK_ORPHAN_GUARD_BYPASS_COMMANDS))
def test_bypass_command_does_not_spawn_riftassetdumper_detection(monkeypatch, command):
    """Regression: no bypass command should spawn a ``tasklist`` or
    ``pgrep RiftAssetDumper`` subprocess.

    This is the property the user cares about: bypass handlers must not
    trigger the orphan-detection probe because they are confirmed not to
    spawn a new ``RiftAssetDumper.exe`` themselves.
    """
    _BULK_FAKE_SUBPROCESS_CALLS.clear()
    monkeypatch.setattr(sys, "argv", ["bulk_export_for_flythrough.py", command, "--yes"])

    # The clean subcommand prompts for confirmation; --yes bypasses that.
    # Patch subprocess.run at the orphan-guard module so any accidental
    # detection probe is captured but not executed. Also patch
    # scripts.bulk_export_for_flythrough.subprocess.run for handlers that
    # might call it directly.
    with patch("scripts.rift_orphan_guard.subprocess.run", side_effect=_bulk_record_subprocess_call):
        with patch(
            "scripts.bulk_export_for_flythrough.subprocess.run",
            side_effect=_bulk_record_subprocess_call,
        ):
            handler_name = {
                "status": "_cmd_status",
                "verify": "_cmd_verify",
                "clean": "_cmd_clean",
            }.get(command)
            if handler_name is not None:
                with patch(f"scripts.bulk_export_for_flythrough.{handler_name}", return_value=0):
                    try:
                        main()
                    except SystemExit:
                        pass
            else:
                try:
                    main()
                except SystemExit:
                    pass

    offending = [
        call
        for call in _BULK_FAKE_SUBPROCESS_CALLS
        if "tasklist" in call or ("pgrep" in call and "riftassetdumper" in call)
    ]
    assert not offending, (
        f"Bypass command {command!r} triggered RiftAssetDumper detection: {offending}"
    )


@pytest.mark.parametrize("command", sorted(_BULK_ORPHAN_GUARD_BYPASS_COMMANDS))
def test_bypass_command_does_not_invoke_orphan_guard(monkeypatch, command):
    """The guard function must not be called for any bypass command."""
    monkeypatch.setattr(sys, "argv", ["bulk_export_for_flythrough.py", command, "--yes"])
    with patch("scripts.bulk_export_for_flythrough._orphan_process_guard") as mock_guard:
        handler_name = {
            "status": "_cmd_status",
            "verify": "_cmd_verify",
            "clean": "_cmd_clean",
        }.get(command)
        if handler_name is not None:
            with patch(f"scripts.bulk_export_for_flythrough.{handler_name}", return_value=0):
                try:
                    main()
                except SystemExit:
                    pass
        else:
            try:
                main()
            except SystemExit:
                pass
    mock_guard.assert_not_called()


# ---------------------------------------------------------------------------
# --force-orphan-guard on bypass commands: must be a safe no-op
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", sorted(_BULK_ORPHAN_GUARD_BYPASS_COMMANDS))
def test_bypass_command_with_force_orphan_guard_is_noop(monkeypatch, command):
    """``--force-orphan-guard`` on a bypass command must not trigger the guard.

    The flag is added to the common argparse parent so it appears on every
    subcommand. For bypass commands the guard is never called regardless
    of the flag, so passing it must be a safe no-op.
    """
    monkeypatch.setattr(
        sys,
        "argv",
        ["bulk_export_for_flythrough.py", command, "--force-orphan-guard", "--yes"],
    )
    with patch("scripts.bulk_export_for_flythrough._orphan_process_guard") as mock_guard:
        handler_name = {
            "status": "_cmd_status",
            "verify": "_cmd_verify",
            "clean": "_cmd_clean",
        }.get(command)
        if handler_name is not None:
            with patch(f"scripts.bulk_export_for_flythrough.{handler_name}", return_value=0):
                try:
                    main()
                except SystemExit:
                    pass
        else:
            try:
                main()
            except SystemExit:
                pass
    mock_guard.assert_not_called()
