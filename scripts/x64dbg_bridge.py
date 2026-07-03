#!/usr/bin/env python3
"""x64dbg bridge: automated breakpoint-based player coordinate discovery.

Generates x64dbg command scripts that set breakpoints at confirmed ModRM code
addresses, log register values when hit, and save structured output for
offline pointer-chain resolution.

Usage::

    # Generate x64dbg script from latest probe-modrm-leads output
    python scripts/x64dbg_bridge.py generate --pid 51804

    # Generate from specific probe file
    python scripts/x64dbg_bridge.py generate --probe Exports/discovery-plan/stage5-live/probe-modrm-leads-*.json

    # Launch x64dbg attached to RIFT (opens GUI)
    python scripts/x64dbg_bridge.py launch --pid 51804

    # Parse x64dbg log output to extract coordinate candidates
    python scripts/x64dbg_bridge.py parse --log log.txt

    # Verify candidates via live ReadProcessMemory
    python scripts/x64dbg_bridge.py verify --pid 51804 --analysis log.analysis.json

Safety:
    Read-only — breakpoints are non-intrusive (bpcnd 0 = auto-continue).
    No memory writes, no code hooks, no DLL injection.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

# Default paths
DEFAULT_PROBE_JSON = "Exports/discovery-plan/stage5-live/probe-modrm-leads-20260703T051817Z.json"
DEFAULT_SCRIPT_OUT = "Exports/x64dbg_auto_trace.txt"
DEFAULT_LOG_OUT = "Exports/x64dbg_trace_log.txt"

# x64dbg executable (from .tools.json)
X64DBG_EXE = REPO_ROOT / ".." / "Tools" / "x64dbg" / "release" / "x64" / "x64dbg.exe"

# Offset labels we know contain potential coordinate data
COORDINATE_OFFSETS: set[int] = {0x304, 0x308, 0x30C, 0x310, 0x314, 0x318, 0x31C, 0x320, 0x324, 0x328}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class BreakpointSpec:
    """A single breakpoint to set in x64dbg."""

    label: str
    rva: str  # hex string without 0x prefix, e.g. "13AD2EA"
    base_register: str  # lower-case: rbx, rcx, rbp
    target_offsets: list[int]  # hex offsets e.g. [0x310, 0x318, 0x320]
    module_name: str = "rift_x64.exe"
    score: float = 0.0


@dataclass
class LogEntry:
    """A single parsed breakpoint hit from the x64dbg log."""

    cluster: str
    base_address: int  # the RBX/RCX/RBP value (player struct ptr)
    base_register: str
    offset_values: dict[int, int] = field(default_factory=dict)  # offset -> raw hex dword
    raw_line: str = ""

    def float_at(self, offset: int) -> float | None:
        """Unpack a raw dword at the given offset as float32."""
        raw = self.offset_values.get(offset)
        if raw is None:
            return None
        try:
            return struct.unpack("<f", struct.pack("<I", raw & 0xFFFFFFFF))[0]
        except struct.error:
            return None

    def to_coord_candidates(
        self,
        max_world_abs: float = 50000.0,
        max_y_abs: float = 10000.0,
    ) -> dict[int, tuple[float, float, float] | None]:
        """Try to read consecutive float triples at coordinate offsets.

        Only returns triples that pass world-coordinate reasonableness checks
        (delegates to ``_is_valid_coord_triple``).

        Note: only checks offsets within ``COORDINATE_OFFSETS`` (0x304-0x328)
        which are the known player-struct member offsets from ModRM analysis.
        """
        results: dict[int, tuple[float, float, float] | None] = {}
        for offset in COORDINATE_OFFSETS:
            if offset + 8 not in COORDINATE_OFFSETS:
                continue

            v0 = self.float_at(offset)
            v1 = self.float_at(offset + 4)
            v2 = self.float_at(offset + 8)

            if v0 is None or v1 is None or v2 is None:
                continue

            if _is_valid_coord_triple(v0, v1, v2, max_world_abs=max_world_abs, max_y_abs=max_y_abs):
                results[offset] = (v0, v1, v2)

        return results


# ---------------------------------------------------------------------------
# Coordinate validation helpers
# ---------------------------------------------------------------------------


def _is_valid_coord_triple(
    x: float,
    y: float,
    z: float,
    *,
    max_world_abs: float = 50000.0,
    max_y_abs: float = 10000.0,
) -> bool:
    """Check if three float values could be a valid 3D world coordinate."""
    # NaN check
    if x != x or y != y or z != z:
        return False
    # World bounds
    if not all(abs(v) < max_world_abs for v in (x, y, z)):
        return False
    if abs(y) > max_y_abs:
        return False
    # Degenerate: all near-zero
    if abs(x) < 0.01 and abs(y) < 0.01 and abs(z) < 0.01:
        return False
    # Degenerate: all identical (table data, not a position)
    if abs(x - y) < 0.001 and abs(y - z) < 0.001:
        return False
    return True


# ---------------------------------------------------------------------------
# Probe data loading
# ---------------------------------------------------------------------------


def _find_latest_probe_json() -> Path:
    """Find the most recent probe-modrm-leads JSON in stage5-live."""
    stage5 = REPO_ROOT / "Exports" / "discovery-plan" / "stage5-live"
    candidates = sorted(stage5.glob("probe-modrm-leads-*.json"), reverse=True)
    if not candidates:
        raise FileNotFoundError(
            f"No probe-modrm-leads-*.json found in {stage5}. "
            "Run: python scripts/probe_modrm_leads.py --execute-live-read "
            "--experimental-live --confirm-live-read --pid <PID>"
        )
    return candidates[0]


def _resolve_probe_path(path: str | None) -> Path:
    """Resolve a probe JSON path or find the latest."""
    if path:
        p = Path(path)
        if not p.is_absolute():
            p = REPO_ROOT / p
    else:
        p = _find_latest_probe_json()
    if not p.exists():
        raise FileNotFoundError(f"Probe JSON not found: {p}")
    return p


def load_breakpoint_specs(probe_json_path: Path) -> list[BreakpointSpec]:
    """Load breakpoint specifications from a probe-modrm-leads JSON report."""
    data = json.loads(probe_json_path.read_text(encoding="utf-8"))

    specs: list[BreakpointSpec] = []
    region_base = 0

    for cluster in data.get("ConfirmedClusters", []):
        if not cluster.get("SignatureConfirmed"):
            continue

        label = cluster.get("Label", "unknown")
        score = cluster.get("PlayerCoordinateScore", 0.0)

        # Determine base register: the register with the most hits
        base_counts = cluster.get("BaseRegisterCounts", {})
        if not base_counts:
            continue
        base_reg = max(base_counts, key=base_counts.get).lower()

        # Compute RVA from ConfirmedAtVA and RegionBase
        confirmed_va_str = cluster.get("ConfirmedAtVA")
        matches = cluster.get("SignaturesMatched", [])
        if matches:
            region_base = int(matches[0].get("RegionBase", "0"), 16)
            confirmed_va = int(confirmed_va_str, 16) if confirmed_va_str else 0
            rva = confirmed_va - region_base
        else:
            # Fallback to FirstRVA
            first_rva = cluster.get("FirstRVA", "0")
            rva = int(first_rva, 16)

        # Collect target offsets
        offset_counts = cluster.get("TargetOffsetCounts", {})
        target_offsets = sorted(int(k, 16) for k in offset_counts.keys())

        module_name = "rift_x64.exe"

        specs.append(
            BreakpointSpec(
                label=label,
                rva=f"{rva:X}",
                base_register=base_reg,
                target_offsets=target_offsets,
                module_name=module_name,
                score=score,
            )
        )

    # Sort by score descending, then by label
    specs.sort(key=lambda s: (-s.score, s.label))
    return specs


# ---------------------------------------------------------------------------
# x64dbg script generation
# ---------------------------------------------------------------------------


def generate_x64dbg_script(
    specs: list[BreakpointSpec],
    output_path: Path | None = None,
) -> str:
    """Generate an x64dbg command script from breakpoint specifications.

    The script:
    1. Clears existing breakpoints
    2. Sets breakpoints with bplog for register/memory logging
    3. Uses bpcnd 0 so breakpoints auto-continue (game doesn't freeze)

    Returns the script text. If ``output_path`` is provided, also writes to disk.
    """
    lines: list[str] = [
        'init "RIFT Player Struct Probe"',
        "",
        "// ============================================================================",
        "// RIFT Player Coordinate Breakpoint Script",
        "// Generated by scripts/x64dbg_bridge.py",
        "// ============================================================================",
        "//",
        "// Instructions:",
        "//   1. Attach x64dbg to rift_x64.exe (File -> Attach)",
        "//   2. Run this script (File -> Script -> select this file)",
        "//   3. Let the game run for ~10 seconds",
        "//   4. Press F12 to pause",
        "//   5. Right-click in the Log window -> Save to file",
        "//   6. Run: python scripts/x64dbg_bridge.py parse --log <saved_log.txt>",
        "// ============================================================================",
        "",
        "// Clear any existing breakpoints",
        "bc *",
        "",
        "// ---------------------------------------------------------------------------",
        "// Breakpoints at confirmed player-struct-accessing code",
        "// Format: [RIFT_BRIDGE] hit=<cluster> base=<reg_value> <offset>=<hex_dword> ...",
        "// ---------------------------------------------------------------------------",
        "",
    ]

    for spec in specs:
        bp_addr = f"{spec.module_name}+{spec.rva}"
        lines.append(f'log "Setting breakpoint {spec.label} at {bp_addr} (score={spec.score:.4f})"')
        lines.append(f"bp {bp_addr}")

        # Auto-continue: bpcnd 0 means the BP fires but doesn't pause
        lines.append(f"bpcnd {bp_addr}, 0")

        # Build the bplog format string
        # Include the register name so the parser knows which register was used
        log_parts: list[str] = [
            f"[RIFT_BRIDGE] hit={spec.label} reg={spec.base_register} base={{{spec.base_register}}}"
        ]

        # Add all offsets we track
        for offset in sorted(spec.target_offsets):
            log_parts.append(f"{offset:#x}={{{'dword'}({spec.base_register}+{offset:#x})}}")

        # Also add key coordinate offsets even if not in the cluster's specific hits
        for extra_off in sorted(COORDINATE_OFFSETS):
            if extra_off not in spec.target_offsets:
                log_parts.append(f"{extra_off:#x}={{{'dword'}({spec.base_register}+{extra_off:#x})}}")

        log_str = " ".join(log_parts)
        lines.append(f'bplog {bp_addr}, "{log_str}"')
        lines.append("")

    lines.extend(
        [
            "// ---------------------------------------------------------------------------",
            "// All breakpoints set. Resume execution.",
            "// ---------------------------------------------------------------------------",
            'log "=== RIFT BRIDGE: Breakpoints active. Game is running. ==="',
            'log "=== After ~10 seconds, press F12 to pause, then save this log. ==="',
            "",
            "run",
        ]
    )

    script_text = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(script_text, encoding="utf-8")
        print(f"x64dbg script written: {output_path}")

    return script_text


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

# Matches lines like:
#   [RIFT_BRIDGE] hit=cluster_04 reg=rbx base=0x7FF6A1B2C3D0 0x310=43FA0000 ...
# x64dbg outputs hex values WITH 0x prefix (e.g. {rbx} -> 0x7FF6A1B2C3D0),
# but we accept both forms for robustness across versions.
_LOG_LINE_RE = re.compile(r"\[RIFT_BRIDGE\]\s+hit=(\S+)\s+reg=(\S+)\s+base=(?:0x)?([0-9A-Fa-f]+)\s+(.*)")

# Matches individual offset=value pairs: 0x310=43FA0000
# x64dbg {dword(addr)} outputs raw hex WITHOUT 0x prefix
_OFFSET_PAIR_RE = re.compile(r"(0x[0-9A-Fa-f]+)=([0-9A-Fa-f]+)")


def parse_x64dbg_log(log_path: Path) -> list[LogEntry]:
    """Parse x64dbg log output and extract breakpoint hit entries.

    Returns a list of LogEntry objects, one per breakpoint hit line found.
    """
    entries: list[LogEntry] = []
    text = log_path.read_text(encoding="utf-8", errors="replace")

    for line in text.splitlines():
        m = _LOG_LINE_RE.search(line)
        if not m:
            continue

        cluster = m.group(1)
        base_register = m.group(2)
        try:
            base_address = int(m.group(3), 16)
        except ValueError:
            continue

        rest = m.group(4)

        offset_values: dict[int, int] = {}
        for om in _OFFSET_PAIR_RE.finditer(rest):
            try:
                offset = int(om.group(1), 16)
                value = int(om.group(2), 16)
                offset_values[offset] = value
            except ValueError:
                continue

        entries.append(
            LogEntry(
                cluster=cluster,
                base_address=base_address,
                base_register=base_register,
                offset_values=offset_values,
                raw_line=line.strip(),
            )
        )

    return entries


def analyze_log_entries(
    entries: list[LogEntry],
    specs: list[BreakpointSpec] | None = None,
) -> dict:
    """Analyze parsed log entries for coordinate candidates.

    Returns a dict with:
    - unique_bases: set of distinct base pointers observed
    - coord_candidates: list of promising coordinate triples
    - stats: per-cluster hit counts
    """
    # Build spec lookup
    spec_map: dict[str, BreakpointSpec] = {}
    if specs:
        spec_map = {s.label: s for s in specs}

    unique_bases: set[int] = set()
    coord_candidates: list[dict] = []
    cluster_hits: dict[str, int] = {}

    for entry in entries:
        cluster_hits[entry.cluster] = cluster_hits.get(entry.cluster, 0) + 1
        unique_bases.add(entry.base_address)

        # Resolve base register from spec
        base_reg = "rbx"
        if entry.cluster in spec_map:
            base_reg = spec_map[entry.cluster].base_register

        entry.base_register = base_reg

        # Get coordinate candidates
        triples = entry.to_coord_candidates()
        for base_off, (x, y, z) in triples.items():
            # Filter: all three must be non-zero and non-identical
            if abs(x) < 0.01 and abs(y) < 0.01 and abs(z) < 0.01:
                continue
            if abs(x - y) < 0.001 and abs(y - z) < 0.001:
                continue  # degenerate: all identical

            coord_candidates.append(
                {
                    "cluster": entry.cluster,
                    "base_address": f"0x{entry.base_address:X}",
                    "base_offset": f"0x{base_off:X}",
                    "absolute_address": f"0x{entry.base_address + base_off:X}",
                    "x": round(x, 4),
                    "y": round(y, 4),
                    "z": round(z, 4),
                    "base_register": base_reg,
                }
            )

    return {
        "total_entries": len(entries),
        "unique_bases": sorted(unique_bases),
        "num_unique_bases": len(unique_bases),
        "coord_candidates": coord_candidates,
        "num_coord_candidates": len(coord_candidates),
        "cluster_hits": cluster_hits,
    }


# ---------------------------------------------------------------------------
# Pointer chain verification via ReadProcessMemory
# ---------------------------------------------------------------------------


def verify_coordinate_candidates(
    candidates: list[dict],
    pid: int,
    *,
    max_world_abs: float = 50000.0,
    max_y_abs: float = 10000.0,
) -> list[dict]:
    """Verify coordinate candidates by re-reading memory via ReadProcessMemory.

    For each candidate, reads 12 bytes (3x f32) at the absolute address and
    re-validates the values using ``_is_valid_coord_triple``. Returns only
    candidates that pass re-validation.

    Requires ``pid`` of the running RIFT process.
    """
    # Ensure project root is on sys.path for the import below
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from scripts.live_memory_scanner import WindowsReadOnlyProcessReader  # noqa: E402

    verified: list[dict] = []
    seen = set()

    with WindowsReadOnlyProcessReader(pid) as reader:
        for c in candidates:
            abs_addr = int(c["absolute_address"], 16)
            if abs_addr in seen:
                continue
            seen.add(abs_addr)

            data = reader.read(abs_addr, 12)
            if not data or len(data) < 12:
                continue

            try:
                x, y, z = struct.unpack("<fff", data[:12])
            except struct.error:
                continue

            if _is_valid_coord_triple(x, y, z):
                verified.append(
                    {
                        **c,
                        "x_verified": round(x, 4),
                        "y_verified": round(y, 4),
                        "z_verified": round(z, 4),
                    }
                )

    return verified


def launch_x64dbg(pid: int, script_path: Path | None = None) -> None:
    """Launch x64dbg attached to the given process.

    Opens the x64dbg GUI. If ``script_path`` is provided, prints instructions
    for loading the script after attach.
    """
    if not X64DBG_EXE.exists():
        print(f"ERROR: x64dbg not found at {X64DBG_EXE}")
        print("  Install x64dbg in C:\\RIFT MODDING\\Tools\\x64dbg\\")
        print("  Or update .tools.json with the correct path.")
        sys.exit(1)

    cmd = [str(X64DBG_EXE), "-p", str(pid)]
    print(f"Launching: {' '.join(cmd)}")
    if script_path:
        print(f"After attach, load script: File -> Script -> {script_path}")
    print()

    subprocess.Popen(cmd, cwd=str(X64DBG_EXE.parent))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_generate(args: argparse.Namespace) -> int:
    """Generate an x64dbg command script."""
    probe_path = _resolve_probe_path(args.probe)
    specs = load_breakpoint_specs(probe_path)
    print(f"Loaded {len(specs)} breakpoint specs from {probe_path.name}")
    for s in specs:
        print(
            f"  {s.label}: {s.module_name}+{s.rva} ({s.base_register}), "
            f"score={s.score:.4f}, offsets={[f'0x{off:X}' for off in s.target_offsets]}"
        )

    out_path = Path(args.out) if args.out else REPO_ROOT / DEFAULT_SCRIPT_OUT
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path

    generate_x64dbg_script(specs, out_path)
    print()
    print("Next steps:")
    print(f"  1. Launch x64dbg: python scripts/x64dbg_bridge.py launch --pid {args.pid or '<PID>'}")
    print(f"  2. In x64dbg, load the script: File -> Script -> {out_path}")
    print("  3. Let the game run ~10 seconds, press F12 to pause")
    print("  4. Right-click Log window -> Save to file")
    print("  5. Parse: python scripts/x64dbg_bridge.py parse --log <saved_log.txt>")
    return 0


def _cmd_launch(args: argparse.Namespace) -> int:
    """Launch x64dbg attached to a process."""
    if not args.pid or args.pid <= 0:
        print("ERROR: --pid is required for launch", file=sys.stderr)
        return 1

    script_path = None
    if args.script:
        script_path = Path(args.script)
        if not script_path.exists():
            print(f"WARNING: script not found: {script_path}")

    launch_x64dbg(args.pid, script_path)
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    """Verify coordinate candidates via live ReadProcessMemory."""
    analysis_path = Path(args.analysis)
    if not analysis_path.is_absolute():
        analysis_path = REPO_ROOT / analysis_path
    if not analysis_path.exists():
        print(f"ERROR: analysis file not found: {analysis_path}", file=sys.stderr)
        return 1

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    candidates = analysis.get("coord_candidates", [])
    if not candidates:
        print("No coordinate candidates to verify.")
        return 0

    print(f"Verifying {len(candidates)} candidates via ReadProcessMemory (PID {args.pid})...")
    verified = verify_coordinate_candidates(candidates, args.pid)
    print(f"Verified: {len(verified)}/{len(candidates)} candidates passed re-validation")

    if verified:
        print("\nVerified coordinate candidates:")
        verified.sort(key=lambda c: abs(c["x_verified"]) + abs(c["y_verified"]) + abs(c["z_verified"]), reverse=True)
        for c in verified[:20]:
            print(
                f"  [{c['cluster']}] @ {c['absolute_address']} "
                f"({c['base_register']}): "
                f"({c['x_verified']:.2f}, {c['y_verified']:.2f}, {c['z_verified']:.2f})"
            )

        # Write verified output
        out_path = analysis_path.with_suffix(".verified.json")
        out_path.write_text(json.dumps(verified, indent=2), encoding="utf-8")
        print(f"\nVerified candidates written: {out_path}")
    else:
        print("No candidates passed re-validation. The logged values may have been transient.")

    return 0


def _cmd_parse(args: argparse.Namespace) -> int:
    """Parse an x64dbg log file."""
    log_path = Path(args.log)
    if not log_path.is_absolute():
        log_path = REPO_ROOT / log_path
    if not log_path.exists():
        print(f"ERROR: log file not found: {log_path}", file=sys.stderr)
        return 1

    print(f"Parsing: {log_path}")
    entries = parse_x64dbg_log(log_path)
    print(f"Found {len(entries)} breakpoint hit entries")

    # Load specs for context
    try:
        probe_path = _resolve_probe_path(args.probe)
        specs = load_breakpoint_specs(probe_path)
    except FileNotFoundError:
        specs = None

    analysis = analyze_log_entries(entries, specs)
    print(f"Unique base pointers: {analysis['num_unique_bases']}")
    print(f"Coordinate candidates: {analysis['num_coord_candidates']}")
    print()

    if analysis["cluster_hits"]:
        print("Breakpoint hits by cluster:")
        for cluster, count in sorted(analysis["cluster_hits"].items()):
            print(f"  {cluster}: {count} hits")

    if analysis["coord_candidates"]:
        print("\nTop coordinate candidates:")
        # Sort by magnitude (prefer non-trivial positions)
        candidates = sorted(
            analysis["coord_candidates"],
            key=lambda c: abs(c["x"]) + abs(c["y"]) + abs(c["z"]),
            reverse=True,
        )
        for c in candidates[:20]:
            print(
                f"  [{c['cluster']}] @ {c['absolute_address']} "
                f"(base={c['base_address']}, off={c['base_offset']}): "
                f"({c['x']:.2f}, {c['y']:.2f}, {c['z']:.2f})"
            )
    else:
        print("No coordinate candidates found (all values were zero, NaN, or degenerate).")
        print("This may mean:")
        print("  - The breakpoints haven't fired yet (game needs to run longer)")
        print("  - The offsets don't contain float coordinates")
        print("  - The player struct pointer in the register is NULL")

    # Write analysis JSON
    out_path = Path(args.out) if args.out else log_path.with_suffix(".analysis.json")
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
    print(f"\nAnalysis written: {out_path}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="x64dbg bridge: automated breakpoint-based player coordinate discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", help="Subcommand")

    # ---- generate ----
    gen = sub.add_parser("generate", help="Generate x64dbg breakpoint script")
    gen.add_argument("--probe", help="Path to probe-modrm-leads JSON (default: latest in stage5-live)")
    gen.add_argument("--pid", type=int, default=0, help="Target PID (for instructions only)")
    gen.add_argument("--out", default=DEFAULT_SCRIPT_OUT, help=f"Output script path (default: {DEFAULT_SCRIPT_OUT})")

    # ---- launch ----
    launch = sub.add_parser("launch", help="Launch x64dbg attached to a process")
    launch.add_argument("--pid", type=int, required=True, help="Target RIFT process PID")
    launch.add_argument("--script", help="Path to x64dbg script to load after attach")

    # ---- verify ----
    verify_parser = sub.add_parser("verify", help="Verify candidates via ReadProcessMemory")
    verify_parser.add_argument("--pid", type=int, required=True, help="Target RIFT process PID")
    verify_parser.add_argument("--analysis", required=True, help="Path to analysis JSON from parse command")

    # ---- parse ----
    parse = sub.add_parser("parse", help="Parse x64dbg log output")
    parse.add_argument("--log", required=True, help="Path to x64dbg log file")
    parse.add_argument("--probe", help="Path to probe-modrm-leads JSON (for context)")
    parse.add_argument("--out", help="Output analysis JSON path (default: <log>.analysis.json)")

    args = parser.parse_args(argv)

    if args.command == "generate":
        return _cmd_generate(args)
    elif args.command == "launch":
        return _cmd_launch(args)
    elif args.command == "verify":
        return _cmd_verify(args)
    elif args.command == "parse":
        return _cmd_parse(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
