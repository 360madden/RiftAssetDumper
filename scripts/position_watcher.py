"""position_watcher.py — Persistent read-only position monitor for RIFT automated bots.

Periodically reads known player coordinate addresses from the RIFT process
and logs position changes with timestamps, speed, and movement state.

Reuses WindowsReadOnlyProcessReader from live_memory_scanner.py for the
low-overhead ReadProcessMemory calls (~0.1ms per poll for 12 bytes).

Usage:
    # Manual mode (PID + address required)
    python scripts/position_watcher.py --pid 51804 --address 0x1234ABCD
        [--poll-interval-ms 50] [--out-dir Exports/position-logs]

    # Auto mode: detect PID + load verified address from x64dbg_bridge output
    python scripts/position_watcher.py --auto
        [--poll-interval-ms 50] [--out-dir Exports/position-logs]
        [--verified-json Exports/x64dbg_trace_log.verified.json]

Output:
    Exports/position-logs/pos_log_<timestamp>.jsonl  — structured position log
    Exports/position-logs/pos_current.txt              — tail-able summary

Safety:
    Read-only. No writes to the target process. No hooks. No injection.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import struct
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import IO

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.live_memory_scanner import WindowsReadOnlyProcessReader  # noqa: E402

# ============================================================================
# Data structures
# ============================================================================


@dataclass
class Position:
    """A parsed 3D position from process memory."""

    x: float
    y: float
    z: float

    def distance_to(self, other: Position) -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return (dx * dx + dy * dy + dz * dz) ** 0.5

    def to_dict(self) -> dict[str, float]:
        return {"x": round(self.x, 4), "y": round(self.y, 4), "z": round(self.z, 4)}


class MovementState(Enum):
    UNKNOWN = "unknown"
    IDLE = "idle"
    WALKING = "walking"
    RUNNING = "running"
    TELEPORT = "teleport"


# Speed thresholds in units/second
IDLE_SPEED_THRESHOLD = 0.5
WALKING_SPEED_THRESHOLD = 7.0
TELEPORT_SPEED_THRESHOLD = 100.0


@dataclass
class WatcherState:
    """Mutable state tracked across poll cycles."""

    current_position: Position | None = None
    last_position: Position | None = None
    current_state: MovementState = MovementState.UNKNOWN
    last_state: MovementState = MovementState.UNKNOWN
    poll_count: int = 0
    read_failures: int = 0
    start_time: float = field(default_factory=time.monotonic)
    last_timestamp: float = field(default_factory=time.monotonic)


# ============================================================================
# Position watcher
# ============================================================================


class PositionWatcher:
    """Persistent read-only position monitor for a RIFT process."""

    def __init__(
        self,
        pid: int,
        base_address: int,
        poll_interval_ms: int = 50,
        log_dir: Path | None = None,
        max_retry_failures: int = 30,
    ) -> None:
        self.pid = pid
        self.base_address = base_address
        self.poll_interval = max(poll_interval_ms, 10) / 1000.0  # convert to seconds
        self.log_dir = log_dir or Path("Exports/position-logs")
        self.max_retry_failures = max_retry_failures
        self._state = WatcherState()
        self._log_path: Path | None = None
        self._current_path: Path | None = None
        self._log_fh: IO[str] | None = None

    def _ensure_log_dir(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _init_log_files(self) -> None:
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self._log_path = self.log_dir / f"pos_log_{ts}.jsonl"
        self._current_path = self.log_dir / "pos_current.txt"
        self._log_fh = open(self._log_path, "a", encoding="utf-8")

    def read_position(self, reader: WindowsReadOnlyProcessReader) -> Position | None:
        """Read 12 bytes at base_address and unpack as 3x float32 (X, Y, Z)."""
        try:
            data = reader.read(self.base_address, 12)
            if not data or len(data) < 12:
                return None
            x, y, z = struct.unpack("<fff", data[:12])
            return Position(x=x, y=y, z=z)
        except OSError, struct.error, ValueError:
            return None

    def classify_state(self, last_pos: Position, curr_pos: Position, dt: float) -> tuple[MovementState, float]:
        """Classify movement state from position delta and time.

        Returns (state, speed_units_per_second).
        """
        if dt <= 0.0:
            return MovementState.UNKNOWN, 0.0

        distance = curr_pos.distance_to(last_pos)
        speed = distance / dt

        if speed > TELEPORT_SPEED_THRESHOLD:
            return MovementState.TELEPORT, speed
        if speed >= WALKING_SPEED_THRESHOLD:
            return MovementState.RUNNING, speed
        if speed >= IDLE_SPEED_THRESHOLD:
            return MovementState.WALKING, speed
        return MovementState.IDLE, speed

    def _write_log_entry(
        self,
        pos: Position,
        state: MovementState,
        speed: float,
        dt: float,
        distance: float | None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "state": state.value,
            "speed_ups": round(speed, 3),
            **pos.to_dict(),
        }
        if distance is not None:
            entry["distance"] = round(distance, 4)
            entry["dt_s"] = round(dt, 3)
        entry["poll"] = self._state.poll_count
        entry["failures"] = self._state.read_failures

        if self._log_fh:
            self._log_fh.write(json.dumps(entry) + "\n")
            self._log_fh.flush()

    def _write_summary(self, pos: Position, state: MovementState, speed: float) -> None:
        if not self._current_path:
            return
        elapsed = time.monotonic() - self._state.start_time
        line = (
            f"[{elapsed:7.1f}s] poll={self._state.poll_count:6d} "
            f"state={state.value:8s} speed={speed:7.2f}u/s "
            f"pos=({pos.x:9.2f}, {pos.y:9.2f}, {pos.z:9.2f}) "
            f"err={self._state.read_failures}\n"
        )
        self._current_path.write_text(line, encoding="utf-8")

    def _on_state_change(self, new_state: MovementState, pos: Position) -> None:
        elapsed = time.monotonic() - self._state.start_time
        print(
            f"  [{elapsed:7.1f}s] STATE: {self._state.last_state.value} "
            f"→ {new_state.value} at ({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f})"
        )

    def run(self) -> None:
        """Run the persistent position monitoring loop.

        Blocks until interrupted. Handles process start/stop gracefully.
        """
        self._ensure_log_dir()
        self._init_log_files()

        print(f"PositionWatcher: PID={self.pid} addr=0x{self.base_address:X}")
        print(f"  Poll interval: {self.poll_interval * 1000:.0f} ms")
        print(f"  Log: {self._log_path}")
        print(f"  Summary: {self._current_path}")
        print("  Press Ctrl+C to stop.\n")

        self._state.start_time = time.monotonic()
        reader: WindowsReadOnlyProcessReader | None = None

        try:
            while True:
                cycle_start = time.monotonic()
                self._state.poll_count += 1

                # Attach/reconnect if needed
                if reader is None:
                    try:
                        reader = WindowsReadOnlyProcessReader(self.pid)
                        if self._state.read_failures == 0:
                            print(f"  Attached to PID {self.pid}")
                        else:
                            print(f"  Re-attached to PID {self.pid}")
                    except OSError:
                        self._state.read_failures += 1
                        if self._state.read_failures >= self.max_retry_failures:
                            print(
                                f"  Cannot attach to PID {self.pid} after {self.max_retry_failures} retries — exiting."
                            )
                            break
                        if self._state.read_failures <= 3 or self._state.read_failures % 10 == 0:
                            print(
                                f"  Cannot attach to PID {self.pid} (attempt {self._state.read_failures}/{self.max_retry_failures}) — waiting..."
                            )
                        time.sleep(1.0)
                        continue

                # Read position
                pos = self.read_position(reader)
                if pos is None:
                    self._state.read_failures += 1
                    if self._state.read_failures <= 3 or self._state.read_failures % 100 == 0:
                        print(f"  Read failure #{self._state.read_failures} — process may have exited")
                    # Try to reconnect
                    try:
                        reader.close()
                    except Exception:
                        pass
                    reader = None
                    time.sleep(0.5)
                    continue

                self._state.read_failures = 0
                now = time.monotonic()
                dt = now - self._state.last_timestamp if self._state.last_position else 0.0
                self._state.current_position = pos

                if self._state.last_position is not None and dt > 0.0:
                    new_state, speed = self.classify_state(self._state.last_position, pos, dt)
                    distance = pos.distance_to(self._state.last_position)
                    self._state.last_state = self._state.current_state
                    self._state.current_state = new_state

                    # Log on position change or state change
                    if new_state != self._state.last_state:
                        self._on_state_change(new_state, pos)

                    self._write_log_entry(pos, new_state, speed, dt, distance)
                else:
                    speed = 0.0
                    # First poll or no previous position
                    self._write_log_entry(pos, MovementState.UNKNOWN, 0.0, 0.0, None)

                self._write_summary(pos, self._state.current_state, speed)
                self._state.last_position = pos
                self._state.last_timestamp = now

                # Sleep to maintain poll interval
                elapsed = time.monotonic() - cycle_start
                remaining = self.poll_interval - elapsed
                if remaining > 0:
                    time.sleep(remaining)

        except KeyboardInterrupt:
            print("\nPositionWatcher stopped.")
        finally:
            if reader:
                try:
                    reader.close()
                except Exception:
                    pass
            if self._log_fh:
                try:
                    self._log_fh.close()
                except Exception:
                    pass


# ============================================================================
# PID auto-detection
# ============================================================================

# Windows process enumeration constants
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    """Windows PROCESSENTRY32W structure for process enumeration."""

    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def find_rift_pid() -> int | None:
    """Find the PID of the rift_x64.exe process.

    Uses ``CreateToolhelp32Snapshot`` + ``Process32FirstW``/``Process32NextW``
    to enumerate running processes without external dependencies.

    Returns:
        PID of the single rift_x64.exe process, or ``None`` if not found.

    Raises:
        RuntimeError: if multiple rift_x64.exe processes are found (ambiguous).
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")

    pids: list[int] = []
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)

        if not kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
            return None

        while True:
            # WCHAR arrays are auto-converted to str by ctypes on access
            exe_name = str(pe.szExeFile).rstrip("\x00")
            if exe_name.lower() == "rift_x64.exe":
                pids.append(pe.th32ProcessID)

            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                break
    finally:
        kernel32.CloseHandle(snapshot)

    if len(pids) > 1:
        pid_list = ", ".join(str(p) for p in pids)
        raise RuntimeError(f"Multiple rift_x64.exe processes found (PIDs: {pid_list}). Use --pid to specify which one.")
    return pids[0] if pids else None


# ============================================================================
# Verified address auto-loading
# ============================================================================


def find_latest_verified_json(search_dir: Path | None = None) -> Path | None:
    """Find the most recently modified ``*.verified.json`` file.

    Searches ``Exports/`` recursively by default. Returns the path
    of the newest matching file, or ``None`` if none found.
    """
    if search_dir is None:
        search_dir = _project_root / "Exports"
    if not search_dir.exists():
        return None
    candidates = sorted(
        search_dir.rglob("*.verified.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def load_best_verified_address(
    verified_path: Path,
) -> tuple[int, dict[str, object]]:
    """Load the best coordinate candidate from a verified.json file.

    Picks the candidate with the highest magnitude
    (``abs(x) + abs(y) + abs(z)``) to avoid degenerate/uninitialized
    coordinates.

    Returns:
        ``(absolute_address_int, candidate_dict)``.

    Raises:
        ValueError: if the file is empty or no valid candidates found.
    """
    data = json.loads(verified_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError(f"{verified_path}: expected non-empty list of verified candidates")

    best: dict[str, object] | None = None
    best_mag = -1.0
    for entry in data:
        if not isinstance(entry, dict):
            continue
        x = float(entry.get("x_verified", 0) or 0)
        y = float(entry.get("y_verified", 0) or 0)
        z = float(entry.get("z_verified", 0) or 0)
        mag = abs(x) + abs(y) + abs(z)
        if mag > best_mag:
            best_mag = mag
            best = entry

    if best is None or best_mag <= 0.0:
        raise ValueError(f"{verified_path}: no candidates with non-zero coordinates")

    addr_str = str(best.get("absolute_address", ""))
    addr = int(addr_str, 16) if addr_str else 0
    if addr == 0:
        raise ValueError(f"{verified_path}: candidate has invalid absolute_address")

    return addr, best


# ============================================================================
# CLI
# ============================================================================


def _parse_hex_address(addr_str: str) -> int:
    """Parse a hex address like 0x1234ABCD or 1234ABCD."""
    return int(addr_str, 16)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Persistent read-only RIFT position monitor",
        epilog=(
            "Examples:\n"
            "  python scripts/position_watcher.py --pid 51804 --address 0x1A2B3C4D\n"
            "  python scripts/position_watcher.py --auto\n"
            "  python scripts/position_watcher.py --auto --verified-json Exports/foo.verified.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-detect RIFT PID and load verified coordinate address from x64dbg_bridge output",
    )
    parser.add_argument(
        "--pid",
        type=int,
        default=0,
        help="Target RIFT process PID (required unless --auto)",
    )
    parser.add_argument(
        "--address",
        default="",
        help="Hex address of the X coordinate, e.g. 0x1234ABCD (required unless --auto)",
    )
    parser.add_argument(
        "--verified-json",
        default="",
        help="Path to verified.json from x64dbg_bridge (auto-mode default: latest in Exports/)",
    )
    parser.add_argument(
        "--poll-interval-ms",
        type=int,
        default=50,
        help="Polling interval in milliseconds (default: 50, min: 10)",
    )
    parser.add_argument(
        "--out-dir",
        default="Exports/position-logs",
        help="Directory for position log output (default: Exports/position-logs)",
    )
    args = parser.parse_args(argv)

    # --- Resolve PID and address ---
    pid: int = args.pid
    address: int = 0

    if args.auto:
        # Auto-detect PID
        if pid <= 0:
            pid = find_rift_pid() or 0
            if pid <= 0:
                print("ERROR: rift_x64.exe is not running.", file=sys.stderr)
                print("  Start RIFT and try again, or use --pid to specify a PID manually.", file=sys.stderr)
                sys.exit(1)
            print(f"Auto-detected RIFT PID: {pid}")

        # Auto-load verified address
        verified_path: Path | None = None
        if args.verified_json:
            verified_path = Path(args.verified_json)
            if not verified_path.is_absolute():
                verified_path = _project_root / verified_path
        else:
            verified_path = find_latest_verified_json()

        if verified_path is None or not verified_path.exists():
            print("ERROR: No verified.json found from x64dbg_bridge.", file=sys.stderr)
            print("  Run x64dbg_bridge first:", file=sys.stderr)
            print("    1. python scripts/x64dbg_bridge.py generate", file=sys.stderr)
            print("    2. Launch x64dbg, attach, load script, save log", file=sys.stderr)
            print("    3. python scripts/x64dbg_bridge.py parse --log <log.txt>", file=sys.stderr)
            print(
                "    4. python scripts/x64dbg_bridge.py verify --pid <PID> --analysis <log.analysis.json>",
                file=sys.stderr,
            )
            print("  Or use --verified-json to specify the path manually.", file=sys.stderr)
            sys.exit(1)

        print(f"Loading verified address from: {verified_path}")
        try:
            address, best_candidate = load_best_verified_address(verified_path)
            cluster = best_candidate.get("cluster", "?")
            x_v = best_candidate.get("x_verified", 0)
            y_v = best_candidate.get("y_verified", 0)
            z_v = best_candidate.get("z_verified", 0)
            print(f"  Cluster: {cluster}")
            print(f"  Address: 0x{address:X}")
            print(f"  Verified coords: ({x_v}, {y_v}, {z_v})")
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        # Manual mode: PID and address are required
        if pid <= 0:
            print("ERROR: --pid is required (or use --auto).", file=sys.stderr)
            sys.exit(1)
        if not args.address:
            print("ERROR: --address is required (or use --auto).", file=sys.stderr)
            sys.exit(1)
        address = _parse_hex_address(args.address)

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = _project_root / out_dir

    watcher = PositionWatcher(
        pid=pid,
        base_address=address,
        poll_interval_ms=args.poll_interval_ms,
        log_dir=out_dir,
    )
    watcher.run()


if __name__ == "__main__":
    main()
