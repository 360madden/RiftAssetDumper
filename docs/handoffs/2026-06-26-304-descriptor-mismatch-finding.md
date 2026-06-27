# Discovery: @304 Descriptor/Format Mismatch on mesh#34 (meshSize=329)

**Date**: 2026-06-26
**Type**: Discovery Finding (candidate-only)
**Status**: Evidence documented, no parser/export behavior change

---

## Summary

The `@304/#57` extra stream on mesh#34 in the meshSize=329 family has a **descriptor/format mismatch**: the embedded descriptor `36040200` says `float32xvec2` (matching the known UV stream on mesh#7), but the role classifier identifies the byte pattern as `position-float3-ror1-lead` and decoded values are position-like in magnitude but don't match the primary position stream.

## Evidence

### Asset: `0364ea142bc00ce7`

| Stream | Mesh | Offset→Block | Payload | Descriptor | Role | Vectors |
|:--|:--|:--|---:|:--|:--|---:|
| #28 | #7 | @212→#28 | 576B | `37040300` float32xvec3 | position-float3-ror1-lead | 48 |
| #29 | #7 | @220→#29 | 576B | `37040300` float32xvec3 | normal-float3-ror1-lead | 48 |
| #32 | #7 | @296→#32 | 192B | `10010400` bytexvec4 | u32-repeated-pattern-body | 48 |
| #33 | #7 | @304→#33 | 384B | **`36040200` float32xvec2** | uv-float2-ror1-lead | **48** |
| #28 | #34 | @212→#28 | 576B | `37040300` float32xvec3 | position-float3-ror1-lead | 48 |
| #53 | #34 | @220→#53 | 360B | `37040300` float32xvec3 | normal-float3-ror1-lead | **30** |
| #32 | #34 | @296→#32 | 192B | `10010400` bytexvec4 | u32-repeated-pattern-body | 16 |
| **#57** | **#34** | **@304→#57** | **240B** | **`36040200` float32xvec2** | **position-float3-ror1-lead** | **20 (f3) / 30 (f2)** |

### Key observations

1. **Same descriptor, different roles**: Stream #33 (mesh#7) and #57 (mesh#34) both have descriptor `36040200` (float32xvec2). On mesh#7, the role is UV (48 vectors = vertex count). On mesh#34, the role classifier says position-float3 (20 vectors ≠ vertex count 48).

2. **Decoded value comparison** (ror1 float3):
   - @212 position v0: ~(11.97, 38.4, 1.04) — world-space position range
   - @304 extra v0: ~(97.6, 19.6, 9.76) — position-like magnitude but **different range**
   - @304 vectors cluster tightly: X≈9.7, Y≈19.7, Z≈9.75 across all 5 visible vectors

3. **Vector count mismatch**: @304 payload=240 gives 20 vectors as float3 or 30 vectors as float2. Neither consistently matches the primary position count (48) nor the normal count (30) across all 12 samples.

4. **Tight clustering**: The @304 decoded float3 values cluster in a very narrow range (~0.1 extent) around (9.7, 19.7, 9.75). This is inconsistent with per-vertex position data (which should have wider extent) but could indicate reference points, anchor positions, or bounding box centers.

### Cross-sample evidence (12 mesh#34 IDs)

- Extra payloads: 96, 240, 280 bytes
- Extra remainder mod 12: 0, 4 (mostly float3-aligned)
- `0xC2` in byte positions 2-5: 11/12 samples (consistent with ror1 float3 pattern)
- Shared prefix bytes (4B/8B/16B): 0/0/0 (no fixed header — data varies per asset)

## Interpretation

The @304 stream on mesh#34 is a **secondary position-like data stream** with a descriptor that doesn't match its actual content. Possible interpretations:

1. **Reference points / anchor positions**: Tight clustering around a single point suggests these are not per-vertex geometry but reference locations
2. **Descriptor reuse**: The `36040200` descriptor may be a default/fallback that doesn't reflect the actual data format in this mesh block context
3. **LOD or collision data**: Secondary position data for simplified geometry or physics

## Impact on promotion gates

This finding keeps the `mesh34-complete-geometry-binding` gate blocked:

- mesh#34 has 4 streams but they don't form a standard position+normal+UV+index binding
- The @304 stream is not UV data despite the float2 descriptor
- The @304 vector count doesn't match any primary attribute count consistently
- mesh#34 has 0 attribute sets and 0 UV streams

## Next steps

- Investigate whether @304 values correlate with mesh bounding box centers or transform origins
- Check if the tight cluster point appears in the NIF scene graph (NiNode transform?)
- Determine if the descriptor mismatch is a known Gamebryo pattern (descriptor as "hint" not "type")
- Explore meshSize=326 source-binding-family (23 evidence groups) as alternative promotion path
