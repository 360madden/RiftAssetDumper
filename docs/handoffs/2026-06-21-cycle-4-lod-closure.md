# Cycle 4.1 — LOD-Aware Closure (Session Handoff)

**Date**: 2026-06-21
**Status**: ✅ COMPLETE — 227/227 flythrough assets classified; 9/9 proof guards PASS; pytest 41/41
**Commit**: `29d6710` — `feat(cycle4): LOD-aware closure for 34 unclassified flythrough assets`

## Saturation Context

Cycle 2/3 saturated along the texture-link axis:

| Axis | Cap | Reason |
|---|---|---|
| Texture-link JSONL (779 lines) | saturated | full-archive rescan yielded 0 new entries |
| `consumer_ready` | **159/227** | `textures.linked_texture_count > 0` hard gate is the ceiling |
| Geometry (9 unresolved) | 0 gain | the gap is on the texture gate, not geometry |

Cycle 4 picks a **fresh discovery axis** — LOD-aware rendering — that bypasses both
the texture gate and the geometry gate. Even if `consumer_ready` doesn't grow, the
metadata unlocks downstream LOD-aware rendering decisions.

## What Shipped

### Scripts

- **`scripts/cycle4_lod_metadata.py`** (v0.1) — idempotent enricher
  - **Heuristic 1**: MeshSize-family vertex-rank (group by `mesh_size`, rank by `vertex_count` desc)
  - **Heuristic 2**: singleton detection (`family_size == 1` → `lod_type="singleton"`)
  - **Heuristic 3**: absolute-vertex-count tier (mesh_size=None, p80/p20 quantiles)
  - Atomically patches stage6 manifests with:
    - `geometry.lod_index` (int, ≥ 0)
    - `geometry.lod_type` (enum: `singleton` | `low` | `medium` | `high`)
    - `geometry.lod_tier_count_in_family` (int, ≥ 1)
    - `producer.cycle4_producers`, `producer.cycle4_version`, `producer.cycle4_last_applied`
  - **Atomic write** (tmp + os.replace), **idempotent re-runs**, **cleans stale `last_updated_at`**

### Tests

- **`tests/test_cycle4_lod_metadata.py`** (8 tests):
  - MeshSize-family rank test
  - Singleton detection test
  - Absolute-vertex-count tier test
  - Atomic write test (no `.tmp` leak)
  - Idempotent re-run test (cycle4_producers no-dup)
  - Markdown render test
  - Producer stamp + legacy fields cleanup test
  - **jsonschema acceptance test** (end-to-end contract lock against the locked schema)

### Schema Extension

- **`Assets/Exports/discovery-plan/cycle-2/stage2/scene-manifest-v1.schema.json`** (force-added; force-overrides gitignore so a fresh clone has the schema):
  - Whitelists `geometry.{lod_index, lod_type, lod_tier_count_in_family}` (strict integers; enum for `lod_type`)
  - Whitelists `producer.{cycle4_producers, cycle4_version, cycle4_last_applied}`
  - Schema stays strict (`additionalProperties: false`) for all other fields
  - **Matches v0.6/v0.7/v0.8 schema-evolution precedent**

## Runtime Result

| Metric | Value |
|---|---:|
| Flythrough total | **227** |
| Previously classified (FT-7.2) | 193 |
| Newly classified (Cycle 4.1) | **34** |
| Manifests patched (OK) | **34** |
| Manifests patched (FAILED) | 0 |
| High tier | 5 |
| Medium tier | 19 |
| Singleton tier | 10 |
| Mesh-family rank | 14 |
| Family-rank | 10 |
| Absolute tier | 10 |
| Manifest validation | **241/241 PASS** |
| pytest | **41/41 PASS** |
| ruff | **0 errors** |
| mypy | **0 errors** |

## Classification Examples (top tier)

Tier=high (5 assets):

| Asset | mesh_size | vertex_count |
|---|---:|---:|
| `0910220376b18d36` | 297 | largest cycle-3 single-block export |
| `9f32d26c425ed264` | 297 | 8 NiMesh blocks decoded |
| `51d6c99244779406` | — | dense world geometry |
| `96bedfae4bd7dd40` | 297 | rank-1 of family |
| `9a813814bba6478e` | 297 | rank-2 of family |

## Tier Distribution Notable

| Tier | Count | Examples |
|---|---:|---|
| **singleton** | 10 | `b5dc665faa848f85` (decoration), `1e8d2bcc6546b548` (decoration), `0603cce7cee15eb8` |
| **high** | 5 | `0910220376b18d36`, `9f32d26c425ed264`, +3 |
| **medium** | 19 | mesh_size=297 dense family + cycle-3 unresolved + friendlier entries |

## Evidence

| File | Contents |
|---|---|
| `Assets/build/flythrough/evidence/cycle4.1/lod-closure.json` | full classification evidence (gitignored FT pipeline output) |
| `Assets/build/flythrough/evidence/cycle4.1/LOD_CLOSURE.md` | markdown summary of tier + reason distributions |
| 34 stage6 manifests at `Assets/Exports/discovery-plan/cycle-2/stage6/manifest-*.json` | now carry `geometry.lod_*` + `producer.cycle4_*` |

## Why Schema Extension (vs. Sidecar)

Code-reviewer and 9th guard both pointed toward the locked schema's strict
`additionalProperties: false` would reject the new fields. Three options were
considered:

1. **Extend locked schema** (chosen) — matches v0.6/v0.7/v0.8 schema-evolution
   precedent; consumer-facing contract stays unified in one file
2. **Sidecar JSON per asset** — defensible but downstream RiftFlythrough must
   open 2 files instead of 1; rejected
3. **Revert patches, redesign later** — loses the metadata, rejected

## Schema Migration TODO (Tracked Issue)

The schema lives at `Assets/Exports/discovery-plan/cycle-2/stage2/` which is
gitignored (per the `.gitignore` rule that excludes `Exports/`). This commit
force-added the schema (`git add -f`) so a fresh clone gets it.

**TODO(cycle4+, follow-up)**: migrate the schema to **`docs/schemas/scene-manifest-v1.schema.json`**
to match the tracked schema convention used by other schemas:

- `docs/schemas/scene-graph-v1.schema.json`
- `docs/schemas/post50-*.schema.json`  
- `docs/schemas/residual-*.schema.json`

Update the 5 reference sites:

| File | Line | Reference |
|---|---:|---|
| `scripts/build_scene_manifest.py` | 53 | `SCHEMA_PATH = ...` |
| `scripts/rift_workflow_guards.py` | 2629 | (9th guard schema load) |
| `scripts/build_aggregate_stats.py` | 28 | `MANIFEST_SCHEMA_PATH = ...` |
| `tests/test_scene_manifest_validation.py` | 29 | `SCHEMA_PATH = ...` |
| `tests/test_validate_scene_manifest_schema.py` | 43 | (test fixture) |

After migration, all references simplify to `docs/schemas/scene-manifest-v1.schema.json`
and the force-add hack can be removed.

## State at Handoff

- HEAD: `29d6710` (pushed to `origin/main`)
- Working tree: clean
- Schema → tracked (`git add -f` workaround with TODO to migrate)
- 9/9 proof guards PASS
- pytest 475/475 + 41 (incl. 8 cycle4) PASS

## Next-Free Pivot Hypotheses

After cycle 4 ships, remaining unverified axes:

1. **Sibling grouping** (cross-MeshSize ladders) — provably distinct from LOD-many;
   could expand OBJs via shared-source pattern (but capped by texture gate)
2. **Shader parsing** (NSL programs in NIF v20.6.0.0) — entirely unexplored; high
   risk, high potential for materials beyond `NiTexturingProperty`
3. **Asset semantic index reuse** (`build-asset-semantic-index`) — currently
   dormant in `scripts/discovery-matrices/nif-semantic-hints.json`; could surface
   categories like `hint:map-zone` for downstream routing
