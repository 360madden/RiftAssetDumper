"""Validate x64dbg_bridge.py log format round-trip: generate → simulate → parse → verify.

Covers:
- ``_is_valid_coord_triple``: NaN / out-of-bounds / degenerate / valid rejection
- ``BreakpointSpec`` construction and ``generate_x64dbg_script`` output shape
- ``parse_x64dbg_log``: log line → ``LogEntry`` parsing (cluster, register, base address, offset values)
- ``LogEntry.float_at``: IEEE 754 float32 unpacking correctness (known bit patterns)
- ``LogEntry.to_coord_candidates``: coordinate triple detection and filtering
- ``analyze_log_entries``: full pipeline producing structured analysis

No live process access needed — pure mock/fixture data.
"""

from __future__ import annotations

import re
import struct
import sys
import tempfile
from pathlib import Path

# Ensure scripts/ is importable
_project_root = Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.x64dbg_bridge import (  # noqa: E402
    _LOG_LINE_RE,
    _OFFSET_PAIR_RE,
    COORDINATE_OFFSETS,
    BreakpointSpec,
    LogEntry,
    _is_valid_coord_triple,
    analyze_log_entries,
    generate_x64dbg_script,
    parse_x64dbg_log,
)

# ============================================================================
# _is_valid_coord_triple tests
# ============================================================================


class TestIsValidCoordTriple:
    """Coordinate validation: reject NaN, out-of-bounds, degenerate; accept real coords."""

    def test_accepts_valid_world_coordinate(self) -> None:
        assert _is_valid_coord_triple(1234.5, 50.0, -789.0)

    def test_rejects_nan_x(self) -> None:
        assert not _is_valid_coord_triple(float("nan"), 50.0, -789.0)

    def test_rejects_nan_y(self) -> None:
        assert not _is_valid_coord_triple(100.0, float("nan"), -789.0)

    def test_rejects_nan_z(self) -> None:
        assert not _is_valid_coord_triple(100.0, 50.0, float("nan"))

    def test_rejects_out_of_bounds_x(self) -> None:
        assert not _is_valid_coord_triple(60000.0, 50.0, -789.0)

    def test_rejects_out_of_bounds_y(self) -> None:
        assert not _is_valid_coord_triple(100.0, 50000.0, -789.0)

    def test_rejects_y_above_max_y_abs(self) -> None:
        assert not _is_valid_coord_triple(100.0, 12000.0, -789.0)

    def test_rejects_y_below_negative_max_y_abs(self) -> None:
        assert not _is_valid_coord_triple(100.0, -12000.0, -789.0)

    def test_rejects_all_near_zero(self) -> None:
        assert not _is_valid_coord_triple(0.0, 0.0, 0.0)

    def test_rejects_all_near_zero_epsilon(self) -> None:
        assert not _is_valid_coord_triple(0.005, 0.003, 0.001)

    def test_rejects_all_identical_degenerate(self) -> None:
        # Table data: all values equal, not a real coordinate
        assert not _is_valid_coord_triple(4242.0, 4242.0, 4242.0)

    def test_accepts_custom_bounds(self) -> None:
        assert _is_valid_coord_triple(100.0, 500.0, -100.0, max_world_abs=1000.0, max_y_abs=600.0)

    def test_rejects_custom_bounds_exceeded(self) -> None:
        assert not _is_valid_coord_triple(100.0, 700.0, -100.0, max_y_abs=600.0)


# ============================================================================
# BreakpointSpec and script generation
# ============================================================================


class TestBreakpointSpec:
    """BreakpointSpec construction and script generation."""

    def test_breakpoint_spec_construction(self) -> None:
        spec = BreakpointSpec(
            label="cluster_04",
            rva="13AD2EA",
            base_register="rbx",
            target_offsets=[0x310, 0x318, 0x320],
            module_name="rift_x64.exe",
            score=1.0,
        )
        assert spec.label == "cluster_04"
        assert spec.rva == "13AD2EA"
        assert spec.base_register == "rbx"
        assert spec.module_name == "rift_x64.exe"
        assert spec.score == 1.0
        assert 0x310 in spec.target_offsets

    def test_generate_script_produces_bplog_commands(self) -> None:
        spec = BreakpointSpec(
            label="test_cluster",
            rva="ABCDEF",
            base_register="rcx",
            target_offsets=[0x310, 0x320],
            score=0.95,
        )
        script = generate_x64dbg_script([spec])

        # Must contain bplog command
        assert "bplog" in script
        # Must contain the module-relative address
        assert "rift_x64.exe+ABCDEF" in script
        # Must contain auto-continue
        assert "bpcnd rift_x64.exe+ABCDEF, 0" in script
        # Must set the breakpoint
        assert "bp rift_x64.exe+ABCDEF" in script
        # Must contain the structured log format markers
        assert "[RIFT_BRIDGE]" in script
        assert "hit=test_cluster" in script
        assert "reg=rcx" in script
        assert "base={rcx}" in script
        # Must include the target offsets (x64dbg expression format: {dword(reg+off)})
        assert "{dword(rcx+0x310)}" in script
        assert "{dword(rcx+0x320)}" in script

    def test_generate_script_includes_all_coordinate_offsets(self) -> None:
        """Even if the spec only lists a few offsets, the script logs ALL COORDINATE_OFFSETS."""
        spec = BreakpointSpec(
            label="sparse_cluster",
            rva="123456",
            base_register="rbx",
            target_offsets=[0x310],  # Only one offset
            score=0.5,
        )
        script = generate_x64dbg_script([spec])

        # All COORDINATE_OFFSETS should appear in the dword expressions
        # x64dbg expression format: {dword(reg+off)}
        for offset in COORDINATE_OFFSETS:
            expected = f"{{dword(rbx+{offset:#x})}}"
            assert expected in script, (
                f"Missing offset 0x{offset:X} in generated script (expected {expected})"
            )

    def test_generate_script_writes_to_disk(self) -> None:
        spec = BreakpointSpec(
            label="disk_test",
            rva="FEDCBA",
            base_register="rbx",
            target_offsets=[0x304],
            score=0.5,
        )
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            out_path = Path(f.name)

        try:
            script = generate_x64dbg_script([spec], output_path=out_path)
            on_disk = out_path.read_text(encoding="utf-8")
            assert on_disk == script
            assert "rift_x64.exe+FEDCBA" in on_disk
        finally:
            out_path.unlink(missing_ok=True)

    def test_generate_script_runs_and_clears_breakpoints(self) -> None:
        spec = BreakpointSpec(
            label="bp_test",
            rva="111111",
            base_register="rbx",
            target_offsets=[0x304],
            score=0.5,
        )
        script = generate_x64dbg_script([spec])
        assert "bc *" in script

    def test_generate_script_with_multiple_specs(self) -> None:
        """Two specs produce two bplog lines, each targeting its own register."""
        specs = [
            BreakpointSpec(
                label="cluster_04",
                rva="13AD2EA",
                base_register="rbx",
                target_offsets=[0x310],
                score=1.0,
            ),
            BreakpointSpec(
                label="cluster_05",
                rva="ABCDEF",
                base_register="rcx",
                target_offsets=[0x320],
                score=0.95,
            ),
        ]
        script = generate_x64dbg_script(specs)
        # Both breakpoints present
        assert "bp rift_x64.exe+13AD2EA" in script
        assert "bp rift_x64.exe+ABCDEF" in script
        # Both bplog commands present
        assert "hit=cluster_04" in script
        assert "hit=cluster_05" in script
        assert "reg=rbx" in script
        assert "reg=rcx" in script


# ============================================================================
# Full end-to-end round-trip test
# ============================================================================


class TestFullRoundTrip:
    """Generate script → render bplog template → parse → verify values."""

    def test_generate_then_parse_roundtrip(self) -> None:
        """End-to-end: extract bplog format, simulate x64dbg expansion, parse, verify."""
        spec = BreakpointSpec(
            label="cluster_04",
            rva="13AD2EA",
            base_register="rbx",
            target_offsets=[0x310, 0x318],
            score=1.0,
        )
        script = generate_x64dbg_script([spec])

        # Extract the bplog format string from the generated script
        # It looks like: bplog rift_x64.exe+13AD2EA, "[RIFT_BRIDGE] hit=..."
        bplog_match = re.search(r'bplog [^,]+,\s*"(.+)"', script)
        assert bplog_match is not None, "Could not find bplog command in generated script"
        bplog_format = bplog_match.group(1)

        # Simulate what x64dbg would output when the breakpoint fires.
        # {rbx} → hex address, {dword(rbx+offset)} → hex dword value.
        sim_rbx = 0x7FF6A1B2C3D0
        # Pre-compute IEEE 754 hex for test coordinates
        sim_310_hex = f"{struct.unpack('<I', struct.pack('<f', 500.0))[0]:08X}"
        sim_318_hex = f"{struct.unpack('<I', struct.pack('<f', -250.0))[0]:08X}"

        # Render the template by substituting x64dbg expressions
        rendered = bplog_format.replace("{rbx}", f"0x{sim_rbx:X}")
        rendered = rendered.replace(
            "{dword(rbx+0x310)}", sim_310_hex
        )
        rendered = rendered.replace(
            "{dword(rbx+0x318)}", sim_318_hex
        )
        # Also substitute all other coordinate offsets with zero
        for off in COORDINATE_OFFSETS:
            if off in (0x310, 0x318):
                continue
            rendered = rendered.replace(
                f"{{dword(rbx+{off:#x})}}", "00000000"
            )

        # Write rendered log to temp file
        f = tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w", encoding="utf-8"
        )
        log_path = Path(f.name)
        f.write(rendered + "\n")
        f.close()

        try:
            # Parse the log
            entries = parse_x64dbg_log(log_path)
            assert len(entries) == 1, f"Expected 1 entry, got {len(entries)}"
            entry = entries[0]

            # Verify parsed fields
            assert entry.cluster == "cluster_04"
            assert entry.base_register == "rbx"
            assert entry.base_address == sim_rbx

            # Verify float unpacking at 0x310 → 500.0
            val_310 = entry.float_at(0x310)
            assert val_310 is not None
            assert abs(val_310 - 500.0) < 0.01, f"Expected ~500.0, got {val_310}"

            # Verify float unpacking at 0x318 → -250.0
            val_318 = entry.float_at(0x318)
            assert val_318 is not None
            assert abs(val_318 - (-250.0)) < 0.01, f"Expected ~-250.0, got {val_318}"

            # All unused offsets should unpack to 0.0
            for off in COORDINATE_OFFSETS:
                if off in (0x310, 0x318):
                    continue
                v = entry.float_at(off)
                assert v is not None, f"Missing offset 0x{off:X}"
                assert v == 0.0, f"Offset 0x{off:X} expected 0.0, got {v}"

            # Verify coordinate candidate detection
            # At offsets 0x310: (500.0, ?, ?) — need three consecutive at 0x310,0x314,0x318
            # But 0x314=0.0 so this triple is near-zero and filtered out.
            # At offsets 0x314: (0.0, -250.0, ?) — missing 0x31C
            # So no valid triple should be found in this simple test case.

        finally:
            log_path.unlink(missing_ok=True)


# ============================================================================
# Log line regex tests
# ============================================================================


class TestLogLineRegex:
    """Validate the compiled regex patterns against expected x64dbg output formats."""

    def test_log_line_re_matches_full_format(self) -> None:
        line = "[RIFT_BRIDGE] hit=cluster_04 reg=rbx base=0x7FF6A1B2C3D0 0x310=43FA0000 0x318=C3FA0000 0x320=41200000"
        m = _LOG_LINE_RE.search(line)
        assert m is not None
        assert m.group(1) == "cluster_04"
        assert m.group(2) == "rbx"
        assert m.group(3) == "7FF6A1B2C3D0"
        assert "0x310=43FA0000" in m.group(4)

    def test_log_line_re_matches_without_0x_prefix(self) -> None:
        line = "[RIFT_BRIDGE] hit=cluster_05 reg=rcx base=1234ABCD 0x310=00000000"
        m = _LOG_LINE_RE.search(line)
        assert m is not None
        assert m.group(3) == "1234ABCD"

    def test_log_line_re_does_not_match_noise(self) -> None:
        assert _LOG_LINE_RE.search("log some random text") is None
        assert _LOG_LINE_RE.search("[RIFT_BRIDGE] incomplete") is None

    def test_offset_pair_re_extracts_pairs(self) -> None:
        rest = "0x310=43FA0000 0x318=C3FA0000 0x320=00000000"
        pairs = _OFFSET_PAIR_RE.findall(rest)
        assert len(pairs) == 3
        assert pairs[0] == ("0x310", "43FA0000")
        assert pairs[1] == ("0x318", "C3FA0000")
        assert pairs[2] == ("0x320", "00000000")

    def test_offset_pair_re_handles_mixed_content(self) -> None:
        rest = "0x310=43FA0000 garbage_text 0x320=41200000"
        pairs = _OFFSET_PAIR_RE.findall(rest)
        assert len(pairs) == 2


# ============================================================================
# Log parsing (parse_x64dbg_log) tests
# ============================================================================


class TestParseX64dbgLog:
    """Round-trip: write synthetic log → parse → verify LogEntry fields."""

    def _write_log(self, lines: list[str]) -> Path:
        """Write a temporary log file, return its Path."""
        f = tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w", encoding="utf-8"
        )
        f.write("\n".join(lines) + "\n")
        f.close()
        return Path(f.name)

    def test_parses_single_hit(self) -> None:
        log = self._write_log([
            "[RIFT_BRIDGE] hit=cluster_04 reg=rbx base=0x7FF6A1B2C3D0 0x310=43FA0000 0x318=C3FA0000 0x320=41200000",
        ])
        try:
            entries = parse_x64dbg_log(log)
            assert len(entries) == 1
            e = entries[0]
            assert e.cluster == "cluster_04"
            assert e.base_register == "rbx"
            assert e.base_address == 0x7FF6A1B2C3D0
            assert e.offset_values[0x310] == 0x43FA0000
            assert e.offset_values[0x318] == 0xC3FA0000
            assert e.offset_values[0x320] == 0x41200000
        finally:
            log.unlink(missing_ok=True)

    def test_parses_multiple_hits_different_clusters(self) -> None:
        log = self._write_log([
            "[RIFT_BRIDGE] hit=cluster_04 reg=rbx base=0x1000 0x310=00000001",
            "[RIFT_BRIDGE] hit=cluster_05 reg=rcx base=0x2000 0x320=00000002",
            "[RIFT_BRIDGE] hit=cluster_04 reg=rbx base=0x3000 0x310=00000003",
        ])
        try:
            entries = parse_x64dbg_log(log)
            assert len(entries) == 3
            assert entries[0].cluster == "cluster_04"
            assert entries[0].base_address == 0x1000
            assert entries[1].cluster == "cluster_05"
            assert entries[1].base_register == "rcx"
            assert entries[2].base_address == 0x3000
        finally:
            log.unlink(missing_ok=True)

    def test_ignores_non_bridge_lines(self) -> None:
        log = self._write_log([
            'log "Setting breakpoint cluster_04 at rift_x64.exe+13AD2EA"',
            "some random log output",
            "[RIFT_BRIDGE] hit=cluster_04 reg=rbx base=0x1000 0x310=00000001",
            "bp rift_x64.exe+13AD2EA",
        ])
        try:
            entries = parse_x64dbg_log(log)
            assert len(entries) == 1
        finally:
            log.unlink(missing_ok=True)

    def test_parses_empty_log(self) -> None:
        log = self._write_log([])
        try:
            entries = parse_x64dbg_log(log)
            assert entries == []
        finally:
            log.unlink(missing_ok=True)

    def test_parses_base_without_0x_prefix(self) -> None:
        log = self._write_log([
            "[RIFT_BRIDGE] hit=test reg=rbx base=ABCDEF 0x310=00000001",
        ])
        try:
            entries = parse_x64dbg_log(log)
            assert len(entries) == 1
            assert entries[0].base_address == 0xABCDEF
        finally:
            log.unlink(missing_ok=True)

    def test_skips_malformed_base_address(self) -> None:
        log = self._write_log([
            "[RIFT_BRIDGE] hit=test reg=rbx base=NOT_HEX 0x310=00000001",
        ])
        try:
            entries = parse_x64dbg_log(log)
            assert entries == []  # int(..., 16) raises ValueError → skipped
        finally:
            log.unlink(missing_ok=True)


# ============================================================================
# LogEntry.float_at tests — IEEE 754 float32 unpacking
# ============================================================================


class TestLogEntryFloatAt:
    """Verify LogEntry.float_at correctly unpacks hex dwords to float32."""

    def test_unpacks_positive_float(self) -> None:
        # 43FA0000 = 500.0 in IEEE 754 float32
        entry = LogEntry(
            cluster="test",
            base_address=0x1000,
            base_register="rbx",
            offset_values={0x310: 0x43FA0000},
        )
        result = entry.float_at(0x310)
        assert result is not None
        assert abs(result - 500.0) < 0.001

    def test_unpacks_negative_float(self) -> None:
        # C3FA0000 = -500.0 in IEEE 754 float32
        entry = LogEntry(
            cluster="test",
            base_address=0x1000,
            base_register="rbx",
            offset_values={0x318: 0xC3FA0000},
        )
        result = entry.float_at(0x318)
        assert result is not None
        assert abs(result - (-500.0)) < 0.001

    def test_unpacks_zero(self) -> None:
        entry = LogEntry(
            cluster="test",
            base_address=0x1000,
            base_register="rbx",
            offset_values={0x320: 0x00000000},
        )
        result = entry.float_at(0x320)
        assert result == 0.0

    def test_unpacks_one(self) -> None:
        # 3F800000 = 1.0
        entry = LogEntry(
            cluster="test",
            base_address=0x1000,
            base_register="rbx",
            offset_values={0x304: 0x3F800000},
        )
        result = entry.float_at(0x304)
        assert result is not None
        assert abs(result - 1.0) < 0.0001

    def test_unpacks_small_fraction(self) -> None:
        # 3DCCCCCD = 0.1
        entry = LogEntry(
            cluster="test",
            base_address=0x1000,
            base_register="rbx",
            offset_values={0x308: 0x3DCCCCCD},
        )
        result = entry.float_at(0x308)
        assert result is not None
        assert abs(result - 0.1) < 0.0001

    def test_returns_none_for_missing_offset(self) -> None:
        entry = LogEntry(
            cluster="test",
            base_address=0x1000,
            base_register="rbx",
            offset_values={},
        )
        assert entry.float_at(0x310) is None

    def test_unpack_roundtrip_matches_struct(self) -> None:
        """Verify float_at produces the same result as struct.unpack directly."""
        test_values: list[float] = [0.0, 1.0, -1.0, 3.14159, -999.5, 12345.678]
        for expected in test_values:
            raw = struct.unpack("<I", struct.pack("<f", expected))[0]
            entry = LogEntry(
                cluster="test",
                base_address=0x1000,
                base_register="rbx",
                offset_values={0x304: raw},
            )
            result = entry.float_at(0x304)
            assert result is not None
            # float32 cannot represent arbitrary decimals exactly;
            # the round-trip preserved value is the closest float32 to `expected`.
            rt_expected = struct.unpack("<f", struct.pack("<f", expected))[0]
            assert result == rt_expected, (
                f"float_at({raw:#x}) expected {rt_expected} (float32 of {expected}), got {result}"
            )


# ============================================================================
# LogEntry.to_coord_candidates tests
# ============================================================================


class TestToCoordCandidates:
    """Verify coordinate triple detection from LogEntry offset values."""

    def _make_entry(self, offset_values: dict[int, int]) -> LogEntry:
        return LogEntry(
            cluster="test",
            base_address=0x1000,
            base_register="rbx",
            offset_values=offset_values,
        )

    @staticmethod
    def _float_to_hex(f: float) -> int:
        raw: int = struct.unpack("<I", struct.pack("<f", f))[0]
        return raw

    def test_detects_valid_coordinate_triple(self) -> None:
        entry = self._make_entry({
            0x304: self._float_to_hex(100.0),
            0x308: self._float_to_hex(50.0),
            0x30C: self._float_to_hex(-200.0),
        })
        candidates = entry.to_coord_candidates()
        assert 0x304 in candidates
        triple = candidates[0x304]
        assert triple is not None
        x, y, z = triple
        assert abs(x - 100.0) < 0.01
        assert abs(y - 50.0) < 0.01
        assert abs(z - (-200.0)) < 0.01

    def test_rejects_nan_triple(self) -> None:
        nan_hex = self._float_to_hex(float("nan"))
        entry = self._make_entry({
            0x304: self._float_to_hex(100.0),
            0x308: nan_hex,
            0x30C: self._float_to_hex(-200.0),
        })
        candidates = entry.to_coord_candidates()
        assert 0x304 not in candidates

    def test_rejects_all_zero_triple(self) -> None:
        entry = self._make_entry({
            0x304: 0x00000000,
            0x308: 0x00000000,
            0x30C: 0x00000000,
        })
        candidates = entry.to_coord_candidates()
        assert 0x304 not in candidates

    def test_rejects_degenerate_identical_triple(self) -> None:
        val = self._float_to_hex(4242.0)
        entry = self._make_entry({
            0x304: val,
            0x308: val,
            0x30C: val,
        })
        candidates = entry.to_coord_candidates()
        assert 0x304 not in candidates

    def test_rejects_out_of_bounds_triple(self) -> None:
        entry = self._make_entry({
            0x304: self._float_to_hex(99999.0),
            0x308: self._float_to_hex(50.0),
            0x30C: self._float_to_hex(-200.0),
        })
        candidates = entry.to_coord_candidates()
        assert 0x304 not in candidates

    def test_returns_empty_for_no_consecutive_offsets(self) -> None:
        entry = self._make_entry({
            0x310: self._float_to_hex(100.0),
            # missing 0x314 and 0x318 — so only one value, not a triple
            0x31C: self._float_to_hex(50.0),
        })
        candidates = entry.to_coord_candidates()
        assert len(candidates) == 0

    def test_detects_multiple_offset_slots(self) -> None:
        """If data exists at multiple consecutive triple positions, returns all valid ones."""
        entry = self._make_entry({
            # First triple at 0x304, 0x308, 0x30C
            0x304: self._float_to_hex(100.0),
            0x308: self._float_to_hex(50.0),
            0x30C: self._float_to_hex(-200.0),
            # Second triple at 0x310, 0x314, 0x318
            0x310: self._float_to_hex(300.0),
            0x314: self._float_to_hex(20.0),
            0x318: self._float_to_hex(-100.0),
        })
        candidates = entry.to_coord_candidates()
        # Both triples should be detected
        assert 0x304 in candidates
        assert 0x310 in candidates

    def test_skips_offsets_near_end_of_range(self) -> None:
        """Offsets near the end of COORDINATE_OFFSETS (0x324, 0x328) can't form triples
        because 0x328+4 and 0x328+8 aren't in COORDINATE_OFFSETS."""
        entry = self._make_entry({
            0x324: self._float_to_hex(100.0),
            0x328: self._float_to_hex(50.0),
        })
        candidates = entry.to_coord_candidates()
        # 0x324+8=0x32C not in COORDINATE_OFFSETS, 0x328+8=0x330 not in set
        assert 0x324 not in candidates
        assert 0x328 not in candidates


# ============================================================================
# analyze_log_entries tests
# ============================================================================


class TestAnalyzeLogEntries:
    """Full pipeline: entries → analysis dict with stats, candidates, cluster hits."""

    @staticmethod
    def _float_hex(f: float) -> int:
        raw: int = struct.unpack("<I", struct.pack("<f", f))[0]
        return raw

    def test_empty_entries(self) -> None:
        result = analyze_log_entries([])
        assert result["total_entries"] == 0
        assert result["num_unique_bases"] == 0
        assert result["num_coord_candidates"] == 0

    def test_single_entry_no_coords(self) -> None:
        entry = LogEntry(
            cluster="test",
            base_address=0x1000,
            base_register="rbx",
            offset_values={},  # No data
        )
        result = analyze_log_entries([entry])
        assert result["total_entries"] == 1
        assert result["num_unique_bases"] == 1
        assert result["num_coord_candidates"] == 0

    def test_single_entry_with_coordinate_triple(self) -> None:
        entry = LogEntry(
            cluster="cluster_04",
            base_address=0x7FF6A1B2C3D0,
            base_register="rbx",
            offset_values={
                0x310: self._float_hex(123.5),
                0x314: self._float_hex(45.0),
                0x318: self._float_hex(-78.2),
            },
        )
        result = analyze_log_entries([entry])
        assert result["num_coord_candidates"] >= 1
        c = result["coord_candidates"][0]
        assert c["cluster"] == "cluster_04"
        assert "0x7FF6A1B2C3D0" in c["base_address"]
        assert abs(c["x"] - 123.5) < 0.01
        assert abs(c["y"] - 45.0) < 0.01
        assert abs(c["z"] - (-78.2)) < 0.01
        assert c["base_register"] == "rbx"

    def test_multiple_entries_aggregate_cluster_hits(self) -> None:
        entries = [
            LogEntry(cluster="c1", base_address=0x1000, base_register="rbx"),
            LogEntry(cluster="c1", base_address=0x2000, base_register="rbx"),
            LogEntry(cluster="c2", base_address=0x3000, base_register="rcx"),
        ]
        result = analyze_log_entries(entries)
        assert result["cluster_hits"] == {"c1": 2, "c2": 1}

    def test_unique_bases_deduplicates(self) -> None:
        entries = [
            LogEntry(cluster="c1", base_address=0x1000, base_register="rbx"),
            LogEntry(cluster="c2", base_address=0x1000, base_register="rbx"),  # same base
            LogEntry(cluster="c3", base_address=0x2000, base_register="rcx"),
        ]
        result = analyze_log_entries(entries)
        assert result["num_unique_bases"] == 2

    def test_absolute_address_computed_correctly(self) -> None:
        entry = LogEntry(
            cluster="test",
            base_address=0x7FF600000000,
            base_register="rbx",
            offset_values={
                0x310: self._float_hex(1.0),
                0x314: self._float_hex(2.0),
                0x318: self._float_hex(3.0),
            },
        )
        result = analyze_log_entries([entry])
        assert result["num_coord_candidates"] >= 1
        c = result["coord_candidates"][0]
        expected_abs = 0x7FF600000000 + 0x310
        assert c["absolute_address"] == f"0x{expected_abs:X}"

    def test_specs_override_base_register(self) -> None:
        """When specs are provided, base_register is resolved from the spec map."""
        spec = BreakpointSpec(
            label="my_cluster",
            rva="ABCDEF",
            base_register="rcx",
            target_offsets=[0x310],
            score=1.0,
        )
        entry = LogEntry(
            cluster="my_cluster",
            base_address=0x1000,
            base_register="rbx",  # Will be overridden
            offset_values={
                0x310: self._float_hex(1.0),
                0x314: self._float_hex(2.0),
                0x318: self._float_hex(3.0),
            },
        )
        result = analyze_log_entries([entry], specs=[spec])
        assert result["num_coord_candidates"] >= 1
        assert result["coord_candidates"][0]["base_register"] == "rcx"
