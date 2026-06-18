# meshSize=297 TEXCOORD Discovery — Cycle 3.1

**Date**: 2026-06-18
**Status**: ✅ COMPLETE — 9 OBJs exported from previously untapped family
**Commits**: `a499fa0` (9-guard recalibration) → mesh297-discovery

## Discovery Path

1. **Guard recalibration** (`a499fa0`): The 3 inventory-dependent guards (attribute_extra, position_source_sibling_lead, residual_lead) were recalibrated from deleted Source/ copied-set baselines to live-archive data. This exposed the meshSize=297 TEXCOORD residual stream in full detail.

2. **Lead identification**: `residual_lead_guard` flagged meshSize=297 @24 TEXCOORD as a "singleton follow-up only" with plausible=0.9074, extent=128.0, 54 float3 vectors.

3. **Deep probe**: `probe-nif-mesh` confirmed `DescriptorClassification: float32xvec3 (position/normal/UV vertex data)` — the TEXCOORD label was a misclassification by the string heuristic.

4. **Decode + export**: `decode-nif-geometry --experimental-position-source --write-obj` successfully exported an OBJ with 54 vertices, 60 faces, CLEAN validation.

5. **Batch export**: 8/9 remaining meshSize=297 assets exported (1 failed: mesh block #6 missing). Total: 9 OBJs, 429 vertices, 435 faces, 0 structural issues.

## Key Findings

| Metric | Value |
|--------|------:|
| Exported OBJs | 9 |
| Total vertices | 429 |
| Total faces | 435 |
| NaN/Inf | 0 |
| Unique IdPrefixes | 10 |
| Mesh blocks in family | 374 |
| Largest mesh | `9f32d26c425ed264` — 247v/245f |
| Failed | `0910220376b18d36` (mesh block #6 missing) |

## Stream Details

- **Offset**: 24
- **Payload**: 648 bytes = 54 vertices × 12 bytes/vert (float3 XYZ)
- **Classification**: float32xvec3 (position/normal/UV vertex data)
- **Label**: TEXCOORD (string-heuristic misclassification)
- **Topology**: degenerate-bridge UInt16BE strip

## Remaining Work

- 374 mesh blocks in the family — only mesh block #6 was probed. Other blocks (#7, #27, etc.) may contain additional geometry.
- 10 unique IdPrefixes — full 32-char IDs for all should be resolved.
- MeshSize=297 isn't in `flythrough-index.json` or `probe-meshsize-lookup.json` — needs integration.

## Resumption

```bash
# Probe another mesh block in the family
dotnet run --project src/RiftAssetDumper -- probe-nif-mesh --id 6f9c38ef4a6e5ab7 --mesh-block 7

# Export all mesh blocks for an asset
python scripts/live_family_scanner.py --probe --export --limit 10 --exhaustive
```

## OBJ Output

```
Exports/discovery-plan/mesh297-probe/
  03bcfae6561407a1/decode-nif-geometry-mesh6.obj  (54v, 60f)
  0d1c9c5d9073ce22/decode-nif-geometry-mesh6.obj  (4v, 2f)
  2581c6d1c4ee35b8/decode-nif-geometry-mesh6.obj  (4v, 2f)
  6f9c38ef4a6e5ab7/decode-nif-geometry-mesh6.obj  (54v, 60f)
  79fda55deefb4435/decode-nif-geometry-mesh6.obj  (54v, 60f)
  9f32d26c425ed264/decode-nif-geometry-mesh6.obj  (247v, 245f)
  cfbd6bffb7620092/decode-nif-geometry-mesh6.obj  (4v, 2f)
  e383643b31af4ff2/decode-nif-geometry-mesh6.obj  (4v, 2f)
  e7358576c7daf7ea/decode-nif-geometry-mesh6.obj  (4v, 2f)
```
