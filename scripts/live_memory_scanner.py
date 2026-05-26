"""Read-only live-memory scan planning and fixture-backed scanner core.

The live execution path is intentionally gated by the workflow command. Tests use
``FixtureProcessReader`` only; CI must never attach to a live process.
"""

from __future__ import annotations

import ctypes
import json
import re
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
