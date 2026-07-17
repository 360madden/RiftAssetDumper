#!/usr/bin/env python3
"""navmesh_observer.py — NM-7 read-only observer agent.

A read-only bot that watches the player's live game position and reports
path waypoints toward a goal.  No movement injection, no game writes, no
input simulation — stays within the ``live-memory-readonly-safety-boundary``.

Architecture
------------
The observer wraps three existing modules:

  * ``navmesh_state.NavmeshState`` — polls live position, projects onto navmesh.
  * ``navmesh_pathfind.find_path`` — Detour A* pathfinding on the navmesh.
  * ``navmesh_coord_transform`` — converts between OBJ ↔ memory coordinates.

On each ``update()`` tick the observer:

  1. Polls the player's live position (via ``RIFTMemoryScanner``).
  2. Projects the position onto the current zone's Detour navmesh.
  3. Checks progress along the planned path (waypoint arrival, off-path detection).
  4. Replans automatically when the player deviates too far.
  5. Reports a human-readable status line.

Modes
-----
  ``--once``   One-shot path computation: print waypoints and exit.
  ``--watch``  Continuous monitoring: poll position, report progress every N seconds.

Prerequisites
-------------
  - Game must be running (``rift_x64.exe``).
  - Run as Administrator for ``ReadProcessMemory``.
  - ``recast-1.5.7.jar`` + ``detour-1.5.7.jar`` in ``Exports/navmesh-phase1/lib/``.
  - A zone walkable OBJ from the NM-1 pipeline.

Safety
------
  * Read-only by construction — no ``WriteProcessMemory``, no input simulation.
  * Position reads are the same ``PROCESS_VM_READ`` path already proven safe.
  * All output goes to stdout / JSON; nothing is written to the game process.

Usage
-----
  # One-shot: compute and print the path once
  python scripts/navmesh_observer.py --zone-obj <path-to-zone-walkable.obj> --goal 1234,56,789 --once

  # Watch mode: poll every second, report progress
  python scripts/navmesh_observer.py --zone-obj <path-to-zone-walkable.obj> --goal 1234,56,789 --watch

  # With a specific coordinate transform
  python scripts/navmesh_observer.py --zone-obj <path> --goal 1234,56,789 --transform <path-to-coord-transform.json> --watch --interval 0.5
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

# ---------------------------------------------------------------------------
# Path boilerplate
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.build_navmesh import DETOUR_JAR, RECAST_JAR, _start_jvm  # noqa: E402
from scripts.navmesh_coord_transform import (  # noqa: E402
    DEFAULT_TRANSFORM_PATH,
    load_transform,
    memory_to_obj,
    obj_to_memory,
)
from scripts.navmesh_pathfind import (  # noqa: E402
    _build_recast_and_detour,
    compute_path_distance,
    find_path,
    parse_coords,
)
from scripts.navmesh_phase0_feasibility import parse_obj  # noqa: E402
from scripts.navmesh_state import (  # noqa: E402
    NavmeshState,
    NavmeshStatus,
    StaticPositionSource,
)

if TYPE_CHECKING:
    from scripts.navmesh_state import NavmeshQueryProvider, PositionSource

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARRIVAL_THRESHOLD = 2.0  # world units — "close enough to the waypoint"
DEVIATION_THRESHOLD = 50.0  # world units — player is off-path
DEVIATION_BEFORE_REPLAN = 3  # consecutive off-path ticks before auto-replan
DEFAULT_POLL_INTERVAL = 1.0  # seconds
DEFAULT_SEARCH_EXTENTS = 50.0  # half-extent for findNearestPoly

REPO_ROOT = _PROJECT_ROOT
DEFAULT_OUT_DIR = REPO_ROOT / "Exports" / "navmesh-phase7"


# ============================================================================
# DetourNavmeshQueryProvider — production implementation of the Protocol
# ============================================================================


class DetourNavmeshQueryProvider:
    """Production ``NavmeshQueryProvider`` wrapping a live Detour NavMeshQuery.

    Wraps the JVM-dependent navmesh + query objects produced by
    ``navmesh_pathfind._build_recast_and_detour()``.  Implements both
    ``find_nearest_poly`` (for live-position projection) and ``find_path``
    (for A* pathfinding).

    This is the first concrete implementation of the Protocol defined in
    ``navmesh_state.NavmeshQueryProvider`` — prior consumers used mocks.
    """

    def __init__(self, navmesh_result: dict[str, Any]) -> None:
        """Wrap a navmesh build result.

        Args:
            navmesh_result: Dict from ``_build_recast_and_detour()`` with
                keys ``query`` (Java NavMeshQuery), ``filter`` (Java
                DefaultQueryFilter), and ``navmesh`` (Java NavMesh).
        """
        self._query: Any = navmesh_result["query"]
        self._filter: Any = navmesh_result["filter"]
        self._navmesh: Any = navmesh_result["navmesh"]

    # -- NavmeshQueryProvider interface ------------------------------------

    def find_nearest_poly(
        self,
        x: float,
        y: float,
        z: float,
        *,
        search_extents: tuple[float, float, float] = (
            DEFAULT_SEARCH_EXTENTS,
            DEFAULT_SEARCH_EXTENTS,
            DEFAULT_SEARCH_EXTENTS,
        ),
    ) -> tuple[int, tuple[float, float, float]]:
        """Snap (x, y, z) in OBJ coords to the nearest walkable polygon.

        Returns (poly_ref, snapped_pos).  poly_ref=0 means off-navmesh.
        """
        import jpype  # noqa: F811

        pos_arr = jpype.JFloat[3]
        pos_arr[0], pos_arr[1], pos_arr[2] = x, y, z
        ext_arr = jpype.JFloat[3]
        ext_arr[0], ext_arr[1], ext_arr[2] = search_extents

        result = self._query.findNearestPoly(pos_arr, ext_arr, self._filter)
        if result.failed() or result.result is None:
            return (0, (x, y, z))

        r = result.result
        return (
            int(r.getNearestRef()),
            (float(r.getNearestPos()[0]), float(r.getNearestPos()[1]), float(r.getNearestPos()[2])),
        )

    def find_path(
        self,
        start: tuple[float, float, float],
        goal: tuple[float, float, float],
        *,
        smooth: bool = True,
        search_extents: tuple[float, float, float] = (
            DEFAULT_SEARCH_EXTENTS,
            DEFAULT_SEARCH_EXTENTS,
            DEFAULT_SEARCH_EXTENTS,
        ),
    ) -> dict[str, Any]:
        """Run Detour A* from ``start`` to ``goal`` in OBJ coordinates.

        Returns the same dict shape as ``navmesh_pathfind.find_path()``.
        """
        return find_path(
            self._query,
            self._filter,
            start,
            goal,
            smooth=smooth,
            search_extents=search_extents,
        )


# ============================================================================
# NavmeshObserver — read-only path watcher
# ============================================================================


@dataclass
class ObserverState:
    """Snapshot produced by ``NavmeshObserver.update()``.

    All position fields are in **OBJ / world** coordinates unless
    suffixed ``_mem`` (live-memory coordinates).  ``arrived`` is True
    when the player has reached the final waypoint.  ``off_path`` is
    True when the player's projected position is farther than
    ``DEVIATION_THRESHOLD`` from the expected path segment.
    """

    # Navmesh status
    on_navmesh: bool
    poly_ref: int
    current_pos_obj: tuple[float, float, float]
    current_pos_mem: tuple[float, float, float]

    # Path state
    has_path: bool
    path_error: str | None
    waypoints_total: int
    waypoint_index: int  # 0-based; waypoints_total when arrived
    next_waypoint_obj: tuple[float, float, float] | None
    next_waypoint_mem: tuple[float, float, float] | None
    next_waypoint_distance: float  # world units
    total_remaining_distance: float  # world units
    total_path_distance: float

    # Deviation
    off_path: bool
    deviation_count: int
    replan_triggered: bool

    # Meta
    arrived: bool
    update_count: int


class NavmeshObserver:
    """Read-only path watcher — reports waypoints, never injects movement.

    Lifecycle::

        observer = NavmeshObserver(query_provider, position_source, coord_transform)
        observer.update()                         # prime the position
        result = observer.set_goal_memory(goal)   # compute path
        if not result["success"]:
            ...  # no path

        while True:
            state = observer.update()
            print(observer.format_progress(state))
            if state.arrived:
                break
            time.sleep(1.0)

    The observer tracks which waypoint the player should head toward,
    detects when they've arrived at each waypoint, flags off-path
    deviation, and automatically replans when deviation persists.

    Safety: read-only by construction.  ``set_goal_memory`` / ``set_goal_obj``
    compute a path; ``update`` polls position and checks progress.  No
    game writes, no input injection, no DLL injection.
    """

    def __init__(
        self,
        query_provider: NavmeshQueryProvider,
        position_source: PositionSource,
        coord_transform: dict[str, Any],
        *,
        teleport_threshold: float = 5000.0,
        arrival_threshold: float = ARRIVAL_THRESHOLD,
        deviation_threshold: float = DEVIATION_THRESHOLD,
        deviation_before_replan: int = DEVIATION_BEFORE_REPLAN,
    ) -> None:
        self._state = NavmeshState(
            position_source=position_source,
            query_provider=query_provider,
            coord_transform=coord_transform,
            teleport_threshold=teleport_threshold,
        )
        self._transform = coord_transform
        self._arrival_threshold = arrival_threshold
        self._deviation_threshold = deviation_threshold
        self._deviation_before_replan = deviation_before_replan

        # Path state
        self._path: dict[str, Any] | None = None
        self._goal_obj: tuple[float, float, float] | None = None
        self._wp_index: int = 0
        self._deviation_count: int = 0
        self._replan_count: int = 0
        self._replan_triggered_flag: bool = False

    # -- Public API --------------------------------------------------------

    def set_goal_obj(self, goal: tuple[float, float, float]) -> dict[str, Any]:
        """Compute a path from the current position to *goal* in OBJ coordinates.

        Must be called after at least one ``update()`` to prime the position.
        """
        self._goal_obj = goal
        self._path = self._state.find_path(goal)
        self._wp_index = 0
        self._deviation_count = 0
        self._replan_count = 0
        return self._path

    def set_goal_memory(self, goal_mem: tuple[float, float, float]) -> dict[str, Any]:
        """Compute a path from the current position to *goal* in memory coordinates.

        The goal is converted to OBJ coordinates via the coordinate transform.
        """
        goal_obj = memory_to_obj(goal_mem[0], goal_mem[1], goal_mem[2], self._transform)
        return self.set_goal_obj(goal_obj)

    def update(self) -> ObserverState:
        """Poll the position source, project onto navmesh, check path progress.

        Returns an ``ObserverState`` snapshot.  Safe to call at any rate;
        the underlying ``NavmeshState.update()`` is idempotent.
        """
        status: NavmeshStatus = self._state.update()
        if self._path is not None and self._path.get("success", False):
            self._check_progress(status)
        return self._build_state(status)

    def format_progress(self, state: ObserverState) -> str:
        """Return a single-line human-readable progress string.

        Example::

            WP 3/12 | next: (1234.5, 56.7, 890.1) dist 45.2m | remaining: 234.1m
            WP 5/12 | next: (1300.0, 58.2, 920.0) dist 12.3m | ⚠ off-path (1)
            ✓ Arrived at goal
        """
        if state.arrived:
            return "✓ Arrived at goal"

        if not state.has_path:
            return f"✗ No path — {state.path_error or 'unknown error'}"

        if not state.on_navmesh:
            return "? Player off-navmesh"

        parts: list[str] = []

        # Waypoint progress
        wp_str = f"WP {min(state.waypoint_index + 1, state.waypoints_total)}/{state.waypoints_total}"
        parts.append(wp_str)

        # Next waypoint
        if state.next_waypoint_mem:
            nx, ny, nz = state.next_waypoint_mem
            parts.append(f"| next: ({nx:.1f}, {ny:.1f}, {nz:.1f}) dist {state.next_waypoint_distance:.1f}m")

        # Remaining
        parts.append(f"| remaining: {state.total_remaining_distance:.1f}m")

        # Deviation
        if state.off_path:
            parts.append(f"| ⚠ off-path ({state.deviation_count})")
        if state.replan_triggered:
            parts.append("| ↻ replanned")

        return " ".join(parts)

    # -- Internal ----------------------------------------------------------

    def _build_state(self, status: NavmeshStatus) -> ObserverState:
        """Build an ObserverState from the latest NavmeshStatus + path state."""
        on_navmesh = status.on_navmesh
        has_path = self._path is not None and self._path.get("success", False)
        path_error: str | None = None if has_path else (self._path.get("error") if self._path else "No path set")

        waypoints: list[dict[str, Any]] = self._path.get("waypoints", []) if has_path else []
        waypoints_total = len(waypoints)

        next_wp_obj: tuple[float, float, float] | None = None
        next_wp_mem: tuple[float, float, float] | None = None
        next_wp_dist = 0.0
        total_remaining = 0.0
        total_path_dist = compute_path_distance(waypoints) if waypoints else 0.0

        player_obj = status.snapped_obj_pos

        if waypoints and self._wp_index < waypoints_total:
            next_wp_obj = tuple(waypoints[self._wp_index]["pos"])
            next_wp_mem = obj_to_memory(next_wp_obj[0], next_wp_obj[1], next_wp_obj[2], self._transform)
            next_wp_dist = _euclidean(player_obj, next_wp_obj)
            # Remaining distance from player through remaining waypoints
            from_player = [{"pos": list(player_obj)}] + [{"pos": w["pos"]} for w in waypoints[self._wp_index + 1 :]]
            total_remaining = compute_path_distance(from_player) if len(from_player) >= 2 else next_wp_dist

        arrived = bool(has_path and self._wp_index >= waypoints_total and waypoints_total > 0)
        off_path = self._deviation_count > 0
        replan_triggered = self._replan_triggered_flag
        self._replan_triggered_flag = False

        return ObserverState(
            on_navmesh=on_navmesh,
            poly_ref=status.poly_ref,
            current_pos_obj=player_obj,
            current_pos_mem=obj_to_memory(player_obj[0], player_obj[1], player_obj[2], self._transform),
            has_path=has_path,
            path_error=path_error,
            waypoints_total=waypoints_total,
            waypoint_index=min(self._wp_index, waypoints_total),
            next_waypoint_obj=next_wp_obj,
            next_waypoint_mem=next_wp_mem,
            next_waypoint_distance=round(next_wp_dist, 1),
            total_remaining_distance=round(total_remaining, 1),
            total_path_distance=round(total_path_dist, 1),
            off_path=off_path,
            deviation_count=self._deviation_count,
            replan_triggered=replan_triggered,
            arrived=arrived,
            update_count=status.update_count,
        )

    def _check_progress(self, status: NavmeshStatus) -> None:
        """Check waypoint arrival and path deviation after a position update.

        Side-effects: advances ``_wp_index`` on arrival, increments
        ``_deviation_count`` on off-path, triggers replan when deviation
        persists.

        Called from ``update()`` after the ``NavmeshState`` tick.
        """
        waypoints: list[dict[str, Any]] = self._path.get("waypoints", []) if self._path else []
        if not waypoints or self._wp_index >= len(waypoints):
            return

        target = tuple(waypoints[self._wp_index]["pos"])
        player = status.snapped_obj_pos
        dist = _euclidean(player, target)

        if dist < self._arrival_threshold:
            self._wp_index += 1
            self._deviation_count = 0  # reset on progress
            return

        # Check deviation from the current path segment
        if self._is_off_segment(player, waypoints):
            self._deviation_count += 1
            if self._deviation_count >= self._deviation_before_replan and self._goal_obj:
                self._replan()
        else:
            # Player is on-path but hasn't reached the waypoint yet
            self._deviation_count = max(0, self._deviation_count - 1)

    def _is_off_segment(
        self,
        player: tuple[float, float, float],
        waypoints: list[dict[str, Any]],
    ) -> bool:
        """Check if *player* is too far from the current path segment.

        The segment runs from the last passed waypoint (or current position
        on first segment) to the current target waypoint.  Returns True if
        the perpendicular distance exceeds ``_deviation_threshold``.
        """
        if self._wp_index >= len(waypoints):
            return False

        seg_start: tuple[float, float, float]
        if self._wp_index > 0:
            seg_start = tuple(waypoints[self._wp_index - 1]["pos"])
        elif self._state.last_obj_pos:
            seg_start = self._state.last_obj_pos
        else:
            seg_start = player  # first update, accept

        seg_end = tuple(waypoints[self._wp_index]["pos"])
        perp_dist = _point_to_segment_distance(player, seg_start, seg_end)
        return perp_dist > self._deviation_threshold

    def _replan(self) -> None:
        """Replan the path from current position to the original goal.

        Resets waypoint index and deviation counter on success.  Called
        automatically when deviation persists beyond
        ``_deviation_before_replan`` ticks.
        """
        if not self._goal_obj:
            return
        new_path = self._state.find_path(self._goal_obj)
        if new_path.get("success"):
            self._path = new_path
            self._wp_index = 0
            self._deviation_count = 0
            self._replan_count += 1
            self._replan_triggered_flag = True


# ============================================================================
# Live-memory position source factory
# ============================================================================


def _make_live_position_source(
    process_name: str = "rift_x64.exe",
    time_func: Any = None,
) -> PositionSource | None:
    """Create a ``LiveMemoryPositionSource`` if the game is running.

    Returns None if the process can't be found or opened (with a message
    to stderr).  The caller should fall back to a static or interactive
    source.
    """
    if time_func is None:
        time_func = time.monotonic

    try:
        from scripts.navmesh_state import LiveMemoryPositionSource
        from scripts.rift_memory_scanner import RIFTMemoryScanner

        scanner = RIFTMemoryScanner()
        if not scanner.find_process(process_name):
            print(f"ERROR: {process_name} not found. Is the game running?", file=sys.stderr)
            return None
        if not scanner.open_process():
            print("ERROR: Could not open process. Run as Administrator.", file=sys.stderr)
            return None
        if not scanner.find_module():
            print("ERROR: Could not find module base.", file=sys.stderr)
            return None

        print(f"Attached to {process_name} (PID {scanner.process_id})", file=sys.stderr)
        return LiveMemoryPositionSource(scanner, time_func=time_func)
    except Exception as exc:
        print(f"ERROR: Failed to create live position source: {exc}", file=sys.stderr)  # noqa: F541
        return None


# ============================================================================
# Pure-Python helpers
# ============================================================================


def _euclidean(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """Euclidean distance between two 3D points."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _point_to_segment_distance(
    p: tuple[float, float, float],
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> float:
    """Perpendicular distance from point *p* to segment *ab*."""
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ap = (p[0] - a[0], p[1] - a[1], p[2] - a[2])
    ab_len_sq = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2

    if ab_len_sq < 1e-9:
        return _euclidean(p, a)

    t = max(0.0, min(1.0, (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / ab_len_sq))
    closest = (a[0] + t * ab[0], a[1] + t * ab[1], a[2] + t * ab[2])
    return _euclidean(p, closest)


# ============================================================================
# CLI
# ============================================================================


def _export_path_json(
    path: dict[str, Any],
    goal: tuple[float, float, float],
    out_path: Path,
    transform: dict[str, Any],
) -> None:
    """Write the path result to a JSON file for external consumption."""
    waypoints = path.get("waypoints", [])
    export: dict[str, Any] = {
        "goal_obj": list(goal),
        "goal_mem": list(obj_to_memory(goal[0], goal[1], goal[2], transform)),
        "success": path.get("success", False),
        "error": path.get("error"),
        "waypoints_obj": [w["pos"] for w in waypoints],
        "waypoints_mem": [list(obj_to_memory(w["pos"][0], w["pos"][1], w["pos"][2], transform)) for w in waypoints],
        "waypoint_count": len(waypoints),
        "total_distance": compute_path_distance(waypoints),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(export, indent=2, default=str) + "\n", encoding="utf-8")


def _print_waypoints(path: dict[str, Any], transform: dict[str, Any]) -> None:
    """Print waypoints in both OBJ and memory coordinates."""
    waypoints = path.get("waypoints", [])
    if not waypoints:
        print("No waypoints.")
        return

    print(f"\nPath: {len(waypoints)} waypoints, {compute_path_distance(waypoints):.1f} world units\n")
    print(f"{'#':>3}  {'OBJ (world)':>35}  {'Memory (live)':>35}")
    print("-" * 78)
    for i, wp in enumerate(waypoints):
        pos = wp["pos"]
        mem = obj_to_memory(pos[0], pos[1], pos[2], transform)
        flags = wp.get("flags", 0)
        flag_str = ""
        if flags == 1:
            flag_str = " [start]"
        elif flags == 2:
            flag_str = " [goal]"
        elif flags == 4:
            flag_str = " [off-mesh]"
        print(
            f"{i:3d}  ({pos[0]:10.2f}, {pos[1]:8.2f}, {pos[2]:10.2f})  "
            f"({mem[0]:10.2f}, {mem[1]:8.2f}, {mem[2]:10.2f}){flag_str}"
        )


def _watch_loop(
    observer: NavmeshObserver,
    interval: float,
    max_ticks: int | None = None,
) -> int:
    """Continuous monitoring loop.  Prints progress every *interval* seconds.

    Press Ctrl+C to stop.  Returns 0 on arrival, 1 on interruption.
    """
    tick = 0
    print("\nWatching... (Ctrl+C to stop)\n", file=sys.stderr)

    try:
        while max_ticks is None or tick < max_ticks:
            state = observer.update()
            print(observer.format_progress(state))

            if state.arrived:
                print("\n✓ Goal reached!", file=sys.stderr)
                return 0

            if state.replan_triggered:
                print(f"  ↻ Replanned path (replan #{observer._replan_count})", file=sys.stderr)

            tick += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="NM-7 read-only observer agent — watches player position, reports path waypoints",
    )
    parser.add_argument(
        "--zone-obj",
        required=True,
        help="Path to zone walkable OBJ (from NM-1 pipeline)",
    )
    parser.add_argument(
        "--goal",
        required=True,
        help="Goal position in memory coordinates: x,y,z",
    )
    parser.add_argument(
        "--transform",
        default=str(DEFAULT_TRANSFORM_PATH),
        help=f"Path to coord-transform.json (default: {DEFAULT_TRANSFORM_PATH})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="One-shot: compute path, print waypoints, exit (no live game needed)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuous monitoring: poll live position, report progress",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Poll interval in seconds for --watch (default: {DEFAULT_POLL_INTERVAL})",
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=None,
        help="Maximum watch ticks before exiting (default: unlimited)",
    )
    parser.add_argument(
        "--arrival-threshold",
        type=float,
        default=ARRIVAL_THRESHOLD,
        help=f"Distance threshold for waypoint arrival (default: {ARRIVAL_THRESHOLD})",
    )
    parser.add_argument(
        "--deviation-threshold",
        type=float,
        default=DEVIATION_THRESHOLD,
        help=f"Distance threshold for off-path detection (default: {DEVIATION_THRESHOLD})",
    )
    parser.add_argument(
        "--process-name",
        default="rift_x64.exe",
        help="Target process name for live position reads (default: rift_x64.exe)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write path JSON to file (for --once mode)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use a static position source instead of live memory (for testing)",
    )

    args = parser.parse_args(argv)

    # Validate mode
    if not args.once and not args.watch:
        print("ERROR: Must specify --once or --watch", file=sys.stderr)
        return 1

    # Load zone OBJ
    zone_obj = Path(args.zone_obj)
    if not zone_obj.exists():
        print(f"ERROR: Zone OBJ not found: {zone_obj}", file=sys.stderr)
        return 1

    # Load coordinate transform
    try:
        transform = load_transform(args.transform)
    except Exception as exc:
        print(f"ERROR: Failed to load transform: {exc}", file=sys.stderr)
        return 1

    # Parse goal
    try:
        goal_mem = parse_coords(args.goal)
    except ValueError as exc:
        print(f"ERROR: Invalid goal coordinates: {exc}", file=sys.stderr)
        return 1

    goal_obj = memory_to_obj(goal_mem[0], goal_mem[1], goal_mem[2], transform)
    print(f"Goal (memory): {goal_mem}", file=sys.stderr)
    print(f"Goal (OBJ):    ({goal_obj[0]:.2f}, {goal_obj[1]:.2f}, {goal_obj[2]:.2f})", file=sys.stderr)

    # Check jars
    if not RECAST_JAR.exists() or not DETOUR_JAR.exists():
        print(f"ERROR: recast4j jars not found at:\n  {RECAST_JAR}\n  {DETOUR_JAR}", file=sys.stderr)
        return 1

    # Load geometry
    print(f"\nLoading zone OBJ: {zone_obj}", file=sys.stderr)
    vertices, faces = parse_obj(zone_obj)
    print(f"  {len(vertices)} vertices, {len(faces)} faces", file=sys.stderr)

    if not vertices or not faces:
        print("ERROR: Zone OBJ has no vertices or faces", file=sys.stderr)
        return 1

    # Start JVM
    print("Starting JVM with recast4j...", file=sys.stderr)
    _start_jvm()

    # Build navmesh
    print("Building navmesh (Recast → Detour)...", file=sys.stderr)
    navmesh_result = _build_recast_and_detour(
        vertices,
        faces,
        cell_size=0.5,
        cell_height=0.25,
        agent_height=1.8,
        agent_radius=0.5,
        agent_max_climb=0.5,
        agent_max_slope=45.0,
        region_min_size=8,
    )

    if not navmesh_result["success"]:
        print(f"ERROR: Navmesh build failed: {navmesh_result.get('error')}", file=sys.stderr)
        return 1

    print(f"  {navmesh_result['npolys']} polys, {navmesh_result['nverts']} verts", file=sys.stderr)

    # Create query provider
    query_provider = DetourNavmeshQueryProvider(navmesh_result)

    # Create position source
    position_source: PositionSource

    if args.dry_run or args.once:
        # Use a static source at origin for one-shot mode
        position_source = StaticPositionSource([(0.0, 0.0, 0.0)])
    else:
        live_source = _make_live_position_source(process_name=args.process_name)
        if live_source is None:
            return 1
        position_source = live_source
        print("Live position source ready.", file=sys.stderr)

    # Create observer
    observer = NavmeshObserver(
        query_provider=query_provider,
        position_source=position_source,
        coord_transform=transform,
        arrival_threshold=args.arrival_threshold,
        deviation_threshold=args.deviation_threshold,
    )

    # Prime the position
    observer.update()
    print("Position primed.", file=sys.stderr)

    # Compute initial path
    print("\nComputing path to goal...", file=sys.stderr)
    path = observer.set_goal_obj(goal_obj)

    if not path.get("success"):
        print(f"ERROR: Pathfinding failed: {path.get('error', 'Unknown')}", file=sys.stderr)
        if path.get("start_poly_ref"):
            print(f"  Start poly: {path['start_poly_ref']}, Goal poly: {path.get('goal_poly_ref')}", file=sys.stderr)
        return 1

    # --once mode: print waypoints and exit
    if args.once:
        _print_waypoints(path, transform)
        if args.out:
            _export_path_json(path, goal_obj, Path(args.out), transform)
            print(f"\nPath JSON written to: {args.out}", file=sys.stderr)
        return 0

    # --watch mode: continuous monitoring
    return _watch_loop(observer, args.interval, args.max_ticks)


if __name__ == "__main__":
    sys.exit(main())
