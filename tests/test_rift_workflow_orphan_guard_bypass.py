"""Regression tests for the orphan-process guard bypass set in scripts/rift_workflow.py.

The bypass set was emptied during the rift_read_only split: the 40 read-only
commands that previously required bypass have moved to the peer entry point
``scripts/rift_read_only.py``, which dispatches them without invoking the
orphan-process guard. This file now asserts the empty-set invariant (the
bypass set stays empty unless a new read-only command is added back to
rift_workflow.py that genuinely shares dispatch with a spawner).

The --help / -h handling is still tested because argparse processes those
flags before the guard check in main() runs.
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

import scripts.rift_workflow as _rw  # noqa: E402
from scripts.rift_workflow import _ORPHAN_GUARD_BYPASS_COMMANDS  # noqa: E402

# Startup assertion: the bypass set must be a frozenset. After the
# rift_read_only split it is EMPTY — all 40 read-only commands moved to
# the peer entry point scripts/rift_read_only.py. This catches accidental
# re-introduction of the bypass (e.g. if someone adds a new read-only
# command to rift_workflow.py without also updating rift_read_only.py).
assert isinstance(_ORPHAN_GUARD_BYPASS_COMMANDS, frozenset), (
    f"_ORPHAN_GUARD_BYPASS_COMMANDS must be a frozenset, got "
    f"{type(_ORPHAN_GUARD_BYPASS_COMMANDS).__name__}"
)
assert _ORPHAN_GUARD_BYPASS_COMMANDS == frozenset(), (
    f"Bypass set must be empty after rift_read_only split, got "
    f"{sorted(_ORPHAN_GUARD_BYPASS_COMMANDS)}. If you are adding a new "
    f"read-only command to rift_workflow.py, also add it to "
    f"scripts/rift_read_only.py:READ_ONLY_COMMANDS."
)


# ---------------------------------------------------------------------------
# --help / -h: argparse handles them before main() body runs, but the
# guard must still not be invoked.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_flag_does_not_invoke_guard(monkeypatch, flag):
    """``--help`` / ``-h`` must exit cleanly without invoking the orphan guard."""
    monkeypatch.setattr(sys, "argv", ["rift_workflow.py", flag])

    with patch("scripts.rift_workflow._orphan_process_guard") as mock_guard:
        with patch("scripts.rift_workflow._run_command", return_value=0):
            with patch("scripts.rift_workflow.generated_output_guard", return_value=None):
                try:
                    _rw.main()
                except SystemExit as exc:
                    # argparse calls sys.exit(0) on --help
                    assert exc.code in (0, None)
    mock_guard.assert_not_called()
