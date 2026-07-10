"""Integration test: full pipeline from probe_modrm_leads JSON through
x64dbg_bridge (generate → simulate log → parse → verify) to
position_watcher auto-mode address loading.

Tests the end-to-end data flow without requiring a live RIFT process.
Uses synthetic probe JSON, synthetic x64dbg log lines, and temp-file
verified.json fixtures.
"""

from __future__ import annotations

import json
import re
import struct
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from scripts.live_memory_scanner import FixtureProcessReader
from scripts.position_watcher import (
    find_latest_verified_json,
    load_best_verified_address,
)
from scripts.x64dbg_bridge import (
    _LOG_LINE_RE,
    BreakpointSpec,
    LogEntry,
    analyze_log_entries,
    generate_x64dbg_script,
    load_breakpoint_specs,
    parse_x64dbg_log,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockProcessReader:
    """Shared mock for WindowsReadOnlyProcessReader.

    Two modes:
    - Pass *fixture* to wrap a ``FixtureProcessReader`` (used when
      ``verify_coordinate_candidates`` reads from it via ``__enter__``).
    - Pass *read_bytes* for a simple mock whose ``read()`` always returns
      the same bytes (used for empty/graceful-failure tests).
    """

    def __init__(
        self,
        pid: int,
        fixture: FixtureProcessReader | None = None,
        read_bytes: bytes = b"",
    ) -> None:
        self._pid = pid
        self._fixture = fixture
        self._read_bytes = read_bytes

    def __enter__(self) -> FixtureProcessReader | _MockProcessReader:
        if self._fixture is not None:
            return self._fixture
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def read(self, base_address: int, size: int) -> bytes:
        return self._read_bytes


def _f32_to_hex(v: float) -> str:
    """Encode a float as the hex value x64dbg's {dword}(addr) would output.

    x64dbg reads 4 bytes from memory, interprets them as a little-endian
    uint32 (native x64 byte order), and returns that integer as hex.
    So for float 500.0 (bytes 00 00 FA 43 in memory), {dword}(addr)
    returns ``43FA0000``.
    """
    raw = struct.unpack("<I", struct.pack("<f", v))[0]
    return f"{raw:08X}"


def _make_probe_json(entries: list[dict]) -> Path:
    """Write a minimal probe-modrm-leads JSON to a temp file and return its Path."""
    data = {
        "SchemaVersion": "probe-modrm-leads/v1",
        "TargetProcessName": "rift_x64.exe",
        "Pid": 0,
        "ConfirmedClusters": entries,
    }
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, f)
    f.close()
    return Path(f.name)


def _make_verified_json(entries: list[dict]) -> Path:
    """Write a verified.json list to a temp file and return its Path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".verified.json", delete=False, encoding="utf-8")
    json.dump(entries, f)
    f.close()
    return Path(f.name)


def _make_log_file(lines: list[str]) -> Path:
    """Write log lines to a temp file and return its Path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    f.write("\n".join(lines) + "\n")
    f.close()
    return Path(f.name)


# ---------------------------------------------------------------------------
# Step 1: probe JSON → BreakpointSpec
# ---------------------------------------------------------------------------


class TestProbeToSpecs:
    """Loading BreakpointSpec objects from a synthetic probe-modrm-leads JSON."""

    def test_loads_confirmed_clusters(self) -> None:
        probe = _make_probe_json(
            [
                {
                    "Label": "cluster_04",
                    "Rank": 4,
                    "FirstRVA": "0x13AD2EA",
                    "ConfirmedAtVA": "0x7FF60000D2EA",
                    "HitCount": 12,
                    "BaseRegisterCounts": {"RBX": 12},
                    "TargetOffsetCounts": {
                        "0x310": 3,
                        "0x318": 3,
                    },
                    "PlayerCoordinateScore": 1.0,
                    "SignatureConfirmed": True,
                    "SignaturesMatched": [
                        {
                            "Address": "0x7FF60000D2EA",
                            "RegionBase": "0x7FF600000000",
                            "OffsetInRegion": 53994,
                            "SnippetHex": "0000",
                        }
                    ],
                },
            ]
        )
        try:
            specs = load_breakpoint_specs(probe)
            assert len(specs) == 1
            spec = specs[0]
            assert spec.label == "cluster_04"
            assert spec.rva == "D2EA"
            assert spec.base_register == "rbx"
            assert 0x310 in spec.target_offsets
            assert 0x318 in spec.target_offsets
            assert spec.score == 1.0
        finally:
            probe.unlink()

    def test_skips_unconfirmed_clusters(self) -> None:
        probe = _make_probe_json(
            [
                {
                    "Label": "cluster_04",
                    "Rank": 4,
                    "FirstRVA": "0x13AD2EA",
                    "ConfirmedAtVA": "0x7FF60000D2EA",
                    "HitCount": 12,
                    "BaseRegisterCounts": {"RBX": 12},
                    "TargetOffsetCounts": {"0x310": 3},
                    "PlayerCoordinateScore": 1.0,
                    "SignatureConfirmed": False,  # NOT confirmed
                    "SignaturesMatched": [],
                },
                {
                    "Label": "cluster_05",
                    "Rank": 5,
                    "FirstRVA": "0x786B2F",
                    "ConfirmedAtVA": "0x7FF60007B2F",
                    "HitCount": 10,
                    "BaseRegisterCounts": {"RBX": 10},
                    "TargetOffsetCounts": {"0x310": 2},
                    "PlayerCoordinateScore": 1.0,
                    "SignatureConfirmed": True,
                    "SignaturesMatched": [
                        {
                            "Address": "0x7FF60007B2F",
                            "RegionBase": "0x7FF600000000",
                            "OffsetInRegion": 31535,
                            "SnippetHex": "0000",
                        }
                    ],
                },
            ]
        )
        try:
            specs = load_breakpoint_specs(probe)
            assert len(specs) == 1
            assert specs[0].label == "cluster_05"
        finally:
            probe.unlink()

    def test_no_base_register_counts_skips(self) -> None:
        """Cluster with empty BaseRegisterCounts is skipped."""
        probe = _make_probe_json(
            [
                {
                    "Label": "orphan",
                    "Rank": 1,
                    "FirstRVA": "0x1000",
                    "ConfirmedAtVA": "0x7FF60001000",
                    "HitCount": 5,
                    "BaseRegisterCounts": {},
                    "TargetOffsetCounts": {"0x310": 1},
                    "PlayerCoordinateScore": 0.5,
                    "SignatureConfirmed": True,
                    "SignaturesMatched": [
                        {
                            "Address": "0x7FF60001000",
                            "RegionBase": "0x7FF600000000",
                            "OffsetInRegion": 4096,
                            "SnippetHex": "0000",
                        }
                    ],
                },
            ]
        )
        try:
            specs = load_breakpoint_specs(probe)
            assert len(specs) == 0
        finally:
            probe.unlink()

    def test_speccs_sorted_by_score_descending(self) -> None:
        probe = _make_probe_json(
            [
                {
                    "Label": "low",
                    "Rank": 3,
                    "FirstRVA": "0x3000",
                    "ConfirmedAtVA": "0x7FF60003000",
                    "HitCount": 5,
                    "BaseRegisterCounts": {"RCX": 5},
                    "TargetOffsetCounts": {"0x310": 1},
                    "PlayerCoordinateScore": 0.3,
                    "SignatureConfirmed": True,
                    "SignaturesMatched": [
                        {
                            "Address": "0x7FF60003000",
                            "RegionBase": "0x7FF600000000",
                            "OffsetInRegion": 0x3000,
                            "SnippetHex": "0000",
                        }
                    ],
                },
                {
                    "Label": "high",
                    "Rank": 1,
                    "FirstRVA": "0x1000",
                    "ConfirmedAtVA": "0x7FF60001000",
                    "HitCount": 10,
                    "BaseRegisterCounts": {"RBX": 10},
                    "TargetOffsetCounts": {"0x310": 5},
                    "PlayerCoordinateScore": 1.0,
                    "SignatureConfirmed": True,
                    "SignaturesMatched": [
                        {
                            "Address": "0x7FF60001000",
                            "RegionBase": "0x7FF600000000",
                            "OffsetInRegion": 0x1000,
                            "SnippetHex": "0000",
                        }
                    ],
                },
            ]
        )
        try:
            specs = load_breakpoint_specs(probe)
            assert len(specs) == 2
            assert specs[0].label == "high"
            assert specs[1].label == "low"
        finally:
            probe.unlink()

    def test_registers_lowercased(self) -> None:
        """Base registers from the JSON are lowercased."""
        probe = _make_probe_json(
            [
                {
                    "Label": "upper",
                    "Rank": 1,
                    "FirstRVA": "0x1000",
                    "ConfirmedAtVA": "0x7FF60001000",
                    "HitCount": 5,
                    "BaseRegisterCounts": {"RBX": 5},
                    "TargetOffsetCounts": {"0x310": 1},
                    "PlayerCoordinateScore": 1.0,
                    "SignatureConfirmed": True,
                    "SignaturesMatched": [
                        {
                            "Address": "0x7FF60001000",
                            "RegionBase": "0x7FF600000000",
                            "OffsetInRegion": 0x1000,
                            "SnippetHex": "0000",
                        }
                    ],
                },
            ]
        )
        try:
            specs = load_breakpoint_specs(probe)
            assert specs[0].base_register == "rbx"
        finally:
            probe.unlink()


# ---------------------------------------------------------------------------
# Step 2: BreakpointSpec → x64dbg script
# ---------------------------------------------------------------------------


class TestSpecsToScript:
    """Generating x64dbg command scripts from BreakpointSpec objects."""

    def test_generates_script_with_bplog_and_bpcnd(self) -> None:
        spec = BreakpointSpec(
            label="cluster_04",
            rva="13AD2EA",
            base_register="rbx",
            target_offsets=[0x310, 0x318, 0x320],
            module_name="rift_x64.exe",
            score=1.0,
        )
        script = generate_x64dbg_script([spec])
        assert "bp rift_x64.exe+13AD2EA" in script
        assert "bpcnd rift_x64.exe+13AD2EA, 0" in script
        assert "bplog rift_x64.exe+13AD2EA" in script
        assert "[RIFT_BRIDGE]" in script
        assert "hit=cluster_04" in script
        assert "reg=rbx" in script
        assert "base={rbx}" in script
        # x64dbg expr format: {dword(reg+offset)} — braces wrap the full expression
        assert "{dword(rbx+0x310)}" in script

    def test_includes_coordinate_offsets_not_in_target(self) -> None:
        """All COORDINATE_OFFSETS appear even if not in target_offsets."""
        spec = BreakpointSpec(
            label="test",
            rva="1000",
            base_register="rcx",
            target_offsets=[0x310],  # only one target offset
            module_name="rift_x64.exe",
            score=0.5,
        )
        script = generate_x64dbg_script([spec])
        # Should include all 10 COORDINATE_OFFSETS
        for off in [0x304, 0x308, 0x310, 0x320, 0x328]:
            assert f"{off:#x}" in script, f"Missing offset {off:#x}"

    def test_writes_to_disk(self) -> None:
        spec = BreakpointSpec(
            label="cluster_04",
            rva="13AD2EA",
            base_register="rbx",
            target_offsets=[0x310],
            module_name="rift_x64.exe",
            score=1.0,
        )
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "script.txt"
            script = generate_x64dbg_script([spec], out)
            assert out.exists()
            wrote = out.read_text()
            assert wrote == script
            assert "rift_x64.exe+13AD2EA" in wrote

    def test_multi_spec_script(self) -> None:
        specs = [
            BreakpointSpec(
                label="cluster_04",
                rva="13AD2EA",
                base_register="rbx",
                target_offsets=[0x310],
                module_name="rift_x64.exe",
                score=1.0,
            ),
            BreakpointSpec(
                label="cluster_05",
                rva="786B2F",
                base_register="rcx",
                target_offsets=[0x320],
                module_name="rift_x64.exe",
                score=0.95,
            ),
        ]
        script = generate_x64dbg_script(specs)
        assert "rift_x64.exe+13AD2EA" in script
        assert "rift_x64.exe+786B2F" in script
        assert "hit=cluster_04" in script
        assert "hit=cluster_05" in script
        assert "reg=rbx" in script
        assert "reg=rcx" in script


# ---------------------------------------------------------------------------
# Step 3: simulate x64dbg log → parse
# ---------------------------------------------------------------------------


class TestSimulateLogAndParse:
    """Generate a synthetic x64dbg log and parse it into LogEntry objects."""

    # Pre-computed IEEE 754 float32 hex values
    COORD_X = 500.0  # 0x43FA0000
    COORD_Y = 50.0  # 0x42480000
    COORD_Z = -800.0  # 0xC4480000
    BASE_PTR = 0x7FF600010000

    def _encode_log_line(
        self,
        cluster: str,
        reg: str,
        base: int,
        offset_values: dict[int, float],
    ) -> str:
        """Build a synthetic [RIFT_BRIDGE] log line matching x64dbg output."""
        parts = [f"[RIFT_BRIDGE] hit={cluster} reg={reg} base={base:#x}"]
        for off, val in offset_values.items():
            parts.append(f"{off:#x}={_f32_to_hex(val)}")
        return " ".join(parts)

    def _encode_coord_triple(
        self,
        cluster: str,
        reg: str,
        base: int,
        start_off: int,
    ) -> str:
        """Encode an (x,y,z) triple at consecutive offsets."""
        x = self.COORD_X + (start_off * 10)
        y = self.COORD_Y + (start_off * 2)
        z = self.COORD_Z - (start_off * 10)
        return self._encode_log_line(
            cluster,
            reg,
            base,
            {start_off: x, start_off + 4: y, start_off + 8: z},
        )

    def test_parse_single_rifp_bridge_line(self) -> None:
        line = self._encode_coord_triple(
            "cluster_04",
            "rbx",
            self.BASE_PTR,
            0x310,
        )
        log = _make_log_file([line, "# some noise", "non-bridge text"])
        try:
            entries = parse_x64dbg_log(log)
            assert len(entries) == 1
            e = entries[0]
            assert e.cluster == "cluster_04"
            assert e.base_register == "rbx"
            assert e.base_address == self.BASE_PTR
            assert 0x310 in e.offset_values
            assert 0x314 in e.offset_values
            assert 0x318 in e.offset_values
        finally:
            log.unlink()

    def test_float_unpacking_roundtrip(self) -> None:
        """IEEE 754 float32 round-trip through hex log → parse → float_at."""
        # Use _encode_log_line directly with exact values (no offset arithmetic)
        x, y, z = self.COORD_X, self.COORD_Y, self.COORD_Z
        line = self._encode_log_line(
            "cluster_04",
            "rbx",
            self.BASE_PTR,
            {0x310: x, 0x314: y, 0x318: z},
        )
        log = _make_log_file([line])
        try:
            entries = parse_x64dbg_log(log)
            e = entries[0]
            # Precision: ~7 decimal digits for float32
            assert e.float_at(0x310) == pytest.approx(self.COORD_X, rel=1e-5)
            assert e.float_at(0x314) == pytest.approx(self.COORD_Y, rel=1e-5)
            assert e.float_at(0x318) == pytest.approx(self.COORD_Z, rel=1e-5)
        finally:
            log.unlink()

    def test_multiple_hits_parsed(self) -> None:
        lines = [
            self._encode_coord_triple("cluster_04", "rbx", self.BASE_PTR, 0x310),
            self._encode_coord_triple("cluster_05", "rcx", 0x7FF600020000, 0x310),
            "some random log noise",
        ]
        log = _make_log_file(lines)
        try:
            entries = parse_x64dbg_log(log)
            assert len(entries) == 2
            assert {e.cluster for e in entries} == {"cluster_04", "cluster_05"}
        finally:
            log.unlink()

    def test_non_bridge_lines_ignored(self) -> None:
        # No [RIFT_BRIDGE] prefix — all ignored
        lines = [
            "bp rift_x64.exe+13AD2EA",
            "bpcnd rift_x64.exe+13AD2EA, 0",
            "log Setting breakpoint cluster_04",
        ]
        log = _make_log_file(lines)
        try:
            entries = parse_x64dbg_log(log)
            assert len(entries) == 0
        finally:
            log.unlink()

    def test_base_without_0x_prefix_still_parsed(self) -> None:
        """x64dbg may or may not prefix with 0x; regex handles both."""
        line = "[RIFT_BRIDGE] hit=test reg=rbx base=7FF600010000 0x310=C3FA0000 0x314=42480000"
        log = _make_log_file([line])
        try:
            entries = parse_x64dbg_log(log)
            assert len(entries) == 1
            assert entries[0].base_address == 0x7FF600010000
        finally:
            log.unlink()


# ---------------------------------------------------------------------------
# Step 4: parse → analyze → coord_candidates
# ---------------------------------------------------------------------------


class TestAnalyzeToCandidates:
    """Parse log entries → analyze → extract coordinate candidates."""

    BASE = 0x7FF600010000

    def _make_entry(
        self,
        cluster: str,
        base_reg: str,
        base_addr: int,
        offset_values: dict[int, float],
    ) -> LogEntry:
        return LogEntry(
            cluster=cluster,
            base_address=base_addr,
            base_register=base_reg,
            offset_values={k: struct.unpack("<I", struct.pack("<f", v))[0] for k, v in offset_values.items()},
        )

    def test_valid_triple_becomes_candidate(self) -> None:
        """A valid (x,y,z) triple at 0x310/0x314/0x318 → candidate."""
        entry = self._make_entry(
            "cluster_04",
            "rbx",
            self.BASE,
            {0x310: 150.0, 0x314: 25.0, 0x318: -300.0},
        )
        analysis = analyze_log_entries([entry])
        assert analysis["num_coord_candidates"] == 1
        c = analysis["coord_candidates"][0]
        assert c["cluster"] == "cluster_04"
        assert c["x"] == pytest.approx(150.0)
        assert c["y"] == pytest.approx(25.0)
        assert c["z"] == pytest.approx(-300.0)
        assert c["absolute_address"] == f"0x{self.BASE + 0x310:X}"

    def test_nan_values_rejected(self) -> None:
        entry = self._make_entry(
            "test",
            "rbx",
            self.BASE,
            {0x310: float("nan"), 0x314: 1.0, 0x318: 2.0},
        )
        analysis = analyze_log_entries([entry])
        assert analysis["num_coord_candidates"] == 0

    def test_all_zero_triple_rejected(self) -> None:
        entry = self._make_entry(
            "test",
            "rbx",
            self.BASE,
            {0x310: 0.0, 0x314: 0.0, 0x318: 0.0},
        )
        # analyze_log_entries applies coordinate validation internally
        # The triple (0,0,0) is rejected by _is_valid_coord_triple (near-zero check)
        analysis = analyze_log_entries([entry])
        assert analysis["num_coord_candidates"] == 0

    def test_out_of_bounds_rejected(self) -> None:
        entry = self._make_entry(
            "test",
            "rbx",
            self.BASE,
            {0x310: 99999.0, 0x314: 0.0, 0x318: 99999.0},
        )
        analysis = analyze_log_entries([entry])
        assert analysis["num_coord_candidates"] == 0

    def test_multiple_offset_slots_detected(self) -> None:
        """If data has coords at 0x310 and 0x320, both are candidates."""
        entry = self._make_entry(
            "test",
            "rbx",
            self.BASE,
            {
                0x310: 10.0,
                0x314: 20.0,
                0x318: 30.0,
                0x320: 100.0,
                0x324: 200.0,
                0x328: 300.0,
            },
        )
        analysis = analyze_log_entries([entry])
        assert analysis["num_coord_candidates"] == 2

    def test_cluster_hits_counted(self) -> None:
        e1 = self._make_entry(
            "cluster_04",
            "rbx",
            self.BASE,
            {0x310: 10.0, 0x314: 20.0, 0x318: 30.0},
        )
        e2 = self._make_entry(
            "cluster_04",
            "rbx",
            self.BASE + 0x1000,
            {0x310: 40.0, 0x314: 50.0, 0x318: 60.0},
        )
        analysis = analyze_log_entries([e1, e2])
        assert analysis["cluster_hits"]["cluster_04"] == 2
        assert analysis["unique_bases"] is not None

    def test_unique_bases_tracked(self) -> None:
        e1 = self._make_entry(
            "a",
            "rbx",
            0x1000,
            {0x310: 1.0, 0x314: 2.0, 0x318: 3.0},
        )
        e2 = self._make_entry(
            "b",
            "rbx",
            0x2000,
            {0x310: 4.0, 0x314: 5.0, 0x318: 6.0},
        )
        analysis = analyze_log_entries([e1, e2])
        assert analysis["num_unique_bases"] == 2


# ---------------------------------------------------------------------------
# Step 5: verified.json + position_watcher auto-load
# ---------------------------------------------------------------------------


class TestVerifiedToPositionWatcher:
    """Load verified.json → position_watcher auto-mode address resolution."""

    def test_best_address_loaded_from_verified(self) -> None:
        vf = _make_verified_json(
            [
                {
                    "cluster": "cluster_04",
                    "absolute_address": "0x7FF60001310",
                    "x_verified": 500.0,
                    "y_verified": 50.0,
                    "z_verified": -800.0,
                },
            ]
        )
        try:
            addr, cand = load_best_verified_address(vf)
            assert addr == 0x7FF60001310
            assert cand["cluster"] == "cluster_04"
        finally:
            vf.unlink()

    def test_picks_highest_magnitude_from_verified(self) -> None:
        vf = _make_verified_json(
            [
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
                    "y_verified": 3000.0,
                    "z_verified": -2000.0,
                },
            ]
        )
        try:
            addr, cand = load_best_verified_address(vf)
            assert addr == 0x2000
            assert cand["cluster"] == "big"
        finally:
            vf.unlink()

    def test_find_latest_verified_json_in_temp_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # Create a verified.json in a subdirectory
            sub = Path(td) / "stage5-live"
            sub.mkdir()
            vf = sub / "test.verified.json"
            vf.write_text(
                json.dumps(
                    [
                        {
                            "cluster": "found",
                            "absolute_address": "0xBEEF",
                            "x_verified": 1.0,
                            "y_verified": 1.0,
                            "z_verified": 1.0,
                        }
                    ]
                )
            )

            result = find_latest_verified_json(Path(td))
            assert result is not None
            assert result.name == "test.verified.json"

    def test_load_best_from_latest_verified(self) -> None:
        """End-to-end: find latest verified.json and load best address."""
        with tempfile.TemporaryDirectory() as td:
            vf = Path(td) / "pipeline.verified.json"
            vf.write_text(
                json.dumps(
                    [
                        {
                            "cluster": "pipeline",
                            "absolute_address": "0xDECAF",
                            "x_verified": 100.0,
                            "y_verified": 0.0,
                            "z_verified": 200.0,
                        },
                    ]
                )
            )

            found = find_latest_verified_json(Path(td))
            assert found is not None
            addr, cand = load_best_verified_address(found)
            assert addr == 0xDECAF
            assert cand["cluster"] == "pipeline"


# ---------------------------------------------------------------------------
# Step 6: full simulated pipeline (no live process)
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """End-to-end: synthetic probe JSON → specs → script → simulate log
    → parse → analyze → candidates → verified.json → position_watcher auto.
    """

    REGION_BASE = 0x7FF600000000
    PLAYER_BASE = 0x7FF600010000

    def test_full_simulated_pipeline(self) -> None:
        """Drive the full pipeline end-to-end with synthetic data."""
        # --- Phase 1: probe JSON → BreakpointSpec objects ---
        probe = _make_probe_json(
            [
                {
                    "Label": "cluster_04",
                    "Rank": 4,
                    "FirstRVA": "0x13AD2EA",
                    "ConfirmedAtVA": f"0x{self.REGION_BASE + 0x13AD2EA:X}",
                    "HitCount": 12,
                    "BaseRegisterCounts": {"RBX": 12},
                    "TargetOffsetCounts": {
                        "0x310": 3,
                        "0x318": 3,
                        "0x320": 3,
                    },
                    "PlayerCoordinateScore": 1.0,
                    "SignatureConfirmed": True,
                    "SignaturesMatched": [
                        {
                            "Address": f"0x{self.REGION_BASE + 0x13AD2EA:X}",
                            "RegionBase": f"0x{self.REGION_BASE:X}",
                            "OffsetInRegion": 0x13AD2EA,
                            "SnippetHex": "0000",
                        }
                    ],
                },
                {
                    "Label": "cluster_05",
                    "Rank": 5,
                    "FirstRVA": "0x786B2F",
                    "ConfirmedAtVA": f"0x{self.REGION_BASE + 0x786B2F:X}",
                    "HitCount": 10,
                    "BaseRegisterCounts": {"RCX": 10},
                    "TargetOffsetCounts": {
                        "0x320": 2,
                        "0x310": 2,
                    },
                    "PlayerCoordinateScore": 0.95,
                    "SignatureConfirmed": True,
                    "SignaturesMatched": [
                        {
                            "Address": f"0x{self.REGION_BASE + 0x786B2F:X}",
                            "RegionBase": f"0x{self.REGION_BASE:X}",
                            "OffsetInRegion": 0x786B2F,
                            "SnippetHex": "0000",
                        }
                    ],
                },
            ]
        )
        try:
            specs = load_breakpoint_specs(probe)
            assert len(specs) == 2
            # Verify register resolution
            spec_map = {s.label: s for s in specs}
            assert spec_map["cluster_04"].base_register == "rbx"
            assert spec_map["cluster_05"].base_register == "rcx"

            # --- Phase 2: specs → x64dbg script ---
            script = generate_x64dbg_script(specs)
            assert "bplog rift_x64.exe+13AD2EA" in script
            assert "bplog rift_x64.exe+786B2F" in script
            assert "bpcnd rift_x64.exe+13AD2EA, 0" in script
            assert "bpcnd rift_x64.exe+786B2F, 0" in script

            # --- Phase 3: simulate x64dbg log ---
            # Build log lines that match the bplog format
            # For cluster_04 (rbx): coords at 0x310/0x314/0x318
            log_lines = [
                (
                    "[RIFT_BRIDGE] hit=cluster_04 reg=rbx "
                    f"base=0x{self.PLAYER_BASE:X} "
                    f"0x304={_f32_to_hex(0.0)} "
                    f"0x308={_f32_to_hex(0.0)} "
                    f"0x30C={_f32_to_hex(0.0)} "
                    f"0x310={_f32_to_hex(500.0)} "
                    f"0x314={_f32_to_hex(50.0)} "
                    f"0x318={_f32_to_hex(-800.0)} "
                    f"0x31C={_f32_to_hex(0.0)} "
                    f"0x320={_f32_to_hex(0.0)} "
                    f"0x324={_f32_to_hex(0.0)} "
                    f"0x328={_f32_to_hex(0.0)}"
                ),
                # cluster_05 (rcx): coords at 0x310/0x314/0x318 (same offsets)
                (
                    "[RIFT_BRIDGE] hit=cluster_05 reg=rcx "
                    f"base=0x{self.PLAYER_BASE + 0x1000:X} "
                    f"0x304={_f32_to_hex(0.0)} "
                    f"0x308={_f32_to_hex(0.0)} "
                    f"0x30C={_f32_to_hex(0.0)} "
                    f"0x310={_f32_to_hex(1000.0)} "
                    f"0x314={_f32_to_hex(1100.0)} "
                    f"0x318={_f32_to_hex(-2000.0)} "
                    f"0x31C={_f32_to_hex(0.0)} "
                    f"0x320={_f32_to_hex(0.0)} "
                    f"0x324={_f32_to_hex(0.0)} "
                    f"0x328={_f32_to_hex(0.0)}"
                ),
            ]
            log = _make_log_file(log_lines)
            try:
                # --- Phase 4: parse log → entries ---
                entries = parse_x64dbg_log(log)
                assert len(entries) == 2

                # Verify float unpacking
                e4 = entries[0]
                assert e4.float_at(0x310) == pytest.approx(500.0, rel=1e-6)
                assert e4.float_at(0x314) == pytest.approx(50.0, rel=1e-6)
                assert e4.float_at(0x318) == pytest.approx(-800.0, rel=1e-6)

                # --- Phase 5: analyze → coord_candidates ---
                analysis = analyze_log_entries(entries, specs)
                assert analysis["num_coord_candidates"] >= 2  # one per entry
                assert analysis["cluster_hits"]["cluster_04"] == 1
                assert analysis["cluster_hits"]["cluster_05"] == 1

                candidates = analysis["coord_candidates"]
                # cluster_04 coords: (500, 50, -800), magnitude ~1350
                # cluster_05 coords: (1000, 1100, -2000), magnitude ~4100
                # cluster_05 should have the higher magnitude

                # --- Phase 6: simulate verified.json output ---
                verified_entries = [
                    {
                        "cluster": c["cluster"],
                        "absolute_address": c["absolute_address"],
                        "x_verified": c["x"],
                        "y_verified": c["y"],
                        "z_verified": c["z"],
                    }
                    for c in candidates
                ]
                vf = _make_verified_json(verified_entries)
                try:
                    # --- Phase 7: position_watcher auto-load ---
                    addr, cand = load_best_verified_address(vf)
                    # Should pick cluster_05 (higher magnitude: 4100 vs 1350)
                    assert cand["cluster"] == "cluster_05"
                    assert addr == self.PLAYER_BASE + 0x1000 + 0x310

                    # Verify the loaded coordinates match
                    assert cand["x_verified"] == pytest.approx(1000.0, rel=1e-5)
                    assert cand["y_verified"] == pytest.approx(1100.0, rel=1e-5)
                    assert cand["z_verified"] == pytest.approx(-2000.0, rel=1e-5)
                finally:
                    vf.unlink()
            finally:
                log.unlink()
        finally:
            probe.unlink()

    def test_pipeline_with_empty_hits(self) -> None:
        """Probe JSON loaded but simulated log has no [RIFT_BRIDGE] lines."""
        probe = _make_probe_json(
            [
                {
                    "Label": "cluster_04",
                    "Rank": 4,
                    "FirstRVA": "0x13AD2EA",
                    "ConfirmedAtVA": f"0x{self.REGION_BASE + 0x13AD2EA:X}",
                    "HitCount": 12,
                    "BaseRegisterCounts": {"RBX": 12},
                    "TargetOffsetCounts": {"0x310": 3},
                    "PlayerCoordinateScore": 1.0,
                    "SignatureConfirmed": True,
                    "SignaturesMatched": [
                        {
                            "Address": f"0x{self.REGION_BASE + 0x13AD2EA:X}",
                            "RegionBase": f"0x{self.REGION_BASE:X}",
                            "OffsetInRegion": 0x13AD2EA,
                            "SnippetHex": "0000",
                        }
                    ],
                },
            ]
        )
        try:
            specs = load_breakpoint_specs(probe)
            assert len(specs) == 1

            # Log with no bridge hits
            log = _make_log_file(
                [
                    "bp rift_x64.exe+13AD2EA",
                    "bpcnd rift_x64.exe+13AD2EA, 0",
                    "log Breakpoints set",
                ]
            )
            try:
                entries = parse_x64dbg_log(log)
                assert len(entries) == 0
                analysis = analyze_log_entries(entries, specs)
                assert analysis["num_coord_candidates"] == 0
            finally:
                log.unlink()
        finally:
            probe.unlink()

    def test_bplog_template_round_trip(self) -> None:
        """Extract bplog template from script, fill with x64dbg expression
        rules, then parse the result and verify round-trip correctness.

        This is the most realistic test: it takes the EXACT format string
        x64dbg would use (the bplog "..." argument), substitutes register
        and memory values exactly as x64dbg would, and verifies our parser
        recovers the original values.
        """
        # --- Generate a script with known specs ---
        spec = BreakpointSpec(
            label="bplog_roundtrip",
            rva="DEAD",
            base_register="rbx",
            target_offsets=[0x310, 0x318],
            module_name="rift_x64.exe",
            score=1.0,
        )
        script = generate_x64dbg_script([spec])

        # --- Extract the bplog template (quoted string after the comma) ---
        bplog_line = next(
            (line for line in script.split("\n") if line.startswith("bplog ")),
            None,
        )
        assert bplog_line is not None, "No bplog line in generated script"

        # bplog rift_x64.exe+DEAD, "[RIFT_BRIDGE] ... {rbx} ... {dword(rbx+0x310)} ..."
        # [^,]+ matches the address without consuming the comma (avoids backtracking)
        template_match = re.search(r'bplog\s+[^,]+,\s+"(.+)"', bplog_line)
        assert template_match is not None, f"Could not extract template from bplog line:\n{bplog_line}"
        template = template_match.group(1)

        # Verify the template contains expected x64dbg expression patterns
        assert "{rbx}" in template
        assert "{dword(rbx+0x310)}" in template

        # --- Set up mock register/memory values ---
        mock_registers: dict[str, int] = {
            "rbx": 0x7FF6000BEEF,
        }
        # Memory at rbx+offset → dword value (hex string as x64dbg would output)
        mock_memory: dict[int, int] = {
            0x304: 0,
            0x308: 0,
            0x30C: 0,
            0x310: 0x43FA0000,  # 500.0f
            0x314: 0x42480000,  # 50.0f
            0x318: 0xC4480000,  # -800.0f
            0x31C: 0,
            0x320: 0,
            0x324: 0,
            0x328: 0,
        }

        # --- Apply x64dbg expression substitution rules ---
        # Rule 1: {register} → hex value WITH 0x prefix
        def sub_register(m: re.Match) -> str:
            reg = m.group(1)
            val = mock_registers.get(reg)
            if val is None:
                raise KeyError(f"No mock value for register {reg}")
            return f"0x{val:X}"

        # Rule 2: {dword(register+offset)} → raw hex WITHOUT 0x prefix
        def sub_dword(m: re.Match) -> str:
            reg = m.group(1)
            offset = int(m.group(2), 16)
            base = mock_registers.get(reg)
            if base is None:
                raise KeyError(f"No mock value for register {reg}")
            val = mock_memory.get(offset)
            if val is None:
                raise KeyError(f"No mock memory at offset {offset:#x}")
            return f"{val:08X}"

        filled = template
        # Apply {dword(...)} first (more specific pattern), then {register}
        filled = re.sub(
            r"\{dword\(([a-z]+)\+(0x[0-9A-Fa-f]+)\)\}",
            sub_dword,
            filled,
        )
        filled = re.sub(r"\{([a-z]+)\}", sub_register, filled)

        # The filled line IS the simulated x64dbg log output
        # It should match our parser's _LOG_LINE_RE
        log = _make_log_file([filled])
        try:
            entries = parse_x64dbg_log(log)
            assert len(entries) == 1, f"Expected 1 entry, got {len(entries)}. Filled line:\n{filled}"
            e = entries[0]

            # Verify cluster/register/base
            assert e.cluster == "bplog_roundtrip"
            assert e.base_register == "rbx"
            assert e.base_address == 0x7FF6000BEEF

            # Verify float unpacking of dword values
            assert e.float_at(0x310) == pytest.approx(500.0, rel=1e-5)
            assert e.float_at(0x314) == pytest.approx(50.0, rel=1e-5)
            assert e.float_at(0x318) == pytest.approx(-800.0, rel=1e-5)

            # Zero dwords unpack to 0.0
            assert e.float_at(0x304) == pytest.approx(0.0)
            assert e.float_at(0x328) == pytest.approx(0.0)
        finally:
            log.unlink()

    def test_verify_coordinate_candidates_with_mocked_reader(self) -> None:
        """Call verify_coordinate_candidates with a mocked
        WindowsReadOnlyProcessReader that returns fixture memory.

        This is the only pipeline stage that previously required a live
        RIFT process. The mock replaces the real ReadProcessMemory calls
        with in-memory fixture data, making the full pipeline testable
        offline.
        """
        from scripts.x64dbg_bridge import verify_coordinate_candidates

        # --- Set up fixture memory ---
        # Address 0x10000: valid player coords (500.0, 50.0, -800.0)
        # Address 0x20000: zero coords (should be rejected)
        # Address 0x30000: NaN coords (should be rejected)
        # Address 0x40000: out-of-bounds coords (should be rejected)

        def _f32_bytes(*values: float) -> bytes:
            return b"".join(struct.pack("<f", v) for v in values)

        fixture = FixtureProcessReader(
            [
                (0x10000, _f32_bytes(500.0, 50.0, -800.0), "rw"),
                (0x20000, _f32_bytes(0.0, 0.0, 0.0), "rw"),
                (0x30000, _f32_bytes(float("nan"), 1.0, 2.0), "rw"),
                (0x40000, _f32_bytes(99999.0, 99999.0, 99999.0), "rw"),
            ]
        )

        with mock.patch(
            "scripts.live_memory_scanner.WindowsReadOnlyProcessReader",
            lambda pid: _MockProcessReader(pid, fixture=fixture),
        ):
            candidates = [
                {
                    "cluster": "cluster_04",
                    "absolute_address": "0x10000",
                    "base_register": "rbx",
                },
                {
                    "cluster": "cluster_04",
                    "absolute_address": "0x20000",
                    "base_register": "rbx",
                },
                {
                    "cluster": "cluster_04",
                    "absolute_address": "0x30000",
                    "base_register": "rbx",
                },
                {
                    "cluster": "cluster_04",
                    "absolute_address": "0x40000",
                    "base_register": "rbx",
                },
            ]

            verified = verify_coordinate_candidates(candidates, pid=9999)

            # Only the first candidate (valid coords) should pass
            assert len(verified) == 1
            v = verified[0]
            assert v["absolute_address"] == "0x10000"
            assert v["x_verified"] == pytest.approx(500.0, rel=1e-5)
            assert v["y_verified"] == pytest.approx(50.0, rel=1e-5)
            assert v["z_verified"] == pytest.approx(-800.0, rel=1e-5)

    def test_verify_deduplicates_addresses(self) -> None:
        """Duplicate absolute_address entries are verified only once."""
        from scripts.x64dbg_bridge import verify_coordinate_candidates

        fixture = FixtureProcessReader(
            [
                (0xAAA00, struct.pack("<fff", 10.0, 20.0, 30.0), "rw"),
            ]
        )

        with mock.patch(
            "scripts.live_memory_scanner.WindowsReadOnlyProcessReader",
            lambda pid: _MockProcessReader(pid, fixture=fixture),
        ):
            candidates = [
                {"absolute_address": "0xAAA00"},
                {"absolute_address": "0xAAA00"},  # duplicate
                {"absolute_address": "0xAAA00"},  # duplicate
            ]
            verified = verify_coordinate_candidates(candidates, pid=9999)
            assert len(verified) == 1

    def test_verify_empty_candidates_returns_empty(self) -> None:
        """Empty candidate list → empty result."""
        from scripts.x64dbg_bridge import verify_coordinate_candidates

        with mock.patch(
            "scripts.live_memory_scanner.WindowsReadOnlyProcessReader",
            lambda pid: _MockProcessReader(pid, read_bytes=b"\x00" * 12),
        ):
            verified = verify_coordinate_candidates([], pid=9999)
            assert verified == []

    def test_verify_read_failure_graceful(self) -> None:
        """If reader.read returns empty/short data, candidate is skipped."""
        from scripts.x64dbg_bridge import verify_coordinate_candidates

        with mock.patch(
            "scripts.live_memory_scanner.WindowsReadOnlyProcessReader",
            lambda pid: _MockProcessReader(pid, read_bytes=b""),
        ):
            candidates = [
                {"absolute_address": "0x1000"},
            ]
            verified = verify_coordinate_candidates(candidates, pid=9999)
            assert verified == []

    def test_pipeline_cross_references_regex_and_parse(self) -> None:
        """Verify the LOG_LINE_RE regex correctly matches generated bplog format."""
        spec = BreakpointSpec(
            label="regex_test",
            rva="ABCD",
            base_register="rbp",
            target_offsets=[0x310, 0x318],
            module_name="rift_x64.exe",
            score=0.8,
        )
        script = generate_x64dbg_script([spec])

        # Extract and verify the bplog format string from the script
        bplog_line = next(
            (line for line in script.split("\n") if line.startswith("bplog ")),
            None,
        )
        assert bplog_line is not None, "No bplog line found in generated script"
        assert "[RIFT_BRIDGE]" in bplog_line
        assert "hit=regex_test" in bplog_line
        assert "reg=rbp" in bplog_line

        # The format is: bplog rift_x64.exe+ABCD, "[RIFT_BRIDGE] ..."
        # Simulate x64dbg filling in the values:
        # {rbp} → 0x7FF6000ABCD, {dword(rbp+0x310)} → 43FA0000
        simulated = (
            "[RIFT_BRIDGE] hit=regex_test reg=rbp "
            "base=0x7FF6000ABCD "
            "0x304=00000000 "
            "0x308=00000000 "
            "0x30C=00000000 "
            "0x310=43FA0000 "
            "0x314=42480000 "
            "0x318=C4480000 "
            "0x31C=00000000 "
            "0x320=00000000 "
            "0x324=00000000 "
            "0x328=00000000"
        )

        # This must match the regex
        m = _LOG_LINE_RE.search(simulated)
        assert m is not None, f"Regex failed to match simulated log line:\n{simulated}"
        assert m.group(1) == "regex_test"
        assert m.group(2) == "rbp"
        assert m.group(3).upper() == "7FF6000ABCD"

        # Parse through the full pipeline
        log = _make_log_file([simulated])
        try:
            entries = parse_x64dbg_log(log)
            assert len(entries) == 1
            e = entries[0]
            assert e.cluster == "regex_test"
            assert e.base_register == "rbp"
            assert e.base_address == 0x7FF6000ABCD
            assert e.float_at(0x310) == pytest.approx(500.0, rel=1e-6)
            assert e.float_at(0x314) == pytest.approx(50.0, rel=1e-6)
            assert e.float_at(0x318) == pytest.approx(-800.0, rel=1e-6)
        finally:
            log.unlink()
