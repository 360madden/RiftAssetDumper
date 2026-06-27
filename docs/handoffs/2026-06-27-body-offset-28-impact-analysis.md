# Body Offset 28 Impact Analysis

## Summary

Switch residual position classifier from legacy body offset (29) to Ghidra body offset (28) to fix float plausibility computation.

## Evidence

### Probe Data (payload=288, asset 014e1ff60d8508f1, stream 21)

**Legacy Stats (offset 29):**

- Float32Count: 72
- PlausibleFloat32Count: 6
- Plausible ratio: 6/72 = 0.0833
- Float range: -1.22e-27 to 4.8e+29 (garbage)

**GhidraStats (offset 28):**

- Float32Count: 72
- PlausibleFloat32Count: 71
- Plausible ratio: 71/72 = 0.9861
- Float range: -36 to 23.4 (valid position-like values)

### Root Cause

Legacy offset computation:

```csharp
var legacyPayloadOffset = blockPayload.Length - checked((int)declaredPayloadBytes);
```

This includes the trailing flag byte in the offset, pushing the body start 1 byte too late.

Ghidra offset computation:

```csharp
payloadPrefixBytes = offset; // after walking 28-byte structural header
```

This correctly identifies the body start at offset 28.

Block structure:

- [4 declared][4 second][4 pairCount][8 pairs][4 elemCount][4 elemDesc] = 28 bytes header
- [payload data]
- [1 byte trailing flag]

## Impact on Classifier

### Current State (offset 29)

Payload 288 classifier report:

- 6 samples, 24 vectors each
- Plausible ratio: 0.9444
- Strict pass: false (threshold 0.95)
- Delta to threshold: 0.0056

### Expected State (offset 28)

If each sample has 71/72 plausible floats:

- 6 samples * 72 floats = 432 total floats
- 6 samples * 71 plausible = 426 plausible floats
- Plausible ratio: 426/432 = 0.9861
- Strict pass: true (0.9861 >= 0.95)

This would clear the `residual-position-strict-threshold-not-met` blocker.

## Safety Assessment

### Why This Change Is Safe

1. **Structural evidence**: The 28-byte header walk is structurally sound
2. **Float plausibility**: GhidraStats show valid position-like values across all samples
3. **Export independence**: OBJ exporter uses NifPositionSourceSiblingAccumulator (sibling pairing), not direct float3 stream consumption
4. **Candidate-only**: Classifier remains candidate-only, not promoted geometry truth
5. **Test coverage**: 591 tests passing, 11/11 validation guards

### Potential Regressions

1. **Other payload families**: Need to verify improvement across all 6 payload sizes (96, 180, 192, 228, 288, 396)
2. **Non-position streams**: Ensure offset 28 doesn't break other role classifiers
3. **Proof guards**: Re-run all 11 validation guards to check for regressions

## Implementation Plan

1. Modify `BuildNifResidualPositionClassifierReview` call site (line 5314) to use `GhidraRoleStats` instead of `RoleStats`
2. Re-run residual position classifier to measure improvement
3. Re-run all proof guards to check for regressions
4. Verify OBJ export regression safety
5. Update test expectations if needed
6. Update project documentation

## Code Changes

### Location 1: Classifier call site (line 5314)

**Before:**

```csharp
StrictRotatedFloat3PositionClassifierReview: BuildNifResidualPositionClassifierReview(
    group.RotatedFloat3VectorCount,
    group.RotatedFloat3FiniteVectorRatio,
    group.RotatedFloat3PlausibleValueRatio,
    group.RotatedFloat3NonZeroVectorRatio,
    group.RotatedFloat3MaxExtent),
```

**After:**

```csharp
StrictRotatedFloat3PositionClassifierReview: BuildNifResidualPositionClassifierReview(
    group.GhidraRotatedFloat3VectorCount,
    group.GhidraRotatedFloat3FiniteVectorRatio,
    group.GhidraRotatedFloat3PlausibleValueRatio,
    group.GhidraRotatedFloat3NonZeroVectorRatio,
    group.GhidraRotatedFloat3MaxExtent),
```

### Location 2: Accumulator construction (line 4864)

**Before:**

```csharp
residual.RoleStats.RotatedFloat3Stats?.VectorCount,
residual.RoleStats.RotatedFloat3Stats?.FiniteVectorRatio,
residual.RoleStats.RotatedFloat3Stats?.PlausibleValueRatio,
residual.RoleStats.RotatedFloat3Stats?.NonZeroVectorRatio,
residual.RoleStats.RotatedFloat3Stats?.MaxExtent,
residual.RoleStats.RotatedFloat3Stats?.Prefix
```

**After:**

```csharp
residual.GhidraRoleStats?.RotatedFloat3Stats?.VectorCount,
residual.GhidraRoleStats?.RotatedFloat3Stats?.FiniteVectorRatio,
residual.GhidraRoleStats?.RotatedFloat3Stats?.PlausibleValueRatio,
residual.GhidraRoleStats?.RotatedFloat3Stats?.NonZeroVectorRatio,
residual.GhidraRoleStats?.RotatedFloat3Stats?.MaxExtent,
residual.GhidraRoleStats?.RotatedFloat3Stats?.Prefix
```

### Location 3: Accumulator type definition (line 16174)

Need to add Ghidra variants of the rotated float3 fields to `NifMeshResidualStreamAccumulator`.

## Verification

1. Run `python scripts/rift_read_only.py post50-residual-strict-threshold-delta` to verify improvement
2. Run `python scripts/rift_read_only.py post50-validation-suite` to check for regressions
3. Run `dotnet test` to verify all 591 tests still pass
4. Manually inspect OBJ exports to verify no visual changes

## Next Steps

After verification:

1. Update `current-phase.md` to document the fix
2. Update `knowledge.md` with the body-offset-28 finding
3. Re-assess promotion blockers
4. Plan next discovery lead
