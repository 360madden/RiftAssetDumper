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

---

## One-page brief

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

### Hard constraints

- Do not require consumers to infer transforms from OBJ geometry alone.
- Do not drop source asset IDs/hashes during merge/export.
- Do not classify material/vertex-color-only assets as generic missing-texture
  failures without evidence.
- Do not lock a schema that cannot distinguish schema faults from
  RiftFlythrough consumer/rendering faults.

### Open questions

1. Should coordinate-system fields be per-entry or pack-level?
2. Should point-only geometry be valid v1 or debug-only?
3. Should placeholder textures be warnings or hard consumer-ready errors?
4. Should material/vertex-color-only assets count as materialized for C2-3?
5. Should non-identity assets be required C2-5 screenshot fixtures?
