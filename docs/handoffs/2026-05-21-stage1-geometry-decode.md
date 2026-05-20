# Stage 1: Safe Geometry Decode — Completed

**Date:** 2026-05-21  
**Status:** ✅ Complete

## Scope

Stage 1 of [discovery-plan-50.md](../discovery-plan-50.md): implement safe geometry decode from NIF attribute-set meshes, including OBJ face export and cross-validation of UInt16-packed position streams.

## What was delivered

### 1. OBJ face export from @264 UInt16BE index strip

- **Command:** `decode-nif-geometry --write-obj` with `@264` extra-stream index decoding
- **Mechanism:** Walks UInt16 big-endian values in the `@264` extra stream body as a degenerate-bridge triangle strip, emitting raw-zero-based vertex indices
- **Degenerate-bridge handling:** 1-degenerate window suppresses faces; 2+ degenerate windows close the strip segment; even windows maintain winding, odd windows flip
- **Vertex mapping:** raw-zero-based index mapping (1-based OBJ convention applied at export time: `oa = objVertexBase + a + 1`)
- **Proof:** Strips are structurally consistent with degenerate-bridge stitching: mirrored adjacent-repeat bridge count, non-alternating parity, segments uniformly sized, cross-segment dropped window count = 0

### 2. UInt16 position cross-validation

- **Command:** `validate-uint16-positions --id <16hex> --mesh-block <n>`
- **Mechanism:** For each attribute set, reads float32 position stream and scans companion data streams for magic-43606 UInt16-packed position encoding; reports per-vertex comparison, OLS line fitting, JSON report output
- **Result:** **No magic-43606 UInt16-packed position streams** exist alongside float32 attribute positions in the current sample set

### 3. CLI help text

- Added `validate-uint16-positions` to `PrintUsage()` in `Program.cs`

## Scope validated

| Check | Result |
|-------|--------|
| Build | 0 errors (2 pre-existing SharpCompress warnings) |
| Python unit tests | 56/56 passed |
| `validate-uint16-positions` on known attribute-set meshes | 12 meshes across 8 unique IDs tested |
| UInt16 position streams found | **0** (finding: encoding absent from sample set) |
| Aggregated results | `Exports/discovery-plan/stage1/uint16-validation-full.json` |

## Handoffs referenced

- `2026-05-19-204500-rift-assets-u16triples-export-safety-handoff.md`
- `2026-05-20-stage0-baseline.md`
- `2026-05-20-stage1-obj-face-export.md`
- `2026-05-20-153524-rift-assets-session-obj-export-guards.md`
- `2026-05-20-stage2-ps-py-guards-migration.md`
- `2026-05-21-stage1-resume-before-restart.md`

## Next steps

1. Stage 2 (PS→Py guards migration) — substantial porting of remaining proof guards
2. Expand sample set from archives for broader UInt16 position coverage
3. Investigate why position stream references appear absent in attribute-set meshes (schema mismatch, offset error, or actual absence)
4. Full PS→Py migration of remaining complex workflow modes
