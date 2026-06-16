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
