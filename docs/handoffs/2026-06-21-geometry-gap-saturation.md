# Geometry Gap Saturation — Texture Gate Is the Real Ceiling

**Date**: 2026-06-21
**Status**: ✅ ANALYSIS COMPLETE — geometry work cannot grow `consumer_ready` for the 9 unresolved assets; texture gate is the definitive ceiling.

## Finding (Verified)

The user requested pivoting to "geometry gap expansion — probe the 9 unresolved assets for alternate mesh-block combinations to break the geometry gate." After deep analysis, the geometry gate is **not** the bottleneck that prevents these 9 from becoming `consumer_ready`. The real ceiling is the **`textures["linked_texture_count"] > 0`** hard gate in `scripts/build_scene_manifest.py:build_validation()`.

Even if all 9 assets are decoded to `face_count > 0`, the validation will still fail at the texture gate because:

- **5 decoration assets** have `texture_property_count = 0` in their NIF material scan — there are no texture references to link. `linked_texture_count` is permanently 0.
- **4 cycle-3 assets** have `texture_property_count = 1` (NIF-level NiTexturingProperty exists) but **no resolvable DDS references** in the live archive. As shown in commit `c060c98`, the full-archive texture-link scan yields 0 new entries via the additive dedup-merge utility (commit `8a9d862`). `linked_texture_count` is permanently 0.

The texture-link work has reached **terminal saturation** at 779 entries (`7,434` raw → `779` resolved) — there is mathematically no incremental gain available regardless of geometry work.

## Asset-by-Asset Analysis

### Group A: 5 Decoration Pos-Only Assets (tex_props = 0)

These are confirmed decoration geometry. Even with fan faces (from `--experimental-position-source`), they cannot reach `consumer_ready` because they have no textures to link.

| Asset ID | mesh_block | blocks | mesh_size | tex_props | Outcome |
|----------|-----------:|-------:|----------:|----------:|---------|
| 0e0c61ad75d2af1e | 7 | 15 | 193 | 0 | decoration geometry (final) |
| 1601c1f75e0a6022 | 6 | 19 | 272 | 0 | decoration geometry (final) |
| 1e8d2bcc6546b548 | 17 | 22 | 197 | 0 | decoration geometry (final) |
| 35ca1d9dbad6d245 | 7 | 15 | 193 | 0 | decoration geometry (final) |
| b5dc665faa848f85 | 12 | 21 | 214 | 0 | decoration geometry (final) |

These **already** have OBJs in `Assets/build/flythrough/objs/...` (vertex_count > 0, face_count = 0). The `consumer_ready` validation fails on `linked_texture_count > 0`, not on geometry.

### Group B: 4 Cycle-3 tex=1 Assets

These have NIF-level texture properties but **no linkable DDS references** in the live archive. OBJs exist in `Exports/discovery-plan/mesh297-probe/` (`v=4 f=2` — degenerate quads, but technically faced).

| Asset ID | mesh_blocks | tex_props | Outcome |
|----------|------------:|----------:|---------|
| 0d1c9c5d9073ce22 | 22 | 1 | 4v/2f quad; no resolvable DDS |
| 2581c6d1c4ee35b8 | 22 | 1 | 4v/2f quad; no resolvable DDS |
| cfbd6bffb7620092 | 22 | 1 | 4v/2f quad; no resolvable DDS |
| e383643b31af4ff2 | 22 | 1 | 4v/2f quad; no resolvable DDS |

These **ARE NOT** in `flythrough-index.json` (the 227-entry subset). They belong to the broader 81,341-model universe but are out of scope for the RiftFlythrough delivery pipeline. The `consumer_ready` validation doesn't apply because they were never ingested.

## The Hard Gate — Quote from build_scene_manifest.py:291

```python
consumer_ready = (
    geometry["vertex_count"] > 0
    and geometry["face_count"] > 0
    and geometry["has_faces"]
    and materials["material_status"] != "unknown"
    and textures["source"] != "unknown"
    and textures["linked_texture_count"] > 0   # ← hard gate, source of saturation
    and geometry["mesh_block"] is not None
)
```

Today's terminal state for the 9 unresolved assets:

- `linked_textures` is permanently `[]` (no-linkable or tex_props=0)
- `consumer_ready` validation cannot succeed regardless of geometry work

## Recommended Path

**Terminate geometry expansion work** for these 9 assets. The expected gain from geometry work on these 9 is **+0 `consumer_ready` assets**.

### Optional Cosmetic Improvement (Low Value)

The only bounded move remaining is metadata enrichment on Group A:

- Run `python scripts/bulk_export_for_flythrough.py run --asset-ids <5 IDs>` to re-decode with `--experimental-position-source`
- Would update 5 entries in `flythrough-index.json` from `face_count=0` to `face_count>0`
- `render_class` would change from `point-only` to `faced`
- **`consumer_ready` count would remain at 159**, unchanged

This is documentation fidelity, not consumer-grade progress.

## Reference: Saturation Posture

This finding extends the previous saturation analysis (commit `3f0d788` on texture-linkage) into the geometry domain. **Both** the texture-link pipeline AND the consumer_ready geometric payload ceiling have been reached:

| Pipeline stage | State |
|----------------|-------|
| DDS-extract (commit `3203326`-family) | Saturated (no new DDS refs available) |
| Texture-link JSONL (779 lines) | Saturated (per additive dedup-merge analysis) |
| Consumer_ready (`159/227`) | Capped: 9 assets can't pass texture gate |

## Next-Direction Hypotheses (Out of Scope)

1. **LOD variant expansion** — push FT-7 classification 193/217 → 217/217. Metadata-only, no `consumer_ready` change.
2. **Validator relaxation** — explore whether `consumer_ready` can be loosened for material-only decoration (semantic change, not implementation).
3. **Cycle 4 bootstrap** — fresh discovery front on a new signal axis. High risk, high potential.

Sibling repos (RiftFlythrough) untouched. No code changes.
