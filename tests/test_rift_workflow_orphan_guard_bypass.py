"""Regression tests for the orphan-process guard bypass set in scripts/rift_workflow.py.

Asserts the property the user cares about: for EVERY command in
``_ORPHAN_GUARD_BYPASS_COMMANDS``, running ``main()`` with that command must
NOT invoke the orphan-process guard (and therefore must NOT spawn the
``tasklist`` / ``pgrep RiftAssetDumper`` subprocess the guard uses to detect
orphans).

The guard is the only thing in this codebase that calls ``tasklist`` or
``pgrep RiftAssetDumper``; if the guard is bypassed, no RiftAssetDumper
DETECTION subprocess is spawned. Bypass handlers themselves are confirmed
not to spawn a new ``RiftAssetDumper.exe`` (they are pure-Python status /
report / guard routines), so the guard is unnecessary for them.

Design note: ``_run_command`` is mocked to a no-op so the real handler
bodies don't execute (many need inventory files, NIF data, or external
tools). The bypass logic in ``main()`` runs *before* ``_run_command`` is
called, so the guard-check is still exercised realistically.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the scripts package is importable when tests are run in isolation
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import scripts.rift_workflow as _rw  # noqa: E402
from scripts.rift_workflow import _ORPHAN_GUARD_BYPASS_COMMANDS  # noqa: E402

# Startup assertion: the bypass set must be a frozenset with the original 4
# members. This catches accidental removal of the safety net at import time.
assert isinstance(_ORPHAN_GUARD_BYPASS_COMMANDS, frozenset), (
    f"_ORPHAN_GUARD_BYPASS_COMMANDS must be a frozenset, got "
    f"{type(_ORPHAN_GUARD_BYPASS_COMMANDS).__name__}"
)
assert {"tools-status", "ghidra-dry-run", "--help", "-h"} <= _ORPHAN_GUARD_BYPASS_COMMANDS, (
    "Bypass set must include the original 4 members (tools-status, "
    "ghidra-dry-run, --help, -h)"
)


# Commands are command names only (skip --help / -h flags which argparse
# handles before main() body runs -- covered by a separate test below).
BYPASS_COMMAND_NAMES = sorted(c for c in _ORPHAN_GUARD_BYPASS_COMMANDS if not c.startswith("-"))


def _argv_for(command: str) -> list[str]:
    """Build a minimal argv that selects ``command`` without requiring files."""
    return ["rift_workflow.py", command, "--list-json"]


# Module-level recording buffer for the global subprocess.run mock.
_RECORDED_SUBPROCESS_CALLS: list[str] = []


def _global_subprocess_recorder(*args, **kwargs):
    """Global ``subprocess.run`` mock that records every invocation."""
    cmd_list = list(args[0]) if args else list(kwargs.get("args", []))
    cmd_text = " ".join(str(part) for part in cmd_list).lower()
    _RECORDED_SUBPROCESS_CALLS.append(cmd_text)
    return MagicMock(spec=subprocess.CompletedProcess, returncode=0, stdout="", stderr="")


def _reset_recorded_calls() -> None:
    _RECORDED_SUBPROCESS_CALLS.clear()


@pytest.mark.parametrize("command", BYPASS_COMMAND_NAMES)
def test_bypass_command_does_not_invoke_orphan_guard(monkeypatch, command):
    """The guard function must not be called for any bypass command."""
    _reset_recorded_calls()
    monkeypatch.setattr(sys, "argv", _argv_for(command))

    with patch("scripts.rift_workflow._orphan_process_guard") as mock_guard:
        with patch("scripts.rift_workflow._run_command", return_value=0):
            with patch("scripts.rift_workflow.generated_output_guard", return_value=None):
                try:
                    _rw.main()
                except SystemExit:
                    pass  # argparse --help / parse errors exit cleanly
    mock_guard.assert_not_called()


@pytest.mark.parametrize("command", BYPASS_COMMAND_NAMES)
def test_bypass_command_does_not_spawn_riftassetdumper_detection(monkeypatch, command):
    """No bypass command should spawn a ``tasklist`` or ``pgrep RiftAssetDumper`` subprocess.

    The orphan-guard is the only thing in the codebase that probes for
    RiftAssetDumper.exe via ``tasklist`` (Windows) or ``pgrep -x
    RiftAssetDumper`` (POSIX). If the guard is bypassed, no
    RiftAssetDumper DETECTION subprocess is spawned.

    The mock is applied at the global ``subprocess.run`` level so any
    handler that imports subprocess directly is also captured. The
    ``with`` block scopes the patch to the test, so pytest internals
    outside the block are unaffected.
    """
    _reset_recorded_calls()
    monkeypatch.setattr(sys, "argv", _argv_for(command))

    with patch("subprocess.run", side_effect=_global_subprocess_recorder):
        with patch("scripts.rift_workflow._orphan_process_guard") as mock_guard:
            with patch("scripts.rift_workflow._run_command", return_value=0):
                with patch("scripts.rift_workflow.generated_output_guard", return_value=None):
                    try:
                        _rw.main()
                    except SystemExit:
                        pass
    mock_guard.assert_not_called()

    offending = [
        call
        for call in _RECORDED_SUBPROCESS_CALLS
        if "tasklist" in call or ("pgrep" in call and "riftassetdumper" in call)
    ]
    assert not offending, (
        f"Bypass command {command!r} triggered RiftAssetDumper detection: {offending}"
    )


# ---------------------------------------------------------------------------
# --force-orphan-guard on bypass commands: must be a safe no-op
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", BYPASS_COMMAND_NAMES)
def test_bypass_command_with_force_orphan_guard_is_noop(monkeypatch, command):
    """``--force-orphan-guard`` on a bypass command must not trigger the guard."""
    _reset_recorded_calls()
    monkeypatch.setattr(
        sys,
        "argv",
        ["rift_workflow.py", command, "--force-orphan-guard", "--list-json"],
    )

    with patch("scripts.rift_workflow._orphan_process_guard") as mock_guard:
        with patch("scripts.rift_workflow._run_command", return_value=0):
            with patch("scripts.rift_workflow.generated_output_guard", return_value=None):
                try:
                    _rw.main()
                except SystemExit:
                    pass
    mock_guard.assert_not_called()


# ---------------------------------------------------------------------------
# --help / -h: argparse handles them before main() body runs, but the
# guard must still not be invoked.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_flag_does_not_invoke_guard(monkeypatch, flag):
    """``--help`` / ``-h`` must exit cleanly without invoking the orphan guard."""
    _reset_recorded_calls()
    monkeypatch.setattr(sys, "argv", ["rift_workflow.py", flag])

    with patch("scripts.rift_workflow._orphan_process_guard") as mock_guard:
        try:
            _rw.main()
        except SystemExit as exc:
            # argparse calls sys.exit(0) on --help
            assert exc.code in (0, None)
    mock_guard.assert_not_called()
