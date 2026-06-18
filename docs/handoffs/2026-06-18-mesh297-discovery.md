# meshSize=297 TEXCOORD Discovery — Cycle 3.1 COMPLETE

**Date**: 2026-06-18
**Status**: ✅ COMPLETE — 17 OBJs exported from previously untapped family
**Commits**: `a499fa0` (guard recalibration) → `f6081ac` (initial) → `3b31989` (multi-block) → final

## Final Results

| Metric | Value |
|--------|------:|
| Total OBJs | **17** |
| Total vertices | **55,805** |
| Total faces | **55,795** |
| NaN/Inf issues | 0 |
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
| **`0910220376b18d36`** | **#7** | **38,957** | **38,955** |
| `cfbd6bffb7620092` | #6 | 4 | 2 |
| `e383643b31af4ff2` | #6 | 4 | 2 |
| `e7358576c7daf7ea` | #6 | 4 | 2 |
| **`9f32d26c425ed264`** | #6 | 247 | 245 |
| | #27 | 12,993 | 12,991 |
| | #45 | 247 | 245 |
| | #59 | 247 | 245 |
| | #76 | 164 | 162 |
| | #90 | 988 | 986 |
| | #103 | 1,424 | 1,422 |
| | #117 | 356 | 354 |

## Discovery Iterations

1. **TEXCOORD lead** (offset=24, plausible=0.9074): String heuristic misclassified `float32xvec3` position data as TEXCOORD
2. **Single-block batch export**: 8/9 assets exported (1 failed — mesh at block #7 not #6)
3. **Multi-block discovery**: `9f32d26c425ed264` revealed 8 NiMesh blocks
4. **Failed asset recovery**: `0910220376b18d36` block #7 — the largest single-block export in project history

## Glow Lead (Dead End)

- meshSize=305, offset=0, label="glow", plausible=0.9487
- Decoded but geometrically degenerate — all vertices at (0,0,1)
- Confirmed: glow sprite/billboard effect, not usable geometry
