"""Unit tests for value-type scanning in ``scripts/live_memory_scanner.py``.

These tests use fixture-based process readers — no live process access required.
Tests cover:

    * _validate_value_type
    * scan_value_type (f32, i32, u32 ranges, NaN exclusion, max_matches cap)
    * build_value_scan_plan (dry-run, live-ready, refusal gates)
    * write_value_scan_reports
"""

from __future__ import annotations

import json
import os
import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.live_memory_scanner import (  # noqa: E402
    FixtureProcessReader,
    _validate_value_type,
    build_value_scan_plan,
    scan_value_type,
    write_value_scan_reports,
)


def _make_float_region(base: int, values: list[float]) -> tuple[int, bytes, str]:
    data = b"".join(struct.pack("<f", v) for v in values)
    return (base, data, "0x04")


def _make_int_region(base: int, values: list[int]) -> tuple[int, bytes, str]:
    data = b"".join(struct.pack("<i", v) for v in values)
    return (base, data, "0x04")


def _make_uint_region(base: int, values: list[int]) -> tuple[int, bytes, str]:
    data = b"".join(struct.pack("<I", v) for v in values)
    return (base, data, "0x04")


# ============================================================================
# _validate_value_type
# ============================================================================


class TestValidateValueType(unittest.TestCase):
    def test_valid_types(self):
        self.assertEqual(_validate_value_type("f32"), "f32")
        self.assertEqual(_validate_value_type("i32"), "i32")
        self.assertEqual(_validate_value_type("u32"), "u32")

    def test_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            _validate_value_type("f64")
        with self.assertRaises(ValueError):
            _validate_value_type("")


# ============================================================================
# scan_value_type — float32 range scan
# ============================================================================


class TestScanValueTypeFloat32(unittest.TestCase):
    def setUp(self):
        values = [1.0, 2.5, -3.0, 100.0, 0.0, -500.0, 500.0]
        self.reader = FixtureProcessReader([_make_float_region(0x1000, values)])

    def test_range_scan(self):
        result = scan_value_type(self.reader, "f32", 0.0, 10.0, max_scan_bytes=1024, max_matches=1024)
        self.assertEqual(result["MatchCount"], 3)
        self.assertEqual(result["BytesScanned"], 28)
        self.assertFalse(result["TimedOut"])
        matched_values = [m["Value"] for m in result["Matches"]]
        self.assertIn(0.0, matched_values)
        self.assertIn(1.0, matched_values)
        self.assertIn(2.5, matched_values)
        self.assertNotIn(100.0, matched_values)
        self.assertNotIn(-3.0, matched_values)

    def test_exact_inclusive_bound(self):
        result = scan_value_type(self.reader, "f32", 1.0, 1.0, max_scan_bytes=1024, max_matches=1024)
        self.assertEqual(result["MatchCount"], 1)
        self.assertEqual(result["Matches"][0]["Value"], 1.0)

    def test_empty_range(self):
        result = scan_value_type(self.reader, "f32", 9999.0, 10000.0, max_scan_bytes=1024, max_matches=1024)
        self.assertEqual(result["MatchCount"], 0)
        self.assertEqual(len(result["Matches"]), 0)


# ============================================================================
# scan_value_type — int32
# ============================================================================


class TestScanValueTypeInt32(unittest.TestCase):
    def test_range_scan(self):
        int_values = [-10, 0, 5, 42, 100, 304, 320, 328]
        int_reader = FixtureProcessReader([_make_int_region(0x2000, int_values)])
        result = scan_value_type(int_reader, "i32", 0, 50, max_scan_bytes=1024, max_matches=1024)
        self.assertEqual(result["MatchCount"], 3)
        self.assertEqual(result["ValueType"], "i32")
        matched_ints = [m["Value"] for m in result["Matches"]]
        self.assertIn(0, matched_ints)
        self.assertIn(5, matched_ints)
        self.assertIn(42, matched_ints)
        self.assertNotIn(100, matched_ints)


# ============================================================================
# scan_value_type — uint32
# ============================================================================


class TestScanValueTypeUint32(unittest.TestCase):
    def test_range_scan(self):
        uint_values = [0, 100, 0x304, 0x320, 0xFFFFFFFF, 0x7FFFFFFF]
        uint_reader = FixtureProcessReader([_make_uint_region(0x3000, uint_values)])
        result = scan_value_type(uint_reader, "u32", 0x300, 0x330, max_scan_bytes=1024, max_matches=1024)
        self.assertEqual(result["MatchCount"], 2)
        matched_uints = [m["Value"] for m in result["Matches"]]
        self.assertIn(0x304, matched_uints)
        self.assertIn(0x320, matched_uints)


# ============================================================================
# Edge cases
# ============================================================================


class TestScanValueTypeEdgeCases(unittest.TestCase):
    def test_nan_exclusion(self):
        nan_values = [float("nan"), 1.0, float("nan"), 2.5, float("-nan")]
        nan_reader = FixtureProcessReader([_make_float_region(0x4000, nan_values)])
        result = scan_value_type(nan_reader, "f32", 0.0, 10.0, max_scan_bytes=1024, max_matches=1024)
        self.assertEqual(result["MatchCount"], 2)

    def test_max_matches_cap(self):
        many_floats = [float(i) for i in range(100)]
        many_reader = FixtureProcessReader([_make_float_region(0x5000, many_floats)])
        result = scan_value_type(many_reader, "f32", 0.0, 100.0, max_scan_bytes=4096, max_matches=5)
        self.assertEqual(result["MatchCount"], 5)

    def test_multi_region(self):
        r1 = _make_float_region(0x1000, [1.0, 2.0])
        r2 = _make_float_region(0x3000, [3.0, 4.0])
        multi_reader = FixtureProcessReader([r1, r2])
        result = scan_value_type(multi_reader, "f32", 1.0, 4.0, max_scan_bytes=4096, max_matches=1024)
        self.assertEqual(result["MatchCount"], 4)
        self.assertEqual(result["RegionsScanned"], 2)
        addresses = [int(m["Address"], 16) for m in result["Matches"]]
        self.assertEqual(addresses, sorted(addresses))


# ============================================================================
# build_value_scan_plan
# ============================================================================


class TestBuildValueScanPlan(unittest.TestCase):
    def test_dry_run_plan(self):
        plan = build_value_scan_plan(
            repo_root=REPO_ROOT,
            process_name="rift_x64.exe",
            pid=0,
            value_type="f32",
            min_val=-500.0,
            max_val=500.0,
            execute_live_read=False,
            experimental_live=False,
            confirm_live_read=False,
            max_scan_bytes=16 * 1024 * 1024,
            max_matches=1024,
            max_regions=256,
            timeout_seconds=10,
        )
        self.assertEqual(plan["SchemaVersion"], "live-value-scan/v1")
        self.assertFalse(plan["LiveProcessReadExecuted"])
        self.assertFalse(plan["ExecutionAllowed"])
        self.assertGreater(len(plan["RefusalReasons"]), 0)
        self.assertEqual(plan["ValueType"], "f32")
        self.assertEqual(plan["MinValue"], -500.0)
        self.assertEqual(plan["MaxValue"], 500.0)
        self.assertTrue(plan["Safety"]["ReadOnly"])

    def test_live_ready_plan(self):
        plan = build_value_scan_plan(
            repo_root=REPO_ROOT,
            process_name="rift_x64.exe",
            pid=12345,
            value_type="i32",
            min_val=0,
            max_val=1000,
            execute_live_read=True,
            experimental_live=True,
            confirm_live_read=True,
            max_scan_bytes=16 * 1024 * 1024,
            max_matches=1024,
            max_regions=256,
            timeout_seconds=10,
        )
        self.assertTrue(plan["ExecutionAllowed"])
        self.assertEqual(plan["Pid"], 12345)
        self.assertEqual(len(plan["RefusalReasons"]), 0)

    def test_refuse_wrong_process(self):
        plan = build_value_scan_plan(
            repo_root=REPO_ROOT,
            process_name="notepad.exe",
            pid=12345,
            value_type="f32",
            min_val=0.0,
            max_val=100.0,
            execute_live_read=True,
            experimental_live=True,
            confirm_live_read=True,
            max_scan_bytes=16 * 1024 * 1024,
            max_matches=1024,
            max_regions=256,
            timeout_seconds=10,
        )
        self.assertFalse(plan["ExecutionAllowed"])

    def test_refuse_inverted_range(self):
        plan = build_value_scan_plan(
            repo_root=REPO_ROOT,
            process_name="rift_x64.exe",
            pid=12345,
            value_type="f32",
            min_val=500.0,
            max_val=100.0,
            execute_live_read=True,
            experimental_live=True,
            confirm_live_read=True,
            max_scan_bytes=16 * 1024 * 1024,
            max_matches=1024,
            max_regions=256,
            timeout_seconds=10,
        )
        self.assertFalse(plan["ExecutionAllowed"])


# ============================================================================
# write_value_scan_reports
# ============================================================================


class TestWriteValueScanReports(unittest.TestCase):
    def test_report_writing(self):
        plan = build_value_scan_plan(
            repo_root=REPO_ROOT,
            process_name="rift_x64.exe",
            pid=0,
            value_type="f32",
            min_val=0.0,
            max_val=10.0,
            execute_live_read=False,
            experimental_live=False,
            confirm_live_read=False,
            max_scan_bytes=16 * 1024 * 1024,
            max_matches=1024,
            max_regions=256,
            timeout_seconds=10,
        )
        plan["ScanResult"] = {
            "ValueType": "f32",
            "ValueTypeLabel": "float32",
            "MinValue": 0.0,
            "MaxValue": 10.0,
            "BytesScanned": 64,
            "RegionsScanned": 2,
            "TimedOut": False,
            "MatchCount": 3,
            "Matches": [
                {"Address": "0x1000", "Value": 1.0, "RegionBase": "0x1000", "OffsetInRegion": 0},
                {"Address": "0x1004", "Value": 2.5, "RegionBase": "0x1000", "OffsetInRegion": 4},
                {"Address": "0x1010", "Value": 0.0, "RegionBase": "0x1000", "OffsetInRegion": 16},
            ],
        }
        json_path, md_path = write_value_scan_reports(plan, REPO_ROOT)
        try:
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            report_json = json.loads(json_path.read_text())
            self.assertEqual(report_json["SchemaVersion"], "live-value-scan/v1")
            self.assertEqual(report_json["ScanResult"]["MatchCount"], 3)
            md_content = md_path.read_text()
            self.assertIn("Sample matches", md_content)
            self.assertIn("1.0", md_content)
        finally:
            if json_path.exists():
                os.unlink(json_path)
            if md_path.exists():
                os.unlink(md_path)


if __name__ == "__main__":
    unittest.main()
