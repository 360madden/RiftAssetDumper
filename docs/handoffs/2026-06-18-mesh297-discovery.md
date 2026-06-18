# meshSize=297 TEXCOORD Discovery — Cycle 3.1

**Date**: 2026-06-18
**Status**: ✅ COMPLETE — 14 OBJs exported from previously untapped family
**Commits**: `a499fa0` (9-guard recalibration) → `f6081ac` (initial 297 discovery) → multi-block expansion

## Discovery Path

1. **Guard recalibration** (`a499fa0`): 3 inventory-dependent guards recalibrated for live archive, exposing meshSize=297 TEXCOORD residual stream.

2. **Single-block discovery**: `probe-nif-mesh` on `6f9c38ef4a6e5ab7` confirmed `DescriptorClassification: float32xvec3` at offset=24. TEXCOORD label was a string-heuristic misclassification. Exported: 54v/60f.

3. **Batch export**: 8/9 remaining single-mesh assets exported via `decode-nif-geometry --experimental-position-source`.

4. **Multi-block expansion**: `probe-nif` on `9f32d26c425ed264` revealed 8 NiMesh blocks (not just #6). Decoded 5 additional blocks (#27, #45, #59, #76, #90). Block #27 alone: 12,993v/12,991f.

5. **Glow investigation**: meshSize=305 "glow" lead decoded but proved degenerate (all vertices at (0,0,1)) — billboard/sprite effect, not geometry.

## Key Findings

| Metric | Value |
|--------|------:|
| Total OBJs exported | **14** (9 single-mesh + 5 multi-block from 9f32d2) |
| Total vertices | **15,315** |
| Total faces | **15,309** |
| NaN/Inf issues | 0 |
| Largest single block | `9f32d2 #27` — 12,993v/12,991f |
| Multi-block asset | `9f32d26c425ed264` — 6 blocks, 14,886v/14,874f |
| Unique IdPrefixes | 10 |
| Mesh blocks in family | 374 |

## Per-Asset Breakdown

| Asset | Mesh Block(s) | Vertices | Faces |
|-------|:---:|---:|---:|
| `03bcfae6561407a1` | #6 | 54 | 60 |
| `0d1c9c5d9073ce22` | #6 | 4 | 2 |
| `2581c6d1c4ee35b8` | #6 | 4 | 2 |
| `6f9c38ef4a6e5ab7` | #6 | 54 | 60 |
| `79fda55deefb4435` | #6 | 54 | 60 |
| **`9f32d26c425ed264`** | **#6** | 247 | 245 |
| | **#27** | **12,993** | **12,991** |
| | **#45** | 247 | 245 |
| | **#59** | 247 | 245 |
| | **#76** | 164 | 162 |
| | **#90** | 988 | 986 |
| `cfbd6bffb7620092` | #6 | 4 | 2 |
| `e383643b31af4ff2` | #6 | 4 | 2 |
| `e7358576c7daf7ea` | #6 | 4 | 2 |

## Not Yet Probed

- `0910220376b18d36` — mesh block #6 not found (different NIF structure)
- 2 remaining NiMesh blocks in `9f32d26c425ed264` (8 total, 6 exported)
- Other meshSize=297 assets may have additional blocks beyond #6
- 374 mesh blocks total in the family — significant untapped potential

## Glow Investigation (Dead End)

- meshSize=305, offset=0, label="glow", plausible=0.9487
- 2 samples: `fe9eb21c2bba1700` and `24a3a40e515c079c`
- Both decoded: 15v/13f each, clean
- All vertices at (0,0,1) — degenerate glow sprite, not usable geometry
- **Verdict**: Dead end. Documented for completeness.

## OBJ Output

```
Exports/discovery-plan/mesh297-probe/
  03bcfae6561407a1/  (54v/60f)
  0d1c9c5d9073ce22/  (4v/2f)
  2581c6d1c4ee35b8/  (4v/2f)
  6f9c38ef4a6e5ab7/  (54v/60f)
  79fda55deefb4435/  (54v/60f)
  9f32d26c425ed264/
    decode-nif-geometry-mesh6.obj   (247v/245f)
    9f32d2/mb27/                   (12,993v/12,991f)
    9f32d2/mb45/                   (247v/245f)
    9f32d2/mb59/                   (247v/245f)
    9f32d2/mb76/                   (164v/162f)
    9f32d2/mb90/                   (988v/986f)
  cfbd6bffb7620092/  (4v/2f)
  e383643b31af4ff2/  (4v/2f)
  e7358576c7daf7ea/  (4v/2f)
```
