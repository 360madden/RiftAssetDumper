# Stage 18 — batch-sweep runner, OBJ integrity check, candidate exhaustion

**Date:** 2026-05-21 (actual run 2026-06-07)  
**Previous:** Stage 17 (meshSize=354 faced family, 76 OBJs, OBJ manifest)

## Summary

Created `scripts/batch_sweep.py` — a comprehensive 4-phase tool for OBJ integrity validation, candidate discovery, batch export, and manifest building. Ran full integrity check on all exported OBJs, confirmed exhaustive candidate sweep (0 unexported index-stream meshes remain), and validated all 4 proof guards. **94 OBJs total, zero structural issues.**

## New Tool: `scripts/batch_sweep.py`

### Commands

```powershell
python scripts/batch_sweep.py                     # Dry-run: list unexported candidates
python scripts/batch_sweep.py --execute            # Export all candidates
python scripts/batch_sweep.py --execute --limit 5  # Export first 5 only
python scripts/batch_sweep.py --summary            # Show summary of all OBJs
python scripts/batch_sweep.py --integrity-check    # Validate all OBJs + build manifest
python scripts/batch_sweep.py --manifest           # Build manifest only
```

### Phase structure

| Phase | Function | Purpose |
|-------|----------|---------|
| 1 | `discover_candidates()` | Cross-references mesh-binding inventory against exported OBJs to find unexported meshes with index streams |
| 2 | `batch_export()` | Runs `decode-nif-geometry --experimental-position-source --write-obj` on each candidate |
| 3 | `integrity_check()` | Validates all OBJs: SHA256, index bounds, NaN detection, negative indices, deduplication |
| 4 | `build_manifest()` | Generates `obj-manifest-stage18.json` with per-OBJ SHA256 hashes and structural metadata |

### Quality gates

- `ruff check`: 0 violations ✅
- `mypy`: 0 errors ✅
- Python 3.14 compatible (no external deps beyond stdlib)

## OBJ Inventory (Stage 18 baseline)

| Metric | Stage 17 | Stage 18 | Delta |
|--------|----------|----------|-------|
| Unique OBJs | 76 | **94** | +18 |
| Faced OBJs | 48 | **65** | +17 |
| Position-only | 28 | **29** | +1 |
| Total vertices | 4,695 | **6,079** | +1,384 |
| Total faces | 7,766 | **10,795** | +3,029 |
| Total bytes | 583K | **781K** | +198K |

### Integrity check results

| Check | Result |
|-------|--------|
| NaN detected | 0 ✅ |
| Index bounds issues | 0 ✅ |
| Negative indices | 0 ✅ |
| File access errors | 0 ✅ |

All 94 OBJs pass all structural validation checks. Manifest written to `Exports/obj-manifest-stage18.json` with SHA256 hashes for every entry.

## Candidate Discovery

**Dry-run result: 0 unexported candidates with index streams found.**

The exhaustive sweep across all mesh sizes is complete. Every mesh in the copied archive set that has an index stream and can be paired with position/normal/UV data has been exported. Remaining unexported meshes are either:

- Position-only families (no index streams)
- Have index streams but no position/vertex pairings
- Missing from the copied archive set entirely

## Guarded Truths

| Guard | Status | Key Assertions |
|-------|:------:|---------------|
| `attribute-extra-proof-guard` | ✅ PASSED | 4 @264 groups intact, raw-zero-based 5/5, degenerate-bridge-stitch, parity 0/0, strip structure varied |
| `usage-access-correlation-guard` | ✅ PASSED | 5 roles (uv: 4,633, normal: 4,167, index-strip: 1,977, position: 210, index-list: 109), 0 pairing exceptions |
| `position-source-sibling-lead-guard` | ✅ PASSED | Guarded sibling leads intact |
| `residual-lead-guard` | ✅ PASSED | 173 total residuals, 1,162 meshes across categories |

## CI

| Check | Result |
|-------|--------|
| `dotnet build` | 0 errors ✅ |
| `dotnet test` | 6/6 ✅ |
| `ruff check scripts/` | 0 violations ✅ |
| `mypy scripts/` | 0 errors ✅ |
| All 4 proof guards | PASSED ✅ |

## Files changed this session

| File | Change type | Description |
|------|:-----------:|-------------|
| `scripts/batch_sweep.py` | + NEW | 4-phase batch-sweep runner + OBJ integrity checker |
| `docs/handoffs/2026-06-07-stage18-batch-sweep-integrity.md` | + NEW | This handoff document |

## Remaining Leads

| # | Lead | Priority |
|---|------|----------|
| 1 | Investigate uint16-packed position reinterpretation for dead-end families (meshSize=305 stream@188 magic-43606) | 🟡 Speculative |
| 2 | Scale to live archive extraction for mesh sizes absent from copied set (meshSize=465, others) | 🟢 Blocked (no manifest) |
| 3 | Investigate the +18 OBJ delta between Stage 17 and 18 — which mesh families were exported in the interim? | 🟡 Housekeeping |
| 4 | Build 3D viewer integration script (automated OBJ → render for visual validation) | 🟢 Future |
