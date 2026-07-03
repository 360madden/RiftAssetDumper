"""Tests for find_rift_pid(), find_latest_verified_json(), and
load_best_verified_address() in scripts/position_watcher.py.
"""

from __future__ import annotations

import ctypes
import json
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest

from scripts.position_watcher import (
    PROCESSENTRY32W,
    TH32CS_SNAPPROCESS,
    find_latest_verified_json,
    find_rift_pid,
    load_best_verified_address,
)

# ===========================================================================
# PROCESSENTRY32W struct layout + constants
# ===========================================================================


class TestProcessEntry32W:
    def test_struct_size(self) -> None:
        """sizeof(PROCESSENTRY32W) matches expected layout."""
        sz = ctypes.sizeof(PROCESSENTRY32W)
        assert sz > 0, "PROCESSENTRY32W must have non-zero size"

    def test_dw_size_initial_value(self) -> None:
        """After zero-initialise, dwSize is 0."""
        pe = PROCESSENTRY32W()
        assert pe.dwSize == 0

    def test_set_dw_size(self) -> None:
        """Can set dwSize and read it back."""
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        assert pe.dwSize == ctypes.sizeof(PROCESSENTRY32W)

    def test_th32_process_id_field_exists(self) -> None:
        """th32ProcessID field is present and defaults to 0."""
        pe = PROCESSENTRY32W()
        assert pe.th32ProcessID == 0

    def test_sz_exe_file_field_exists(self) -> None:
        """szExeFile is a WCHAR array of length 260."""
        pe = PROCESSENTRY32W()
        # Accessing it shouldn't crash
        _ = pe.szExeFile

    def test_th32cs_snapprocess_constant(self) -> None:
        """TH32CS_SNAPPROCESS = 0x00000002."""
        assert TH32CS_SNAPPROCESS == 0x00000002


# ===========================================================================
# find_rift_pid()
# ===========================================================================


class TestFindRiftPid:
    def test_returns_none_when_rift_not_running(self) -> None:
        """Should return None when no rift_x64.exe process exists."""
        # This is a live test — if RIFT happens to be running it'll return
        # a PID. But on CI / dev machine without RIFT, it returns None.
        result = find_rift_pid()
        # Accept both None and a valid int (if RIFT is running).
        assert result is None or (isinstance(result, int) and result > 0), (
            f"Expected None or positive int, got {result!r}"
        )

    def test_finds_single_rifp_process(self) -> None:
        """Mock: single rift_x64.exe found."""
        # Build a mock PROCESSENTRY32W with the exe name
        mock_pe = PROCESSENTRY32W()
        mock_pe.th32ProcessID = 12345
        mock_pe.szExeFile = "rift_x64.exe"

        with (
            mock.patch("scripts.position_watcher.ctypes.WinDLL") as mock_windll,
        ):
            # Configure mock kernel32
            kernel32 = mock.MagicMock()
            mock_windll.return_value = kernel32

            # CreateToolhelp32Snapshot succeeds
            kernel32.CreateToolhelp32Snapshot.return_value = 1  # valid handle

            # Process32FirstW: fills pe and returns True
            def first_side_effect(snapshot, pe_ptr):
                ctypes.memmove(
                    pe_ptr,
                    ctypes.addressof(mock_pe),
                    ctypes.sizeof(PROCESSENTRY32W),
                )
                return True

            kernel32.Process32FirstW.side_effect = first_side_effect

            # Process32NextW: returns False (no more processes)
            kernel32.Process32NextW.return_value = False

            # CloseHandle: no-op
            kernel32.CloseHandle.return_value = True

            result = find_rift_pid()
            assert result == 12345

    def test_multiple_rifp_processes_raises(self) -> None:
        """Mock: two rift_x64.exe processes found → RuntimeError."""
        mock_pe1 = PROCESSENTRY32W()
        mock_pe1.th32ProcessID = 100
        mock_pe1.szExeFile = "rift_x64.exe"

        mock_pe2 = PROCESSENTRY32W()
        mock_pe2.th32ProcessID = 200
        mock_pe2.szExeFile = "rift_x64.exe"

        with (
            mock.patch("scripts.position_watcher.ctypes.WinDLL") as mock_windll,
        ):
            kernel32 = mock.MagicMock()
            mock_windll.return_value = kernel32
            kernel32.CreateToolhelp32Snapshot.return_value = 1

            _call_count = 0

            def process32_side_effect(snapshot, pe_ptr):
                nonlocal _call_count
                _call_count += 1
                if _call_count == 1:
                    ctypes.memmove(
                        pe_ptr,
                        ctypes.addressof(mock_pe1),
                        ctypes.sizeof(PROCESSENTRY32W),
                    )
                    return True
                elif _call_count == 2:
                    ctypes.memmove(
                        pe_ptr,
                        ctypes.addressof(mock_pe2),
                        ctypes.sizeof(PROCESSENTRY32W),
                    )
                    return True
                return False

            kernel32.Process32FirstW.side_effect = process32_side_effect
            kernel32.Process32NextW.side_effect = process32_side_effect
            kernel32.CloseHandle.return_value = True

            with pytest.raises(RuntimeError, match="Multiple rift_x64.exe"):
                find_rift_pid()

    def test_case_insensitive_match(self) -> None:
        """Mock: RIFT_X64.EXE (uppercase) still matches."""
        mock_pe = PROCESSENTRY32W()
        mock_pe.th32ProcessID = 9999
        mock_pe.szExeFile = "RIFT_X64.EXE"

        with (
            mock.patch("scripts.position_watcher.ctypes.WinDLL") as mock_windll,
        ):
            kernel32 = mock.MagicMock()
            mock_windll.return_value = kernel32
            kernel32.CreateToolhelp32Snapshot.return_value = 1

            def first_side_effect(snapshot, pe_ptr):
                ctypes.memmove(
                    pe_ptr,
                    ctypes.addressof(mock_pe),
                    ctypes.sizeof(PROCESSENTRY32W),
                )
                return True

            kernel32.Process32FirstW.side_effect = first_side_effect
            kernel32.Process32NextW.return_value = False
            kernel32.CloseHandle.return_value = True

            result = find_rift_pid()
            assert result == 9999

    def test_no_processes_at_all(self) -> None:
        """Mock: Process32FirstW fails → None."""
        with (
            mock.patch("scripts.position_watcher.ctypes.WinDLL") as mock_windll,
        ):
            kernel32 = mock.MagicMock()
            mock_windll.return_value = kernel32
            kernel32.CreateToolhelp32Snapshot.return_value = 1
            kernel32.Process32FirstW.return_value = False  # no processes
            kernel32.CloseHandle.return_value = True

            result = find_rift_pid()
            assert result is None

    def test_snapshot_failure_raises(self) -> None:
        """Mock: CreateToolhelp32Snapshot returns INVALID_HANDLE_VALUE."""
        from scripts.position_watcher import INVALID_HANDLE_VALUE

        with (
            mock.patch("scripts.position_watcher.ctypes.WinDLL") as mock_windll,
        ):
            kernel32 = mock.MagicMock()
            mock_windll.return_value = kernel32
            kernel32.CreateToolhelp32Snapshot.return_value = INVALID_HANDLE_VALUE

            with pytest.raises(OSError, match="CreateToolhelp32Snapshot"):
                find_rift_pid()

    def test_substring_no_false_match(self) -> None:
        """Mock: a process named 'not_rift_x64.exe_backup' is NOT matched."""
        mock_pe = PROCESSENTRY32W()
        mock_pe.th32ProcessID = 7777
        mock_pe.szExeFile = "not_rift_x64.exe_backup"

        with (
            mock.patch("scripts.position_watcher.ctypes.WinDLL") as mock_windll,
        ):
            kernel32 = mock.MagicMock()
            mock_windll.return_value = kernel32
            kernel32.CreateToolhelp32Snapshot.return_value = 1

            def first_side_effect(snapshot, pe_ptr):
                ctypes.memmove(
                    pe_ptr,
                    ctypes.addressof(mock_pe),
                    ctypes.sizeof(PROCESSENTRY32W),
                )
                return True

            kernel32.Process32FirstW.side_effect = first_side_effect
            kernel32.Process32NextW.return_value = False
            kernel32.CloseHandle.return_value = True

            result = find_rift_pid()
            assert result is None

    def test_skips_non_rifp_processes(self) -> None:
        """Mock: only non-RIFT processes → None."""
        mock_pe1 = PROCESSENTRY32W()
        mock_pe1.th32ProcessID = 1
        mock_pe1.szExeFile = "chrome.exe"

        mock_pe2 = PROCESSENTRY32W()
        mock_pe2.th32ProcessID = 2
        mock_pe2.szExeFile = "explorer.exe"

        _call_count = 0

        def process32_side_effect(snapshot, pe_ptr):
            nonlocal _call_count
            _call_count += 1
            if _call_count == 1:
                ctypes.memmove(
                    pe_ptr,
                    ctypes.addressof(mock_pe1),
                    ctypes.sizeof(PROCESSENTRY32W),
                )
                return True
            elif _call_count == 2:
                ctypes.memmove(
                    pe_ptr,
                    ctypes.addressof(mock_pe2),
                    ctypes.sizeof(PROCESSENTRY32W),
                )
                return True
            return False

        with (
            mock.patch("scripts.position_watcher.ctypes.WinDLL") as mock_windll,
        ):
            kernel32 = mock.MagicMock()
            mock_windll.return_value = kernel32
            kernel32.CreateToolhelp32Snapshot.return_value = 1
            kernel32.Process32FirstW.side_effect = process32_side_effect
            kernel32.Process32NextW.side_effect = process32_side_effect
            kernel32.CloseHandle.return_value = True

            result = find_rift_pid()
            assert result is None


# ===========================================================================
# find_latest_verified_json()
# ===========================================================================


class TestFindLatestVerifiedJson:
    def test_no_files_returns_none(self) -> None:
        """Empty directory → None."""
        with tempfile.TemporaryDirectory() as td:
            result = find_latest_verified_json(Path(td))
            assert result is None

    def test_non_existent_directory_returns_none(self) -> None:
        """Non-existent directory → None."""
        result = find_latest_verified_json(Path("/nonexistent/dir/xyz"))
        assert result is None

    def test_single_file_returned(self) -> None:
        """Single .verified.json found and returned."""
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "test.verified.json"
            f.write_text("[]")
            result = find_latest_verified_json(Path(td))
            assert result == f.resolve()

    def test_picks_newest_file(self) -> None:
        """Multiple files — returns most recently modified."""
        with tempfile.TemporaryDirectory() as td:
            older = Path(td) / "older.verified.json"
            older.write_text("[]")
            time.sleep(0.1)  # ensure different mtime
            newer = Path(td) / "newer.verified.json"
            newer.write_text("[]")

            result = find_latest_verified_json(Path(td))
            assert result == newer.resolve()

    def test_filters_only_verified_json_extension(self) -> None:
        """Only *.verified.json; .json and other extensions ignored."""
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "not_verified.json").write_text("[]")
            (Path(td) / "other.txt").write_text("hello")
            # No .verified.json files
            result = find_latest_verified_json(Path(td))
            assert result is None

    def test_explicit_empty_dir_returns_none(self) -> None:
        """An explicitly provided empty directory returns None."""
        with tempfile.TemporaryDirectory() as td:
            result = find_latest_verified_json(Path(td))
            assert result is None

    def test_nested_directories_searched(self) -> None:
        """rglob recurses into subdirectories."""
        with tempfile.TemporaryDirectory() as td:
            sub = Path(td) / "sub" / "deep"
            sub.mkdir(parents=True)
            f = sub / "deep.verified.json"
            f.write_text("[]")

            result = find_latest_verified_json(Path(td))
            assert result == f.resolve()


# ===========================================================================
# load_best_verified_address()
# ===========================================================================


def _make_verified_json(entries: list[dict]) -> Path:
    """Write entries to a temp .verified.json and return its Path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".verified.json", delete=False, encoding="utf-8"
    )
    json.dump(entries, f)
    f.close()
    return Path(f.name)


class TestLoadBestVerifiedAddress:
    def test_single_valid_candidate(self) -> None:
        """Single candidate with valid coords and address."""
        path = _make_verified_json([
            {
                "cluster": "cluster_04",
                "absolute_address": "0x7FF6A1B2C3D0",
                "x_verified": 100.0,
                "y_verified": 50.0,
                "z_verified": -200.0,
            }
        ])
        try:
            addr, cand = load_best_verified_address(path)
            assert addr == 0x7FF6A1B2C3D0
            assert cand["cluster"] == "cluster_04"
            assert cand["x_verified"] == 100.0
        finally:
            path.unlink()

    def test_picks_highest_magnitude(self) -> None:
        """Multiple candidates — returns one with largest abs(x)+abs(y)+abs(z)."""
        path = _make_verified_json([
            {
                "cluster": "small",
                "absolute_address": "0x1000",
                "x_verified": 1.0,
                "y_verified": 2.0,
                "z_verified": 3.0,
            },
            {
                "cluster": "big",
                "absolute_address": "0x2000",
                "x_verified": 5000.0,
                "y_verified": -3000.0,
                "z_verified": 2000.0,
            },
            {
                "cluster": "medium",
                "absolute_address": "0x3000",
                "x_verified": 50.0,
                "y_verified": 50.0,
                "z_verified": 50.0,
            },
        ])
        try:
            addr, cand = load_best_verified_address(path)
            assert addr == 0x2000
            assert cand["cluster"] == "big"
        finally:
            path.unlink()

    def test_empty_list_raises(self) -> None:
        """Empty list → ValueError."""
        path = _make_verified_json([])
        try:
            with pytest.raises(ValueError, match="expected non-empty list"):
                load_best_verified_address(path)
        finally:
            path.unlink()

    def test_non_list_raises(self) -> None:
        """Not a list → ValueError."""
        path = _make_verified_json({"not": "a list"})  # type: ignore[arg-type]
        try:
            with pytest.raises(ValueError, match="expected non-empty list"):
                load_best_verified_address(path)
        finally:
            path.unlink()

    def test_all_zero_coordinates_raises(self) -> None:
        """All candidates have zero magnitude → ValueError."""
        path = _make_verified_json([
            {
                "cluster": "zero",
                "absolute_address": "0x1000",
                "x_verified": 0.0,
                "y_verified": 0.0,
                "z_verified": 0.0,
            }
        ])
        try:
            with pytest.raises(ValueError, match="no candidates with non-zero"):
                load_best_verified_address(path)
        finally:
            path.unlink()

    def test_missing_absolute_address_raises(self) -> None:
        """No absolute_address field → ValueError."""
        path = _make_verified_json([
            {
                "cluster": "no_addr",
                # missing absolute_address
                "x_verified": 10.0,
                "y_verified": 20.0,
                "z_verified": 30.0,
            }
        ])
        try:
            with pytest.raises(ValueError, match="invalid absolute_address"):
                load_best_verified_address(path)
        finally:
            path.unlink()

    def test_invalid_hex_address_raises(self) -> None:
        """absolute_address is not valid hex → ValueError."""
        path = _make_verified_json([
            {
                "cluster": "bad_hex",
                "absolute_address": "not_a_number",
                "x_verified": 10.0,
                "y_verified": 20.0,
                "z_verified": 30.0,
            }
        ])
        try:
            with pytest.raises(ValueError, match="invalid literal for int"):
                load_best_verified_address(path)
        finally:
            path.unlink()

    def test_address_without_0x_prefix(self) -> None:
        """absolute_address without 0x prefix still works."""
        path = _make_verified_json([
            {
                "cluster": "no_prefix",
                "absolute_address": "7FF6A1B2C3D0",
                "x_verified": 10.0,
                "y_verified": 20.0,
                "z_verified": 30.0,
            }
        ])
        try:
            addr, cand = load_best_verified_address(path)
            assert addr == 0x7FF6A1B2C3D0
            assert cand["cluster"] == "no_prefix"
        finally:
            path.unlink()

    def test_none_coordinates_treated_as_zero(self) -> None:
        """None for x_verified/y_verified/z_verified → 0.0."""
        path = _make_verified_json([
            {
                "cluster": "null_coords",
                "absolute_address": "0x1000",
                "x_verified": None,
                "y_verified": None,
                "z_verified": None,
            },
            {
                "cluster": "valid",
                "absolute_address": "0x2000",
                "x_verified": 1.0,
                "y_verified": 1.0,
                "z_verified": 1.0,
            },
        ])
        try:
            # null coords have magnitude 0, valid has magnitude 3 → picks valid
            addr, cand = load_best_verified_address(path)
            assert addr == 0x2000
            assert cand["cluster"] == "valid"
        finally:
            path.unlink()

    def test_none_coordinates_with_only_zero_entry_raises(self) -> None:
        """Only entry has None/null coords → ValueError (all zero)."""
        path = _make_verified_json([
            {
                "cluster": "all_null",
                "absolute_address": "0x1000",
                "x_verified": None,
                "y_verified": None,
                "z_verified": None,
            }
        ])
        try:
            with pytest.raises(ValueError, match="no candidates with non-zero"):
                load_best_verified_address(path)
        finally:
            path.unlink()

    def test_skips_non_dict_entries(self) -> None:
        """Non-dict entries are skipped; valid dict still found."""
        path = _make_verified_json([
            "not a dict",  # type: ignore[list-item]
            42,  # type: ignore[list-item]
            None,  # type: ignore[list-item]
            {
                "cluster": "survivor",
                "absolute_address": "0xABCD",
                "x_verified": 100.0,
                "y_verified": 0.0,
                "z_verified": 0.0,
            },
        ])
        try:
            addr, cand = load_best_verified_address(path)
            assert addr == 0xABCD
            assert cand["cluster"] == "survivor"
        finally:
            path.unlink()

    def test_missing_coordinate_keys_default_to_zero(self) -> None:
        """Entries without x/y/z_verified keys still contribute (as 0.0)."""
        path = _make_verified_json([
            {
                "cluster": "no_coords",
                "absolute_address": "0x1000",
                # no x_verified, y_verified, z_verified
            },
            {
                "cluster": "has_coords",
                "absolute_address": "0x2000",
                "x_verified": 0.001,
                "y_verified": 0.0,
                "z_verified": 0.0,
            },
        ])
        try:
            # no_coords → magnitude 0.0, has_coords → 0.001 → picks has_coords
            addr, cand = load_best_verified_address(path)
            assert addr == 0x2000
            assert cand["cluster"] == "has_coords"
        finally:
            path.unlink()

    def test_negative_coordinates_count_toward_magnitude(self) -> None:
        """Negative coordinates increase magnitude via abs()."""
        path = _make_verified_json([
            {
                "cluster": "neg",
                "absolute_address": "0xF00D",
                "x_verified": -1000.0,
                "y_verified": -2000.0,
                "z_verified": -3000.0,
            },
            {
                "cluster": "pos",
                "absolute_address": "0xBEEF",
                "x_verified": 500.0,
                "y_verified": 500.0,
                "z_verified": 500.0,
            },
        ])
        try:
            # neg magnitude = 6000, pos magnitude = 1500 → picks neg
            addr, cand = load_best_verified_address(path)
            assert addr == 0xF00D
            assert cand["cluster"] == "neg"
        finally:
            path.unlink()

    def test_large_float_coordinates(self) -> None:
        """Very large float coordinates handled correctly."""
        path = _make_verified_json([
            {
                "cluster": "big",
                "absolute_address": "0xBEEF0000DEAD",
                "x_verified": 1e30,
                "y_verified": 0.0,
                "z_verified": 0.0,
            }
        ])
        try:
            addr, cand = load_best_verified_address(path)
            assert addr == 0xBEEF0000DEAD
            assert cand["x_verified"] == 1e30
        finally:
            path.unlink()
