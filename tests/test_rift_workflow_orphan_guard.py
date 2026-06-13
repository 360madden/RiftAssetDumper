"""Tests for the orphan-process guard added to scripts/rift_workflow.py.

Covers:
- _count_running_riftassetdumper_processes returns 0 on non-Windows
- It correctly counts matching lines in tasklist output
- It handles the "no matches" INFO message and empty output
- It returns 0 on subprocess errors (timeout, file not found, OSError)
- _orphan_process_guard proceeds when count is below threshold
- _orphan_process_guard exits (code 2) when count is at or above threshold
- --force-orphan-guard proceeds despite a high count (with a warning)
"""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from scripts.rift_workflow import (  # type: ignore[attr-defined]
    _count_running_riftassetdumper_processes,
    _orphan_process_guard,
)

# ---------------------------------------------------------------------------
# _count_running_riftassetdumper_processes
# ---------------------------------------------------------------------------


def test_count_returns_zero_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert _count_running_riftassetdumper_processes() == 0


@pytest.mark.parametrize(
    "stdout,expected",
    [
        pytest.param(
            "INFO: No tasks are running which match the specified criteria.\r\n",
            0,
            id="no_matches",
        ),
        pytest.param(
            "INFO: No tasks are running which match the specified criteria.\r\n"
            '"RiftAssetDumper.exe","12345","Console","1","2,634,312 K"\r\n',
            1,
            id="info_plus_real_row",
        ),
        pytest.param(
            '"RiftAssetDumper.exe","12345","Console","1","2,634,312 K"\r\n',
            1,
            id="localized_memory_with_comma",
        ),
        pytest.param("", 0, id="empty"),
        pytest.param(
            "RiftAssetDumper.exe          12345 Console                    1   2,634,312 K\r\n"
            "RiftAssetDumper.exe          67890 Console                    1   3,173,648 K\r\n",
            2,
            id="two_rows",
        ),
        pytest.param(
            "\r\n"
            "RiftAssetDumper.exe          12345 Console                    1   2,634,312 K\r\n"
            "\r\n"
            "SomeOther.exe                99999 Services                   0     100,000 K\r\n"
            "RiftAssetDumper.exe          67890 Console                    1   3,173,648 K\r\n",
            2,
            id="blank_lines_and_unrelated_rows",
        ),
    ],
)
def test_count_parses_subprocess_output(stdout: str, expected: int) -> None:
    """Each tasklist-output variant yields the expected process count."""
    fake_result = MagicMock(spec=subprocess.CompletedProcess)
    fake_result.stdout = stdout
    fake_result.returncode = 0
    with patch("subprocess.run", return_value=fake_result):
        assert _count_running_riftassetdumper_processes() == expected


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(subprocess.TimeoutExpired(cmd="tasklist", timeout=5), id="timeout"),
        pytest.param(FileNotFoundError(), id="file_not_found"),
        pytest.param(OSError("access denied"), id="oserror"),
    ],
)
def test_count_returns_zero_on_subprocess_error(exc: Exception) -> None:
    """Subprocess exceptions (timeout, missing tasklist, OS denial) yield 0."""
    with patch("subprocess.run", side_effect=exc):
        assert _count_running_riftassetdumper_processes() == 0


# ---------------------------------------------------------------------------
# _orphan_process_guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "count,threshold,expected",
    [
        pytest.param(0, 2, 0, id="zero_count_default_threshold"),
        pytest.param(1, 2, 1, id="below_threshold"),
        pytest.param(4, 5, 4, id="custom_threshold"),
    ],
)
def test_guard_proceeds_below_threshold(count: int, threshold: int, expected: int) -> None:
    """When count is strictly below threshold, the guard returns the count unchanged."""
    with patch("scripts.rift_orphan_guard._count_running_riftassetdumper_processes", return_value=count):
        assert _orphan_process_guard(threshold=threshold, force=False) == expected


@pytest.mark.parametrize(
    "count,expected_substring",
    [
        pytest.param(2, "2 RiftAssetDumper process", id="at_threshold"),
        pytest.param(3, "3 RiftAssetDumper process", id="above_threshold"),
    ],
)
def test_guard_exits_at_or_above_threshold(count: int, expected_substring: str, capsys) -> None:
    """When count meets/exceeds threshold (and force=False), guard exits with code 2."""
    with patch("scripts.rift_orphan_guard._count_running_riftassetdumper_processes", return_value=count):
        with pytest.raises(SystemExit) as exc_info:
            _orphan_process_guard(threshold=2, force=False)
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert expected_substring in captured.err
        assert "Get-Process RiftAssetDumper" in captured.err
        assert "--force-orphan-guard" in captured.err


def test_guard_warns_and_proceeds_with_force(capsys):
    with patch("scripts.rift_orphan_guard._count_running_riftassetdumper_processes", return_value=3):
        result = _orphan_process_guard(threshold=2, force=True)
        assert result == 3
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "--force-orphan-guard" in captured.err
