"""Unit tests for snapshot-diff value scanning in ``scripts/live_memory_scanner.py``.

These tests use fixture-based process readers — no live process access required.
Tests cover:

    * scan_value_snapshot (empty, NaN exclusion, basic)
    * diff_value_snapshots (single candidates, Vector3 triples)
    * build_diff_scan_plan (snapshot-a, snapshot-b, refusal gates)
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.live_memory_scanner import (  # noqa: E402
    FixtureProcessReader,
    build_diff_scan_plan,
    diff_value_snapshots,
    scan_value_snapshot,
)


def _make_region(base: int, floats: list[float]) -> tuple[int, bytes, str]:
    data = b"".join(struct.pack("<f", f) for f in floats)
    return (base, data, "0x04")


# ============================================================================
# scan_value_snapshot
# ============================================================================


class TestScanValueSnapshot(unittest.TestCase):
    def test_basic_snapshot(self):
        reader = FixtureProcessReader([_make_region(0x1000, [1.0, 2.0, 3.0, 100.0, 200.0])])
        snap = scan_value_snapshot(reader, "f32", 0.0, 500.0, max_scan_bytes=65536)
        self.assertEqual(snap["SchemaVersion"], "live-value-snapshot/v1")
        self.assertEqual(snap["ValueType"], "f32")
        self.assertEqual(snap["MatchCount"], 5)
        self.assertEqual(snap["Snapshot"].get("0x1000"), 1.0)
        self.assertEqual(snap["Snapshot"].get("0x1004"), 2.0)

    def test_empty_region(self):
        reader = FixtureProcessReader([])
        snap = scan_value_snapshot(reader, "f32", 0.0, 500.0)
        self.assertEqual(snap["MatchCount"], 0)
        self.assertEqual(len(snap["Snapshot"]), 0)

    def test_nan_exclusion(self):
        reader = FixtureProcessReader(
            [_make_region(0x2000, [float("nan"), 1.0, float("nan"), 2.0])]
        )
        snap = scan_value_snapshot(reader, "f32", 0.0, 10.0)
        self.assertEqual(snap["MatchCount"], 2)
        self.assertEqual(sorted(snap["Snapshot"].keys()), ["0x2004", "0x200C"])


# ============================================================================
# diff_value_snapshots
# ============================================================================


class TestDiffValueSnapshots(unittest.TestCase):
    def setUp(self):
        self.snap_a = {
            "SchemaVersion": "live-value-snapshot/v1",
            "Timestamp": "2026-07-03T00:00:00Z",
            "ValueType": "f32",
            "Snapshot": {
                "0x1000": 10.0,
                "0x1004": 5.0,
                "0x1008": 1.0,
                "0x100C": 7.0,
                "0x1010": 100.0,
            },
        }
        self.snap_b = {
            "SchemaVersion": "live-value-snapshot/v1",
            "Timestamp": "2026-07-03T00:01:00Z",
            "ValueType": "f32",
            "Snapshot": {
                "0x1000": 12.0,
                "0x1004": 5.5,
                "0x1008": 0.99,
                "0x100C": 7.0,
            },
        }

    def test_intersection_and_changed_counts(self):
        diff = diff_value_snapshots(self.snap_a, self.snap_b)
        self.assertEqual(diff["Stats"]["IntersectionCount"], 4)
        self.assertEqual(diff["Stats"]["ChangedCount"], 2)

    def test_single_candidate_score(self):
        diff = diff_value_snapshots(self.snap_a, self.snap_b)
        singles = diff["SingleCandidates"]
        self.assertEqual(len(singles), 2)
        self.assertGreaterEqual(singles[0]["Score"], 150)

    def test_vector3_triple_detection(self):
        snap_a3 = {
            "SchemaVersion": "live-value-snapshot/v1",
            "ValueType": "f32",
            "Snapshot": {
                "0x3000": 0.0, "0x3004": 0.0, "0x3008": 0.0,
                "0x4000": 5.0, "0x4004": 10.0, "0x4008": 15.0,
            },
        }
        snap_b3 = {
            "SchemaVersion": "live-value-snapshot/v1",
            "ValueType": "f32",
            "Snapshot": {
                "0x3000": 0.0, "0x3004": 0.0, "0x3008": 0.0,
                "0x4000": 6.0, "0x4004": 11.0, "0x4008": 16.0,
            },
        }
        diff3 = diff_value_snapshots(snap_a3, snap_b3)
        vec3s = diff3["Vector3Candidates"]
        self.assertEqual(len(vec3s), 1)
        self.assertEqual(vec3s[0]["BaseAddress"], "0x4000")
        self.assertEqual(vec3s[0]["ValuesB"], [6.0, 11.0, 16.0])


# ============================================================================
# build_diff_scan_plan
# ============================================================================


class TestBuildDiffScanPlan(unittest.TestCase):
    def test_snapshot_a_plan(self):
        plan = build_diff_scan_plan(
            repo_root=REPO_ROOT,
            process_name="rift_x64.exe",
            pid=0,
            value_type="f32",
            min_val=0.0,
            max_val=100.0,
            execute_live_read=False,
            experimental_live=False,
            confirm_live_read=False,
            max_scan_bytes=65536,
            max_matches=64,
            max_regions=32,
            timeout_seconds=10,
        )
        self.assertEqual(plan["SchemaVersion"], "live-snapshot-diff/v1")
        self.assertEqual(plan["Pass"], "snapshot-a")
        self.assertFalse(plan["ExecutionAllowed"])

    def test_refuse_wrong_process(self):
        plan = build_diff_scan_plan(
            repo_root=REPO_ROOT,
            process_name="notepad.exe",
            pid=0,
            value_type="f32",
            min_val=0.0,
            max_val=100.0,
            execute_live_read=False,
            experimental_live=False,
            confirm_live_read=False,
            max_scan_bytes=65536,
            max_matches=64,
            max_regions=32,
            timeout_seconds=10,
        )
        self.assertIn("target-process-must-be-rift_x64.exe", plan["RefusalReasons"])


# ============================================================================
# Integration test
# ============================================================================


class TestSnapshotDiffIntegration(unittest.TestCase):
    def test_full_pipeline(self):
        region_a = (0xA000, b"".join(struct.pack("<f", f) for f in [100.0, 50.0, 0.0, 999.0]), "0x04")
        reader_a = FixtureProcessReader([region_a])
        snap_a = scan_value_snapshot(reader_a, "f32", 0.0, 1000.0)

        region_b = (0xA000, b"".join(struct.pack("<f", f) for f in [102.0, 49.0, 0.0, 999.0]), "0x04")
        reader_b = FixtureProcessReader([region_b])
        snap_b = scan_value_snapshot(reader_b, "f32", 0.0, 1000.0)

        diff = diff_value_snapshots(snap_a, snap_b)
        self.assertEqual(diff["Stats"]["IntersectionCount"], 4)
        self.assertEqual(diff["Stats"]["ChangedCount"], 2)


if __name__ == "__main__":
    unittest.main()
