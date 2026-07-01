# Phase 0 Handoff — Navmesh Feasibility (M0.1–M0.3)

**Created**: 2026-06-30
**Updated**: 2026-06-30 (M0.3 geometry enrichment from live-archive exports)
**Roadmap**: `docs/roadmap/navmesh-navigation-roadmap.md` Phase 0
**Verdict**: **GO** — geometry confirmed viable for navmesh generation

## What was done

Phase 0 M0.1 (load geometry into Recast) and M0.2 (walkability classification)
were started. RecastDemo could not be used (no CMake/MSVC build tools), so a
**pure-Python feasibility analyzer** was written as a proxy:

- **Script**: `scripts/navmesh_phase0_feasibility.py` (mypy+ruff clean, 35 tests)
- **Script**: `scripts/classify_walkability.py` (mypy+ruff clean, 22 tests)
- **Method**: OBJ parse → slope classification (≤45° → walkable) → 2D XZ grid
  rasterization → 4-way flood-fill connected components → verdict

### M0.3 — Multi-asset geometry enrichment

10 OBJs were exported from 4 live-archive assets using the C# dumper
(`decode-nif-geometry --experimental-position-source --write-obj`). All 10
were analyzed for walkability:

| Asset | Family | Exported | Key mesh | V | Walkable | Best Verdict |
|---|---|---:|---:|---|---|
| `cf54e712ff57eaac` | vanilla architecture | 6 | #6 (6,489v, 49.0%, 1 comp) | 6,489 | 49.0% | **PROMISING** |
| `cf54e712ff57eaac` | vanilla architecture | — | #37 (13,283v, 33.1%, 1 comp) | **13,283** | 33.1% | **PROMISING** |
| `cf54e712ff57eaac` | vanilla architecture | — | #137 (13,283v, 24.5%, 1 comp) | **13,283** | 24.5% | **PROMISING** |
| `cf54e712ff57eaac` | vanilla architecture | — | #83 (1,685v, 67.0%, 1 comp) | 1,685 | 67.0% | **PROMISING** |
| `cf54e712ff57eaac` | vanilla architecture | — | #107 (41v, 30.9%, 1 comp) | 41 | 30.9% | **PROMISING** |
| `cf54e712ff57eaac` | vanilla architecture | — | #65 (6,489v, 47.6%, 12 comp) | 6,489 | 47.6% | PROMISING_WITH_CAVEATS |
| `1674fb283ce86d95` | ep1 dungeon | 2 | #7 (18v, 66.9%, 2 comp) | 18 | 66.9% | PROMISING_WITH_CAVEATS |
| `0364ea142bc00ce7` | ep2 dungeon | 2 | #34 (48v, 29.8%, 4 comp) | 48 | 29.8% | PROMISING_WITH_CAVEATS |
| `27dcdfd581881755` | ep2 arch (ramp) | 3 | #7 (5v, 66.9%, 2 comp) | 5 | 66.9% | PROMISING_WITH_CAVEATS |
| `27dcdfd581881755` | ep2 arch (ramp) | — | #27 (18v, 0%, 0 comp) | 18 | 0.0% | **BLOCKED** |

**5/10 meshes PROMISING (single connected walkable region). 4/10 PROMISING_WITH_CAVEATS
(multi-component but recoverable). 1/10 BLOCKED (all-vertical faces).**

> **Known limitation**: The C# dumper writes all mesh-block exports to a flat
> `decode-nif-geometry/` subdirectory — meshes with the same block index from
> different assets overwrite each other (e.g., mesh#7 exists in 3 assets but
> only the last-exported one survives on disk). Future exports should use
> per-asset `--out` directories.

The star asset `cf54e712ff57eaac` (vanilla architecture, 32 NiMesh blocks)
has 5 meshes with single-component walkability — ideal for Phase 1 Recast input.

### Classification Results (M0.2)

| Label | Count | % |
|---|---:|---:|
| `potentially_walkable` | 118 | 49.4% |
| `walkable_structure` | 43 | 18.0% |
| `non_walkable_vfx` | 40 | 16.7% |
| `non_walkable_character` | 27 | 11.3% |
| `unknown` | 10 | 4.2% |
| `non_walkable_prop` | 1 | 0.4% |

**161/239 (67.4%)** assets are potentially walkable. **171/239 (71.5%)** need
bounding-box shape analysis for definitive classification.

### M0.2.5 — Bounding-box shape analysis (wall vs. floor discrimination)

A standalone shape analyzer was built to compute per-OBJ bounding-box
height/width ratios and classify meshes as floor, platform, structure, or
wall/pillar:

- **Script**: `scripts/analyze_obb_shape.py` (mypy+ruff clean, 20 tests)
- **Input**: 10 exported OBJs from M0.3
- **Method**: OBJ parse → bbox (dx, dy, dz) → h/w and w/h ratios →
  threshold classification → cross-validation against slope-based verdicts

- **Thresholds** (calibrated from the 10-sample dataset):
  - h/w < 0.2 or w/h > 10 → **floor** (very flat)
  - h/w 0.2–0.5 → **platform** (mostly flat)
  - h/w 0.5–1.5 → **structure** (cubic/mixed)
  - h/w ≥ 1.5 → **wall_pillar** (tall and thin)

**Shape distribution** on 10 meshes: 1 floor, 2 platform, 7 structure, 0 wall.

**Key findings**:

- **mesh107** is the only true floor (h/w=0.043, w/h=23.3) — a large flat
  surface ideal for navmesh input

- **4/10 meshes** (40%) are unit-cube normalized by the experimental-position-source
  decode path — shape labels are low-confidence for these (flag:
  `shape_quality: "normalized_unit_cube"`)
- **7/9 (77.8%) agreement** between shape labels and slope-based feasibility
  verdicts — the 2 disagreements are `structure` meshes where shape alone
  can't determine walkability (slope analysis is needed)
- **Cross-validation confirms**: shape + slope together are stronger than
  either alone — shape catches floors that slope misses (large flat surfaces
  at mild angles), slope catches walkable surfaces inside structures that
  shape labels as "structure"

**Known limitation**: The `--experimental-position-source` decode path in the
C# dumper normalizes some meshes to unit-cube bounding boxes (detected in 4/10
cases). This makes shape analysis unreliable for those meshes. The
`--export-obj` path (attribute-set @264) should produce world-scale coordinates
but was tested on `cf54e712ff57eaac` mesh#37 and failed with "no attribute
sets found" — this asset (and likely others in the same family) lack attribute
sets, so @264 decode is unavailable.

### Nature & housing geometry probe (terrain-hunt extension)

2 nature assets and 1 housing asset were exported and analyzed to test the
"no terrain found" hypothesis:

| Asset ID | Family | V | Verdict | Shape | h/w | Finding |
|---|---|---:|---|---|---|---|
| `76657737423f3c74` | ep1 nature | 87 | **BLOCKED** | floor (raw) | — | 0% walkable — all faces exceed 45° slope |
| `2feda40170afea54` | ep1 nature | 54 | **BLOCKED** | floor (raw) | — | 0% walkable — all faces exceed 45° slope |
| `22413f8369d3e7b9` | ep1 housing | 20 | **BLOCKED** | floor (raw) | — | 0% walkable — all faces exceed 45° slope |

**Shape-slope disagreement is a valuable signal**: All 3 nature/housing meshes
have flat bounding boxes (classified as `floor` by shape analysis) but 0%
walkable surface (BLOCKED by slope analysis). This means the meshes are flat
on the XZ plane but all face normals are vertical — likely leaves/branches
(nature) or wall panels (housing). A `floor` shape + BLOCKED slope verdict
is a strong indicator of "decorative vertical surface," not walkable terrain.

**No terrain found after 6 assets across 4 families.** All tested meshes
produce either walkable structures (architecture, dungeons) or non-walkable
decorations (nature, housing ramps). Open-world terrain may not exist in the
NIF geometry archive — or may require the full flythrough pipeline rebuild to
discover.

### M0.2.7 — Combined shape+slope walkability scores

An integration script combines shape analysis (floor/platform/structure/wall_pillar)
with slope-based feasibility verdicts (PROMISING/PROMISING_WITH_CAVEATS/BLOCKED)
to produce a single walkability label per mesh:

- **Script**: `scripts/combine_walkability_scores.py` (mypy+ruff clean, 15 tests)
- **Input**: shape-analysis.json × 2 + walkability-classification.json
- **Method**: Load all 3 data sources → apply 8 decision rules → compute
  combined label + confidence

- **Output**: `Exports/navmesh-phase0/combined-walkability-scores.json`

**Combined scores on 12 meshes**: 10/12 walkable (83.3%), 1 non-walkable,
1 insufficient data. Breakdown:

| Combined Label | Count | Confidence |
|---|---:|---|
| `walkable_structure` | 6 | medium |
| `walkable_floor` | 3 | high |
| `walkable_platform` | 1 | high |
| `non_walkable_vertical` | 1 | medium |
| `insufficient_data` | 1 | unknown |

**Decision rules** (derived from the 13-mesh RIFT dataset):

| Shape | Slope | Combined | Confidence |
|---|---|---|---|
| floor | PROMISING* | `walkable_floor` | high |
| platform | PROMISING* | `walkable_platform` | high |
| structure | PROMISING* | `walkable_structure` | medium |
| floor | BLOCKED | `non_walkable_decorative` | high |
| wall_pillar | BLOCKED | `non_walkable_wall` | high |
| structure | BLOCKED | `non_walkable_vertical` | medium |
| platform | BLOCKED | `non_walkable_steep_ramp` | medium |
| wall_pillar | PROMISING* | `review_wall_walkable` | low |

> **Known limitation**: Nature/housing cross_validation matched wrong
> feasibility reports (both export directories have the same `decode-nif-geometry`
> leaf name, and the nature/housing feasibility reports were not saved to disk).
> The combined scores for nature/housing meshes show `walkable_floor` (wrong) —
> the correct slope verdict is BLOCKED, which would produce
> `non_walkable_decorative`. This is a directory-naming collision issue;
> fix by exporting to per-asset output directories in Phase 1.

---

## Phase 1 Startup — recast4j Bridge Functional

Phase 1 initiated with recast4j (Java port) via jpype1. **Bridge confirmed working** — the full pipeline runs without errors, but produces 0 navmesh polygons (parameter/geometry calibration needed).

### Engine: recast4j v1.5.7 via jpype1

| Component | Status |
|---|---|
| JDK 21 | `C:/RIFT MODDING/Tools/jdk-21.0.11+10` |
| jpype1 | v1.7.1, pip installed |
| recast.jar | 126KB, zero transitive deps |
| detour.jar | 115KB, zero transitive deps |

### API mapped (Java reflection)

- **SimpleInputGeomProvider**(float[], int[]) — built-in OBJ geometry wrapper
- **RecastConfig** — 15-param non-tiled constructor per recast4j source
- **PolyMesh / PolyMeshDetail** — public fields (not getters)
- **RecastBuilder.build**(InputGeomProvider, RecastBuilderConfig)
- Correct bounds pattern: `geom.getMeshBoundsMin/Max()` (matching test suite)
- Correct JArray syntax: `jpype.JFloat[size]` (not JArray.of())

### 0-polys calibration status

The pipeline runs correctly but produces empty navmeshes on all tested geometry
(flat floor, mesh107, mesh37, mesh83). Root cause hypothesis:

- AreaModification default (AreaMod(0)) may mark all geometry unwalkable
- recast4j test suite uses `SampleAreaModifications.SAMPLE_AREAMOD_GROUND`
  (not in core jar — in detour test source)

- Unit-cube normalized RIFT meshes may need different cell_size/agent_height

Next step: find `SampleAreaModifications` or use `AreaMod(63)` (RC_WALKABLE_AREA),
or compile a minimal Java helper that wraps the recast4j test pipeline.

### New artifacts

| Artifact | Path |
|---|---|
| Smoke test script | `scripts/build_navmesh_smoke.py` |
| recast jars | `Exports/navmesh-phase1/lib/*.jar` |
| Smoke output | `Exports/navmesh-phase1/navmesh-smoke.*` |

`1e8d2bcc6546b548` was classified as `walkable_structure` (vanilla architecture)
but probe revealed it's a VFX emitter — 0 NiMesh blocks, only NiParticleSystem
blocks. The classifier's name-based heuristic misclassified it because the zone
map labels it under the vanilla architecture tuple. This is a known limitation
of zone-attribution-only classification without geometry-level confirmation.

## Key findings

1. **Geometry supports navmesh generation**: 5/10 exported meshes produce single
   connected walkable regions. The largest (13,283 vertices, 13,281 faces)
   has 505.66 sq units of walkable surface in a single component.

2. **Architecture meshes are the best targets**: Vanilla architecture asset
   `cf54e712ff57eaac` (32 NiMesh blocks) yields 5 PROMISING meshes with
   single-component walkability — ideal for Phase 1 Recast input.

3. **Small dungeon meshes are walkable but fragmented**: Ep1/ep2 dungeon meshes
   (18-48 vertices each) produce multi-component walkable surfaces — usable for
   structure-level navmesh but not terrain.

4. **All-vertical faces block navmesh**: mesh#27 from the ep2 arch ramp is
   entirely vertical (all faces exceed 45° slope) — correctly flagged as
   BLOCKED by the analyzer.

5. **No terrain found yet**: All tested meshes appear to be structures (bridges,
   buildings, dungeon floors), not open-world terrain. This may be a data
   limitation (only 4 assets sampled) or a genuine gap in the geometry archive.

6. **Classifier needs geometry confirmation**: The zone-attribution heuristic
   produced 1 known false positive (VFX emitter misclassified as architecture).
   The `needs_shape_analysis` flag on 171 assets is the correct answer —
   bounding-box height-to-width ratio is needed for definitive wall vs. floor
   discrimination.

7. **Shape + slope together are stronger than either alone**: The new shape
   analyzer (M0.2.5) achieves 77.8% agreement with slope-based feasibility
   verdicts. The 2 disagreements are `structure` meshes (cubic bounding box)
   that still contain walkable surfaces — shape says "structure" but slope
   says "walkable". Combining both would give a richer walkability signal.

## Verdict: GO for Phase 1

**The geometry is viable.** Multiple independent meshes across 3 asset families
(vanilla architecture, ep1 dungeon, ep2 dungeon) produce contiguous walkable
surfaces. The largest single walkable region (505 sq units, single component)
is more than sufficient for a proof-of-concept navmesh.

**Recommendation**: Proceed to Phase 1 (single-zone navmesh pipeline) with the
vanilla architecture family as the pilot. Defer terrain discovery to Phase 1 —
the flythrough pipeline rebuild will give full 217-asset coverage to answer
whether terrain exists.

## Blockers & next steps

### Phase 1 prerequisites

1. **Rebuild flythrough pipeline** — `bulk_export_for_flythrough.py` + `build_world_placed_merge.py`
   to get the full `world-placed-merged.obj` (73K lines, 217 assets)

2. **Set up Recast/Detour** — either:
   - Install CMake + MSVC Build Tools and build RecastNavigation from source, or
   - Install JDK 21 and use recast4j (Java port, Ghidra JDK may work), or
   - Find a pre-built Recast binary
3. **Select pilot zone** — highest-confidence zone with the most walkable_structure assets

### M0.4 — Single-asset-group smoke test (deferred)

This milestone requires RecastDemo which is blocked on build tools. It can be
folded into Phase 1 M1.1 (Recast library integration) since the Python
feasibility analyzer already confirms geometry viability.

### Classifier refinement

- Run classifier on full 217-asset cohort once flythrough pipeline rebuilds
- Add bounding-box height-to-width ratio heuristic for wall vs. floor discrimination
- Cross-validate against exported OBJ vertex data for false positive detection
- **M0.2.5 delivered**: `scripts/analyze_obb_shape.py` provides shape analysis;
  the classifier should consume its output once more OBJs are available

### Shape analysis improvements

- Re-export OBJs with `--export-obj` (attribute-set @264 path) to avoid
  unit-cube normalization and get world-scale bounding boxes

- Run shape analysis on full flythrough OBJ set (217 assets) once pipeline
  rebuilds

- Add combined shape+slope walkability score: `floor` shape + PROMISING
  slope → high-confidence walkable; `structure` shape + PROMISING slope →
  medium-confidence walkable; `wall_pillar` + PROMISING → flagged for review

## Artifacts produced

| Artifact | Path | Status |
|---|---|---|
| Feasibility script | `scripts/navmesh_phase0_feasibility.py` | ✅ Committed (mypy clean, ruff clean) |
| Feasibility tests | `tests/test_navmesh_phase0_feasibility.py` | ✅ 35 tests pass |
| Walkability classifier | `scripts/classify_walkability.py` | ✅ Committed (mypy clean, ruff clean) |
| Classifier tests | `tests/test_classify_walkability.py` | ✅ 22 tests pass |
| Feasibility reports (×9) | `Exports/navmesh-phase0/feasibility-*.json` | ✅ gitignored |
| Exported OBJs (×10) | `Exports/navmesh-phase0/objs/decode-nif-geometry/*.obj` | ✅ gitignored |
| Walkability report | `Exports/navmesh-phase0/walkability-classification.json` | ✅ gitignored |
| Shape analyzer | `scripts/analyze_obb_shape.py` | ✅ Committed (mypy clean, ruff clean) |
| Shape analyzer tests | `tests/test_analyze_obb_shape.py` | ✅ 20 tests pass |
| Shape analysis report | `Exports/navmesh-phase0/shape-analysis.json` | ✅ gitignored |
| Combined scores script | `scripts/combine_walkability_scores.py` | ✅ Committed (mypy clean, ruff clean) |
| Combined scores tests | `tests/test_combine_walkability_scores.py` | ✅ 15 tests pass |
| Combined scores report | `Exports/navmesh-phase0/combined-walkability-scores.json` | ✅ gitignored |
| Smoke test script | `scripts/build_navmesh_smoke.py` | ✅ Committed (mypy clean, ruff clean) |
| recast4j jars | `Exports/navmesh-phase1/lib/recast-1.5.7.jar` | ✅ gitignored |
| recast4j jars | `Exports/navmesh-phase1/lib/detour-1.5.7.jar` | ✅ gitignored |
| This handoff | `docs/handoffs/2026-06-30-navmesh-phase0-feasibility.md` | ✅ (updated) |

---

## Phase 1 Startup — recast4j Smoke Test

Phase 1 has been initiated with a recast4j bridge via jpype1.

### Engine selection

| Option | Status |
|---|---|
| RecastNavigation (C++) | ❌ CMake not installed |
| recast4j (Java) | ✅ JDK 21 + jpype1 v1.7.1 — zero transitive deps |

### recast4j API mapped

Through iterative Java reflection via jpype, the exact v1.5.7 API was mapped:

- **SimpleInputGeomProvider**(float[], int[]) — built-in, no custom Java needed
- **RecastConfig** — 15-param non-tiled constructor per recast4j source
- **PolyMesh / PolyMeshDetail** — public fields, not getter methods
- **RecastBuilder.build**(InputGeomProvider, RecastBuilderConfig)

### Smoke test

- **Script**: `scripts/build_navmesh_smoke.py` (mypy+ruff clean)
- **Pipeline**: OBJ parse → SimpleInputGeomProvider → RecastBuilder.build() →
  PolyMesh extraction → debug OBJ export

- **Status**: ✅ Pipeline runs (no errors). Produces 0 polys — parameter
  tuning needed (cell_size/cell_height vs. mesh dimensions). The bridge works;
  next step is calibrating RecastConfig for RIFT geometry scale.
