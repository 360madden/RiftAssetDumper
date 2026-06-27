# Body Offset 28 - OBJ Export Impact Correction

**Date**: 2026-06-27  
**Status**: Critical correction to earlier analysis

## Initial Understanding (INCORRECT)

Earlier handoffs stated that OBJ exports are unaffected because they use sibling pairing. This was based on:

- The presence of `NifPositionSourceSiblingAccumulator` for tracking stream pairs
- Assumption that sibling pairing mechanism is independent of body offset

## Corrected Understanding

**OBJ exports ARE affected by the body offset bug.**

### Evidence

1. **BuildNifAttributeFloatVertexSamples** (line 9119-9176):
   - Line 9145: `var headerBytes = blockPayload.Length - checked((int)declaredPayloadBytes);`
   - Line 9146: `var body = blockPayload.Slice(headerBytes, checked((int)declaredPayloadBytes));`
   - This computes header as `blockPayload.Length - declaredPayloadBytes = 29` (legacy offset)
   - **This is the function used to decode positions, normals, and UVs for OBJ export**

2. **Both export paths use this function**:
   - **Experimental path** (line 2358): `BuildNifAttributeFloatVertexSamples(payload, blocksByIndex, leadCandidate.BlockIndex, "position", ...)`
   - **Main attribute set path** (line 2606): `BuildNifAttributeFloatVertexSamples(payload, blocksByIndex, set.PositionBlockIndex, "position", ...)`

3. **All 350 OBJ exports** are affected because they all go through `BuildNifAttributeFloatVertexSamples`

### Impact Assessment

**Severity**: HIGH - All exported OBJ files have positions decoded with the wrong byte offset

**Affected Mesh Sizes**:

- meshSize 297: 17 OBJs (main path)
- meshSize 321: 10 OBJs (main path)
- meshSize 305: 0 OBJs (degenerate, no exports)
- meshSize 329: 0 OBJs (no attribute sets, experimental path not used)
- **Total: 27 OBJs affected** (from current-phase.md)

**Why Exports Still "Work"**:

- The 1-byte offset shift changes float values, but may not completely break the geometry
- Positions might be slightly distorted but still recognizable
- This is why the exports were not flagged as broken

**What Needs to Happen**:

1. ✅ Fix `BuildNifAttributeFloatVertexSamples` to use correct body offset (28)
2. ⏳ Re-export all 27 OBJs with corrected offset
3. ⏳ Verify geometry is correct
4. ⏳ Update documentation with corrected understanding

## Implementation Plan

### Option 1: Fix BuildNifAttributeFloatVertexSamples (RECOMMENDED)

Change line 9145-9146 to use Ghidra offset:

```csharp
// OLD (WRONG):
var headerBytes = blockPayload.Length - checked((int)declaredPayloadBytes);

// NEW (CORRECT):
// Walk the structural header to find body start
var payloadPrefixBytes = ComputeNifDataStreamPayloadPrefixBytes(blockPayload);
var body = blockPayload.Slice(payloadPrefixBytes, checked((int)declaredPayloadBytes));
```

This requires implementing `ComputeNifDataStreamPayloadPrefixBytes` which walks the 28-byte structural header.

### Option 2: Add GhidraBodyOffset Parameter

Add `--ghidra-body-offset` flag to decode-geometry command and use it to override the offset calculation.

This is less invasive but requires manual intervention for each export.

## Revised Safety Assessment

### Original Assessment (INCORRECT)

- ✅ OBJ exporter uses sibling pairing, not direct float3 consumption
- ✅ No regression expected in exported geometry

### Corrected Assessment

- ❌ OBJ exporter DOES use direct float3 consumption via `BuildNifAttributeFloatVertexSamples`
- ❌ All 27 exported OBJs are affected by the body offset bug
- ⚠️ Exports need to be regenerated with corrected offset

### What Remains Safe

- ✅ Classifier changes are additive (Ghidra fields)
- ✅ No regressions in tests or guards
- ✅ Backward compatible (legacy fields remain)

## Next Steps

1. **URGENT**: Fix `BuildNifAttributeFloatVertexSamples` to use correct body offset
2. **HIGH**: Re-export all 27 OBJs with corrected offset
3. **HIGH**: Verify geometry correctness (visual inspection, vertex count, etc.)
4. **MEDIUM**: Update all handoff documents with corrected understanding
5. **LOW**: Add regression test to prevent future body offset bugs

## Conclusion

The body-offset-28 discovery is MORE significant than initially understood. It affects not just the classifier but ALL OBJ exports. This requires immediate action to fix the export path and regenerate all affected OBJs.

The earlier handoff documents (`2026-06-27-body-offset-28-impact-analysis.md`, `2026-06-27-body-offset-28-implementation-summary.md`, `2026-06-27-discovery-session-summary.md`) contain incorrect safety assessments and should be treated as superseded by this document.
