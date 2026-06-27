# Promotion Readiness Blocker Analysis

**Date**: 2026-06-27  
**Status**: Comprehensive analysis of all promotion blockers

## Current Promotion Readiness Status

**Decision**: `not-ready; current evidence is schema-backed candidate proof, not parser/export truth`

## Required Gates (Must Pass for Promotion)

### ✅ PASSING (2/7)

1. **`all-post50-reports-schema-backed`** ✅
   - Evidence: 11/11 reports schema-backed
   - Status: COMPLETE

2. **`mesh329-family-proof-present`** ✅
   - Evidence: evidenceGroups=23, totalLinks=46
   - Status: COMPLETE

### ❌ FAILING (5/7)

3. **`mesh34-complete-geometry-binding`** ❌
   - Evidence: attributeSets=0, uvStreams=0
   - Status: FAILING
   - Root cause: mesh34 variant lacks complete attribute set binding
   - Impact: Cannot prove mesh34 has complete geometry
   - Difficulty: HIGH - fundamental structural issue with mesh34 variant
   - Action needed: Investigate whether mesh34 is a different LOD or variant that intentionally lacks complete binding

4. **`mesh34-extra-position-classified`** ❌
   - Evidence: schema-backed meshSize=329 compare confirms shared @212/#28 and extra @304/#57 evidence; extraPayloads=96,240,280
   - Status: FAILING (candidate-only)
   - Root cause: @304/#57 stream on mesh34 classified as "position-like" instead of "UV"
   - Impact: Cannot classify the extra stream on mesh34
   - Difficulty: MEDIUM - body offset fix may help reclassify
   - Action needed: Wait for body offset fix to regenerate reports, then check if @304/#57 gets reclassified as UV

5. **`residual-strict-threshold`** ❌
   - Evidence: plausible=0.9444
   - Status: FAILING (just below 0.95 threshold)
   - Root cause: Body offset bug causes 1-byte misalignment in float decoding
   - Impact: Payload 288 classifier fails strict threshold
   - Difficulty: LOW - body offset fix implemented
   - Action needed: **WAITING for classifier report regeneration** (RiftAssetDumper.exe PID 96068, 2.4GB memory)
   - Expected outcome: Plausible ratio should improve from 0.9444 to ~0.9861, clearing the 0.95 threshold

6. **`residual-complete-geometry-binding`** ❌
   - Evidence: candidate-only; no complete geometry binding
   - Status: FAILING
   - Root cause: Residual position streams (meshSize=305, payload=288) don't have complete attribute set binding
   - Impact: Cannot prove residual streams have complete geometry
   - Difficulty: HIGH - residual streams are inherently incomplete
   - Action needed: May need to accept this as a permanent blocker or find alternative proof strategy

7. **`parser-export-promotion-allowed`** ❌
   - Evidence: v1 status keeps parser/export promotion locked false
   - Status: FAILING (final gate, depends on all others)
   - Root cause: All other gates must pass first
   - Impact: Cannot promote parser/export to production
   - Difficulty: N/A - depends on clearing all other blockers
   - Action needed: Clear all other gates first

## Blocker Priority Matrix

| Blocker | Difficulty | Impact | Status | Action |
|---------|-----------|--------|--------|--------|
| `residual-strict-threshold` | LOW | HIGH | ⏳ WAITING | Wait for report regeneration |
| `mesh34-extra-position-classified` | MEDIUM | MEDIUM | ⏳ MAYBE | Check after body offset fix |
| `mesh34-complete-geometry-binding` | HIGH | HIGH | ❓ INVESTIGATE | Research mesh34 variant purpose |
| `residual-complete-geometry-binding` | HIGH | HIGH | ❓ INVESTIGATE | Accept as permanent blocker? |
| `parser-export-promotion-allowed` | N/A | CRITICAL | ❌ BLOCKED | Clear all other gates first |

## Expected Impact of Body Offset Fix

The body offset fix (29 → 28) should directly resolve:

1. ✅ **`residual-strict-threshold`** - Payload 288 plausible ratio 0.9444 → ~0.9861
2. ⏳ **`mesh34-extra-position-classified`** - @304/#57 stream may get reclassified from "position-like" to "UV"

This could clear **2 of 5 failing gates**, bringing us from 2/7 passing to 4/7 passing.

## Remaining Blockers After Body Offset Fix

Even with the body offset fix, 3 gates will still be failing:

1. ❌ **`mesh34-complete-geometry-binding`** - mesh34 variant fundamentally lacks complete binding
2. ❌ **`residual-complete-geometry-binding`** - residual streams inherently incomplete
3. ❌ **`parser-export-promotion-allowed`** - depends on all others

## Strategic Options

### Option A: Accept Permanent Blockers

- Accept that mesh34 and residual streams will never have complete geometry binding
- Modify promotion criteria to allow "partial binding" or "candidate-only" evidence
- Risk: Weakens the proof standards

### Option B: Investigate mesh34 Variant Purpose

- Research whether mesh34 is a different LOD or variant that intentionally lacks complete binding
- If proven intentional, document as "expected behavior" and adjust promotion criteria
- Risk: May discover mesh34 is actually broken and needs fixing

### Option C: Alternative Proof Strategy

- Find alternative ways to prove geometry binding without requiring complete attribute sets
- Example: Use sibling pairing or other structural evidence
- Risk: May not be as strong as complete binding proof

### Option D: Scope Reduction

- Reduce promotion scope to exclude mesh34 and residual streams
- Promote parser/export for mesh297 and mesh321 families only (which have complete binding)
- Risk: Limits the usefulness of the promotion

## Recommended Next Steps

1. **IMMEDIATE**: Wait for classifier report regeneration to complete
2. **SHORT-TERM**: Verify body offset fix clears `residual-strict-threshold` gate
3. **SHORT-TERM**: Check if @304/#57 stream gets reclassified after body offset fix
4. **MEDIUM-TERM**: Investigate mesh34 variant purpose and document findings
5. **MEDIUM-TERM**: Decide on strategic option for remaining blockers
6. **LONG-TERM**: Implement chosen strategy and clear remaining gates

## Conclusion

The body offset fix is a **high-leverage change** that should clear 2 of 5 failing gates. However, 3 gates will remain failing due to fundamental structural issues with mesh34 and residual streams.

The project needs a strategic decision on how to handle these permanent blockers:

- Accept them and adjust promotion criteria (Option A)
- Investigate and document as expected behavior (Option B)
- Find alternative proof strategies (Option C)
- Reduce promotion scope (Option D)

The most pragmatic approach is likely **Option B + Option D**: investigate mesh34 to understand its purpose, then reduce promotion scope to exclude permanently incomplete streams.
