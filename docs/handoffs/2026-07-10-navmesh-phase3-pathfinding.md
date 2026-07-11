# Session Handoff — 2026-07-10 (Navmesh Phase 3: Detour A* Pathfinding)

## Summary

Implemented Detour A-star pathfinding on the ep1 dungeons navmesh using recast4j's
Detour library. The pipeline loads OBJ geometry, builds a Recast polymesh,
converts it to a Detour NavMesh via `NavMeshBuilder.createNavMeshData`, then
runs `findNearestPoly` → `findPath` (A*) → `findStraightPath` (string-pulling
smoothing) to produce a waypoint path between two 3D points. Exported as JSON.

---

## What shipped

### `scripts/navmesh_pathfind.py` (NEW, ~450 lines)

Phase 3 Detour A* pathfinding CLI script. Pipeline:

1. Load OBJ geometry (vertices + faces) via `parse_obj`
2. Build Recast polymesh + detail mesh (reuses `_auto_cell_size`, `_auto_agent_params`, `_adaptive_params` from `build_navmesh.py`)
3. Convert to Detour NavMesh via `NavMeshBuilder.createNavMeshData(NavMeshDataCreateParams)`
4. Create `NavMeshQuery` + `DefaultQueryFilter`
5. `findNearestPoly` for start and goal (snaps to navmesh surface)
6. `findPath` (A* through polygon graph)
7. `findStraightPath` with `DT_STRAIGHTPATH_ALL_CROSSINGS` (string-pulling smoothing)
8. Export waypoints as JSON with validation checks

**CLI:**

```bash
python scripts/navmesh_pathfind.py --obj <zone-obj> --from x,y,z --to x,y,z [--adaptive] [--no-smooth] [--out <json>]
```

**Pure-Python helpers (testable without JVM):**

- `parse_coords(s)` — parse comma-separated coordinate strings
- `extract_waypoints_from_straight_path(items)` — convert StraightPathItem objects to JSON dicts
- `compute_path_distance(waypoints)` — total Euclidean distance along path
- `validate_path(waypoints, start, goal)` — structural validation (start/goal match, no backward segments, distance)

### `tests/test_navmesh_pathfind.py` (NEW, 24 tests)

- `TestParseCoords` (8 tests) — basic, negative, integer, whitespace, invalid inputs
- `TestExtractWaypointsFromStraightPath` (3 tests) — empty, single, multiple items
- `TestComputePathDistance` (6 tests) — empty, single, straight, diagonal, multi-segment, negative
- `TestValidatePath` (7 tests) — empty, single, valid, mismatched, backward, distance

---

## End-to-end smoke test

### Query: `(-5, 0, -60) → (15, 0, 20)` on ep1 dungeons

| Metric | Value |
|---|---|
| NavMesh polys | 9 |
| NavMesh verts | 33 |
| Start poly ref | 281474976710656 |
| Goal poly ref | 281474976710663 |
| Raw path (A*) | 1 poly |
| Smoothed waypoints | 2 |
| Path distance | 5.40 world units |
| Waypoint 0 | (10.48, 21.52, -32.92) |
| Waypoint 1 | (11.45, 21.52, -27.60) |
| No backward segments | True |

**Result**: A* pathfinding is functional. `findNearestPoly` correctly snapped
both query points to the nearest navmesh polygons. `findPath` found a valid
poly path. `findStraightPath` produced 2 smoothed waypoints with string-pulling.

**Note**: The raw path has only 1 poly because both snapped positions landed on
the same polygon (the 9-poly navmesh is small — bounds ~100 units). Multi-poly
paths will be demonstrated on larger navmeshes in future phases.

---

## recast4j Detour API discovered

| Class | Package | Purpose |
|---|---|---|
| `NavMeshDataCreateParams` | `org.recast4j.detour` | Parameter holder for NavMeshBuilder |
| `NavMeshBuilder` | `org.recast4j.detour` | `createNavMeshData(params)` → `MeshData` |
| `NavMesh` | `org.recast4j.detour` | `NavMesh(meshData, maxVertsPerPoly, flags)` constructor |
| `NavMeshQuery` | `org.recast4j.detour` | `findNearestPoly`, `findPath`, `findStraightPath` |
| `DefaultQueryFilter` | `org.recast4j.detour` | Default filter (all flags included, area cost=1.0) |
| `Result<T>` | `org.recast4j.detour` | Wraps return values; `.result`, `.failed()`, `.succeeded()` |
| `StraightPathItem` | `org.recast4j.detour` | `.getPos()`, `.getFlags()`, `.getRef()` |
| `FindNearestPolyResult` | `org.recast4j.detour` | `.getNearestRef()`, `.getNearestPos()`, `.isOverPoly()` |

Key API patterns:

- `jpype.JFloat[3]` creates a Java float[] array (NOT `JFloat(3)` which creates a scalar)
- `NavMesh(meshData, nvp, 0)` — flags=0 for single-tile meshes (keeps data in memory)
- `polyFlags[i] = 1` (DT_POLYFLAGS_WALK), `polyAreas[i] = 0` for all polys
- `findStraightPath(start, goal, pathRefs, maxPoints, DT_STRAIGHTPATH_ALL_CROSSINGS)`

---

## Artifacts

| Path | Description |
|---|---|
| `scripts/navmesh_pathfind.py` | Phase 3 pathfinding script (committed) |
| `tests/test_navmesh_pathfind.py` | 24 unit tests (committed) |
| `Exports/navmesh-phase3/ep1-dungeons-path.json` | Smoke test pathfinding result (gitignored) |
| `Exports/navmesh-phase3/ep1-dungeons-path-long.json` | Second query result (gitignored) |
| `docs/handoffs/2026-07-10-navmesh-phase3-pathfinding.md` | This handoff (committed) |
| `docs/roadmap/navmesh-navigation-roadmap.md` | Roadmap updated: Phase 3 marked ✅ |

---

## Validation

| Check | Command | Result |
|---|---|---|
| ruff | `ruff check scripts/navmesh_pathfind.py tests/test_navmesh_pathfind.py` | Clean |
| mypy | `mypy --no-error-summary scripts/navmesh_pathfind.py` | Clean |
| pytest | `pytest tests/test_navmesh_pathfind.py -v` | 24/24 passed |
| Code review | Reviewer approved | All issues fixed |
| End-to-end | `navmesh_pathfind.py --adaptive` on ep1 dungeons | 2 waypoints, 5.40 units |

---

## Key design decisions

1. **Reuse build_navmesh.py helpers** — `_start_jvm`, `_auto_cell_size`, `_auto_agent_params`, `_adaptive_params` imported directly. No duplication of JVM setup or parameter calibration.

2. **Recast build duplication is intentional** — `_build_recast_and_detour()` duplicates the Recast config + build logic from `build_navmesh.py::build_navmesh()` because the pathfind script needs the raw Java `PolyMesh` and `PolyMeshDetail` objects (to pass to `NavMeshBuilder.createNavMeshData`), while `build_navmesh.py` returns Python dicts. The Recast API objects can't be reconstructed from dicts.

3. **Pure-Python helpers tested without JVM** — `parse_coords`, `extract_waypoints_from_straight_path`, `compute_path_distance`, `validate_path` are all pure Python and fully unit-tested. The JVM-dependent functions (`_build_recast_and_detour`, `find_path`) are exercised only via end-to-end smoke tests.

4. **`--adaptive` flag passed through** — The pathfinding CLI supports the same `--adaptive` parameter calibration as `build_navmesh.py`, ensuring consistent navmesh build parameters across phases.

5. **Smoothing on by default** — `findStraightPath` with `DT_STRAIGHTPATH_ALL_CROSSINGS` runs by default. `--no-smooth` disables it for raw poly-path debugging.

---

## Next steps

1. **Phase 2 (Coordinate System Alignment)** — The roadmap specifies coordinate alignment before Phase 4. This requires in-game landmark capture and live memory reads. Phase 3 pathfinding works in OBJ coordinates; Phase 2 would add the memory↔OBJ transform.
2. **Multi-poly path test on ep2 architecture** — The ep2 architecture navmesh (185 polys with tuned params) would demonstrate multi-poly A* paths.
3. **Path validation suite** — Extend `validate_navmesh.py` with pathfinding test cases (same-poly, cross-zone, edge-to-edge, outside-navmesh, no-path).

---

*End of handoff.*
