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

from scripts.rift_workflow import (
    _count_running_riftassetdumper_processes,
    _orphan_process_guard,
)

# ---------------------------------------------------------------------------
# _count_running_riftassetdumper_processes
# ---------------------------------------------------------------------------


def test_count_returns_zero_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert _count_running_riftassetdumper_processes() == 0


def test_count_returns_zero_when_no_matches():
    fake_output = "INFO: No tasks are running which match the specified criteria.\r\n"
    fake_result = MagicMock(spec=subprocess.CompletedProcess)
    fake_result.stdout = fake_output
    fake_result.returncode = 0
    with patch("subprocess.run", return_value=fake_result):
        assert _count_running_riftassetdumper_processes() == 0


def test_count_skips_no_tasks_info_line_but_counts_real_row():
    # The "INFO: No tasks" line must not poison a real RiftAssetDumper.exe
    # row in the same output. This guards against the parser accidentally
    # treating the info line as a CSV record.
    fake_output = (
        "INFO: No tasks are running which match the specified criteria.\r\n"
        "\"RiftAssetDumper.exe\",\"12345\",\"Console\",\"1\",\"2,634,312 K\"\r\n"
    )
    fake_result = MagicMock(spec=subprocess.CompletedProcess)
    fake_result.stdout = fake_output
    fake_result.returncode = 0
    with patch("subprocess.run", return_value=fake_result):
        assert _count_running_riftassetdumper_processes() == 1


def test_count_handles_localized_memory_column_with_comma():
    # Some locales format memory as "1,234,567 K" with thousands separators.
    # csv.reader must parse the quoted column correctly; a naive split(",")
    # would misalign and miss the image name.
    fake_output = (
        "\"RiftAssetDumper.exe\",\"12345\",\"Console\",\"1\",\"2,634,312 K\"\r\n"
    )
    fake_result = MagicMock(spec=subprocess.CompletedProcess)
    fake_result.stdout = fake_output
    fake_result.returncode = 0
    with patch("subprocess.run", return_value=fake_result):
        assert _count_running_riftassetdumper_processes() == 1


def test_count_returns_zero_for_empty_output():
    fake_result = MagicMock(spec=subprocess.CompletedProcess)
    fake_result.stdout = ""
    fake_result.returncode = 0
    with patch("subprocess.run", return_value=fake_result):
        assert _count_running_riftassetdumper_processes() == 0


def test_count_counts_matching_lines():
    fake_output = (
        "RiftAssetDumper.exe          12345 Console                    1   2,634,312 K\r\n"
        "RiftAssetDumper.exe          67890 Console                    1   3,173,648 K\r\n"
    )
    fake_result = MagicMock(spec=subprocess.CompletedProcess)
    fake_result.stdout = fake_output
    fake_result.returncode = 0
    with patch("subprocess.run", return_value=fake_result):
        assert _count_running_riftassetdumper_processes() == 2


def test_count_ignores_blank_lines_and_unrelated_rows():
    fake_output = (
        "\r\n"
        "RiftAssetDumper.exe          12345 Console                    1   2,634,312 K\r\n"
        "\r\n"
        "SomeOther.exe                99999 Services                   0     100,000 K\r\n"
        "RiftAssetDumper.exe          67890 Console                    1   3,173,648 K\r\n"
    )
    fake_result = MagicMock(spec=subprocess.CompletedProcess)
    fake_result.stdout = fake_output
    fake_result.returncode = 0
    with patch("subprocess.run", return_value=fake_result):
        assert _count_running_riftassetdumper_processes() == 2


def test_count_returns_zero_on_subprocess_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="tasklist", timeout=5)):
        assert _count_running_riftassetdumper_processes() == 0


def test_count_returns_zero_on_file_not_found():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert _count_running_riftassetdumper_processes() == 0


def test_count_returns_zero_on_oserror():
    with patch("subprocess.run", side_effect=OSError("access denied")):
        assert _count_running_riftassetdumper_processes() == 0


# ---------------------------------------------------------------------------
# _orphan_process_guard
# ---------------------------------------------------------------------------


def test_guard_proceeds_below_threshold():
    with patch(
        "scripts.rift_orphan_guard._count_running_riftassetdumper_processes", return_value=1
    ):
        assert _orphan_process_guard(threshold=2, force=False) == 1


def test_guard_proceeds_at_zero():
    with patch(
        "scripts.rift_orphan_guard._count_running_riftassetdumper_processes", return_value=0
    ):
        assert _orphan_process_guard(threshold=2, force=False) == 0


def test_guard_exits_at_threshold(capsys):
    with patch(
        "scripts.rift_orphan_guard._count_running_riftassetdumper_processes", return_value=2
    ):
        with pytest.raises(SystemExit) as exc_info:
            _orphan_process_guard(threshold=2, force=False)
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "2 RiftAssetDumper process" in captured.err
        assert "Get-Process RiftAssetDumper" in captured.err
        assert "--force-orphan-guard" in captured.err


def test_guard_exits_above_threshold(capsys):
    with patch(
        "scripts.rift_orphan_guard._count_running_riftassetdumper_processes", return_value=3
    ):
        with pytest.raises(SystemExit) as exc_info:
            _orphan_process_guard(threshold=2, force=False)
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "3 RiftAssetDumper process" in captured.err
        assert "previous Codebuff session" in captured.err


def test_guard_warns_and_proceeds_with_force(capsys):
    with patch(
        "scripts.rift_orphan_guard._count_running_riftassetdumper_processes", return_value=3
    ):
        result = _orphan_process_guard(threshold=2, force=True)
        assert result == 3
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "--force-orphan-guard" in captured.err


def test_guard_custom_threshold():
    with patch(
        "scripts.rift_orphan_guard._count_running_riftassetdumper_processes", return_value=4
    ):
        # threshold=5 should allow 4 to proceed
        assert _orphan_process_guard(threshold=5, force=False) == 4
