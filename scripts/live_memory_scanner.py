"""Read-only live-memory scan planning and fixture-backed scanner core.

The live execution path is intentionally gated by the workflow command. Tests use
``FixtureProcessReader`` only; CI must never attach to a live process.
"""

from __future__ import annotations

import ctypes
import json
import re
import struct
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

SCHEMA_VERSION = "live-memory-scan-plan/v1"
DEFAULT_PROCESS_NAME = "rift_x64.exe"
DEFAULT_MAX_SCAN_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_MATCHES = 32
DEFAULT_MAX_REGIONS = 256
DEFAULT_TIMEOUT_SECONDS = 10
SCAN_CHUNK_SIZE = 64 * 1024

_PATTERN_LABEL_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")


@dataclass(frozen=True)
class HexPattern:
    """Exact byte pattern for a bounded read-only scan."""

    label: str
    data: bytes

    @property
    def normalized_hex(self) -> str:
        return self.data.hex().upper()


@dataclass(frozen=True)
class MemoryRegion:
    """Readable memory region exposed by a process-reader implementation."""

    base_address: int
    size: int
    protection: str = ""


class ProcessReader(Protocol):
    """Minimal read-only process-reader abstraction for live and fixture scans."""

    def iter_regions(self) -> Iterable[MemoryRegion]:
        """Yield candidate readable memory regions."""
        ...

    def read(self, base_address: int, size: int) -> bytes:
        """Read at most ``size`` bytes from ``base_address``."""
        ...


class FixtureProcessReader:
    """In-memory reader used by tests and non-live validation."""

    def __init__(self, regions: Iterable[tuple[int, bytes, str] | MemoryRegion]) -> None:
        self._regions: list[tuple[MemoryRegion, bytes]] = []
        for region in regions:
            if isinstance(region, MemoryRegion):
                self._regions.append((region, b"\x00" * region.size))
            else:
                base_address, data, protection = region
                self._regions.append((MemoryRegion(base_address, len(data), protection), data))

    def iter_regions(self) -> Iterable[MemoryRegion]:
        return [region for region, _ in self._regions]

    def read(self, base_address: int, size: int) -> bytes:
        for region, data in self._regions:
            start = region.base_address
            end = start + region.size
            if start <= base_address < end:
                offset = base_address - start
                return data[offset : offset + size]
        raise ValueError(f"fixture read outside registered regions: 0x{base_address:X}")


def parse_hex_pattern(spec: str) -> HexPattern:
    """Parse ``label=hex`` exact-byte pattern specs."""
    if "=" not in spec:
        raise ValueError("pattern must use label=hex format")
    raw_label, raw_hex = spec.split("=", 1)
    label = raw_label.strip()
    if not _PATTERN_LABEL_RE.match(label):
        raise ValueError(f"invalid pattern label {label!r}; use 1-80 letters/digits/._-")
    normalized = raw_hex.replace("0x", "").replace("0X", "")
    normalized = re.sub(r"[\s_:-]+", "", normalized)
    if not normalized:
        raise ValueError(f"pattern {label!r} has no hex bytes")
    if len(normalized) % 2:
        raise ValueError(f"pattern {label!r} has an odd number of hex nibbles")
    if not _HEX_RE.match(normalized):
        raise ValueError(f"pattern {label!r} contains non-hex characters")
    data = bytes.fromhex(normalized)
    if not data:
        raise ValueError(f"pattern {label!r} has no bytes")
    return HexPattern(label=label, data=data)


def parse_hex_patterns(specs: Iterable[str]) -> list[HexPattern]:
    """Parse and de-duplicate exact-byte pattern specs by label."""
    patterns = [parse_hex_pattern(spec) for spec in specs]
    if not patterns:
        raise ValueError("at least one --live-pattern label=hex is required")
    seen: set[str] = set()
    for pattern in patterns:
        if pattern.label in seen:
            raise ValueError(f"duplicate pattern label {pattern.label!r}")
        seen.add(pattern.label)
    return patterns


def load_pattern_specs_from_file(path: Path) -> list[str]:
    """Load ``label=hex`` specs from a tracked candidate-only target manifest."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("SchemaVersion") != "live-memory-scan-targets/v1":
        raise ValueError("live pattern manifest must use SchemaVersion live-memory-scan-targets/v1")
    if data.get("CandidateOnly") is not True:
        raise ValueError("live pattern manifest must be CandidateOnly=true")
    targets = data.get("Targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("live pattern manifest must contain at least one target")
    specs: list[str] = []
    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            raise ValueError(f"target {index} must be an object")
        label = target.get("Label")
        hex_text = target.get("Hex")
        byte_length = target.get("ByteLength")
        if not isinstance(label, str) or not isinstance(hex_text, str):
            raise ValueError(f"target {index} requires string Label and Hex")
        pattern = parse_hex_pattern(f"{label}={hex_text}")
        if byte_length is not None and byte_length != len(pattern.data):
            raise ValueError(f"target {label!r} ByteLength does not match Hex")
        specs.append(f"{pattern.label}={pattern.normalized_hex}")
    return specs


def _positive_limit(name: str, value: int) -> int:
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _safe_live_output_dir(raw_out: str, repo_root: Path) -> Path:
    allowed = (repo_root / "Exports" / "discovery-plan" / "stage5-live").resolve()
    out_dir = Path(raw_out).resolve() if raw_out else allowed
    if out_dir != allowed and allowed not in out_dir.parents:
        raise ValueError("scan-live-memory output must stay under Exports/discovery-plan/stage5-live")
    return out_dir


def build_live_memory_scan_plan(
    *,
    repo_root: Path,
    out: str,
    process_name: str,
    pid: int,
    pattern_specs: Iterable[str],
    execute_live_read: bool,
    experimental_live: bool,
    confirm_live_read: bool,
    max_scan_bytes: int,
    max_matches: int,
    max_regions: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Build a machine-readable live-memory scan plan without attaching to a process."""
    output_dir = _safe_live_output_dir(out, repo_root)
    patterns = parse_hex_patterns(pattern_specs)
    max_scan_bytes = _positive_limit("max_scan_bytes", max_scan_bytes)
    max_matches = _positive_limit("max_matches", max_matches)
    max_regions = _positive_limit("max_regions", max_regions)
    timeout_seconds = _positive_limit("timeout_seconds", timeout_seconds)

    refusal_reasons: list[str] = []
    if process_name.lower() != DEFAULT_PROCESS_NAME:
        refusal_reasons.append("target-process-must-be-rift_x64.exe")
    if execute_live_read and not experimental_live:
        refusal_reasons.append("missing---experimental-live")
    if execute_live_read and not confirm_live_read:
        refusal_reasons.append("missing---confirm-live-read")
    if execute_live_read and pid <= 0:
        refusal_reasons.append("missing-explicit---pid")
    if not execute_live_read:
        refusal_reasons.append("dry-run-only-no-live-read-requested")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_json = output_dir / f"live-memory-scan-{timestamp}.json"
    output_markdown = output_dir / f"live-memory-scan-{timestamp}.md"
    return {
        "SchemaVersion": SCHEMA_VERSION,
        "TargetProcessName": process_name,
        "Pid": pid if pid > 0 else None,
        "ExecuteLiveRead": execute_live_read,
        "ExperimentalLive": experimental_live,
        "ConfirmLiveRead": confirm_live_read,
        "LiveProcessReadExecuted": False,
        "ExecutionAllowed": execute_live_read and not refusal_reasons,
        "RefusalReasons": refusal_reasons,
        "OutputDirectory": _display_path(output_dir, repo_root),
        "OutputJsonPath": _display_path(output_json, repo_root),
        "OutputMarkdownPath": _display_path(output_markdown, repo_root),
        "Limits": {
            "MaxScanBytes": max_scan_bytes,
            "MaxMatchesPerPattern": max_matches,
            "MaxRegions": max_regions,
            "TimeoutSeconds": timeout_seconds,
            "ChunkBytes": SCAN_CHUNK_SIZE,
        },
        "Patterns": [
            {
                "Label": pattern.label,
                "Hex": pattern.normalized_hex,
                "ByteLength": len(pattern.data),
            }
            for pattern in patterns
        ],
        "Safety": {
            "ReadOnly": True,
            "NoWrites": True,
            "NoHooks": True,
            "NoDllInjection": True,
            "NoRemoteThreads": True,
            "NoFullDump": True,
            "OutputIgnoredGenerated": True,
            "RequiresSeparateLiveExecutionGate": True,
        },
        "NextAction": (
            "Run only after reviewing the exact PID, patterns, limits, output paths, and generated-output guard."
            if execute_live_read
            else "Review this dry-run plan; actual live reads require --execute-live-read --experimental-live --confirm-live-read --pid."
        ),
    }


def scan_process_reader(
    reader: ProcessReader,
    patterns: list[HexPattern],
    *,
    max_scan_bytes: int,
    max_matches: int,
    max_regions: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Scan a process reader for exact byte patterns with bounded reads only."""
    started = time.monotonic()
    bytes_scanned = 0
    regions_scanned = 0
    timed_out = False
    matches: dict[str, list[dict[str, Any]]] = {pattern.label: [] for pattern in patterns}
    seen_addresses: dict[str, set[int]] = {pattern.label: set() for pattern in patterns}
    max_pattern_len = max(len(pattern.data) for pattern in patterns)

    for region in reader.iter_regions():
        if regions_scanned >= max_regions or bytes_scanned >= max_scan_bytes:
            break
        if time.monotonic() - started > timeout_seconds:
            timed_out = True
            break
        regions_scanned += 1
        offset = 0
        overlap = b""
        while offset < region.size and bytes_scanned < max_scan_bytes:
            if time.monotonic() - started > timeout_seconds:
                timed_out = True
                break
            read_size = min(SCAN_CHUNK_SIZE, region.size - offset, max_scan_bytes - bytes_scanned)
            if read_size <= 0:
                break
            address = region.base_address + offset
            chunk = reader.read(address, read_size)
            if not chunk:
                break
            scan_buffer = overlap + chunk
            scan_base = address - len(overlap)
            for pattern in patterns:
                start = 0
                while len(matches[pattern.label]) < max_matches:
                    index = scan_buffer.find(pattern.data, start)
                    if index < 0:
                        break
                    match_address = scan_base + index
                    if match_address not in seen_addresses[pattern.label]:
                        seen_addresses[pattern.label].add(match_address)
                        matches[pattern.label].append(
                            {
                                "Address": f"0x{match_address:X}",
                                "RegionBase": f"0x{region.base_address:X}",
                                "OffsetInRegion": match_address - region.base_address,
                                "SnippetHex": pattern.normalized_hex,
                            }
                        )
                    start = index + 1
            bytes_scanned += len(chunk)
            offset += len(chunk)
            overlap = scan_buffer[-(max_pattern_len - 1) :] if max_pattern_len > 1 else b""
        if timed_out:
            break
        if all(len(pattern_matches) >= max_matches for pattern_matches in matches.values()):
            break

    return {
        "BytesScanned": bytes_scanned,
        "RegionsScanned": regions_scanned,
        "TimedOut": timed_out,
        "PatternResults": [
            {
                "Label": pattern.label,
                "MatchCount": len(matches[pattern.label]),
                "Matches": matches[pattern.label],
            }
            for pattern in patterns
        ],
    }


class WindowsReadOnlyProcessReader:
    """Windows ``ReadProcessMemory`` reader that requests query/read rights only."""

    def __init__(self, pid: int) -> None:
        if sys.platform != "win32":
            raise RuntimeError("live memory scanning is only available on Windows")
        self.pid = pid
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        process_query_limited_information = 0x1000
        process_vm_read = 0x0010
        self._handle = self._kernel32.OpenProcess(process_query_limited_information | process_vm_read, False, pid)
        if not self._handle:
            raise OSError(ctypes.get_last_error(), f"OpenProcess failed for PID {pid}")

    def close(self) -> None:
        if getattr(self, "_handle", None):
            self._kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self) -> WindowsReadOnlyProcessReader:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.close()

    def iter_regions(self) -> Iterable[MemoryRegion]:
        memory_basic_information = _memory_basic_information_type()
        mbi = memory_basic_information()
        address = 0
        mem_commit = 0x1000
        page_guard = 0x100
        page_noaccess = 0x01
        readable = {0x02, 0x04, 0x20, 0x40, 0x80}
        while True:
            result = self._kernel32.VirtualQueryEx(
                self._handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi),
            )
            if not result:
                break
            base_address = int(mbi.BaseAddress or 0)
            region_size = int(mbi.RegionSize)
            protect = int(mbi.Protect)
            state = int(mbi.State)
            if (
                region_size > 0
                and state == mem_commit
                and protect & page_noaccess == 0
                and protect & page_guard == 0
                and protect & 0xFF in readable
            ):
                yield MemoryRegion(base_address=base_address, size=region_size, protection=f"0x{protect:X}")
            next_address = base_address + max(region_size, 1)
            if next_address <= address:
                break
            address = next_address

    def read(self, base_address: int, size: int) -> bytes:
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)
        ok = self._kernel32.ReadProcessMemory(
            self._handle,
            ctypes.c_void_p(base_address),
            buffer,
            size,
            ctypes.byref(bytes_read),
        )
        if not ok:
            return b""
        return buffer.raw[: bytes_read.value]


def _memory_basic_information_type() -> type[ctypes.Structure]:
    class MemoryBasicInformation(ctypes.Structure):
        _fields_ = [
            ("BaseAddress", ctypes.c_void_p),
            ("AllocationBase", ctypes.c_void_p),
            ("AllocationProtect", ctypes.c_ulong),
            ("RegionSize", ctypes.c_size_t),
            ("State", ctypes.c_ulong),
            ("Protect", ctypes.c_ulong),
            ("Type", ctypes.c_ulong),
        ]

    return MemoryBasicInformation


def run_windows_live_scan(plan: dict[str, Any], patterns: list[HexPattern]) -> dict[str, Any]:
    """Execute a gated live scan using Windows read-only APIs."""
    if not plan.get("ExecutionAllowed"):
        raise RuntimeError("live scan execution is not allowed by the plan")
    pid = plan.get("Pid")
    if not isinstance(pid, int) or pid <= 0:
        raise RuntimeError("live scan requires an explicit positive PID")
    limits = plan["Limits"]
    with WindowsReadOnlyProcessReader(pid) as reader:
        scan = scan_process_reader(
            reader,
            patterns,
            max_scan_bytes=int(limits["MaxScanBytes"]),
            max_matches=int(limits["MaxMatchesPerPattern"]),
            max_regions=int(limits["MaxRegions"]),
            timeout_seconds=int(limits["TimeoutSeconds"]),
        )
    result = dict(plan)
    result["LiveProcessReadExecuted"] = True
    result["ScanResult"] = scan
    return result


def write_live_scan_reports(result: dict[str, Any], repo_root: Path) -> tuple[Path, Path]:
    """Write bounded live scan JSON and Markdown reports under ignored output."""
    json_path = repo_root / str(result["OutputJsonPath"])
    markdown_path = repo_root / str(result["OutputMarkdownPath"])
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        "# Live memory scan report",
        "",
        f"SchemaVersion: `{result['SchemaVersion']}`",
        f"Target: `{result['TargetProcessName']}` PID `{result['Pid']}`",
        f"LiveProcessReadExecuted: `{str(result['LiveProcessReadExecuted']).lower()}`",
        "",
        "## Pattern results",
        "",
    ]
    for row in result.get("ScanResult", {}).get("PatternResults", []):
        lines.append(f"- `{row['Label']}`: {row['MatchCount']} matches")
    lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path


# ============================================================================
# Wildcard signature scanning (for probe-modrm-leads)
# ============================================================================

WILDCARD_BYTE = 0x100  # Sentinel value meaning "any byte matches"


@dataclass(frozen=True)
class WildcardSignature:
    """A byte signature with wildcard positions (? bytes match anything)."""

    label: str
    pattern: tuple[int, ...]  # tuple of bytes, WILDCARD_BYTE = match-any

    @property
    def length(self) -> int:
        return len(self.pattern)

    def longest_exact_prefix(self) -> tuple[tuple[int, ...], int]:
        """Return (exact_bytes, length) of longest contiguous non-wildcard segment."""
        best_bytes: tuple[int, ...] = ()
        best_len = 0
        current: list[int] = []
        for b in self.pattern:
            if b != WILDCARD_BYTE:
                current.append(b)
            else:
                if len(current) > best_len:
                    best_bytes = tuple(current)
                    best_len = len(current)
                current = []
        if len(current) > best_len:
            best_bytes = tuple(current)
            best_len = len(current)
        return best_bytes, best_len

    def matches_at(self, buffer: bytes) -> bool:
        """Check if buffer[:length] matches the wildcard pattern."""
        if len(buffer) < self.length:
            return False
        for i, expected in enumerate(self.pattern):
            if expected != WILDCARD_BYTE and buffer[i] != expected:
                return False
        return True


def parse_wildcard_hex(label: str, sig_hex: str) -> WildcardSignature:
    """Parse a hex signature with ?? wildcards like '48 83 EC 20 ?? ?? ?? ??'.

    Returns a WildcardSignature where WILDCARD_BYTE marks wildcard positions.
    """
    parts = sig_hex.strip().split()
    if not parts:
        raise ValueError(f"wildcard signature {label!r} has no bytes")
    pattern: list[int] = []
    for part in parts:
        if part == "??":
            pattern.append(WILDCARD_BYTE)
        else:
            if len(part) != 2:
                raise ValueError(f"wildcard signature {label!r} has malformed byte {part!r}")
            try:
                pattern.append(int(part, 16))
            except ValueError as exc:
                raise ValueError(f"wildcard signature {label!r} has non-hex byte {part!r}") from exc
    return WildcardSignature(label=label, pattern=tuple(pattern))


def scan_wildcard_signatures(
    reader: ProcessReader,
    signatures: list[WildcardSignature],
    *,
    max_scan_bytes: int = DEFAULT_MAX_SCAN_BYTES,
    max_matches: int = DEFAULT_MAX_MATCHES,
    max_regions: int = DEFAULT_MAX_REGIONS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    executable_only: bool = True,
) -> dict[str, Any]:
    """Scan process memory for wildcard signatures.

    Strategy: find longest exact prefix → exact-byte fast-path scan → wildcard verify.
    Falls back to brute-force scan when the longest exact prefix is too short (<4 bytes).
    """
    started = time.monotonic()
    bytes_scanned = 0
    regions_scanned = 0
    timed_out = False
    min_exact_prefix = 4  # Minimum exact prefix length for fast-path

    matches: dict[str, list[dict[str, Any]]] = {sig.label: [] for sig in signatures}
    seen_addresses: dict[str, set[int]] = {sig.label: set() for sig in signatures}

    # Pre-compute exact prefixes for fast-path
    exact_prefixes: dict[str, tuple[bytes, int]] = {}
    use_fast_path: dict[str, bool] = {}
    for sig in signatures:
        exact_bytes, exact_len = sig.longest_exact_prefix()
        exact_prefixes[sig.label] = (bytes(exact_bytes), exact_len)
        use_fast_path[sig.label] = exact_len >= min_exact_prefix

    max_pattern_len = max(sig.length for sig in signatures)

    for region in reader.iter_regions():
        if regions_scanned >= max_regions or bytes_scanned >= max_scan_bytes:
            break
        if time.monotonic() - started > timeout_seconds:
            timed_out = True
            break

        # Filter for executable regions when probing code signatures
        if executable_only:
            try:
                protect = int(region.protection, 16) if region.protection else 0
                if (protect & 0xFF) not in {0x20, 0x40, 0x80}:
                    continue
            except ValueError, TypeError:
                pass

        regions_scanned += 1
        offset = 0
        overlap = b""

        while offset < region.size and bytes_scanned < max_scan_bytes:
            if time.monotonic() - started > timeout_seconds:
                timed_out = True
                break
            read_size = min(SCAN_CHUNK_SIZE, region.size - offset, max_scan_bytes - bytes_scanned)
            if read_size <= 0:
                break
            address = region.base_address + offset
            chunk = reader.read(address, read_size)
            if not chunk:
                break
            scan_buffer = overlap + chunk
            scan_base = address - len(overlap)

            for sig in signatures:
                if len(matches[sig.label]) >= max_matches:
                    continue

                if use_fast_path[sig.label]:
                    exact_bytes, exact_len = exact_prefixes[sig.label]
                    start = 0
                    while len(matches[sig.label]) < max_matches:
                        index = scan_buffer.find(exact_bytes, start)
                        if index < 0:
                            break
                        # Check that the full wildcard pattern fits
                        match_offset = index
                        # Rewind to the start of the full pattern from the exact prefix
                        # Find where the exact prefix starts in the full pattern
                        prefix_start_in_pat = 0
                        pat_list = list(sig.pattern)
                        for pi in range(len(pat_list) - exact_len + 1):
                            seg = pat_list[pi : pi + exact_len]
                            if all(seg[j] == exact_bytes[j] for j in range(exact_len)):
                                prefix_start_in_pat = pi
                                break
                        sig_start = match_offset - prefix_start_in_pat
                        if sig_start >= 0 and sig_start + sig.length <= len(scan_buffer):
                            match_addr = scan_base + sig_start
                            if match_addr not in seen_addresses[sig.label]:
                                candidate = scan_buffer[sig_start : sig_start + sig.length]
                                if sig.matches_at(candidate):
                                    seen_addresses[sig.label].add(match_addr)
                                    matches[sig.label].append(
                                        {
                                            "Address": f"0x{match_addr:X}",
                                            "RegionBase": f"0x{region.base_address:X}",
                                            "OffsetInRegion": match_addr - region.base_address,
                                            "SnippetHex": candidate.hex().upper(),
                                        }
                                    )
                        start = index + 1
                else:
                    # Brute-force fallback for short exact prefixes
                    for si in range(len(scan_buffer) - sig.length + 1):
                        if len(matches[sig.label]) >= max_matches:
                            break
                        match_addr = scan_base + si
                        if match_addr in seen_addresses[sig.label]:
                            continue
                        candidate = scan_buffer[si : si + sig.length]
                        if sig.matches_at(candidate):
                            seen_addresses[sig.label].add(match_addr)
                            matches[sig.label].append(
                                {
                                    "Address": f"0x{match_addr:X}",
                                    "RegionBase": f"0x{region.base_address:X}",
                                    "OffsetInRegion": match_addr - region.base_address,
                                    "SnippetHex": candidate.hex().upper(),
                                }
                            )

            bytes_scanned += len(chunk)
            offset += len(chunk)
            overlap = scan_buffer[-(max_pattern_len - 1) :] if max_pattern_len > 1 else b""

        if timed_out:
            break
        if all(len(matches[sig.label]) >= max_matches for sig in signatures):
            break

    return {
        "BytesScanned": bytes_scanned,
        "RegionsScanned": regions_scanned,
        "TimedOut": timed_out,
        "SignatureResults": [
            {
                "Label": sig.label,
                "MatchCount": len(matches[sig.label]),
                "Matches": matches[sig.label],
            }
            for sig in signatures
        ],
    }


# ============================================================================
# probe-modrm-leads: bridge static ModRM analysis to live memory
# ============================================================================

PROBE_MODRM_SCHEMA = "probe-modrm-leads/v1"
DEFAULT_MODRM_SCAN_PATH = "Exports/binary-phase1/modrm-memory-access-scan.json"
PLAYER_STRUCT_REGISTERS: tuple[str, ...] = ("RBX", "RCX")
PLAYER_STRUCT_OFFSETS: tuple[int, ...] = (
    0x304,
    0x308,
    0x30C,
    0x310,
    0x314,
    0x318,
    0x31C,
    0x320,
    0x324,
    0x328,
)
PLAYER_STRUCT_OFFSET_SET: frozenset[int] = frozenset(PLAYER_STRUCT_OFFSETS)


def load_modrm_scan(path: Path) -> dict[str, Any]:
    """Load a modrm-memory-access-scan JSON report."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "modrm-memory-access-scan/v1":
        raise ValueError(f"modrm scan must use schema modrm-memory-access-scan/v1, got {data.get('schema')!r}")
    if data.get("candidate_only") is not True:
        raise ValueError("modrm scan must be candidate_only=true")
    return data


def score_player_coordinate_likelihood(cluster: dict[str, Any]) -> float:
    """Score a cluster's likelihood of accessing player coordinates.

    Higher score = more likely to be accessing player state (position, velocity, etc.).
    Weighted combination of:
    - Base register is RBX or RCX (primary player-struct registers)
    - Target offsets in the 0x304-0x328 range
    - Hit count density
    """
    base_counts: dict[str, int] = cluster.get("base_register_counts", {})
    offset_counts: dict[str, int] = cluster.get("target_offset_counts", {})
    hit_count = cluster.get("hit_count", 0)

    if hit_count == 0:
        return 0.0

    total_base = sum(base_counts.values())
    player_reg_count = sum(base_counts.get(reg, 0) for reg in PLAYER_STRUCT_REGISTERS)
    reg_score = player_reg_count / total_base if total_base > 0 else 0.0

    total_offsets = sum(offset_counts.values())
    try:
        player_off_count = sum(
            count for offset_str, count in offset_counts.items() if int(offset_str, 16) in PLAYER_STRUCT_OFFSET_SET
        )
    except ValueError, TypeError:
        player_off_count = 0
    off_score = player_off_count / total_offsets if total_offsets > 0 else 0.0

    # 70% weight on register (RBX/RCX), 30% on offsets
    return round(0.70 * reg_score + 0.30 * off_score, 4)


def extract_cluster_signatures(
    modrm_data: dict[str, Any],
    top_n: int = 8,
) -> list[dict[str, Any]]:
    """Extract wildcard signatures from top clusters in a modrm scan report."""
    clusters = modrm_data.get("top_clusters", [])
    if not clusters:
        raise ValueError("modrm scan has no top_clusters")

    extracted: list[dict[str, Any]] = []
    for cluster in clusters[:top_n]:
        sig = cluster.get("candidate_signature", {})
        if not sig.get("valid"):
            continue
        sig_hex = sig.get("sig_hex", "")
        if not sig_hex:
            continue

        rank = cluster.get("rank", len(extracted) + 1)
        label = f"cluster_{rank:02d}"
        score = score_player_coordinate_likelihood(cluster)
        extracted.append(
            {
                "label": label,
                "rank": rank,
                "sig_hex": sig_hex,
                "raw_hex": sig.get("raw_hex", ""),
                "first_rva": cluster.get("first_rva", ""),
                "last_rva": cluster.get("last_rva", ""),
                "hit_count": cluster.get("hit_count", 0),
                "span_bytes": cluster.get("span_bytes", 0),
                "base_register_counts": cluster.get("base_register_counts", {}),
                "opcode_counts": cluster.get("opcode_counts", {}),
                "target_offset_counts": cluster.get("target_offset_counts", {}),
                "wildcard_count": sig.get("wildcard_count", 0),
                "player_coordinate_score": score,
            }
        )

    extracted.sort(key=lambda c: (-c["player_coordinate_score"], c["rank"]))
    return extracted


def build_probe_modrm_leads_plan(
    *,
    repo_root: Path,
    modrm_scan_path: str,
    pid: int,
    process_name: str,
    execute_live_read: bool,
    experimental_live: bool,
    confirm_live_read: bool,
    max_scan_bytes: int,
    max_matches: int,
    max_regions: int,
    timeout_seconds: int,
    top_clusters: int,
) -> dict[str, Any]:
    """Build a machine-readable probe-modrm-leads plan."""
    output_dir = repo_root / "Exports" / "discovery-plan" / "stage5-live"
    modrm_path = repo_root / modrm_scan_path

    refusal_reasons: list[str] = []
    if process_name.lower() != DEFAULT_PROCESS_NAME:
        refusal_reasons.append("target-process-must-be-rift_x64.exe")
    if execute_live_read and not experimental_live:
        refusal_reasons.append("missing---experimental-live")
    if execute_live_read and not confirm_live_read:
        refusal_reasons.append("missing---confirm-live-read")
    if execute_live_read and pid <= 0:
        refusal_reasons.append("missing-explicit---pid")
    if not execute_live_read:
        refusal_reasons.append("dry-run-only-no-live-read-requested")
    if not modrm_path.exists():
        refusal_reasons.append(f"modrm-scan-not-found: {modrm_scan_path}")

    # Load the modrm scan to extract cluster info even in dry-run mode
    clusters_extracted: list[dict[str, Any]] = []
    modrm_total_hits = 0
    if modrm_path.exists():
        try:
            modrm_data = load_modrm_scan(modrm_path)
            modrm_total_hits = modrm_data.get("total_matches", 0)
            clusters_extracted = extract_cluster_signatures(modrm_data, top_n=top_clusters)
        except Exception as exc:
            refusal_reasons.append(f"modrm-load-failed: {exc}")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_json = output_dir / f"probe-modrm-leads-{timestamp}.json"
    output_markdown = output_dir / f"probe-modrm-leads-{timestamp}.md"

    return {
        "SchemaVersion": PROBE_MODRM_SCHEMA,
        "TargetProcessName": process_name,
        "Pid": pid if pid > 0 else None,
        "ExecuteLiveRead": execute_live_read,
        "ExperimentalLive": experimental_live,
        "ConfirmLiveRead": confirm_live_read,
        "LiveProcessReadExecuted": False,
        "ExecutionAllowed": execute_live_read and not refusal_reasons,
        "RefusalReasons": refusal_reasons,
        "ModRMScanPath": modrm_scan_path,
        "ModRMScanTotalHits": modrm_total_hits,
        "ClustersExtracted": len(clusters_extracted),
        "OutputDirectory": _display_path(output_dir, repo_root),
        "OutputJsonPath": _display_path(output_json, repo_root),
        "OutputMarkdownPath": _display_path(output_markdown, repo_root),
        "Limits": {
            "MaxScanBytes": max_scan_bytes,
            "MaxMatchesPerSignature": max_matches,
            "MaxRegions": max_regions,
            "TimeoutSeconds": timeout_seconds,
            "ChunkBytes": SCAN_CHUNK_SIZE,
            "TopClusters": top_clusters,
        },
        "CandidateClusters": [
            {
                "Label": c["label"],
                "Rank": c["rank"],
                "SigHex": c["sig_hex"],
                "FirstRVA": c["first_rva"],
                "HitCount": c["hit_count"],
                "BaseRegisterCounts": c["base_register_counts"],
                "TargetOffsetCounts": c["target_offset_counts"],
                "PlayerCoordinateScore": c["player_coordinate_score"],
            }
            for c in clusters_extracted
        ],
        "Safety": {
            "ReadOnly": True,
            "NoWrites": True,
            "NoHooks": True,
            "NoDllInjection": True,
            "NoRemoteThreads": True,
            "NoFullDump": True,
            "OutputIgnoredGenerated": True,
            "RequiresSeparateLiveExecutionGate": True,
            "ExecutableRegionsOnly": True,
        },
        "NextAction": (
            "Run only after reviewing the exact PID, clusters, output paths, and generated-output guard."
            if execute_live_read
            else "Review this dry-run plan; actual live reads require --execute-live-read --experimental-live --confirm-live-read --pid."
        ),
    }


def run_probe_modrm_leads(
    plan: dict[str, Any],
    reader: ProcessReader,
    signatures: list[WildcardSignature],
) -> dict[str, Any]:
    """Execute a gated probe-modrm-leads live scan."""
    if not plan.get("ExecutionAllowed"):
        raise RuntimeError("probe-modrm-leads live scan is not allowed by the plan")

    limits = plan["Limits"]
    scan = scan_wildcard_signatures(
        reader,
        signatures,
        max_scan_bytes=int(limits["MaxScanBytes"]),
        max_matches=int(limits["MaxMatchesPerSignature"]),
        max_regions=int(limits["MaxRegions"]),
        timeout_seconds=int(limits["TimeoutSeconds"]),
        executable_only=True,
    )

    result = dict(plan)
    result["LiveProcessReadExecuted"] = True

    # Merge scan results with cluster metadata
    confirmed: list[dict[str, Any]] = []
    candidate_map: dict[str, dict[str, Any]] = {}
    for c in plan.get("CandidateClusters", []):
        candidate_map[c["Label"]] = c

    for sig_result in scan.get("SignatureResults", []):
        label = sig_result["Label"]
        cluster = candidate_map.get(label, {})
        confirmed.append(
            {
                "Label": label,
                "Rank": cluster.get("Rank", 0),
                "FirstRVA": cluster.get("FirstRVA", ""),
                "ConfirmedAtVA": sig_result["Matches"][0]["Address"] if sig_result["Matches"] else None,
                "MatchCount": sig_result["MatchCount"],
                "HitCount": cluster.get("HitCount", 0),
                "BaseRegisterCounts": cluster.get("BaseRegisterCounts", {}),
                "TargetOffsetCounts": cluster.get("TargetOffsetCounts", {}),
                "PlayerCoordinateScore": cluster.get("PlayerCoordinateScore", 0.0),
                "SignatureConfirmed": sig_result["MatchCount"] > 0,
                "SignaturesMatched": sig_result["Matches"],
            }
        )

    result["ClustersProbed"] = len(plan.get("CandidateClusters", []))
    result["ClustersConfirmed"] = sum(1 for c in confirmed if c["SignatureConfirmed"])
    result["ConfirmedClusters"] = sorted(confirmed, key=lambda c: (-c["PlayerCoordinateScore"], c["Rank"]))
    result["ScanResult"] = scan

    return result


def write_probe_modrm_leads_reports(result: dict[str, Any], repo_root: Path) -> tuple[Path, Path]:
    """Write probe-modrm-leads JSON and Markdown reports."""
    json_path = repo_root / str(result["OutputJsonPath"])
    markdown_path = repo_root / str(result["OutputMarkdownPath"])
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# probe-modrm-leads report",
        "",
        f"SchemaVersion: `{result['SchemaVersion']}`",
        f"Target: `{result['TargetProcessName']}` PID `{result['Pid']}`",
        f"ModRM scan: `{result['ModRMScanPath']}`",
        f"LiveProcessReadExecuted: `{str(result['LiveProcessReadExecuted']).lower()}`",
        f"Clusters probed: {result.get('ClustersProbed', 0)}",
        f"Clusters confirmed: {result.get('ClustersConfirmed', 0)}",
        "",
        "## Confirmed clusters",
        "",
        "| Rank | Score | Confirmed VA | Hits | Base regs | Target offsets |",
        "|---:|---:|---|---|---|---|",
    ]
    for c in result.get("ConfirmedClusters", []):
        if not c["SignatureConfirmed"]:
            continue
        bases_str = ", ".join(f"{k}={v}" for k, v in c["BaseRegisterCounts"].items())
        offsets_str = ", ".join(f"{k}={v}" for k, v in c["TargetOffsetCounts"].items())
        lines.append(
            f"| {c['Rank']} | {c['PlayerCoordinateScore']:.4f} | "
            f"{c['ConfirmedAtVA']} | {c['HitCount']} | {bases_str} | {offsets_str} |"
        )
    lines.extend(
        [
            "",
            "## Unconfirmed clusters",
            "",
        ]
    )
    for c in result.get("ConfirmedClusters", []):
        if c["SignatureConfirmed"]:
            continue
        bases_str = ", ".join(f"{k}={v}" for k, v in c["BaseRegisterCounts"].items())
        offsets_str = ", ".join(f"{k}={v}" for k, v in c["TargetOffsetCounts"].items())
        lines.append(
            f"- Rank {c['Rank']} (score {c['PlayerCoordinateScore']:.4f}): {c['HitCount']} hits, {bases_str}, {offsets_str}"
        )
    lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path


# ============================================================================
# Value-type scanning (float32 / int32 / uint32 range scans)
# ============================================================================

VALUE_SCHEMA = "live-value-scan/v1"
DEFAULT_VALUE_MAX_MATCHES = 1024


@dataclass(frozen=True)
class ValueTypeDef:
    """Definition for a scannable value type."""

    fmt: str
    size: int
    label: str


_VALUE_TYPES: dict[str, ValueTypeDef] = {
    "f32": ValueTypeDef("<f", 4, "float32"),
    "i32": ValueTypeDef("<i", 4, "int32"),
    "u32": ValueTypeDef("<I", 4, "uint32"),
}


def _validate_value_type(value_type: str) -> str:
    if value_type not in _VALUE_TYPES:
        raise ValueError(f"value-type must be one of {sorted(_VALUE_TYPES.keys())}, got {value_type!r}")
    return value_type


def scan_value_type(
    reader: ProcessReader,
    value_type: str,
    min_val: float,
    max_val: float,
    *,
    max_scan_bytes: int = DEFAULT_MAX_SCAN_BYTES,
    max_matches: int = DEFAULT_VALUE_MAX_MATCHES,
    max_regions: int = DEFAULT_MAX_REGIONS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Scan all readable process memory for typed values within [min_val, max_val].

    Uses 4-byte aligned reads and ``struct.unpack`` for each element.
    Scans ALL committed readable regions (heap, data, stack), not just executable.
    Inclusive bounds; NaN values are naturally excluded.
    """
    vt = _VALUE_TYPES[value_type]
    fmt: str = vt.fmt
    elem_size: int = vt.size

    started = time.monotonic()
    bytes_scanned = 0
    regions_scanned = 0
    timed_out = False
    matches: list[dict[str, Any]] = []
    seen: set[int] = set()

    for region in reader.iter_regions():
        if regions_scanned >= max_regions or bytes_scanned >= max_scan_bytes or len(matches) >= max_matches:
            break
        if time.monotonic() - started > timeout_seconds:
            timed_out = True
            break
        regions_scanned += 1
        offset = 0
        while offset + elem_size <= region.size and bytes_scanned < max_scan_bytes and len(matches) < max_matches:
            if time.monotonic() - started > timeout_seconds:
                timed_out = True
                break
            read_size = min(SCAN_CHUNK_SIZE, region.size - offset, max_scan_bytes - bytes_scanned)
            read_size = (read_size // elem_size) * elem_size
            if read_size < elem_size:
                break
            address = region.base_address + offset
            chunk = reader.read(address, read_size)
            if not chunk:
                break
            for i in range(0, len(chunk) - elem_size + 1, elem_size):
                if len(matches) >= max_matches:
                    break
                elem_addr = address + i
                if elem_addr in seen:
                    continue
                raw = chunk[i : i + elem_size]
                try:
                    value = struct.unpack(fmt, raw)[0]
                except struct.error:
                    continue
                if isinstance(value, float) and value != value:
                    continue
                if min_val <= value <= max_val:
                    seen.add(elem_addr)
                    matches.append(
                        {
                            "Address": f"0x{elem_addr:X}",
                            "Value": value,
                            "RegionBase": f"0x{region.base_address:X}",
                            "OffsetInRegion": elem_addr - region.base_address,
                        }
                    )
            bytes_scanned += len(chunk)
            offset += len(chunk)
        if timed_out:
            break

    return {
        "ValueType": value_type,
        "ValueTypeLabel": vt.label,
        "MinValue": min_val,
        "MaxValue": max_val,
        "BytesScanned": bytes_scanned,
        "RegionsScanned": regions_scanned,
        "TimedOut": timed_out,
        "MatchCount": len(matches),
        "Matches": sorted(matches, key=lambda m: int(m["Address"], 16)),
    }


def build_value_scan_plan(
    *,
    repo_root: Path,
    process_name: str,
    pid: int,
    value_type: str,
    min_val: float,
    max_val: float,
    execute_live_read: bool,
    experimental_live: bool,
    confirm_live_read: bool,
    max_scan_bytes: int,
    max_matches: int,
    max_regions: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Build a machine-readable value-type scan plan without attaching to a process."""
    output_dir = repo_root / "Exports" / "discovery-plan" / "stage5-live"
    _validate_value_type(value_type)
    max_scan_bytes = _positive_limit("max_scan_bytes", max_scan_bytes)
    max_matches = _positive_limit("max_matches", max_matches)
    max_regions = _positive_limit("max_regions", max_regions)
    timeout_seconds = _positive_limit("timeout_seconds", timeout_seconds)

    refusal_reasons: list[str] = []
    if process_name.lower() != DEFAULT_PROCESS_NAME:
        refusal_reasons.append("target-process-must-be-rift_x64.exe")
    if execute_live_read and not experimental_live:
        refusal_reasons.append("missing---experimental-live")
    if execute_live_read and not confirm_live_read:
        refusal_reasons.append("missing---confirm-live-read")
    if execute_live_read and pid <= 0:
        refusal_reasons.append("missing-explicit---pid")
    if not execute_live_read:
        refusal_reasons.append("dry-run-only-no-live-read-requested")
    if max_val <= min_val:
        refusal_reasons.append(f"max-val ({max_val}) must be greater than min-val ({min_val})")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_json = output_dir / f"value-scan-{timestamp}.json"
    output_markdown = output_dir / f"value-scan-{timestamp}.md"

    return {
        "SchemaVersion": VALUE_SCHEMA,
        "TargetProcessName": process_name,
        "Pid": pid if pid > 0 else None,
        "ExecuteLiveRead": execute_live_read,
        "ExperimentalLive": experimental_live,
        "ConfirmLiveRead": confirm_live_read,
        "LiveProcessReadExecuted": False,
        "ExecutionAllowed": execute_live_read and not refusal_reasons,
        "RefusalReasons": refusal_reasons,
        "ValueType": value_type,
        "ValueTypeLabel": _VALUE_TYPES[value_type].label,
        "MinValue": min_val,
        "MaxValue": max_val,
        "OutputDirectory": _display_path(output_dir, repo_root),
        "OutputJsonPath": _display_path(output_json, repo_root),
        "OutputMarkdownPath": _display_path(output_markdown, repo_root),
        "Limits": {
            "MaxScanBytes": max_scan_bytes,
            "MaxMatches": max_matches,
            "MaxRegions": max_regions,
            "TimeoutSeconds": timeout_seconds,
            "ChunkBytes": SCAN_CHUNK_SIZE,
        },
        "Safety": {
            "ReadOnly": True,
            "NoWrites": True,
            "NoHooks": True,
            "NoDllInjection": True,
            "NoRemoteThreads": True,
            "NoFullDump": True,
            "OutputIgnoredGenerated": True,
            "RequiresSeparateLiveExecutionGate": True,
        },
        "NextAction": (
            "Run only after reviewing the exact PID, value type, range, limits, output paths, and generated-output guard."
            if execute_live_read
            else "Review this dry-run plan; actual live reads require --execute-live-read --experimental-live --confirm-live-read --pid."
        ),
    }


def run_live_value_scan(plan: dict[str, Any]) -> dict[str, Any]:
    """Execute a gated live value-type scan using Windows read-only APIs."""
    if not plan.get("ExecutionAllowed"):
        raise RuntimeError("live value scan execution is not allowed by the plan")
    pid = plan.get("Pid")
    if not isinstance(pid, int) or pid <= 0:
        raise RuntimeError("live value scan requires an explicit positive PID")
    limits = plan["Limits"]
    with WindowsReadOnlyProcessReader(pid) as reader:
        scan = scan_value_type(
            reader,
            value_type=str(plan["ValueType"]),
            min_val=float(plan["MinValue"]),
            max_val=float(plan["MaxValue"]),
            max_scan_bytes=int(limits["MaxScanBytes"]),
            max_matches=int(limits["MaxMatches"]),
            max_regions=int(limits["MaxRegions"]),
            timeout_seconds=int(limits["TimeoutSeconds"]),
        )
    result = dict(plan)
    result["LiveProcessReadExecuted"] = True
    result["ScanResult"] = scan
    return result


def write_value_scan_reports(result: dict[str, Any], repo_root: Path) -> tuple[Path, Path]:
    """Write value-type scan JSON and Markdown reports."""
    json_path = repo_root / str(result["OutputJsonPath"])
    markdown_path = repo_root / str(result["OutputMarkdownPath"])
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    scan = result.get("ScanResult", {})
    lines = [
        "# Value-type scan report",
        "",
        f"SchemaVersion: `{result['SchemaVersion']}`",
        f"Target: `{result['TargetProcessName']}` PID `{result['Pid']}`",
        f"Value type: `{result.get('ValueTypeLabel', result.get('ValueType'))}`",
        f"Range: [{result.get('MinValue')}, {result.get('MaxValue')}]",
        f"LiveProcessReadExecuted: `{str(result['LiveProcessReadExecuted']).lower()}`",
        f"Match count: {scan.get('MatchCount', 0)}",
        f"Bytes scanned: {scan.get('BytesScanned', 0):,}",
        f"Regions scanned: {scan.get('RegionsScanned', 0)}",
        "",
    ]
    if scan.get("TimedOut"):
        lines.append("**⚠ Scan timed out before completion.**")
        lines.append("")
    matches = scan.get("Matches", [])
    if matches:
        lines.extend(
            [
                "## Sample matches (first 20)",
                "",
                "| Address | Value | Region |",
                "|---|---|---|",
            ]
        )
        for m in matches[:20]:
            lines.append(f"| {m['Address']} | {m['Value']} | {m['RegionBase']} |")
    else:
        lines.append("*No matches found in scanned regions.*")
    lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path


# ============================================================================
# Snapshot-diff value scanning (two-pass Cheat Engine style for player coords)
# ============================================================================

DIFF_SCHEMA = "live-snapshot-diff/v1"
SNAPSHOT_SCHEMA = "live-value-snapshot/v1"


def scan_value_snapshot(
    reader: ProcessReader,
    value_type: str,
    min_val: float,
    max_val: float,
    *,
    max_scan_bytes: int = DEFAULT_MAX_SCAN_BYTES,
    max_matches: int = DEFAULT_VALUE_MAX_MATCHES,
    max_regions: int = DEFAULT_MAX_REGIONS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Scan all readable process memory and return a flat {address_hex: value} snapshot.

    Identical scan logic to ``scan_value_type`` but outputs a compact snapshot
    format suitable for pairwise diffing.
    """
    raw = scan_value_type(
        reader,
        value_type,
        min_val,
        max_val,
        max_scan_bytes=max_scan_bytes,
        max_matches=max_matches,
        max_regions=max_regions,
        timeout_seconds=timeout_seconds,
    )
    snapshot: dict[str, float] = {}
    for m in raw["Matches"]:
        snapshot[m["Address"]] = float(m["Value"])
    return {
        "SchemaVersion": SNAPSHOT_SCHEMA,
        "Timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ValueType": value_type,
        "ValueTypeLabel": _VALUE_TYPES[value_type].label,
        "MinValue": min_val,
        "MaxValue": max_val,
        "MatchCount": len(snapshot),
        "BytesScanned": raw["BytesScanned"],
        "RegionsScanned": raw["RegionsScanned"],
        "TimedOut": raw["TimedOut"],
        "Snapshot": snapshot,
    }


def diff_value_snapshots(
    snap_a: dict[str, Any],
    snap_b: dict[str, Any],
    *,
    min_delta: float = 0.1,
    max_delta: float = 50.0,
    max_world_abs: float = 10000.0,
) -> dict[str, Any]:
    """Diff two value snapshots and rank candidates by likelihood of being player coordinates.

    Strategy (classic Cheat Engine technique):
    1. Intersection-only: only addresses present in BOTH snapshots
    2. Score each address: alignment + movement magnitude + world bounds
    3. Detect Vector3 triples: consecutive 4-byte addresses (X, Y, Z at N, N+4, N+8)
    4. Return top candidates ranked by score

    Returns a structured report with:
    - ``SingleCandidates``: individual float diffs ranked by score
    - ``Vector3Candidates``: consecutive triple groups with base addresses
    - ``Stats``: summary counts
    """
    snapshot_a: dict[str, float] = snap_a.get("Snapshot", {})
    snapshot_b: dict[str, float] = snap_b.get("Snapshot", {})

    # Intersection: only addresses present in both
    common = set(snapshot_a) & set(snapshot_b)

    # Score each address
    single_candidates: list[dict[str, Any]] = []
    scored_addresses: set[int] = set()
    for addr_str in sorted(common):
        addr = int(addr_str, 16)
        va = snapshot_a[addr_str]
        vb = snapshot_b[addr_str]
        delta = abs(vb - va)

        # NaN guard
        if isinstance(va, float) and va != va:
            continue
        if isinstance(vb, float) and vb != vb:
            continue

        # Zero-delta skip (didn't change)
        if delta < min_delta:
            continue

        score = 0
        reasons: list[str] = []

        # Alignment: struct floats are 4-byte aligned
        if addr % 4 == 0:
            score += 100
            reasons.append("aligned")

        # Movement magnitude: real player movement
        if min_delta <= delta <= max_delta:
            score += 50
            reasons.append("movement_range")

        # World bounds: valid coordinate range
        if abs(va) < max_world_abs and abs(vb) < max_world_abs:
            score += 50
            reasons.append("world_bounds")

        single_candidates.append(
            {
                "Address": addr_str,
                "AddressInt": addr,
                "ValueA": va,
                "ValueB": vb,
                "Delta": round(delta, 6),
                "Score": score,
                "Reasons": reasons,
            }
        )
        scored_addresses.add(addr)

    single_candidates.sort(key=lambda c: (-c["Score"], c["AddressInt"]))

    # Vector3 triple detection: consecutive N, N+4, N+8
    vector3_candidates: list[dict[str, Any]] = []
    seen_triples: set[int] = set()
    for addr in sorted(scored_addresses):
        if addr in seen_triples:
            continue
        n4 = addr + 4
        n8 = addr + 8
        n4_str = f"0x{n4:X}"
        n8_str = f"0x{n8:X}"
        if n4_str in snapshot_a and n8_str in snapshot_a and n4_str in snapshot_b and n8_str in snapshot_b:
            x = snapshot_b.get(f"0x{addr:X}", 0.0)
            y = snapshot_b.get(n4_str, 0.0)
            z = snapshot_b.get(n8_str, 0.0)
            xa = snapshot_a.get(f"0x{addr:X}", 0.0)
            ya = snapshot_a.get(n4_str, 0.0)
            za = snapshot_a.get(n8_str, 0.0)

            dx = abs(x - xa)
            dy = abs(y - ya)
            dz = abs(z - za)
            total_delta = dx + dy + dz

            if total_delta < min_delta:
                continue

            score = 500  # Vector3 bonus
            reasons: list[str] = ["vector3_triple"]
            if addr % 4 == 0:
                score += 100
                reasons.append("aligned")
            if min_delta <= total_delta <= max_delta * 3:
                score += 50
                reasons.append("movement_range")
            if abs(x) < max_world_abs and abs(y) < max_world_abs and abs(z) < max_world_abs:
                score += 50
                reasons.append("world_bounds")

            vector3_candidates.append(
                {
                    "BaseAddress": f"0x{addr:X}",
                    "BaseAddressInt": addr,
                    "ValuesA": [xa, ya, za],
                    "ValuesB": [x, y, z],
                    "Deltas": [round(dx, 6), round(dy, 6), round(dz, 6)],
                    "TotalDelta": round(total_delta, 6),
                    "Score": score,
                    "Reasons": reasons,
                }
            )
            seen_triples.update([addr, n4, n8])

    vector3_candidates.sort(key=lambda c: (-c["Score"], c["BaseAddressInt"]))

    return {
        "SchemaVersion": DIFF_SCHEMA,
        "Timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "SnapshotATimestamp": snap_a.get("Timestamp", ""),
        "SnapshotBTimestamp": snap_b.get("Timestamp", ""),
        "ValueType": snap_a.get("ValueType", ""),
        "Stats": {
            "SnapshotACount": len(snapshot_a),
            "SnapshotBCount": len(snapshot_b),
            "IntersectionCount": len(common),
            "ChangedCount": len(single_candidates),
            "Vector3CandidateCount": len(vector3_candidates),
        },
        "Vector3Candidates": vector3_candidates[:50],
        "SingleCandidates": single_candidates[:100],
    }


def build_diff_scan_plan(
    *,
    repo_root: Path,
    process_name: str,
    pid: int,
    value_type: str,
    min_val: float,
    max_val: float,
    execute_live_read: bool,
    experimental_live: bool,
    confirm_live_read: bool,
    max_scan_bytes: int,
    max_matches: int,
    max_regions: int,
    timeout_seconds: int,
    snapshot_a_path: str | None = None,
) -> dict[str, Any]:
    """Build a machine-readable snapshot-diff scan plan.

    If ``snapshot_a_path`` is provided, the plan describes a snapshot-B-only
    scan (diffing against the existing snapshot-A). Otherwise it describes a
    snapshot-A scan (the first pass).
    """
    output_dir = repo_root / "Exports" / "discovery-plan" / "stage5-live"
    _validate_value_type(value_type)
    max_scan_bytes = _positive_limit("max_scan_bytes", max_scan_bytes)
    max_matches = _positive_limit("max_matches", max_matches)
    max_regions = _positive_limit("max_regions", max_regions)
    timeout_seconds = _positive_limit("timeout_seconds", timeout_seconds)

    refusal_reasons: list[str] = []
    if process_name.lower() != DEFAULT_PROCESS_NAME:
        refusal_reasons.append("target-process-must-be-rift_x64.exe")
    if execute_live_read and not experimental_live:
        refusal_reasons.append("missing---experimental-live")
    if execute_live_read and not confirm_live_read:
        refusal_reasons.append("missing---confirm-live-read")
    if execute_live_read and pid <= 0:
        refusal_reasons.append("missing-explicit---pid")
    if not execute_live_read:
        refusal_reasons.append("dry-run-only-no-live-read-requested")
    if max_val <= min_val:
        refusal_reasons.append(f"max-val ({max_val}) must be greater than min-val ({min_val})")

    is_second_pass = snapshot_a_path is not None and Path(snapshot_a_path).exists()
    if is_second_pass and not snapshot_a_path:
        refusal_reasons.append("snapshot-a-path-required-for-second-pass")

    pass_label = "snapshot-b" if is_second_pass else "snapshot-a"
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snapshot_json = output_dir / f"value-snapshot-{pass_label}-{timestamp}.json"
    diff_json = output_dir / f"value-diff-{timestamp}.json" if is_second_pass else None
    diff_md = output_dir / f"value-diff-{timestamp}.md" if is_second_pass else None

    plan: dict[str, Any] = {
        "SchemaVersion": DIFF_SCHEMA,
        "TargetProcessName": process_name,
        "Pid": pid if pid > 0 else None,
        "ExecuteLiveRead": execute_live_read,
        "ExperimentalLive": experimental_live,
        "ConfirmLiveRead": confirm_live_read,
        "LiveProcessReadExecuted": False,
        "ExecutionAllowed": execute_live_read and not refusal_reasons,
        "RefusalReasons": refusal_reasons,
        "ValueType": value_type,
        "ValueTypeLabel": _VALUE_TYPES[value_type].label,
        "MinValue": min_val,
        "MaxValue": max_val,
        "Pass": pass_label,
        "SnapshotAPath": snapshot_a_path if is_second_pass else None,
        "OutputDirectory": _display_path(output_dir, repo_root),
        "SnapshotOutputJsonPath": _display_path(snapshot_json, repo_root),
        "Limits": {
            "MaxScanBytes": max_scan_bytes,
            "MaxMatches": max_matches,
            "MaxRegions": max_regions,
            "TimeoutSeconds": timeout_seconds,
            "ChunkBytes": SCAN_CHUNK_SIZE,
        },
        "Safety": {
            "ReadOnly": True,
            "NoWrites": True,
            "NoHooks": True,
            "NoDllInjection": True,
            "NoRemoteThreads": True,
            "NoFullDump": True,
            "OutputIgnoredGenerated": True,
            "RequiresSeparateLiveExecutionGate": True,
        },
    }

    if is_second_pass:
        plan["DiffOutputJsonPath"] = _display_path(diff_json, repo_root) if diff_json else None
        plan["DiffOutputMarkdownPath"] = _display_path(diff_md, repo_root) if diff_md else None
        plan["NextAction"] = (
            "Run only after reviewing the exact PID, snapshot-A path, output paths, and generated-output guard. "
            "After the scan completes, the diff report will be generated automatically."
            if execute_live_read
            else "Review this dry-run plan; actual live reads require --execute-live-read --experimental-live --confirm-live-read --pid."
        )
    else:
        plan["NextAction"] = (
            "After this snapshot-A scan completes, MOVE the player in-game and then run scan-live-diff "
            "again with --snapshot-a-path pointing to the snapshot-A JSON to take snapshot-B."
            if execute_live_read
            else "Review this dry-run plan for snapshot-A; run with --execute-live-read --experimental-live --confirm-live-read --pid to take the snapshot."
        )

    return plan


def run_live_diff(
    plan: dict[str, Any],
    snapshot_a_path: str | None = None,
) -> dict[str, Any]:
    """Execute a gated live snapshot-diff scan.

    If ``snapshot_a_path`` is provided (second pass), takes snapshot-B,
    diffs against snapshot-A, and returns the full diff report.
    Otherwise (first pass), takes snapshot-A only.
    """
    if not plan.get("ExecutionAllowed"):
        raise RuntimeError("live diff scan execution is not allowed by the plan")

    # Validate snapshot-a path existence BEFORE opening any process handle
    if snapshot_a_path:
        snap_a_path = Path(snapshot_a_path)
        if not snap_a_path.exists():
            raise FileNotFoundError(f"snapshot-A not found: {snapshot_a_path}")

    snap_a_loaded: dict[str, Any] | None = None
    if snapshot_a_path:
        snap_a_loaded = json.loads(snap_a_path.read_text(encoding="utf-8"))
        # Unwrap: the file was written by write_diff_reports which nests
        # {Snapshot: {SchemaVersion: ..., Snapshot: {addr: val}}}.
        # Extract the inner address->value mapping.
        raw = snap_a_loaded.get("Snapshot", snap_a_loaded)
        if isinstance(raw, dict) and "Snapshot" in raw:
            snap_a_loaded = raw["Snapshot"]
        else:
            snap_a_loaded = raw

    pid = plan.get("Pid")
    if not isinstance(pid, int) or pid <= 0:
        raise RuntimeError("live diff scan requires an explicit positive PID")
    limits = plan["Limits"]

    with WindowsReadOnlyProcessReader(pid) as reader:
        snapshot = scan_value_snapshot(
            reader,
            value_type=str(plan["ValueType"]),
            min_val=float(plan["MinValue"]),
            max_val=float(plan["MaxValue"]),
            max_scan_bytes=int(limits["MaxScanBytes"]),
            max_matches=int(limits["MaxMatches"]),
            max_regions=int(limits["MaxRegions"]),
            timeout_seconds=int(limits["TimeoutSeconds"]),
        )

    result = dict(plan)
    result["LiveProcessReadExecuted"] = True
    result["Snapshot"] = snapshot

    if snapshot_a_path and snap_a_loaded is not None:
        diff = diff_value_snapshots(snap_a_loaded, snapshot)
        result["Diff"] = diff

    return result


def write_diff_reports(
    result: dict[str, Any],
    repo_root: Path,
) -> tuple[Path, Path]:
    """Write snapshot-diff JSON and Markdown reports."""
    json_path = repo_root / str(result["SnapshotOutputJsonPath"])
    json_path.parent.mkdir(parents=True, exist_ok=True)

    # Write snapshot JSON (always)
    payload: dict[str, Any] = {
        "SchemaVersion": result["SchemaVersion"],
        "TargetProcessName": result["TargetProcessName"],
        "Pid": result["Pid"],
        "ValueType": result["ValueType"],
        "ValueTypeLabel": result.get("ValueTypeLabel", ""),
        "MinValue": result["MinValue"],
        "MaxValue": result["MaxValue"],
        "Pass": result["Pass"],
        "LiveProcessReadExecuted": result["LiveProcessReadExecuted"],
        "Limits": result["Limits"],
        "Snapshot": result.get("Snapshot", {}),
    }
    if result.get("Diff"):
        payload["Diff"] = result["Diff"]
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Build markdown
    snapshot = payload.get("Snapshot", {})
    diff = payload.get("Diff", {})
    lines = [
        "# Snapshot-Diff Value Scan Report",
        "",
        f"SchemaVersion: `{payload['SchemaVersion']}`",
        f"Target: `{payload['TargetProcessName']}` PID `{payload['Pid']}`",
        f"Value type: `{payload.get('ValueTypeLabel', payload.get('ValueType'))}`",
        f"Range: [{payload.get('MinValue')}, {payload.get('MaxValue')}]",
        f"Pass: `{payload['Pass']}`",
        f"Snapshot match count: {snapshot.get('MatchCount', 0)}",
        "",
    ]

    if diff:
        stats = diff.get("Stats", {})
        lines.extend(
            [
                "## Diff stats",
                "",
                f"Snapshot-A count: {stats.get('SnapshotACount', 0)}",
                f"Snapshot-B count: {stats.get('SnapshotBCount', 0)}",
                f"Intersection count: {stats.get('IntersectionCount', 0)}",
                f"Changed values: {stats.get('ChangedCount', 0)}",
                "",
            ]
        )

        vec3s = diff.get("Vector3Candidates", [])
        if vec3s:
            lines.extend(
                [
                    "## 🎯 Vector3 Candidates (X, Y, Z triples)",
                    "",
                    "| Base Address | Values (X, Y, Z) | Deltas | Score |",
                    "|---|---:|---:|---:|",
                ]
            )
            for v in vec3s[:20]:
                x, y, z = v["ValuesB"]
                dx, dy, dz = v["Deltas"]
                lines.append(
                    f"| {v['BaseAddress']} | [{x:.3f}, {y:.3f}, {z:.3f}] | "
                    f"[{dx:.3f}, {dy:.3f}, {dz:.3f}] | {v['Score']} |"
                )
            lines.append("")
        else:
            lines.extend(
                [
                    "*No Vector3 triples found.*",
                    "",
                ]
            )

        singles = diff.get("SingleCandidates", [])
        if singles:
            lines.extend(
                [
                    "## Single Float Candidates (top 20 by score)",
                    "",
                    "| Address | Value A | Value B | Delta | Score |",
                    "|---|---:|---:|---:|",
                ]
            )
            for s in singles[:20]:
                lines.append(
                    f"| {s['Address']} | {s['ValueA']:.3f} | {s['ValueB']:.3f} | {s['Delta']:.3f} | {s['Score']} |"
                )
            lines.append("")
    else:
        lines.extend(
            [
                "## Next step",
                "",
                "This is snapshot-A. To complete the diff:",
                "",
                "1. **MOVE** the player character in-game (walk/jump/teleport)",
                "2. Run `scan-live-diff` again with `--snapshot-a-path` pointing to this snapshot JSON",
                "3. The diff report will show Vector3 candidates with movement deltas",
                "",
            ]
        )

    markdown_path = json_path.with_suffix(".md")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path
