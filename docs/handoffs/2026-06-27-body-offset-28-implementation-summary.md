# Body Offset 28 Implementation Summary

## Date

2026-06-27

## Changes Made

### 1. NifMeshResidualStreamAccumulator (line 16162)

Added 6 new optional constructor parameters and properties for Ghidra body offset stats:

- `ghidraRotatedFloat3VectorCount`
- `ghidraRotatedFloat3FiniteVectorRatio`
- `ghidraRotatedFloat3PlausibleValueRatio`
- `ghidraRotatedFloat3NonZeroVectorRatio`
- `ghidraRotatedFloat3MaxExtent`
- `ghidraRotatedFloat3Prefix`

### 2. NifMeshResidualStreamGroup record (line 16732)

Added 7 new fields to the immutable record:

- `GhidraRotatedFloat3VectorCount`
- `GhidraRotatedFloat3FiniteVectorRatio`
- `GhidraRotatedFloat3PlausibleValueRatio`
- `GhidraRotatedFloat3NonZeroVectorRatio`
- `GhidraRotatedFloat3MaxExtent`
- `GhidraRotatedFloat3Prefix`
- `StrictGhidraRotatedFloat3PositionClassifierReview`

### 3. Accumulator construction (line 4852)

Updated the `new NifMeshResidualStreamAccumulator` call to pass Ghidra stats from `residual.GhidraRoleStats?.RotatedFloat3Stats`.

### 4. toResidualStreamRecord function (line 5300)

Updated the function to populate the new Ghidra fields and create a second classifier review using `BuildNifResidualPositionClassifierReview` with the Ghidra stats.

## Build Status

- ✅ Build succeeded (0 warnings, 0 errors)
- ✅ All 56 tests pass
- ✅ Validation suite passes (11/11 checks)

## Expected Impact

### Before (Legacy offset 29)

Payload 288 classifier:

- Plausible ratio: 0.9444
- Strict pass: false
- Delta to 0.95 threshold: 0.0056

### After (Ghidra offset 28)

Expected improvement based on probe JSON analysis:

- Payload 288: 71/72 plausible floats per sample = 0.9861 plausible ratio
- Strict pass: true (0.9861 >= 0.95)
- Blocker cleared: `residual-position-strict-threshold-not-met`

## Evidence Basis

Probe JSON `probe-residual-position-payload288-014e1ff60d8508f1-stream21.json`:

- Legacy Stats (offset 29): 6/72 plausible floats (0.0833)
- GhidraStats (offset 28): 71/72 plausible floats (0.9861)
- Float range with offset 28: -36 to 23.4 (valid position-like values)

## Root Cause

Legacy offset computation includes trailing flag byte:

```csharp
var legacyPayloadOffset = blockPayload.Length - checked((int)declaredPayloadBytes);
// Result: 29 (includes 1-byte trailing flag)
```

Ghidra offset computation walks structural header:

```csharp
payloadPrefixBytes = offset; // after walking 28-byte header
// Result: 28 (correct body start)
```

Block structure:

- 28 bytes: [4 declared][4 second][4 pairCount][8 pairs][4 elemCount][4 elemDesc]
- N bytes: payload data
- 1 byte: trailing flag

## Safety Assessment

### Why This Is Safe

1. **Structural evidence**: 28-byte header walk is structurally sound
2. **Float plausibility**: GhidraStats show valid position-like values
3. **Export independence**: OBJ exporter uses sibling pairing, not direct float3 consumption
4. **Candidate-only**: Classifier remains candidate-only, not promoted geometry truth
5. **Backward compatible**: Legacy fields remain in place; Ghidra fields are additive

### Regressions Checked

- ✅ All 56 unit tests pass
- ✅ Validation suite passes (11/11 checks)
- ✅ Build succeeds with no warnings

## Next Steps

1. **Verify report regeneration**: Check that the regenerated classifier report shows improved plausible ratios
2. **Assess blocker clearance**: Confirm `residual-position-strict-threshold-not-met` is cleared
3. **Update documentation**: Update `current-phase.md` and `knowledge.md` with the finding
4. **Plan next lead**: Identify the next promotion blocker and plan resolution

## Files Modified

1. `src/RiftAssetDumper/Program.cs`:
   - Line 16162: NifMeshResidualStreamAccumulator constructor
   - Line 16732: NifMeshResidualStreamGroup record
   - Line 4852: Accumulator construction
   - Line 5300: toResidualStreamRecord function

## Files Created

1. `docs/handoffs/2026-06-27-body-offset-28-impact-analysis.md`: Impact analysis document
2. `docs/handoffs/2026-06-27-body-offset-28-implementation-summary.md`: This document
