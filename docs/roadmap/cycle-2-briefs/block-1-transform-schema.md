# C2-V4P12 Brief — Transform, Coordinate, and Scene-Manifest Schema

**Prepared**: 2026-06-15  
**Use with**: V4 Pro / stronger-reasoning review block  
**Input evidence**:

- `Assets/Exports/discovery-plan/cycle-2/stage2/transform-examples.json`
- `Assets/Exports/discovery-plan/cycle-2/stage2/pattern-comparison.md`
- `Assets/Exports/discovery-plan/cycle-2/stage2/semantics.md`
- `Assets/Exports/discovery-plan/cycle-2/stage2/coordinate-contract.md`
- `Assets/Exports/discovery-plan/cycle-2/stage2/schema-sketch.md`
- `Assets/Exports/discovery-plan/cycle-2/stage2/scene-manifest-v1.draft.schema.json`
- `Assets/Exports/discovery-plan/cycle-2/stage2/sample-manifest-07f37c99a80da009.json` (first sample, non-id)
- `Assets/Exports/discovery-plan/cycle-2/stage2/C2-2.4-iteration-notes.md` (4 schema gaps for this review)
- `scripts/validate_scene_manifest_schema.py` (C2-2.4 acceptance: schema validates as JSON Schema 2020-12)

---

## V4P12 input brief

Cycle 2’s goal is consumer visual fidelity: decoded meshes must become
**placed, textured, consumer-usable world assets**. Current RiftFlythrough
evidence shows geometry can render, but visual proof is failing because source
identity, material/texture linkage, and world placement are not yet carried as
a durable consumer contract.

### Current evidence

| Signal | Result |
|---|---:|
| v0.3 cohort size | 26 |
| Transform examples available | 26/26 |
| Non-identity transform assets | 4 |
| Identity transform assets | 22 |
| Full flythrough scale check | 217/217 scale = 1.0 |
| Transform field finiteness | 26/26 finite |
| First sample manifest built | `07f37c99a80da009` (non-id, translation `[8.82, -0.85, 0.08]`, `consumer_ready=false`) |
| Schema validator | exits 0 on the draft schema + first sample |

### Draft decisions from M3

| Area | Draft decision |
|---|---|
| Transform truth | Mesh `ParentNiNodeIndex` parent-chain accumulation |
| Authoritative placement source | Existing `world.json` / `scene-graph/v1` sidecar |
| Manifest placement role | Carry summary + link to `world_json`; do not replace full per-mesh scene graph |
| Handedness/up/forward | Right-handed, Y-up, `-Z` forward candidate |
| Rotation | 3x3 row-major matrix; no canonical quaternion in v1 |
| Scale | Uniform float; keep field although current subset is all 1.0 |
| Composition | `v_world = R * (S * v_local) + T` |
| Identity tolerance | `1e-6` |

### Requested V4P12 output

Return a concise decision doc with:

1. **Transform truth model** — accept/revise mesh-parent-chain semantics and
   decide if v1 requires `world_transform_summary`, `world_json`, or both.
2. **Coordinate contract** — accept/revise right-handed/Y-up/`-Z` forward,
   row-major 3x3, uniform scale, and `1e-6` identity tolerance.
3. **Scene-manifest v1 field set** — accept/revise the draft schema shape:
   `geometry`, `world`, `materials`, `textures`, `provenance`, `validation`.
   For each of the 4 schema gaps, return one of: `accept` (lock as-is),
   `revise` (specify the change), or `defer` (park for a later V4 Pro session
   with rationale).

### Validation gate

Before declaring V4P12 complete, the locked schema must pass
`scripts/validate_scene_manifest_schema.py --schema <locked-path>` with exit
code 0, AND the first sample
`Assets/Exports/discovery-plan/cycle-2/stage2/sample-manifest-07f37c99a80da009.json`
must validate against the locked schema with the same exit code.

### Hard constraints

- Do not require consumers to infer transforms from OBJ geometry alone.
- Do not drop source asset IDs/hashes during merge/export.
- Do not classify material/vertex-color-only assets as generic missing-texture
  failures without evidence.
- Do not lock a schema that cannot distinguish schema faults from
  RiftFlythrough consumer/rendering faults.
- The draft schema **must** validate as JSON Schema 2020-12 (acceptance met via
  `scripts/validate_scene_manifest_schema.py`; lock must preserve this).

### Open questions

1. Should coordinate-system fields be per-entry or pack-level?
2. Should point-only geometry be valid v1 or debug-only?
3. Should placeholder textures be warnings or hard consumer-ready errors?
4. Should material/vertex-color-only assets count as materialized for C2-3?
5. Should non-identity assets be required C2-5 screenshot fixtures?
6. **Should `Geometry` require `vertex_count > 0` AND `face_count > 0` for
   `consumer_ready=true`?** (Schema gap #1; current draft is too permissive.)
7. **Should `Materials` carry a `scanned_at` timestamp** to distinguish
   "scanned, found zero" from "never scanned"? (Schema gap #2.)
8. **Should `geometry.obj_sha1` be added** for cross-schema consistency with
   `asset-mesh-manifest-v1`? (Schema gap #3.)
9. **Should `world.accumulated_transform` vs `declared_transform` be split?**
   (Schema gap #4; current `world_transform_summary` collapses both.)

## Identity cohort scale-out (C2-2.4 batch)

- **5 identity manifests built** via `python scripts/build_scene_manifest.py --asset-id <id>` for the first 5 distinct identity asset IDs from `transform-examples.json`
- **9/9 manifests validate** against `scene-manifest-v1.draft.schema.json` with exit code 0 (4 non-id + 5 id)
- **4 contrast tests added** to `tests/test_build_scene_manifest.py`: `test_find_id_asset_ids_returns_nonzero`, `test_identity_manifests_have_identity_transform`, `test_non_id_manifests_have_non_identity_transform`, `test_both_cohorts_share_consumer_ready_false`
- **Schema-scale contrast**: 4 non-id (`world_transform_identity=false`, translation != 0) + 5 id (`world_transform_identity=true`, translation=`[0,0,0]`). Both cohorts share `consumer_ready=false` until the C2-3.x extraction pass runs (the gate is about data extraction completeness, not transform identity)

## Identity cohort source-data dedupe (C2-2.4 follow-on)

- **identity_examples count collapsed 22 -> 20**: original list had 2 internal duplicate pairs (entries 18=19 both `1ecdbaf5a2576ba5`; entries 6=20 both `42024b768fcd2e2b`). Dedupe pass preserves first-occurrence order; no asset_ids were added or removed on disk.
- **non_identity_examples unchanged**: same dedupe audit was not needed (4 distinct entries, no internal duplicates).
- **Source-of-truth updated**: `transform-examples.json._meta.identity_examples_dedup_notes` records the change. Cohort definition = **24 total (4 non-id + 20 distinct id)**, matching the 24 on-disk `sample-manifest-*.json` files.
- **Test pinned**: `test_find_id_asset_ids_returns_nonzero` now asserts `len(ids) == 20` and uniqueness, so cohort regressions are caught at the test level (loose `> 0` would have silently passed against any future shrinkage).

## C2-3.1 texture coverage input

- **Profiler shipped**: `scripts/build_texture_coverage.py` + `tests/test_build_texture_coverage.py` (17 tests). Profiling matrix combines scene-manifest `textures` block (from C2-2.4 sample-manifests) AND flythrough-index.json `linked_textures` (from FT plan Phase 21).
- **Output**: `Assets/Exports/discovery-plan/cycle-2/stage3/texture-coverage.{json,md}` — 24/24 cohort assets profiled.
- **Headline finding**: **23 of 24 cohort assets (~96%) show `scene.linked_texture_count=0` vs `fly.linked_textures.count>0`**. Reading: the scene-manifest stage2 builder (`scripts/build_scene_manifest.py`) reads only `world.json` (carrying `ParentNiNodeIndex` + transforms), which has no texture bindings. So `textures.linked_texture_count` is naturally 0 for the whole cohort. Meanwhile, flythrough-index has texture data for 207/217 assets (Phase 21 linkage database). The 23 vs 1 disparity is the **structured signal**, not random noise.
- **NEW schema gap (proposed by M3)**: add `textures.source: "scene"|"flythrough"|"unknown"` enum to the v1 draft schema. This forces every scene-manifest `textures` block to declare its source-of-truth, and unlocks honest future coverage profiling. Without this discriminant, downstream consumers cannot tell where a `linked_texture_count` came from.
- **producer.command pattern**: the texture-coverage producer carries the full CLI command + input file list, so the run is reproducible byte-for-byte from any future state.
- **Implication for `consumer_ready` gating**: V4 Pro should consider making `consumer_ready=true` require (a) `textures.source` is set to a known value AND (b) `linked_texture_count > 0 OR linked_textures is genuinely empty (textureless surfaces are valid)`. The current draft schema's `consumer_ready` gate is silent on texture source.
- **Full evidence**: `docs/handoffs/2026-06-16-c2-3.1-firing.md` — data-led handoff with M3's priority recommendation: this gap should rank **highest** among the 5 schema gaps V4 Pro must resolve (above the 4 originally listed in the Open questions section).
