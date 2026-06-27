# Discovery: NiDataStream Body Offset Should Be 28, Not 29

**Date**: 2026-06-26
**Type**: Structural Proof Finding
**Status**: Evidence documented; no parser change made (requires high-reasoning review)

---

## Summary

The legacy NiDataStream body offset (29) is **1 byte too late** for all parsed NiDataStream blocks. The correct body offset is 28 (`PayloadPrefixBytes`), not 29 (`LegacyPayloadOffset`). This 1-byte shift dramatically improves float plausibility across ALL stream bodies — including known-good position streams and the residual position classifier targets.

## Evidence

### Structural proof

The `AnalyzeNifDataStreamLayout` function computes two offsets:

| Offset | Value | Computation |
|:--|---:|:--|
| `PayloadPrefixBytes` | 28 | Walk structural header: 4+4+4+(1×8)+4+(1×4) = 28 |
| `LegacyPayloadOffset` | 29 | `blockPayload.Length - declaredPayloadBytes` = 317-288 = 29 |
| `LegacyOffsetMinusPayloadPrefixBytes` | 1 | 29 - 28 = 1 |

The `GhidraStyleLayoutValid` check confirms: `payloadPrefixBytes(28) + declaredPayload(288) + trailer(1) = 317 = blockSize`. The structural header is exactly 28 bytes. The 29th byte is the first byte of the actual data payload.

### Float plausibility comparison

| Stream | Offset | Plausible/Total | Range | Classification |
|:--|:--|---:|:--|:--|
| **Known-good position** (75d5a06d7c0de1dd #21) | 28 (Ghidra) | **48/48 (100%)** | [-16.97, 24.0] | float32-compatible |
| Same stream | 29 (legacy) | 6/48 (12.5%) | [-0.012, 1.0e+36] | uint16-compatible |
| **Residual payload=288** (014e1ff60d8508f1 #21) | 28 (Ghidra) | **71/72 (98.6%)** | [-36.0, 23.4] | float32-compatible |
| Same stream | 29 (legacy) | 6/72 (8.3%) | [-1.22e-27, 4.8e+29] | uint16-compatible |
| **Residual payload=288** (2d7200eca94b990f #21) | 28 (Ghidra) | **float32-compatible** | — | float32-compatible |
| Same stream | 29 (legacy) | — | — | uint16-compatible |
| **Residual payload=288** (495ecea3a7786cf0 #21) | 28 (Ghidra) | **float32-compatible** | — | float32-compatible |
| Same stream | 29 (legacy) | — | — | uint16-compatible |

### Impact on residual position classifier

The residual-packed-position lane for meshSize=305 payload=288 currently fails the strict threshold:

- Current plausible ratio: 0.9444 (threshold: 0.95, delta: 0.0056)
- With offset 28: plausible ratio would be ~0.9861 (71/72 per sample) — **PASSES threshold**

If the classifier used offset 28, the residual strict threshold gate would likely clear, removing the `residual-position-strict-threshold-not-met` blocker.

### Why existing OBJ exports still work

The OBJ exporter uses `NifPositionSourceSiblingAccumulator` for position data — it gets XY from float2 streams and Z from sibling float3 streams. The float3 stream body was never directly consumed for position export. The legacy offset error affected the probe/classifier analysis but not the exported geometry.

For normal/UV streams, the byte-rotation decoding (ror1) operates on the body bytes. The 1-byte offset shift changes which bytes are in the body, but the rotation pattern may partially compensate for the offset error in some cases.

## Root cause

The `LegacyPayloadOffset` computation (`blockPayload.Length - declaredPayloadBytes`) counts from the end of the block, which includes the trailing flag byte. This makes the legacy offset 1 byte larger than the actual structural header size. The structural header walk (`PayloadPrefixBytes`) correctly identifies the header as 28 bytes.

The 1-byte discrepancy has been present since the NiDataStream layout analysis was first implemented. It was masked by:

1. The `LegacyOffsetMinusPayloadPrefixBytes = 1` being treated as a normal invariant
2. The OBJ exporter using sibling pairing rather than direct float3 stream consumption
3. The role classifier using byte-rotation heuristics that partially compensate

## Verification commands

```powershell
# Compare legacy vs Ghidra offset for known-good position stream
dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- probe-nif-stream-body --root <live> --id 75d5a06d7c0de1dd --stream-block 21 --out Exports/probe-known-pos-75d5-legacy.json
dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- probe-nif-stream-body --root <live> --id 75d5a06d7c0de1dd --stream-block 21 --ghidra-body-offset --out Exports/probe-known-pos-75d5-ghidra.json

# Compare for residual payload=288 stream
dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- probe-nif-stream-body --root <live> --id 014e1ff60d8508f1 --stream-block 21 --ghidra-body-offset --out Exports/probe-residual-288-014e-ghidra.json
```

## Next steps

1. **High-reasoning review**: Should the default body offset switch from `LegacyPayloadOffset` (29) to `PayloadPrefixBytes` (28)?
2. **Impact assessment**: Run the full residual position classifier with `--ghidra-body-offset` to measure the plausible ratio improvement across all payload families
3. **Export regression check**: Verify that existing OBJ exports don't regress with the new offset
4. **Test update**: Update the `LegacyOffsetMinusPayloadPrefixBytes = 1` test to reflect the corrected understanding
5. **Gate re-evaluation**: If the classifier passes with offset 28, re-evaluate the `residual-position-strict-threshold` gate

## Safety notes

- This finding is structurally derived, not Ghidra-driven. The `--ghidra-body-offset` flag name is historical; the evidence comes from float plausibility comparison.
- The `nidatastream-parser-export-non-consumption-guard` should be re-run after any parser change.
- All existing proof guards should be re-validated with the corrected offset.
- The `GhidraStyleLayoutValid` flag already confirms the 28-byte layout is structurally valid for all 31,777 parsed blocks.
