# Body Offset 28 Fix - Implications for mesh329 Blockers

**Date**: 2026-06-27  
**Status**: Fix implemented, awaiting classifier report regeneration

## Summary

The body offset fix (29 → 28) may resolve or partially resolve the mesh329 blockers by improving stream role classification accuracy.

## mesh329 Blockers (Current State)

From `post50-position-source-status`:

1. `mesh329-extra-position-like-stream-candidate-only` - mesh#34 @304/#57 stream classified as candidate-only
2. `mesh329-family-proof-candidate-only` - entire family evidence is candidate-only
3. `mesh329-source-binding-compare-export-blocked` - export comparison blocked

## mesh329 Family Structure

From `2026-06-post50-mesh329-family-role-analysis.md`:

### mesh#7 variant (complete attributes)

- `attributeSets = 1`
- Position: `@212 → #28`, role=`position-float3-ror1-lead` (c=75)
- Normal: `@220 → #29`, role=`normal-float3-ror1-lead` (c=85)
- UV: `@304 → #33`, role=`uv-float2-ror1-lead` (c=80)

### mesh#34 variant (incomplete attributes)

- `attributeSets = 0`
- Position: `@212 → #28`, role=`position-float3-ror1-lead` (c=75) **[same as mesh#7]**
- Normal: own stream (e.g. #53)
- **@304 stream**: classified as `position-float3-ror1-lead` (c=75) **[NOT UV]**

## Hypothesis: Body Offset Impact on mesh#34

The mesh#34 @304 stream is being classified as a **position stream** instead of a **UV stream**. This could be caused by:

1. **Misaligned byte decoding** (body offset bug) - causing float values to be garbage
2. **Role classifier confusion** - garbage floats don't match UV patterns, so classifier defaults to position
3. **Descriptor mismatch** - if the descriptor says UV but floats are garbage, classifier may override

### Evidence Supporting This Hypothesis

- The @304 stream has the **same descriptor** as mesh#7's UV stream
- The @304 stream has **similar byte structure** to UV streams
- The role classifier confidence is **lower** on mesh#34 (c=75) vs mesh#7 (c=80)
- With correct body offset (28), float plausibility improves dramatically (0.0833 → 0.9861)

### Expected Impact of Body Offset Fix

1. **Improved float values**: mesh#34 @304 stream will have correctly aligned floats
2. **Better role classification**: UV-pattern floats will be recognized as UV instead of position
3. **Attribute set completion**: mesh#34 may now have `attributeSets = 1` instead of 0
4. **Blocker clearance**: `mesh329-extra-position-like-stream-candidate-only` may be resolved

## Verification Plan

Once the classifier report regenerates:

1. **Check mesh#34 @304 stream role**: Does it change from `position-float3-ror1-lead` to `uv-float2-ror1-lead`?
2. **Check attribute set count**: Does mesh#34 now have `attributeSets = 1`?
3. **Check role confidence**: Does confidence improve from c=75 to c=80+?
4. **Re-run mesh329 family proof**: Do the blockers clear?

## Implications for Other Blockers

### `mesh329-family-proof-candidate-only`

- If mesh#34 now has complete attribute sets, the family proof strength increases
- May move from "candidate-only" to "schema-backed" or "promoted"

### `mesh329-source-binding-compare-export-blocked`

- This blocker is about export comparison being blocked for some reason
- With correct body offset, exports will have proper geometry
- May unblock the comparison

### `parser-export-promotion-not-allowed`

- This is the final gate that requires all other blockers to clear
- Body offset fix addresses multiple blockers simultaneously
- Brings the project closer to parser/export promotion readiness

## Broader Impact

The body offset fix affects **ALL** NiDataStream decoding, not just mesh329. This means:

1. **All mesh sizes** (297, 305, 321, 325, 329) will have improved stream classification
2. **All OBJ exports** will have correct geometry
3. **All role classifiers** will have better float plausibility data
4. **All promotion gates** may see improved evidence quality

## Next Steps

1. **Wait for classifier report** to regenerate with corrected offset
2. **Verify mesh#34 @304 stream** role classification improvement
3. **Re-run mesh329 family proof** to check blocker status
4. **Re-export all 27 OBJs** with corrected offset
5. **Visual validation** of re-exported geometry
6. **Update promotion readiness** assessment

## Conclusion

The body offset fix is a **high-leverage change** that addresses multiple blockers simultaneously:

- ✅ `residual-position-strict-threshold-not-met` (primary target)
- ⏳ `mesh329-extra-position-like-stream-candidate-only` (likely resolved)
- ⏳ `mesh329-family-proof-candidate-only` (likely improved)
- ⏳ `mesh329-source-binding-compare-export-blocked` (likely unblocked)

This single fix may clear 4 of the 6 promotion blockers, bringing the project significantly closer to parser/export promotion readiness.
