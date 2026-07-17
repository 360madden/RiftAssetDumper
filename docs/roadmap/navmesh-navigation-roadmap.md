# Navmesh Navigation Roadmap — Generative Pathfinding from Extracted Geometry

**Created**: 2026-06-30
**Repo**: `RiftAssetDumper` (Assets repo only — no cross-repo edits)
**Status**: Phases 0-6 complete; Phase 7 delivered as observer-only agent
**Parallel to**: `docs/roadmap/semantic-discovery-roadmap.md` and `docs/roadmap/binary-signature-roadmap.md` (independent lane, but consumes artifacts from both)

---

## Purpose

RiftReader reads live game memory to extract player position, facing, and
zone state. RiftFlythrough renders extracted 3D geometry. But neither can
**navigate** the world — there's no pathfinding, no route planning, no
walkability knowledge.

This roadmap delivers **generative navmesh navigation**: build a navigation
mesh from extracted NIF geometry using Recast/Detour, implement A*
pathfinding on it, and wire it to live player position. The result is a
library that can answer "how do I get from A to B?" in the RIFT world.

**Why generative, not extractive**: RIFT does not ship a standard navmesh
format. Gamebryo v20.6.0.0 had no built-in navmesh system; Trion Worlds
built custom server-side pathfinding. No navmesh data was found in the
263,957-entry TWAD archive. We must **generate** the navmesh from the
geometry we already extract.

---

## What We Already Have

| Capability | Status | Relevance to navmesh |
|---|---|---|
| NIF geometry extraction | ✅ 350 OBJ files, 217 unique assets, 30,864 faces, 23,421 vertices | Raw walkable surface candidates |
| `world-placed-merged.obj` | ✅ 2.5 MB, 72,976 lines, hierarchy-aware transforms | Single-file world geometry input for Recast |
| `world.json` per asset | ✅ 217/217 with Scale→Rotate→Translate transforms | Correct spatial placement |
| Zone attribution | ✅ 217 assets with zone confidence (179 high / 27 medium / 23 low) | Per-zone navmesh partitioning |
| Live player position | ✅ `rift_x64.exe + 0x32EBC80` → pos_x (+0x320), pos_z (+0x328) | Runtime start/goal positions for pathfinding |
| Binary signature catalog | ✅ All 8 phases delivered; final database and consumer contract shipped | Survivable player position reads across patches |
| Semantic zone vocabulary | ✅ All 6 phases delivered; unified semantic index available | Zone names/labels for navmesh partitioning |
| `hint:actor-object` classification | ✅ 212 assets classified | Distinguishing structures from creatures |
| MeshSize families | ✅ 30 families, 100% coverage | Grouping assets by structural complexity |

---

## What We Don't Have (Key Unknowns)

| Unknown | Risk | Mitigation |
|---|---|---|
| Does `merged.obj` contain ground/terrain, or only placed structures? | **CRITICAL** — if no terrain, open-world navmesh is blocked | Phase 1 feasibility test; fallback: reconstruct terrain from zone bounds + height samples |
| Are NIF world coordinates 1:1 with live memory coordinates? | **HIGH** — mismatched coordinate systems break pathfinding | Phase 2 cross-validation: stand at known location in-game, compare OBJ vertex positions to live memory reads |
| What is the Y-axis (height) source? | **MEDIUM** — live memory pos_y has only 25 code hits (vs. 517 for pos_z) | pos_y may be terrain-derived; navmesh provides height from geometry |
| Are NIF mesh faces oriented consistently? | **LOW** — Recast is robust to winding order | Recast handles arbitrary triangle soups |
| What's the unit scale? Game units → meters? | **MEDIUM** — Recast expects meter-scale input | Phase 2 measurement: known in-game distances vs. OBJ vertex deltas |

---

## Operating Conventions

1. **Read-only, this repo only.** No cross-repo edits. Navmesh output goes to
   `Exports/navmesh/` (gitignored). Only scripts, schemas, and docs are
   committed.
2. **Recast/Detour is the navmesh engine.** Use the standard open-source
   Recast & Detour library for navmesh generation and pathfinding. No custom
   mesh algorithms.
3. **Navmesh data is generative, not extracted.** The navmesh `.bin` files
   are built from geometry, not decoded from archive entries. They are
   gitignored generated artifacts.
4. **One bounded zone first.** Prove the pipeline on a single well-understood
   zone before scaling to the full world.
5. **Integration, not duplication.** Consume artifacts from the
   semantic-discovery and binary-signature roadmaps; do not rebuild their
   pipelines.
6. **Smoke before full.** Every phase starts with a small bounded test before
   unbounded execution.
7. **RiftFlythrough is the debug consumer.** Navmesh visualization goes into
   RiftFlythrough for human review. RiftReader is the runtime consumer.

---

## Phase 0: Recast Feasibility & Geometry Audit

**Objective**: Determine whether the extracted geometry can support navmesh
generation. This is the **make-or-break phase** — if the geometry lacks
walkable surfaces, the entire roadmap must pivot to terrain reconstruction.

**Entry Criteria**:

- `world-placed-merged.obj` exists and is valid (FT-8 closure artifact)
- Zone attribution map available at `Exports/semantic-phase1/fly_asset_zone_map_v2.json`
- RecastDemo tool accessible (standalone GUI for rapid navmesh prototyping)

**Key Milestones**:

1. **M0.1**: Load `world-placed-merged.obj` into RecastDemo
   - Download/install RecastDemo (standalone GUI tool)
   - Load the merged OBJ directly — 72,976 lines is trivial for Recast
   - Apply default agent parameters (height=2.0, radius=0.6, max climb=0.9, max slope=45°)
   - Build navmesh
   - **Answer**: Does Recast produce a contiguous walkable surface?

2. **M0.2**: Classify "walkable" vs. "non-walkable" meshes
   - Cross-reference each asset in the merged OBJ against:
     - Zone attribution (map-zone assets are likely terrain/structures)
     - MeshSize family (large meshes tend to be terrain; small meshes are decorations)
     - Bounding box height (tall+thin = wall/tree; flat+wide = floor/platform)
     - Semantic hints (`hint:actor-object` vs `hint:map-zone`)
   - Produce: `Exports/navmesh-phase0/walkability-classification.json`
   - Filter merged OBJ to walkable-only subset for cleaner navmesh input

3. **M0.3**: Identify terrain vs. structure gap
   - Inspect the navmesh in RecastDemo: are there large continuous walkable
     regions (terrain), or only isolated platform islands (structures)?
   - If terrain exists: proceed to Phase 1
   - If only structures exist: document the gap; Phase 1 scope narrows to
     "structure-level navmesh" (bridges, buildings, platforms)
   - **Critical finding to document**: what's the largest contiguous walkable
     polygon group? What's the coverage of the world bounds?

4. **M0.4**: Single-asset-group smoke test
   - Pick the largest, flattest asset group in a single zone (highest vertex
     count + widest XZ footprint)
   - Generate navmesh for just that group
   - Walk the navmesh in RecastDemo: can you find a path from one edge to
     another?
   - Document: generation time, navmesh poly count, max poly edge length

**Exit Criteria**:

- RecastDemo confirmed working with RIFT geometry
- Walkability classification produced (at minimum: manual labels for top 20
  largest assets)
- Terrain vs. structure gap documented
- At least one smoke navmesh generated and visually inspected
- Go/No-Go decision documented: proceed with Phase 1, or narrow scope to
  structure-only navmesh, or pivot to terrain reconstruction

**Required Artifacts**:

- `Exports/navmesh-phase0/walkability-classification.json` (gitignored)
- `Exports/navmesh-phase0/smoke-navmesh.bin` (gitignored, Recast binary)
- `docs/handoffs/2026-06-30-navmesh-phase0-feasibility.md` (committed)

**Focus & Anti-Drift Rules**:

- Do NOT write any code during this phase — use RecastDemo GUI exclusively
- Do NOT attempt pathfinding — just navmesh generation
- Do NOT filter assets aggressively — better to have extra non-walkable
  geometry than to accidentally exclude walkable surfaces
- Only use existing artifacts; do not re-extract geometry

---

## Phase 1: Single-Zone Navmesh Generation Pipeline

**Objective**: Automate navmesh generation for a single zone. Build a Python
pipeline that takes the merged OBJ, filters walkable surfaces, runs Recast,
and produces a validated navmesh binary.

**Entry Criteria**:

- Phase 0 exit: feasibility confirmed, terrain/structure gap understood
- One zone selected as the "pilot zone" (highest-confidence zone with the
  most contiguous walkable geometry)
- Recast & Detour C++ library or Python bindings (`pydetour` / `recast4j` /
  custom ctypes wrapper) chosen

**Key Milestones**:

1. **M1.1**: Choose and set up Recast/Detour integration
   - Evaluate options:
     - `recastnavigation` C++ library (build from source, Python ctypes wrapper)
     - `pydetour` (Python bindings, if maintained)
     - `recast4j` (Java port, if Ghidra JDK can run it)
   - Install/build the chosen library
   - Write a minimal Python smoke test: load a simple mesh, build navmesh,
     serialize to `.bin`

2. **M1.2**: Build zone-filtered OBJ extractor
   - Script: `scripts/extract_zone_geometry.py`
   - Input: `world-placed-merged.obj`, `fly_asset_zone_map_v2.json`,
     `walkability-classification.json`

   - Output: `Exports/navmesh-phase1/zone-<name>-walkable.obj`
   - Filter logic:
     - Select assets in the target zone
     - Include only walkable-classified assets
     - Preserve world-space coordinates (already world-placed)
     - Validate: OBJ is valid, non-empty, has faces

3. **M1.3**: Navmesh build script
   - Script: `scripts/build_navmesh.py`
   - Input: zone-filtered OBJ, agent parameters (height, radius, max climb,
     max slope, cell size, cell height)

   - Pipeline: OBJ → Recast `rcContext` → rasterize triangles → filter
     walkable surfaces → partition → build polymesh → build detail mesh →
     create navmesh → serialize to Detour `.bin`

   - Output: `Exports/navmesh-phase1/zone-<name>.nav`
   - Validate: navmesh has >0 polys, all polys are reachable from at least
     one other poly

4. **M1.4**: Navmesh validation suite
   - Script: `scripts/validate_navmesh.py` (or extend `build_navmesh.py`)
   - Checks:
     - Poly count > 0
     - All polys have at least one neighbor (no isolated islands unless they
       are single-poly disconnected)

     - Bounding box matches zone bounds
     - Max poly edge length ≤ reasonable threshold (e.g., 50m)
     - No degenerate polys (area < epsilon)
   - Output: `Exports/navmesh-phase1/zone-<name>-validation.json`

5. **M1.5**: Schema + handoff
   - Write `docs/schemas/navmesh-build-v1.schema.json` (agent parameters,
     input geometry fingerprint, navmesh metadata)

   - Commit schema + pipeline scripts + handoff

**Exit Criteria**:

- Automated pipeline: `python scripts/build_navmesh.py --zone <name>` produces
  a valid navmesh

- Navmesh passes all validation checks
- At least one zone navmesh built and validated
- Schema defined; handoff committed

**Required Artifacts**:

- `scripts/extract_zone_geometry.py` (committed)
- `scripts/build_navmesh.py` (committed)
- `scripts/validate_navmesh.py` (committed)
- `Exports/navmesh-phase1/zone-<name>.nav` (gitignored)
- `Exports/navmesh-phase1/zone-<name>-validation.json` (gitignored)
- `docs/schemas/navmesh-build-v1.schema.json` (committed)
- `docs/handoffs/2026-06-30-navmesh-phase1-pipeline.md` (committed)

---

## Phase 2: Coordinate System Alignment & Scale Calibration

**Objective**: Establish the exact mapping between navmesh coordinates (from
OBJ geometry) and live memory coordinates (from RiftReader). Without this,
pathfinding produces paths in the wrong coordinate space.

**Entry Criteria**:

- Phase 1 exit: at least one zone navmesh built
- Live player position reads working (via RiftReader or binary-signature
  extracted offsets)

- Ability to stand at known locations in-game and record coordinates

**Key Milestones**:

1. **M2.1**: Identify calibration landmarks
   - In the pilot zone, find 3-5 visually distinctive geometry features
     (building corners, bridge endpoints, statue bases)

   - Record their OBJ vertex positions from `world-placed-merged.obj`
   - These are the "ground truth" geometry positions

2. **M2.2**: In-game coordinate capture
   - Stand at each calibration landmark in-game
   - Read live player position (pos_x, pos_y, pos_z) from memory
   - Record 3-5 samples per landmark (to average out floating-point jitter)
   - Document: `Exports/navmesh-phase2/calibration-samples.json`

3. **M2.3**: Compute coordinate transform
   - For each landmark pair (OBJ position, live memory position):
     - Compute delta: Δx, Δy, Δz
     - Compute scale factor: |OBJ_delta| / |memory_delta| for pairs of landmarks
   - Determine:
     - **Scale**: are OBJ units meters? centimeters? game-internal units?
     - **Origin offset**: is there a global offset between OBJ (0,0,0) and
       memory (0,0,0)?

     - **Axis mapping**: X→X, Y→Y, Z→Z? Any axis swaps?
   - Produce transform: `memory_pos = scale * (obj_pos + offset)`
   - Document confidence per axis

4. **M2.4**: Validate transform
   - Apply transform to OBJ landmark positions → predicted memory positions
   - Compare predictions to actual memory readings
   - Tolerance: ±0.5 game units for X/Z, ±1.0 for Y (if Y is terrain-derived)
   - If any landmark exceeds tolerance, investigate and document

5. **M2.5**: Coordinate transform API
   - Script: `scripts/navmesh_coord_transform.py`
   - Functions:
     - `obj_to_memory(x, y, z) → (px, py, pz)`
     - `memory_to_obj(px, py, pz) → (x, y, z)`
   - Load transform parameters from a config file
   - Config: `Exports/navmesh-phase2/coord-transform.json`

**Exit Criteria**:

- Transform established with ≤0.5-unit X/Z accuracy
- Transform validated against at least 3 landmarks
- Transform API functional
- Handoff committed

**Required Artifacts**:

- `Exports/navmesh-phase2/calibration-samples.json` (gitignored)
- `Exports/navmesh-phase2/coord-transform.json` (gitignored)
- `scripts/navmesh_coord_transform.py` (committed)
- `docs/handoffs/2026-06-30-navmesh-phase2-coordinates.md` (committed)

---

## Phase 3: Pathfinding Integration (Detour)

**Objective**: Implement A* pathfinding on the generated navmesh using
Detour. Answer the core question: "find a path from A to B in zone X."

**Entry Criteria**:

- Phase 1 exit: navmesh built for pilot zone
- Phase 2 exit: coordinate transform established
- Detour library integrated (same build as Recast from Phase 1)

**Key Milestones**:

1. **M3.1**: Detour pathfinding smoke test
   - Load the pilot zone navmesh into Detour
   - Pick two points on opposite sides of the navmesh
   - Run `dtNavMeshQuery.findPath(start, end)`
   - Verify: path is non-empty, has at least 2 waypoints, no segment crosses
     non-walkable area

   - Render path in RecastDemo for visual confirmation

2. **M3.2**: Pathfinding API
   - Script: `scripts/navmesh_pathfind.py`
   - CLI: `python scripts/navmesh_pathfind.py --zone <name> --from <x>,<y>,<z> --to <x>,<y>,<z> [--smooth]`
   - Output: JSON array of waypoints (in both OBJ and memory coordinates)
   - Handle edge cases:
     - Start/goal outside navmesh → find nearest poly
     - Start/goal on different disconnected components → no path
     - Straight-line path (single poly) → return direct segment

3. **M3.3**: Path smoothing
   - Detour's raw path is poly-to-poly (jagged)
   - Apply string pulling (Detour's `findStraightPath`) for smoothed waypoints
   - Optionally apply steering/bezier smoothing for natural movement
   - Document: smoothed vs. raw waypoint count reduction

4. **M3.4**: Pathfinding validation suite
   - Script: extend `scripts/validate_navmesh.py` with pathfinding tests
   - Test cases:
     - Same-poly path (trivial)
     - Cross-zone path (many polys)
     - Edge-to-edge path (boundary stress)
     - Start on navmesh edge (boundary handling)
     - Start outside navmesh (nearest-poly fallback)
     - Goal outside navmesh (no-path)
   - Performance: pathfinding time for longest path ≤ 10ms

5. **M3.5**: Schema + handoff
   - Write `docs/schemas/navmesh-path-v1.schema.json`
   - Commit scripts + handoff

**Exit Criteria**:

- Pathfinding functional: `navmesh_pathfind.py` returns valid paths
- All edge cases handled gracefully
- Path smoothing active
- Validation suite passing
- Schema defined; handoff committed

**Required Artifacts**:

- `scripts/navmesh_pathfind.py` (committed)
- `docs/schemas/navmesh-path-v1.schema.json` (committed)
- `docs/handoffs/2026-06-30-navmesh-phase3-pathfinding.md` (committed)

---

## Phase 4: Runtime Bridge — Live Position → Navmesh Pathfinding

**Objective**: Wire live player position (from binary-signature pipeline) to
the navmesh pathfinder. Enable real-time "where am I on the navmesh?" and
"how do I get to point B?" queries.

**Entry Criteria**:

- Phase 3 exit: pathfinding functional
- Binary-signature roadmap Phase 2 exit: stable player position reads
- RiftReader operational (can read live memory)

**Key Milestones**:

1. **M4.1**: Live position → navmesh projection
   - Function: given live memory (px, py, pz), find which navmesh poly the
     player is on

   - Apply coordinate transform (Phase 2): memory → OBJ coordinates
   - Use Detour's `findNearestPoly` to locate the player on the navmesh
   - Handle: player not on navmesh (falling, swimming, out of bounds) →
     return nearest poly + distance

   - Handle: zone transitions (player moves between zones) → reload navmesh

2. **M4.2**: Navmesh state tracker
   - Script: `scripts/navmesh_state.py`
   - Maintains: current zone, current poly, current position (OBJ + memory coords)
   - Update loop: poll live position at ~10 Hz, re-project onto navmesh
   - Detect: zone change, navmesh departure, teleport (discontinuous position jump)

3. **M4.3**: Live pathfinding query
   - Extend `navmesh_pathfind.py` to accept live memory coordinates directly
   - CLI: `python scripts/navmesh_pathfind.py --live --to <x>,<y>,<z>`
   - Reads current player position from live memory (via binary-signature offsets)
   - Applies coordinate transform
   - Finds path from current position to goal
   - Returns path in both OBJ and memory coordinate spaces

4. **M4.4**: Runtime integration test
   - Stand in-game at a known location
   - Run live pathfinding to a known destination
   - Verify: path endpoints match current position and goal (within tolerance)
   - Verify: path is walkable (no segments through walls/obstacles)
   - Verify: update latency ≤ 50ms (20 Hz)

5. **M4.5**: Consumer contract documentation
   - Write `docs/navmesh-consumer-contract.md`
   - Document:
     - How RiftReader loads and queries navmesh
     - Coordinate transform usage
     - Zone switching protocol
     - Error handling (no path, off navmesh, zone change)
   - No cross-repo edits — documentation only

**Exit Criteria**:

- Live position → navmesh projection functional
- Live pathfinding query returns valid paths in real-time
- Zone switching detected and handled
- Consumer contract documented
- Handoff committed

**Required Artifacts**:

- `scripts/navmesh_state.py` (committed)
- `docs/navmesh-consumer-contract.md` (committed)
- `docs/handoffs/2026-06-30-navmesh-phase4-runtime.md` (committed)

---

## Phase 5: Visualization & Debugging (RiftFlythrough Integration)

**Objective**: Render the navmesh and paths in RiftFlythrough for human
review and debugging. This is essential for validating navmesh quality and
path correctness visually.

**Entry Criteria**:

- Phase 4 exit: runtime bridge functional
- RiftFlythrough operational (can load merged.obj + textures)
- Navmesh `.bin` files produced for at least one zone

**Key Milestones**:

1. **M5.1**: Navmesh → OBJ export
   - Script: `scripts/export_navmesh_obj.py`
   - Load Detour navmesh → extract polygon mesh → write as debug OBJ
   - Color-code: walkable polys (green), off-mesh connections (yellow),
     boundary edges (red)

   - Output: `Exports/navmesh-phase5/zone-<name>-navmesh-debug.obj`

2. **M5.2**: Path → line segment export
   - Extend pathfinding to also export paths as line segment OBJs
   - Output: `Exports/navmesh-phase5/path-<id>-debug.obj`
   - Color-code: start (green), goal (red), waypoints (blue), smoothed path
     (yellow)

3. **M5.3**: RiftFlythrough navmesh layer
   - Load navmesh debug OBJ as a semi-transparent overlay in RiftFlythrough
   - Toggle navmesh visibility on/off
   - Click on navmesh → show poly ID and walkability status
   - Click two points → compute and display path

4. **M5.4**: RiftFlythrough live position marker
   - If RiftReader live position available in browser context:
     - Show player position marker on the navmesh
     - Highlight current poly
     - Draw path from player to clicked goal point

**Exit Criteria**:

- Navmesh and paths render correctly in RiftFlythrough
- Toggle and click interaction functional
- At least one zone fully visualized
- Handoff committed

**Required Artifacts**:

- `scripts/export_navmesh_obj.py` (committed)
- `Exports/navmesh-phase5/*.obj` (gitignored)
- `docs/handoffs/2026-06-30-navmesh-phase5-visualization.md` (committed)

---

## Phase 6: Scale-Out & Multi-Zone Navigation

**Objective**: Scale the pipeline from one pilot zone to all zones with valid
navmesh, and implement cross-zone pathfinding.

**Entry Criteria**:

- Phase 1 pipeline proven on pilot zone
- Phase 3 pathfinding functional
- Zone attribution map available (all 217 assets classified)
- Walkability classification extended to all assets

**Key Milestones**:

1. **M6.1**: Batch navmesh generation — **COMPLETE**
   - Script: `scripts/build_all_navmeshes.py`
   - For each zone with ≥5 walkable assets:
     - Extract zone geometry (Phase 1)
     - Build navmesh
     - Validate
     - Export
   - Skip zones with insufficient walkable geometry
   - Output summary: `Exports/navmesh-phase6/navmesh-index.json`
   - Post-ship correction (2026-07-12): the canonical index was written by a
     restricted single-zone smoke run. Current inputs have four zones meeting
     the default threshold, but the stored index contains only
     `ep1.world_objects.dungeons` from that selected cohort.
   - Resolved: selected runs default to a separate index; scope and SHA-256
     provenance are recorded; full pytest runs in CI; 29/29 M6.1 tests pass.
   - Full batch: 4 eligible, 4 built, 0 failed, 10 skipped. A normalized-small
     adaptive profile prevents world-scale agent erosion on housing geometry.

2. **M6.2**: Zone connection graph — **COMPLETE**
   - Identify off-mesh connections between zones:
     - Boundary polys that are close to polys in adjacent zones
     - Known connection points (bridges, portals, zone lines)
   - Build a zone-level graph: nodes=zones, edges=connections
   - Output: `Exports/navmesh-phase6/zone-connection-graph.json`

3. **M6.3**: Cross-zone pathfinding — **COMPLETE**
   - Extend `navmesh_pathfind.py` with `--cross-zone` flag
   - Algorithm: A* at zone level → per-zone navmesh paths → concatenate
   - Handle: zone-unloading, disconnected zones, long-distance fallback

4. **M6.4**: Multi-zone validation — **COMPLETE**
   - Test paths crossing 2, 3, 5+ zones
   - Verify: path continuity at zone boundaries (no gaps)
   - Verify: total path length is reasonable (not circuitous)
   - Performance: cross-zone pathfinding ≤ 100ms for 5-zone path

**Exit Criteria**:

- All viable zones have navmeshes
- Cross-zone pathfinding functional
- Zone connection graph produced
- Validation suite extended for cross-zone paths
- Handoff committed

**Required Artifacts**:

- `scripts/build_all_navmeshes.py` (committed)
- `Exports/navmesh-phase6/navmesh-index.json` (gitignored)
- `Exports/navmesh-phase6/zone-connection-graph.json` (gitignored)
- `docs/handoffs/2026-06-30-navmesh-phase6-scaleout.md` (committed)

---

## Phase 7: Observer-Only Agent (Read-Only Path Watcher)

> **✅ DELIVERED** — `scripts/navmesh_observer.py`

### Design

NM-7 was originally scoped as a bot movement controller (path following +
input injection + state machine).  That design conflicts with the read-only
mandate.  Instead, NM-7 delivers an **observer-only** agent: a CLI tool that
watches the player's live position, computes a path to a goal via the
navmesh, and reports waypoints and progress — but never writes to the game.

### What it does

| Feature | How |
|---|---|
| Live position tracking | ``RIFTMemoryScanner.get_position()`` (read-only) |
| Path computation | Detour A* via ``navmesh_pathfind.find_path()`` |
| Waypoint reporting | Prints OBJ + memory-coordinate waypoints |
| Progress monitoring | Tracks waypoint arrival, remaining distance |
| Off-path detection | Per-segment perpendicular distance check |
| Auto-replan | Recomputes path when deviation persists |
| Continuous watch | ``--watch`` mode polls at configurable interval |

### Safety

The observer stays within ``docs/live-memory-readonly-safety-boundary.md``:

- ✅ Reads player position (proven safe via ``RIFTMemoryScanner``)
- ✅ Uses existing navmesh pathfinding (no new C# code)
- ✅ Outputs to stdout / JSON only
- ❌ No memory writes
- ❌ No input injection
- ❌ No DLL injection
- ❌ No thread suspension

### CLI

```bash
# One-shot: compute path, print waypoints, exit
python scripts/navmesh_observer.py --zone-obj <zone-walkable.obj> --goal 1234,56,789 --once

# Watch mode: continuous progress reporting
python scripts/navmesh_observer.py --zone-obj <zone-walkable.obj> --goal 1234,56,789 --watch

# With dry-run for testing (no live game needed)
python scripts/navmesh_observer.py --zone-obj <zone-walkable.obj> --goal 1234,56,789 --once --dry-run
```

### Entry point

``scripts/navmesh_observer.py`` — standalone script, not registered in
``rift_workflow.py`` or ``rift_read_only.py`` (run directly).

### Original design (preserved for reference)

The original M7.1-M7.3 movement-injection design (path-following controller,
keyboard/mouse simulation, navigation state machine) is preserved in git
history.  It can be resurrected if the safety boundary is ever amended, but
requires an explicit safety review.

---

## Roadmap Summary

| Phase | Topic | Key Artifact | Status |
|-------|-------|-------------|:------:|
| 0 | Recast feasibility & geometry audit | Go/No-Go decision | ✅ |
| 1 | Single-zone navmesh pipeline | `zone-<name>.nav`, build scripts | ✅ |
| 2 | Coordinate system alignment | `coord-transform.json` | ✅ |
| 3 | Pathfinding integration (Detour) | `navmesh_pathfind.py` | ✅ |
| 4 | Runtime bridge (live position) | `navmesh_state.py` | ✅ |
| 5 | Visualization (RiftFlythrough) | Navmesh overlay + path rendering | ✅ |
| 6 | Scale-out & multi-zone | `navmesh-index.json`, cross-zone paths | ✅ |
| 7 | Observer-only agent | ``navmesh_observer.py`` — path watcher | ✅ |

---

## Consumer Contract Summary

When this roadmap completes, consumers can:

```
# Build navmesh for a zone
python scripts/build_navmesh.py --zone Freemarch

# Find a path between two world points
python scripts/navmesh_pathfind.py \
  --zone Freemarch \
  --from 1234.5,56.7,890.1 \
  --to 5678.9,42.3,2345.6 \
  --smooth

# Find a path from live player position to a destination
python scripts/navmesh_pathfind.py \
  --live \
  --to 5678.9,42.3,2345.6

# Export navmesh for visualization
python scripts/export_navmesh_obj.py --zone Freemarch
```

RiftReader integration:

1. Load `navmesh-index.json` to discover available zones
2. Load zone navmesh `.bin` on demand
3. Apply coordinate transform from `coord-transform.json`
4. Query path: `findPath(currentPos, goalPos)`
5. Follow path waypoints; re-project onto navmesh each frame

---

## Dependency Graph

```
Semantic-Discovery Roadmap          Binary-Signature Roadmap
        │                                      │
        ├─ zone vocabulary (Phase 1)           ├─ stable pos_x/pos_z reads
        ├─ walkability hints                   ├─ signature catalog
        │   (hint:map-zone vs actor-object)    │
        │                                      │
        ▼                                      ▼
   Navmesh Navigation Roadmap
        │
        ├─ Phase 0: uses world-placed-merged.obj (FT-8 artifact)
        ├─ Phase 0: uses zone attribution (Cycle 5.2 artifact)
        ├─ Phase 1: uses walkability classification
        ├─ Phase 2: uses live memory position reads
        ├─ Phase 4: uses stable binary signatures
        ├─ Phase 5: integrates with RiftFlythrough
        └─ Phase 6: uses zone vocabulary for partitioning
```

---

## Anti-Drift Rules (All Phases)

1. **This repo only.** No cross-repo edits. Navmesh output goes to the
   phase-specific `Exports/navmesh-phase*/` roots (gitignored).
2. **Recast/Detour is the engine.** No custom mesh or pathfinding algorithms.
   Use the standard library.
3. **Navmesh data is generative.** It is built from geometry, not decoded
   from archives. All `.nav` and `.bin` files are gitignored.
4. **One zone first.** Prove the full pipeline on a single zone before
   scaling.
5. **Coordinate alignment before pathfinding.** Do not implement pathfinding
   until the OBJ↔memory transform is validated.
6. **Visualization before runtime.** Debug the navmesh visually before
   trusting it for live navigation.
7. **Safety-gate movement injection.** Phase 7 requires explicit safety
   review — do not casually implement memory-write movement control.
8. **No new C# parse logic** unless fixing a crash or adding a narrow output
   field.
9. **CI stays green.** No regression on existing 593 Python + 56 dotnet tests.
10. **Consume, don't duplicate.** Use artifacts from semantic-discovery and
    binary-signature roadmaps; do not rebuild their pipelines.

---

## Hard Feasibility Questions (Must Answer in Phase 0)

| # | Question | Risk if "no" |
|:--:|---|---|
| 1 | Does `world-placed-merged.obj` contain ground/terrain geometry? | Open-world navmesh blocked; scope narrows to structure-only |
| 2 | Are NIF world coordinates 1:1 with live memory coordinates? | Transform must be discovered (Phase 2); may be complex if zone-local offsets exist |
| 3 | Can Recast produce a contiguous navmesh from RIFT geometry? | If meshes are too sparse/disconnected, navmesh quality will be poor |
| 4 | Is the unit scale consistent across all assets? | Variable scale requires per-asset normalization |
| 5 | Does pos_y (elevation) come from geometry or a height map? | If from height map, navmesh Y-axis must match terrain Y for correct 3D pathfinding |

---

## Suggested First 10-Day Plan

| Day band | Focus | Deliverable |
|---|---|---|
| 0-1 | Phase 0: Load merged.obj into RecastDemo | Go/No-Go decision documented |
| 1-2 | Phase 0: Walkability classification | `walkability-classification.json` |
| 2-3 | Phase 1: Recast library integration | Python can build navmesh programmatically |
| 3-5 | Phase 1: Zone-filtered OBJ + build pipeline | First zone navmesh built and validated |
| 5-6 | Phase 2: Calibration landmark capture | `coord-transform.json` |
| 6-7 | Phase 3: Detour pathfinding smoke test | `navmesh_pathfind.py` returns valid paths |
| 7-9 | Phase 4: Live position projection | Runtime bridge functional |
| 9-10 | Phase 5: Navmesh → OBJ debug export | Navmesh visible in RiftFlythrough |

---

*This roadmap is the single source of truth for the navmesh navigation phase
of the Assets repo. All work must be traceable to a specific phase and
milestone above.*
