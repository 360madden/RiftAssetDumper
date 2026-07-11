"""navmesh_state.py — NM-4 Runtime Bridge: live position → navmesh projection.

Wires live player position (from a PositionSource such as
``LiveMemoryPositionSource`` wrapping ``RIFTMemoryScanner``) onto a
navmesh query (from a ``NavmeshQueryProvider`` wrapping Detour's
NavMeshQuery). The ``NavmeshState`` coordinator:

  1. Polls the position source.
  2. Applies the OBJ↔memory coordinate transform.
  3. Projects the player onto the navmesh (``findNearestPoly``).
  4. Detects teleports (discontinuous memory-space jumps).
  5. Exposes ``find_path(goal)`` for live pathfinding from the current
     projected position to a goal in OBJ coordinates (or memory
     coordinates via ``find_path_memory``).

The module is **pure Python** (no JVM / no live-game dependency).
Detour-backed production NavmeshQueryProvider implementations live in
the consumer (RiftReader / RiftFlythrough) and wrap the existing
``scripts.navmesh_pathfind.find_path`` + Detour ``findNearestPoly``
APIs. Tests inject mocks.

Safety: read-only end-to-end. ``LiveMemoryPositionSource`` requires
``find_module()`` to have been called on the scanner (caller is
responsible for attaching to ``rift_x64.exe`` with Administrator
privileges). No movement injection. ``Navigation Agent`` (Phase 7)
gates a separate write-only control path.
"""

from __future__ import annotations

import math
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

# Ensure project root is on sys.path so `scripts.*` imports resolve when this
# module is executed directly (e.g. python scripts/navmesh_state.py).
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.navmesh_coord_transform import memory_to_obj  # noqa: E402

# ============================================================================
# Protocols
# ============================================================================


@runtime_checkable
class PositionSource(Protocol):
    """Source of the player's 3D position in memory (live-game) coordinates.

    Implementations must return a ``PlayerPosition`` with a monotonic
    ``timestamp`` for teleport detection. Implementations must be
    **read-only** — never write back to the game process.

    Concrete implementations:
      - ``StaticPositionSource``: scripted sequence (tests / offline replay).
      - ``LiveMemoryPositionSource``: wraps ``RIFTMemoryScanner.get_position()``.
    """

    def get_position(self) -> PlayerPosition:
        """Return the current player position and a monotonic timestamp."""
        ...


@runtime_checkable
class NavmeshQueryProvider(Protocol):
    """Wrapper around a Detour NavMeshQuery for one zone.

    Implementations must be **stateless across calls** (Detour's
    NavMeshQuery is, in fact, safe to reuse but each call should be
    idempotent for the same query args). Production implementations
    wrap a real Detour ``NavMeshQuery`` (``scripts.navmesh_pathfind``
    is the canonical helper for ``find_path``; ``RIFTMemoryScanner``
    + a freshly-loaded navmesh ``.bin`` would build the
    ``findNearestPoly`` side).

    Returns ``(poly_ref, (x,y,z))`` from ``find_nearest_poly`` where a
    ``poly_ref`` of 0 means "no nearby poly" (off-navmesh).
    """

    def find_nearest_poly(
        self,
        x: float,
        y: float,
        z: float,
        *,
        search_extents: tuple[float, float, float] = (50.0, 50.0, 50.0),
    ) -> tuple[int, tuple[float, float, float]]:
        """Snap (x,y,z) to the nearest walkable polygon."""
        ...

    def find_path(
        self,
        start: tuple[float, float, float],
        goal: tuple[float, float, float],
        *,
        smooth: bool = True,
        search_extents: tuple[float, float, float] = (50.0, 50.0, 50.0),
    ) -> dict:
        """Run A* pathfinding from start to goal in OBJ coordinates.

        Expected return shape matches ``scripts.navmesh_pathfind.find_path``:
          - ``success``: bool
          - ``start_poly_ref`` / ``goal_poly_ref``: int
          - ``start_pos`` / ``goal_pos``: [x,y,z] (snapped)
          - ``raw_path``: list[int]
          - ``waypoints``: list of dicts with 'pos' key
        """
        ...


# ============================================================================
# Data classes
# ============================================================================


@dataclass(frozen=True)
class PlayerPosition:
    """A single position reading with metadata.

    Coordinates are in live-memory / RiftReader space. ``timestamp`` is
    monotonic-clock seconds; ``NavmeshState`` compares consecutive
    ``memory_pos`` values against ``teleport_threshold`` to detect
    lumi jumps vs normal movement.
    """

    x: float
    y: float
    z: float
    timestamp: float

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class NavmeshStatus:
    """Snapshot of where the player is on the navmesh after an ``update()``.

    ``on_navmesh=False`` means ``find_nearest_poly`` returned ``poly_ref=0``
    or raised — the player is currently falling, swimming, or out of zone
    bounds. ``teleport_detected=True`` means the memory-space motion
    vector exceeded ``teleport_threshold``. ``zone_changed`` is True only
    when ``current_zone`` was previously set AND the new poly ref differs
    from the prior one (the caller is the source of truth for zone
    attribution; see ``NavmeshState.mark_zone``).
    """

    on_navmesh: bool
    poly_ref: int
    snapped_obj_pos: tuple[float, float, float]
    memory_pos: tuple[float, float, float]
    teleport_detected: bool
    zone_changed: bool
    update_count: int


# ============================================================================
# PositionSource implementations
# ============================================================================


class StaticPositionSource:
    """A ``PositionSource`` that returns positions from a fixed sequence.

    Used in tests and offline replays. Callers can either consume each
    position once (``loop=False``, holds the last reading) or wrap around
    the sequence indefinitely (``loop=True``).
    """

    def __init__(self, positions: Sequence[tuple[float, float, float]], *, loop: bool = False) -> None:
        if not positions:
            raise ValueError("StaticPositionSource requires at least one position")
        if len(positions) == 1:
            # Avoid subtle bugs: a sequence of length 1 should hold value when
            # loop is False, not iterate-and-fail-on-second-read.
            loop = False
        self._positions: list[tuple[float, float, float]] = [(float(p[0]), float(p[1]), float(p[2])) for p in positions]
        self._index = 0
        self._loop = loop

    def get_position(self) -> PlayerPosition:
        pos = self._positions[self._index]
        if self._loop:
            self._index = (self._index + 1) % len(self._positions)
        else:
            self._index = min(self._index + 1, len(self._positions) - 1)
        return PlayerPosition(x=pos[0], y=pos[1], z=pos[2], timestamp=time.monotonic())


class LiveMemoryPositionSource:
    """Production ``PositionSource`` wrapping a ``RIFTMemoryScanner``.

    Reads the player's current (x, y, z) via ``scanner.get_position()``.
    The scanner already handles ``PROCESS_VM_READ`` + module-base lookup;
    inject ``time_func`` in tests to make timestamps deterministic.
    """

    def __init__(self, scanner: Any, *, time_func: Callable[[], float] = time.monotonic) -> None:
        self._scanner = scanner
        self._time_func = time_func

    def get_position(self) -> PlayerPosition:
        x, y, z = self._scanner.get_position()
        return PlayerPosition(x=x, y=y, z=z, timestamp=self._time_func())


# ============================================================================
# NavmeshState
# ============================================================================


# 5000.0 memory-unit threshold (per RIFT gameplay data, lumi/porticulum
# fast-travel jumps 30k+ units in a single frame; normal fast-mounts
# top out at ~500 units / first. 5000 cleanly separates the two without
# flagging legitimate fast riding).
DEFAULT_TELEPORT_THRESHOLD = 5000.0


@dataclass
class NavmeshState:
    """Runtime bridge coordinator: poll position → project to navmesh → pathfind.

    Lifecycle::

        state = NavmeshState(position_source, query_provider, coord_transform)
        while True:
            status = state.update()           # ~10 Hz poll
            if not status.on_navmesh:
                # player fell off, re-project with last good position OR
                # switch to a different zone's navmesh and rebuild state
                ...
            path = state.find_path(goal_obj)
            if path["success"]:
                follow_waypoints(path["waypoints"])

    The state tracks:

      - ``last_memory_pos``: positions-source reading in memory coords.
      - ``last_obj_pos``: same position after coord transform.
      - ``current_poly_ref``: Detour poly ref the player is currently on.
      - ``current_zone``: caller-attributed zone (set via ``mark_zone``).
      - ``update_count``: monotonic update counter.
      - ``_history``: bounded ring buffer of recent (timestamp, obj_pos,
        poly_ref) tuples for diagnostics.

    The observer's role:

      - ``mark_zone(zone_name)`` when zone attribution changes externally
        (e.g. RiftReader detects a zone line via the ``unit_registry``
        signature at ``+0x6E0``). ``zone_changed`` in ``NavmeshStatus``
        becomes True on the next ``update()`` that lands on a different
        poly.
    """

    position_source: PositionSource
    query_provider: NavmeshQueryProvider
    coord_transform: dict[str, Any]
    teleport_threshold: float = DEFAULT_TELEPORT_THRESHOLD
    history_len: int = 32

    # ── Internal state (managed by update(), not in __init__) ───────────

    update_count: int = field(default=0, init=False)
    last_memory_pos: PlayerPosition | None = field(default=None, init=False)
    last_obj_pos: tuple[float, float, float] | None = field(default=None, init=False)
    current_poly_ref: int = field(default=0, init=False)
    current_zone: str | None = field(default=None, init=False)
    _history: list[tuple[float, tuple[float, float, float], int]] = field(default_factory=list, init=False, repr=False)

    def update(self) -> NavmeshStatus:
        """Poll the position source, project onto the navmesh, return status.

        Raises:
            Exception: Propagates exceptions from ``position_source.get_position()``.
                Exceptions from ``query_provider.find_nearest_poly`` are
                caught and recorded as ``on_navmesh=False`` so the state
                tracker remains usable even when the query backend briefly
                fails (e.g. JVM disconnect mid-session).

        Returns:
            ``NavmeshStatus`` with the current poly, on/off-navmesh flag,
            position in both coordinates, plus teleport / zone-change flags.
        """
        pos = self.position_source.get_position()
        memory_pos: tuple[float, float, float] = pos.as_tuple()
        obj_pos: tuple[float, float, float] = memory_to_obj(
            memory_pos[0], memory_pos[1], memory_pos[2], self.coord_transform
        )

        # Project onto navmesh (defensive — query may fail).
        poly_ref, snapped, query_ok = self._safe_nearest_poly(obj_pos)

        # Detect teleport in memory space (gating comparison against
        # prior reading, not adjustment). Skips on first update because
        # there is no prior reading to compare.
        teleport_detected = self._detect_teleport(memory_pos)

        # Zone-change: change is real only if (a) caller has set
        # current_zone, (b) prior poly_ref was non-zero, and (c) the new
        # poly_ref differs from the prior AND is on-navmesh.
        prev_poly_ref = self.current_poly_ref
        if self.current_zone is not None and prev_poly_ref != 0 and poly_ref != 0 and poly_ref != prev_poly_ref:
            zone_changed = True
        else:
            zone_changed = False

        # Commit state.
        self.last_memory_pos = pos
        self.last_obj_pos = obj_pos if query_ok else self.last_obj_pos  # hold last good on fail
        self.current_poly_ref = poly_ref
        self.update_count += 1

        # Ring-buffer history (bounded).
        self._history.append((pos.timestamp, obj_pos, poly_ref))
        if len(self._history) > self.history_len:
            self._history.pop(0)

        return NavmeshStatus(
            on_navmesh=query_ok and poly_ref != 0,
            poly_ref=poly_ref,
            snapped_obj_pos=snapped,
            memory_pos=memory_pos,
            teleport_detected=teleport_detected,
            zone_changed=zone_changed,
            update_count=self.update_count,
        )

    def find_path(
        self,
        goal: tuple[float, float, float],
        *,
        smooth: bool = True,
    ) -> dict:
        """Find a path from the current projected position to ``goal``.

        Args:
            goal: OBJ/world coordinates (x, y, z). Use ``find_path_memory``
                if your goal is in live-memory coordinates.
            smooth: If True, run Detour string-pulling smoothing on the
                poly-path waypoints.

        Returns:
            Detour ``find_path`` result dict (see ``NavmeshQueryProvider``).
            Fails closed with ``success=False`` and an explanatory ``error``
            if ``update()`` has not yet populated ``last_obj_pos`` or the
            player is currently off-navmesh.
        """
        if self.last_obj_pos is None:
            return {
                "success": False,
                "error": "NavmeshState.update() must be called before find_path()",
                "_last_obj_pos": None,
            }
        if self.current_poly_ref == 0:
            return {
                "success": False,
                "error": "Player is off-navmesh; cannot find_path() reliably without re-projection",
                "current_poly_ref": 0,
            }
        return self.query_provider.find_path(self.last_obj_pos, goal, smooth=smooth)

    def find_path_memory(
        self,
        goal_memory: tuple[float, float, float],
        *,
        smooth: bool = True,
    ) -> dict:
        """Like ``find_path`` but the goal is given in live-memory coordinates."""
        goal_obj = memory_to_obj(goal_memory[0], goal_memory[1], goal_memory[2], self.coord_transform)
        return self.find_path(goal_obj, smooth=smooth)

    def mark_zone(self, zone: str | None) -> None:
        """Set the caller's view of the current zone.

        Used by RiftReader (or any external zone-attribution source) to
        indicate "we're now in zone X" so that the next ``update()`` can
        raise ``zone_changed=True`` when poly refs shift across zone
        boundaries. ``zone=None`` clears the assignment (e.g. before
        re-projection after a teleport).
        """
        self.current_zone = zone

    def recompute_zone_from_zone_change(self) -> None:
        """Caller hook: clear ``current_zone`` after a zone transition is
        acknowledged by an external observer (e.g. RiftReader finishes
        reloading the zone navmesh). After this call, ``update()`` will
        not flag ``zone_changed`` until the zone is re-set via
        ``mark_zone``.
        """
        self.current_zone = None

    # ── helpers ──────────────────────────────────────────────────────────

    def _safe_nearest_poly(
        self,
        obj_pos: tuple[float, float, float],
    ) -> tuple[int, tuple[float, float, float], bool]:
        """Wrap ``query_provider.find_nearest_poly`` defensively.

        Returns ``(poly_ref, snapped_pos, ok)``. On exception, ``ok``
        is False and ``poly_ref=0`` with ``snapped=obj_pos``.
        """
        try:
            poly_ref, snapped = self.query_provider.find_nearest_poly(*obj_pos)
        except Exception:  # pragma: no cover — defensive, exercised by tests
            return (0, obj_pos, False)

        if not isinstance(poly_ref, int) or poly_ref < 0:
            return (0, obj_pos, False)
        if len(snapped) != 3 or not all(isinstance(c, (int, float)) for c in snapped):
            # Malformed snapped position: trust poly_ref is bogus too, treat as off-navmesh
            # so on_navmesh is consistent with snapped_obj_pos (always un-snapped obj_pos).
            return (0, obj_pos, False)

        return (poly_ref, (float(snapped[0]), float(snapped[1]), float(snapped[2])), True)

    def _detect_teleport(self, new_memory: tuple[float, float, float]) -> bool:
        """Return True when the player seems to have teleported (lumi /
        porticulum / zone-crossing). First reading returns False
        because there is no prior reference for comparison.
        """
        if self.last_memory_pos is None or self.teleport_threshold <= 0:
            return False
        dx = new_memory[0] - self.last_memory_pos.x
        dy = new_memory[1] - self.last_memory_pos.y
        dz = new_memory[2] - self.last_memory_pos.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        return distance > self.teleport_threshold

    def __repr__(self) -> str:
        return (
            f"NavmeshState(update_count={self.update_count}, "
            f"current_poly_ref={self.current_poly_ref}, "
            f"current_zone={self.current_zone!r}, "
            f"on_navmesh={self.current_poly_ref != 0})"
        )


# ============================================================================
# CLI smoke test (pure-Python, no JVM)
# ============================================================================


def _smoke() -> int:
    """Tiny smoke-test that wires a StaticPositionSource + NoOpQueryProvider."""
    identity_transform: dict[str, Any] = {
        "scale": [1.0, 1.0, 1.0],
        "offset": [0.0, 0.0, 0.0],
        "axis_mapping": [1, 1, 1],
    }

    class _NoOpQuery:
        def find_nearest_poly(self, x, y, z, *, search_extents=(50.0, 50.0, 50.0)):
            return (1, (x, y, z))

        def find_path(self, start, goal, *, smooth=True, search_extents=(50.0, 50.0, 50.0)):
            return {
                "success": True,
                "waypoints": [{"pos": list(start)}, {"pos": list(goal)}],
                "raw_path": [1, 2],
            }

    state = NavmeshState(
        position_source=StaticPositionSource([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]),
        query_provider=_NoOpQuery(),
        coord_transform=identity_transform,
    )
    s1 = state.update()
    s2 = state.update()
    path = state.find_path((20.0, 0.0, 0.0))
    print(s1)
    print(s2)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(_smoke())
