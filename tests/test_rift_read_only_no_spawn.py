"""Regression tests for scripts/rift_read_only.py — the peer entry point for read-only commands.

Asserts the no-spawn invariant via three complementary checks:

1. **Structural check** — every read-only command's ``COMMAND_MAP`` entry in
   ``rift_workflow.py`` has an empty ``dotnet`` key, proving by design that
   no read-only command can spawn a C# process.

2. **Dispatch block check** — every read-only command has a dispatch block
   in ``rift_workflow._run_command`` (so ``rift_read_only.py`` can re-use
   the dispatch).

3. **Runtime smoke check** — each command invokes ``rift_workflow._run_command``
   and does not invoke the orphan-process guard.

These checks together prove the bypass-set reduction in ``rift_workflow.py``
is safe: the 41 read-only commands cannot spawn subprocesses, so the
orphan-process guard is unnecessary for them.
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

import scripts.rift_read_only as _rro  # noqa: E402
import scripts.rift_workflow as _rw  # noqa: E402
from scripts.rift_read_only import READ_ONLY_COMMANDS  # noqa: E402

# Startup assertion: READ_ONLY_COMMANDS must be a frozenset. This catches
# accidental removal of the immutability guarantee at import time.
assert isinstance(READ_ONLY_COMMANDS, frozenset), (
    f"READ_ONLY_COMMANDS must be a frozenset, got {type(READ_ONLY_COMMANDS).__name__}"
)
assert len(READ_ONLY_COMMANDS) >= 40, (
    f"READ_ONLY_COMMANDS must contain at least 40 commands (the audit minimum), got {len(READ_ONLY_COMMANDS)}"
)


COMMAND_NAMES: list[str] = sorted(READ_ONLY_COMMANDS)


def _argv_for(command: str) -> list[str]:
    """Build a minimal argv that selects ``command`` without requiring files."""
    return ["rift_read_only.py", command]


# ---------------------------------------------------------------------------
# 1. Structural check: every read-only command has an empty dotnet key
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", COMMAND_NAMES)
def test_read_only_command_has_empty_dotnet_key(command):
    """Each read-only command's COMMAND_MAP entry must have ``dotnet == ""``.

    This is the design-level proof that the command cannot spawn a C#
    process. The ``COMMAND_MAP`` is the single source of truth for which
    commands are spawners vs pure-Python.
    """
    assert command in _rw.COMMAND_MAP, (
        f"Read-only command {command!r} is not in rift_workflow.COMMAND_MAP. "
        f"rift_read_only.py re-uses rift_workflow._run_command, so every "
        f"read-only command must have a COMMAND_MAP entry."
    )
    entry = _rw.COMMAND_MAP[command]
    dotnet_key = entry.get("dotnet", "")
    assert dotnet_key == "", (
        f"Read-only command {command!r} has non-empty dotnet key {dotnet_key!r}. "
        f"Read-only commands must be pure-Python. If this command spawns C#, "
        f"it should NOT be in rift_read_only.READ_ONLY_COMMANDS."
    )


# ---------------------------------------------------------------------------
# 2. Dispatch block check: every read-only command has a dispatch block
# ---------------------------------------------------------------------------


def _load_rift_workflow_source() -> str:
    return (SCRIPTS_DIR / "rift_workflow.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("command", COMMAND_NAMES)
def test_read_only_command_has_dispatch_block(command):
    """Each read-only command must have a dispatch block in rift_workflow._run_command.

    rift_read_only.py re-uses rift_workflow._run_command, so if the dispatch
    block is missing, the command will fail at runtime with an "unknown
    command" error.
    """
    source = _load_rift_workflow_source()
    marker = f'if command == "{command}":'
    assert marker in source, (
        f"Read-only command {command!r} has no dispatch block in rift_workflow._run_command. "
        f"rift_read_only.py re-uses rift_workflow._run_command — if the block is missing, "
        f"the command will fail at runtime."
    )


# ---------------------------------------------------------------------------
# 3. Runtime smoke checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", COMMAND_NAMES)
def test_read_only_command_invokes_dispatch(monkeypatch, command):
    """Each read-only command must invoke rift_workflow._run_command (not crash)."""
    monkeypatch.setattr(sys, "argv", _argv_for(command))
    with patch("scripts.rift_workflow._run_command") as mock_run:
        try:
            _rro.main()
        except SystemExit:
            pass
    mock_run.assert_called_once()


@pytest.mark.parametrize("command", COMMAND_NAMES)
def test_read_only_command_does_not_invoke_orphan_guard(monkeypatch, command):
    """The orphan-process guard must never be invoked from rift_read_only."""
    monkeypatch.setattr(sys, "argv", _argv_for(command))
    with patch("scripts.rift_orphan_guard._orphan_process_guard") as mock_guard:
        with patch("scripts.rift_workflow._run_command"):
            try:
                _rro.main()
            except SystemExit:
                pass
    mock_guard.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Cross-module invariants
# ---------------------------------------------------------------------------


def test_read_only_commands_are_subset_of_rift_workflow():
    """The 41 read-only commands must be a subset of rift_workflow.COMMAND_MAP.

    This is the backward-compat invariant: rift_read_only re-uses
    rift_workflow._run_command, so every read-only command must also be
    dispatchable via rift_workflow.py. (The empty-bypass-set invariant is
    covered by the startup assertion in test_rift_workflow_orphan_guard_bypass.py.)
    """
    spawner_commands = set(_rw.COMMAND_MAP.keys())
    missing_from_workflow = READ_ONLY_COMMANDS - spawner_commands
    assert not missing_from_workflow, (
        f"Read-only commands must be a subset of rift_workflow.COMMAND_MAP, "
        f"but these are missing: {sorted(missing_from_workflow)}. Add them to "
        f"rift_workflow.COMMAND_MAP (they can stay as read-only entries)."
    )
