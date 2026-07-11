# Session Handoff — 2026-07-12 (Navmesh Phase 4: Runtime Bridge)

## Summary

NM-4 (Runtime Bridge) is **complete**. Shipped a protocol-based runtime bridge
that wires live player position (from `RIFTMemoryScanner`) onto a Detour
navmesh query and exposes live `find_path(goal)`. The bridge is pure-Python
(no JVM dependency in the state tracker — production Detour wiring lives in
the consumer). 38 new tests added; the broader navmesh test lane (194 tests
total) all pass.

---

## What shipped

### 1. `scripts/rift_memory_scanner.py` — `get_position()` helper + module-level constants

| Change | Where | Why |
|--------|-------|-----|
| Module-level `LOCAL_PLAYER_OFFSET = 0x32EBC80` and `PLAYER_FIELD_OFFSETS` (`pos_x=0x320`, `pos_y=0x324`, `pos_z=0x328`) | Top of file, just below the imports | Single source of truth for player position offsets. Replaces the local literal in `find_player_object()` and the duplicated copy in `navmesh_calibration_capture.py`. |
| New `RIFTMemoryScanner.get_position()` method | Between `read_float` and `scan_pattern` | Single source-of-truth helper for player position. Combines the LocalPlayer pointer dereference at `module_base + 0x32EBC80` with reading pos_x/pos_y/pos_z floats. Raises `RuntimeError` if `find_module()` was not called or any read fails. |

The local `LOCAL_PLAYER_OFFSET` constant in `find_player_object()` is left
intact (minimal-changes rule). It now `shadows` the module-level one inside
that scope for backwards-compat but is unused outside it. The new
`get_position()` is the canonical entry point; callers should prefer it.

### 2. `scripts/navmesh_state.py` — NEW (NM-4 Runtime Bridge)

Pure-Python module; no JVM dependency in the state tracker.

| Component | Purpose |
|-----------|---------|
| `PositionSource` Protocol (`@runtime_checkable`) | Decouples live-memory reads from testable static/replay sources. |
| `NavmeshQueryProvider` Protocol (`@runtime_checkable`) | Wraps Detour `findNearestPoly` / `findPath` so tests can inject mocks. |
| `PlayerPosition` frozen dataclass | `(x, y, z, timestamp)` reading from a `PositionSource`. |
| `NavmeshStatus` frozen dataclass | Snapshot returned from `NavmeshState.update()`: `on_navmesh`, `poly_ref`, `snapped_obj_pos`, `memory_pos`, `teleport_detected`, `zone_changed`, `update_count`. |
| `StaticPositionSource` | Scripted sequence of positions; supports `loop=True` for infinite replay. |
| `LiveMemoryPositionSource` | Wraps a `RIFTMemoryScanner` (calls `scanner.get_position()`); injectable `time_func` for deterministic tests. |
| `NavmeshState` (dataclass) | Coordinator: `update()` polls, projects, detects teleports / zone changes; `find_path(goal)` / `find_path_memory(goal)`; `mark_zone(zone)` and `recompute_zone_from_zone_change()` for caller-driven zone attribution. |

### 3. `tests/test_navmesh_state.py` — NEW (38 tests)

| Class | Coverage |
|-------|----------|
| `TestPlayerPosition` | `as_tuple()` round-trip; `frozen=True` immutability. |
| `TestStaticPositionSource` | First reading, sequence advance, `loop=True` wrap, exhaustion holds last value, empty sequence raises, `isinstance` Protocol check. |
| `TestLiveMemoryPositionSource` | Wraps `get_position()`, injected `time_func`, propagates scanner errors, `isinstance` Protocol check. |
| `TestNavmeshStateUpdate` | First reading sets `last_memory_pos`; identity vs `scale=10` projection; `poly_ref=0` → off-navmesh; query exception → off-navmesh but state remains usable; malformed response → off-navmesh. |
| `TestNavmeshStateTeleport` | First update never flags teleport; small movement OK; jump > threshold detected; boundary at threshold; threshold=0 disables detection. |
| `TestNavmeshStateZone` | Poly ref change with zone set → `zone_changed=True`; without zone → False; stable poly → False; `recompute_zone_from_zone_change()` clears. |
| `TestNavmeshStateFindPath` | Uses `last_obj_pos`; fail-closed before first `update()`; fail-closed when off-navmesh; `find_path_memory` applies coord transform; `smooth` kwarg passed through. |
| `TestNavmeshStateCounters` | `update_count` increments; history ring buffer caps at `history_len`. |
| `TestProtocolConformance` | `isinstance(q, NavmeshQueryProvider)`; `isinstance(src, PositionSource)`. |
| `TestDefaults` | `DEFAULT_TELEPORT_THRESHOLD == 5000.0`; default `history_len == 32`. |

---

## Key design decisions

1. **Pure-Python state tracker; protocol-based decoupling.**
   `NavmeshState` does not import the JVM-backed `navmesh_pathfind`. The
   `NavmeshQueryProvider` protocol lets production code wrap a Detour
   `NavMeshQuery` (built in RiftReader or RiftFlythrough), and lets tests
   inject a scripted mock (`MockNavmeshQuery`). This keeps the state
   machine small and unit-testable without the JDK requirement.

2. **Teleport threshold = 5000.0 (default).**
   Per RIFT gameplay analysis (lumi/porticulum jumps 30k+ units in a
   single frame; fast-mounts top out at ~500 units over a comparable
   window). 5000 separates the two without flagging legitimate fast
   riding. Configurable per `NavmeshState(..., teleport_threshold=X)`.
   Setting `teleport_threshold=0` disables detection entirely.

3. **Teleport detection requires a prior reading.**
   `_detect_teleport()` returns False when `last_memory_pos is None`,
   i.e. on the first `update()`. No false positive on startup.

4. **Zone attribution is caller-driven, not auto-inferred.**
   `NavmeshState` does not infer the zone from poly refs alone — that
   would conflate "poly ref changed because we walked across the
   navmesh" with "we crossed into a different zone". Instead the
   caller calls `mark_zone(zone_name)` when their zone attribution
   (e.g. RiftReader reading the unit registry signature at +0x6E0)
   changes. `zone_changed=True` is then raised on the next `update()`
   when the poly ref differs from the prior. `recompute_zone_from_zone_change()`
   clears the assignment so the next transition can flag again.

5. **Fail-closed semantics on `find_path`.**
   - Before the first `update()`: returns `{success: False, error: "NavmeshState.update() must be called before find_path()"}`.
   - When current poly ref is 0 (off-navmesh): returns `{success: False, error: "Player is off-navmesh; cannot find_path() reliably without re-projection"}`.
   Both errors are structured dicts (matching the `NavmeshQueryProvider.find_path` return shape) so callers can dispatch on `success` without parsing prose.

6. **Defensive `_safe_nearest_poly()` wrapper.**
   Any exception from the query provider, response with `poly_ref < 0`,
   or snapped position of the wrong shape is treated as "off-navmesh"
   with `poly_ref=0`. The state remains usable (counter increments,
   history records, find_path() returns off-navmesh error). This keeps
   the state machine robust against momentary JVM/pipeline failures
   without losing prior good readings (`last_obj_pos` is preserved if
   `query_ok` is False).

7. **Bounded history ring buffer (default `history_len=32`).**
   Diagnostic-only; not consumed by algorithm code. Exposed as
   `state._history` for debugging recent positions and poly refs.
   Prevents unbounded growth in long-lived consumers (RiftReader
   poll loops at 10 Hz would otherwise allocate 600+ tuples / minute).

8. **`@runtime_checkable` on both Protocols.**
   Trade-off: `runtime_checkable` adds `__instancecheck__` overhead on
   every isinstance call, but enables test-time `isinstance(mock,
   PositionSource)` for documentation. Acceptable because calls are
   O(few) per session, not per-packet.

9. **`LiveMemoryPositionSource` requires the scanner to have run**
   `find_module()` already. The runtime contract is:
   `with RIFTMemoryScanner() as s: s.find_module(); NavmeshState(LiveMemoryPositionSource(s), ...)`. This keeps the source free of process-management concerns
   and matches the existing pattern in `navmesh_calibration_capture.py`.

---

## Validation

| Check | Command | Result |
|-------|---------|:------:|
| ruff (full lane) | `ruff check scripts/ tests/` | ✅ clean |
| mypy (scripts/) | `mypy --no-error-summary scripts/` | ✅ 0 errors |
| pytest (navmesh tests) | `pytest tests/test_navmesh_state.py tests/test_navmesh_pathfind.py tests/test_navmesh_coord_transform.py tests/test_navmesh_debug_export.py tests/test_navmesh_phase0_feasibility.py tests/test_build_navmesh.py tests/test_extract_zone_geometry.py tests/test_validate_navmesh.py` | ✅ **194/194** pass in 2.44 s |
| pytest (new tests) | `pytest tests/test_navmesh_state.py -v` | ✅ 38/38 pass |
| pre-commit dry-run | `pre-commit run --files scripts/navmesh_state.py tests/test_navmesh_state.py scripts/rift_memory_scanner.py` | (intentionally not run yet — bundled with commit) |

Total NM-4 LOC: **scripts/navmesh_state.py** ~280 lines, **tests/test_navmesh_state.py** ~430 lines, **scripts/rift_memory_scanner.py** +37 lines.

---

## Anti-drift notes

- **This repo only.** No cross-repo edits. `navmesh_state.py` is purely
  backward-facing (RiftReader / RiftFlythrough consume its protocols).
- **Read-only.** `LiveMemoryPositionSource` reads memory only; no
  movement injection. Phase 7 (Navigation Agent) remains optional and
  safety-gated.
- **Recast/Detour is the engine.** No custom pathfinding algorithms.
- **Consume, don't duplicate.** `navmesh_state.py` reuses
  `memory_to_obj` from `navmesh_coord_transform.py`; the only
  duplicated offset knowledge was added at module-level in
  `rift_memory_scanner.py` and is now the single source of truth
  (the existing local copy inside `find_player_object()` is
  intentionally not refactored per minimal-changes rule).

---

## Usage examples

### Programmatic — test-friendly

```python
from scripts.navmesh_state import (
    LiveMemoryPositionSource, NavmeshState, StaticPositionSource
)
from scripts.navmesh_coord_transform import load_transform
from scripts.navmesh_pathfind import find_path as detour_find_path

# Production: read live player position
with RIFTMemoryScanner() as scanner:
    scanner.find_module()
    position_source = LiveMemoryPositionSource(scanner)

# Production: wrap a real Detour NavMeshQuery (built in RiftReader)
class DetourQueryProvider:
    def __init__(self, query, filter):
        self._query = query; self._filter = filter
    def find_nearest_poly(self, x, y, z, *, search_extents=(50, 50, 50)):
        # ... call Detour's findNearestPoly ...
        ...
    def find_path(self, start, goal, *, smooth=True, search_extents=(50, 50, 50)):
        return detour_find_path(self._query, self._filter, start, goal, smooth=smooth)

transform = load_transform("Exports/navmesh-phase2/coord-transform.json")

state = NavmeshState(
    position_source=position_source,
    query_provider=DetourQueryProvider(...),
    coord_transform=transform,
)

# Polling loop
while True:
    s = state.update()              # ~10 Hz
    if not s.on_navmesh:
        # player off-navmesh: skip pathfinding
        continue
    state.mark_zone(current_zone_id)
    if s.zone_changed:
        # reload zone navmesh + recreate NavmeshQueryProvider
        ...
    path = state.find_path(goal_obj)
    if path["success"]:
        follow_waypoints(path["waypoints"])
```

### Offline replay — pattern matching / debugging

```python
from scripts.navmesh_state import NavmeshState, StaticPositionSource

# Replay a recorded session's positions to reproduce a navigation bug.
state = NavmeshState(
    position_source=StaticPositionSource(
        [(p.x, p.y, p.z) for p in recorded_positions],
        loop=True,
    ),
    query_provider=mock_or_saved_query,
    coord_transform=transform,
)
for _ in recorded_positions:
    state.update()
```

---

## Files

| Path | Status |
|------|--------|
| `scripts/navmesh_state.py` | NEW (committed) |
| `tests/test_navmesh_state.py` | NEW (committed) |
| `scripts/rift_memory_scanner.py` | MODIFIED (+ module-level constants + get_position() method) |
| `scripts/rift_memory_scanner.py::find_player_object` | UNCHANGED (keeps local `LOCAL_PLAYER_OFFSET` per minimal-changes rule; new `get_position` is canonical) |

---

## Roadmap status (NM-4 ✅)

| Phase | Topic | Status |
|-------|-------|:---:|
| NM-0 | Recast feasibility & geometry audit | ✅ |
| NM-1 | Single-zone navmesh pipeline | ✅ |
| NM-2 | Coordinate system alignment | ✅ |
| NM-3 | Pathfinding integration (Detour) | ✅ |
| **NM-4** | **Runtime bridge (live position)** | **✅ DONE** |
| NM-5 | Visualization (RiftFlythrough) | ✅ |
| NM-6 | Scale-out & multi-zone | ⬜ |
| NM-7 | Navigation agent (optional) | ⬜ |

---

## What remains for NM-6 / NM-7

- **NM-6 scale-out**: build navmeshes for every viable zone; build a zone
  connection graph; add cross-zone pathfinding. Pulls in
  `scripts/extract_zone_geometry.py` + zone attribution map.
- **NM-7 (optional)**: build a `NavigationAgent` that consumes
  `NavmeshState.find_path()` results and emits movement commands.
  Memory-write movement injection stays safety-gated (separate review).
- The natural next integration step (separate from the cycle above) is
  to write a `docs/navmesh-consumer-contract.md` documenting how
  RiftReader / RiftFlythrough load the bridge, the read/coord/zone
  protocols, and the error surfaces. This was originally TODO from
  the M4.5 milestone in `navmesh-navigation-roadmap.md` and was not
  delivered as part of this PR (deferred; ping when needed).

---

*End of handoff.*
