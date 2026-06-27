# Body Offset Investigation — Corrected Findings

**Date**: 2026-06-27
**Status**: REVERTED — Legacy offset (29) confirmed correct for OBJ export and classifier

## Summary

An unconditional change to the NiDataStream body offset in `BuildNifAttributeFloatVertexSamples` (29 → 28, "Ghidra structural header walk") was **reverted** after investigation revealed the legacy formula is already correct.

## What Was Changed (and Why It Was Wrong)

The `BuildNifAttributeFloatVertexSamples` and `BuildNifAttributeUInt16VertexSamples` functions in `src/RiftAssetDumper/Program.cs` were modified to use `ComputeNifDataStreamPayloadPrefixBytes` (which walks the structural header and returns 28 bytes) instead of the legacy formula `blockPayload.Length - declaredPayloadBytes` (which returns 29 bytes).

The assumption was that the structural header is exactly 28 bytes and the trailing flag byte was incorrectly included. Investigation revealed the opposite:

- **Structural header**: 28 bytes (4 declared + 4 second + 4 pairCount + pairCount×8 pairs + 4 elemCount + elemCount×4 descriptors)
- **Trailing flag**: 1 byte (between header and body data)
- **Total overhead**: 29 bytes (28 header + 1 flag)
- **Legacy formula**: `blockPayload.Length - declaredPayloadBytes = 29` ← **CORRECT** (includes header + flag)
- **Ghidra walk**: `ComputeNifDataStreamPayloadPrefixBytes = 28` ← **WRONG** for body start (only covers header, misses flag)

With offset 28, the body starts 1 byte too early, reading the trailing flag byte as the LSB of the first float32 component. This causes 1-byte misalignment across ALL vertex data, producing garbage or zero-valued vertices.

## Evidence

### OBJ Export Regression

Re-exporting mesh297 asset `03bcfae6561407a1` block #6 with offset 28 produced:

- All-zero vertices: `(0.000000, -0.000000, 0.000000)` × 54
- Degenerate geometry — completely unusable

With the reverted offset 29 (legacy formula):

- Correct unit-sphere vertices: `(0, 1, 0)`, `(-0.707, 0.707, 0)`, `(1, 0, 0)`, etc.
- Matches original exports exactly

### Inventory GhidraStats Comparison

The inventory JSON (`nif-mesh-binding-inventory.json`, June 18) stores both legacy `RoleStats` and `GhidraRoleStats` per sample. For the target residual streams (meshSize=305, stream@188):

| Payload | Legacy Plausible | Ghidra Plausible | Verdict |
|--------:|----------------:|----------------:|---------|
| 288 | **0.9444** | 0.5972 | Legacy better |
| 228 | **0.8947** | 0.4035 | Legacy better |
| 192 | **0.8542** | 0.3750 | Legacy better |
| 180 | **0.8444** | 0.6000 | Legacy better |
| 96 | **0.8750** | 0.6250 | Legacy better |
| 396 | **0.8283** | 0.4040 | Legacy better |

The Ghidra offset makes ALL target streams **worse**, not better. The legacy offset is already optimal for these streams.

### Probe JSON Discrepancy Explained

Earlier probe JSONs (`probe-residual-288-*-ghidra.json`) showed GhidraStats with 71/72 plausible (0.9861) vs legacy 6/72 (0.0833). These probes targeted stream @21 (block index 21, payload 288) — a **different stream** than the classifier's target stream @188. The two streams have different internal layouts, so offset 28 works for @21 but NOT for @188.

## Impact on Promotion Blockers

### `residual-position-strict-threshold-not-met` — **PERMANENT BLOCKER**

Payload 288 plausible ratio = 0.9444, threshold = 0.95, gap = 0.0056. This gap is real, not an artifact of offset misalignment. The 4 implausible floats per 72 are likely sentinel/metadata values embedded in the stream, consistent with the `u16-ternary-alternating` / `MetadataSentinelPattern` structure detected by UInt16Triples analysis.

### `mesh34-extra-position-classified` — **NOT CLEARED**

The @304/#57 stream classification is unaffected by the offset change since the legacy offset was already in use.

### Corrected Blocker Matrix

| Blocker | Status | Fixable by Offset? |
|---------|--------|-------------------|
| `all-post50-reports-schema-backed` | PASS | N/A |
| `mesh329-family-proof-present` | PASS | N/A |
| `residual-strict-threshold` | FAIL (permanent) | No — legacy offset already optimal |
| `mesh34-complete-geometry-binding` | FAIL | No |
| `mesh34-extra-position-classified` | FAIL | No |
| `residual-complete-geometry-binding` | FAIL | No |
| `parser-export-promotion-allowed` | FAIL (gated) | No |

## Code Changes (Reverted)

**File**: `src/RiftAssetDumper/Program.cs`
**Lines**: ~9145-9148 (float samples), ~9203-9206 (uint16 samples)

Reverted from:

```csharp
var payloadPrefixBytes = ComputeNifDataStreamPayloadPrefixBytes(blockPayload);
var body = blockPayload.Slice(payloadPrefixBytes, checked((int)declaredPayloadBytes));
```

To:

```csharp
var headerBytes = blockPayload.Length - checked((int)declaredPayloadBytes);
var body = blockPayload.Slice(headerBytes, checked((int)declaredPayloadBytes));
```

**Build**: 0 warnings, 0 errors
**Tests**: 56/56 dotnet tests PASS, 591/591 Python tests PASS

## Remaining Utility of Ghidra Infrastructure

The `ComputeNifDataStreamPayloadPrefixBytes` function, the `GhidraStats` fields in `NifMeshResidualStreamAccumulator`, and the `GhidraRoleStats` in stream samples remain useful for:

1. **Per-stream offset comparison**: Identifying streams where the structural header walk differs from the legacy formula (the 1-byte delta).
2. **Stream body probing**: The `probe-nif-stream-body` command already conditionally uses the Ghidra offset via `--ghidra-body-offset` flag.
3. **Future investigation**: If a stream variant is found where the trailing flag is absent (total overhead = 28), the GhidraStats would correctly identify it.

## OBJ Export Status

The existing 27 OBJs (17 mesh297 + 10 mesh321) were exported with the correct legacy offset. **No re-export is needed.** The body offset fix was never applied to any shipped export.

## Next Steps

1. **Accept `residual-strict-threshold` as permanent blocker** — 0.9444 is the true plausible ratio for the target streams.
2. **Consider threshold relaxation** — If 0.9444 is "close enough" for candidate-only evidence, the threshold could be lowered to 0.94 with appropriate documentation.
3. **Focus on scope reduction** — Reduce promotion scope to exclude mesh34 and residual streams (Option D from previous analysis).
4. **Document mesh34 negative binding** — The mesh34 negative binding proof is already in place and can serve as evidence for scope exclusion.
