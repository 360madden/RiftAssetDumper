"""Unit tests for probe-modrm-leads scaffolding in ``scripts/live_memory_scanner.py``.

These tests use fixture-based process readers and synthetic ModRM scan data —
no live process access required. Tests cover:

    * WildcardSignature parsing + matching
    * scan_wildcard_signatures (fixture-based)
    * Player coordinate likelihood scoring
    * extract_cluster_signatures from real modrm scan
    * build_probe_modrm_leads_plan (dry-run + gate validation)
    * CLI --list-json integration
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.live_memory_scanner import (  # noqa: E402
    FixtureProcessReader,
    build_probe_modrm_leads_plan,
    extract_cluster_signatures,
    load_modrm_scan,
    parse_wildcard_hex,
    scan_wildcard_signatures,
    score_player_coordinate_likelihood,
)
from scripts.probe_modrm_leads import main as probe_main  # noqa: E402

# ============================================================================
# WildcardSignature parsing + matching
# ============================================================================


class TestWildcardSignature(unittest.TestCase):
    def test_parse_basic(self):
        sig = parse_wildcard_hex("test", "48 83 EC 20 48 8B D9 ?? ?? ?? ??")
        self.assertEqual(sig.label, "test")
        self.assertEqual(sig.length, 11)

    def test_matches_exact_first_bytes(self):
        sig = parse_wildcard_hex("test", "48 83 EC 20 48 8B D9 ?? ?? ?? ??")
        buf = bytes([0x48, 0x83, 0xEC, 0x20, 0x48, 0x8B, 0xD9, 0xFF, 0xFF, 0xAA, 0xBB])
        self.assertTrue(sig.matches_at(buf))

    def test_wildcard_matches_any(self):
        sig = parse_wildcard_hex("test", "48 83 EC 20 48 8B D9 ?? ?? ?? ??")
        buf = bytes([0x48, 0x83, 0xEC, 0x20, 0x48, 0x8B, 0xD9, 0xAA, 0xBB, 0xCC, 0xDD])
        self.assertTrue(sig.matches_at(buf))

    def test_short_buffer_does_not_match(self):
        sig = parse_wildcard_hex("test", "48 83 EC 20 48 8B D9 ?? ?? ?? ??")
        self.assertFalse(sig.matches_at(bytes([0x48, 0x83, 0xEC])))

    def test_longest_exact_prefix(self):
        sig = parse_wildcard_hex("test", "48 83 EC 20 48 8B D9 ?? ?? ?? ??")
        prefix_bytes, prefix_len = sig.longest_exact_prefix()
        self.assertEqual(prefix_len, 7)
        self.assertEqual(prefix_bytes[0], 0x48)

    def test_longest_exact_prefix_wild_start(self):
        sig = parse_wildcard_hex("wild_at_start", "?? ?? 48 83 EC 20 ?? ??")
        p2, l2 = sig.longest_exact_prefix()
        self.assertEqual(l2, 4)
        self.assertEqual(p2[0], 0x48)

    def test_longest_exact_prefix_all_wild(self):
        sig = parse_wildcard_hex("all_wild", "?? ?? ?? ??")
        p3, l3 = sig.longest_exact_prefix()
        self.assertEqual(l3, 0)

    def test_longest_exact_prefix_no_wild(self):
        sig = parse_wildcard_hex("no_wild", "48 83 EC 20")
        p4, l4 = sig.longest_exact_prefix()
        self.assertEqual(l4, 4)

    def test_empty_sig_rejected(self):
        with self.assertRaises(ValueError):
            parse_wildcard_hex("empty", "")

    def test_malformed_hex_rejected(self):
        with self.assertRaises(ValueError):
            parse_wildcard_hex("bad", "XX 83 EC")


# ============================================================================
# scan_wildcard_signatures (fixture-based)
# ============================================================================


class TestScanWildcardSignatures(unittest.TestCase):
    def test_wildcard_fixture_scan(self):
        fixture_data = (
            b"\x00" * 100
            + bytes([0x48, 0x83, 0xEC, 0x20, 0x48, 0x8B, 0xD9, 0xFF, 0xAA])
            + b"\x00" * 100
        )
        fixture = FixtureProcessReader([(0x1000, fixture_data, "fixture")])
        wc_sig = parse_wildcard_hex("test_sig", "48 83 EC 20 48 8B D9 ?? ??")
        scan_result = scan_wildcard_signatures(
            fixture,
            [wc_sig],
            max_scan_bytes=1024,
            max_matches=5,
            max_regions=1,
            timeout_seconds=5,
            executable_only=False,
        )
        self.assertEqual(scan_result["SignatureResults"][0]["MatchCount"], 1)
        self.assertEqual(
            scan_result["SignatureResults"][0]["Matches"][0]["Address"],
            f"0x{0x1000 + 100:X}",
        )
        self.assertFalse(scan_result["TimedOut"])

    def test_boundary_crossing(self):
        border_data = b"\x00" * 253 + bytes([0x48]) + b"\x00" * 50
        border_fixture = FixtureProcessReader([(0x2000, border_data, "fixture")])
        short_sig = parse_wildcard_hex("short", "48")
        scan_border = scan_wildcard_signatures(
            border_fixture,
            [short_sig],
            max_scan_bytes=1024,
            max_matches=5,
            max_regions=1,
            timeout_seconds=5,
            executable_only=False,
        )
        self.assertEqual(scan_border["SignatureResults"][0]["MatchCount"], 1)


# ============================================================================
# Player coordinate likelihood scoring
# ============================================================================


class TestPlayerCoordinateLikelihood(unittest.TestCase):
    def test_pure_rbx_score(self):
        cluster = {
            "base_register_counts": {"RBX": 10},
            "target_offset_counts": {"0x310": 10},
            "hit_count": 10,
        }
        self.assertEqual(score_player_coordinate_likelihood(cluster), 1.0)

    def test_mixed_register_offset_score(self):
        cluster = {
            "base_register_counts": {"RBX": 5, "RAX": 5},
            "target_offset_counts": {"0x310": 5, "0x100": 5},
            "hit_count": 10,
        }
        self.assertEqual(score_player_coordinate_likelihood(cluster), 0.5)

    def test_no_player_regs_score(self):
        cluster = {
            "base_register_counts": {"RAX": 10},
            "target_offset_counts": {"0x100": 10},
            "hit_count": 10,
        }
        self.assertEqual(score_player_coordinate_likelihood(cluster), 0.0)

    def test_empty_cluster_score(self):
        cluster = {
            "base_register_counts": {},
            "target_offset_counts": {},
            "hit_count": 0,
        }
        self.assertEqual(score_player_coordinate_likelihood(cluster), 0.0)


# ============================================================================
# extract_cluster_signatures from real modrm scan
# ============================================================================


class TestExtractClusterSignatures(unittest.TestCase):
    def setUp(self):
        self.modrm_path = REPO_ROOT / "Exports" / "binary-phase1" / "modrm-memory-access-scan.json"

    def test_extract_from_real_scan(self):
        if not self.modrm_path.exists():
            self.skipTest(f"modrm scan not found at {self.modrm_path}")
        modrm_data = load_modrm_scan(self.modrm_path)
        clusters = extract_cluster_signatures(modrm_data, top_n=8)
        self.assertGreaterEqual(len(clusters), 1)
        # Check sorted by score descending
        for i in range(len(clusters) - 1):
            self.assertGreaterEqual(
                clusters[i]["player_coordinate_score"],
                clusters[i + 1]["player_coordinate_score"],
            )
        top = clusters[0]
        self.assertGreater(top["rank"], 0)
        self.assertTrue(top["label"].startswith("cluster_"))
        self.assertGreater(len(top["sig_hex"]), 0)
        self.assertGreater(top["player_coordinate_score"], 0)


# ============================================================================
# build_probe_modrm_leads_plan (dry-run + gate validation)
# ============================================================================


class TestBuildProbeModrmLeadsPlan(unittest.TestCase):
    def test_dry_run_plan(self):
        plan = build_probe_modrm_leads_plan(
            repo_root=REPO_ROOT,
            modrm_scan_path="Exports/binary-phase1/modrm-memory-access-scan.json",
            pid=0,
            process_name="rift_x64.exe",
            execute_live_read=False,
            experimental_live=False,
            confirm_live_read=False,
            max_scan_bytes=1024 * 1024,
            max_matches=4,
            max_regions=64,
            timeout_seconds=10,
            top_clusters=8,
        )
        self.assertEqual(plan["SchemaVersion"], "probe-modrm-leads/v1")
        self.assertFalse(plan["LiveProcessReadExecuted"])
        self.assertFalse(plan["ExecutionAllowed"])
        self.assertGreater(len(plan["RefusalReasons"]), 0)
        self.assertIn("dry-run-only-no-live-read-requested", plan["RefusalReasons"])
        self.assertEqual(plan["OutputDirectory"], "Exports/discovery-plan/stage5-live")
        self.assertGreaterEqual(plan["ClustersExtracted"], 0)
        self.assertEqual(plan["Limits"]["TopClusters"], 8)
        self.assertTrue(plan["Safety"]["ReadOnly"])
        self.assertTrue(plan["Safety"]["ExecutableRegionsOnly"])

    def test_live_read_blocked_without_pid(self):
        plan = build_probe_modrm_leads_plan(
            repo_root=REPO_ROOT,
            modrm_scan_path="Exports/binary-phase1/modrm-memory-access-scan.json",
            pid=0,
            process_name="rift_x64.exe",
            execute_live_read=True,
            experimental_live=True,
            confirm_live_read=True,
            max_scan_bytes=1024,
            max_matches=3,
            max_regions=2,
            timeout_seconds=5,
            top_clusters=3,
        )
        self.assertFalse(plan["ExecutionAllowed"])
        self.assertIn("missing-explicit---pid", plan["RefusalReasons"])

    def test_live_read_allowed_with_all_gates(self):
        plan = build_probe_modrm_leads_plan(
            repo_root=REPO_ROOT,
            modrm_scan_path="Exports/binary-phase1/modrm-memory-access-scan.json",
            pid=12345,
            process_name="rift_x64.exe",
            execute_live_read=True,
            experimental_live=True,
            confirm_live_read=True,
            max_scan_bytes=1024,
            max_matches=3,
            max_regions=2,
            timeout_seconds=5,
            top_clusters=3,
        )
        self.assertTrue(plan["ExecutionAllowed"])

    def test_wrong_process_name_refused(self):
        plan = build_probe_modrm_leads_plan(
            repo_root=REPO_ROOT,
            modrm_scan_path="Exports/binary-phase1/modrm-memory-access-scan.json",
            pid=12345,
            process_name="notepad.exe",
            execute_live_read=False,
            experimental_live=False,
            confirm_live_read=False,
            max_scan_bytes=1024,
            max_matches=3,
            max_regions=2,
            timeout_seconds=5,
            top_clusters=3,
        )
        self.assertIn("target-process-must-be-rift_x64.exe", plan["RefusalReasons"])


# ============================================================================
# CLI integration
# ============================================================================

class TestCLIIntegration(unittest.TestCase):
    def setUp(self):
        self.modrm_path = REPO_ROOT / "Exports" / "binary-phase1" / "modrm-memory-access-scan.json"

    def test_list_json_with_real_scan(self):
        if not self.modrm_path.exists():
            self.skipTest(f"modrm scan not found at {self.modrm_path}")
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = probe_main(["--modrm-scan", str(self.modrm_path), "--list-json"])
        self.assertEqual(exit_code, 0)
        cli_output = json.loads(output.getvalue())
        self.assertEqual(cli_output["SchemaVersion"], "probe-modrm-leads/v1")

    def test_list_json_without_modrm_fails(self):
        bad_path = REPO_ROOT / "Exports" / "binary-phase1" / "nonexistent.json"
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = probe_main(["--modrm-scan", str(bad_path), "--list-json"])
        self.assertNotEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
