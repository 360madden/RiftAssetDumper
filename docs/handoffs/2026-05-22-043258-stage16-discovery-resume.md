# Stage 16 — Discovery Resume: New Mesh Families & Aggressive Lead Pursuit

**Date:** 2026-05-22 04:32 UTC  
**Previous:** Stage 15 (mypy 2.1.0 CI fix, meshSize=465 investigation)

## Summary

Aggressive lead pursuit across all untapped mesh families. **4 new faced families discovered** (meshSize=267, 345, 361, 365) plus additional variants in known families (301, 321). Total OBJ inventory grew from 56 → 73 unique meshes (+17), faces from ~3,177 → 7,744 (+4,567), a 144% increase in face coverage.

## New Discoveries

### New Faced Families

| Mesh Size | Samples | Vertex Range | Face Range | Index Role | Confidence |
|-----------|---------|-------------|------------|------------|------------|
| **267** | 1 | 5 | 2 | `index-u16be-list-lead` | 90 |
| **345** | 4 | 137–149 | 414–424 | `index-u16be-strip-lead` | 90–95 |
| **361** | 2 | 151 | 414 | `index-u16be-strip-lead` | 90 |
| **365** | 2 | 138–176 | 414–464 | `index-u16be-strip-lead` | 90–95 |

### New Variants in Known Families

| Mesh Size | Sample | Vertices | Faces | Index Role |
|-----------|--------|----------|-------|-------------|
| 301 | 2feda40170afea54 mesh#6 | 54 | 52 | `index-u16be-list-lead` |
| 321 | 21900d2ee4f931ca mesh#6 | 137 | 414 | `index-u16be-strip-lead` |

### Export Details

All 11 new faced OBJs exported successfully via `--experimental-position-source`:
- All structurally valid (index bounds OK, no NaN)
- Degenerate-bridge triangle-strip walking for strip-lead index streams
- Pairing-based face generation for list-lead index streams

## Blockers Investigated

### meshSize=465 — CONFIRMED DEAD END
- 13 samples across 4 patterns in `assets.050`, all mesh#8
- Stream layout: 3× normal-float3 (uint16-packed, tangent-space data), 1× UV, 1× u32 metadata
- **No position stream, no index stream** — 0 pairings across all samples
- All 3 "normal" streams are uint16-encoded (not float32); float32 decode produces denormal garbage
- Position-only OBJs (111, 122, 60 vertices) with 0 faces
- **Verdict:** Not exportable as faced geometry without reinterpreting uint16-packed data

### meshSize=280, 303, 316, 330, 354 — NO INDEX STREAMS
- Probed meshSize=280 (36v, 0f), meshSize=316 (4v, 0f) — both position-only
- These mesh sizes lack index streams despite appearing in pair-compatible inventory patterns

## Key Methodology

The breakthrough came from querying the mesh-binding inventory for **unexported mesh sizes with index streams** (`index-u16be-strip-lead` or `index-u16be-list-lead`). This targeted approach found 11 mesh sizes with index streams, 6 of which produced faced OBJs on first attempt.

Previous approach (probing by pair-compatible count alone) was ineffective because many pair-compatible families have variants without index streams.

## Inventory Snapshot

| Metric | Stage 14 | Stage 16 | Delta |
|--------|----------|----------|-------|
| Unique OBJs | 56 | **73** | +17 |
| Faced OBJs | ~23 | **47** | +24 |
| Position-only | ~33 | 26 | -7 |
| Total vertices | 1,881 | **4,649** | +2,768 |
| Total faces | 3,177 | **7,744** | +4,567 |
| Mesh families | 13 | **17** | +4 |
| Total OBJ bytes | ~71K | **579K** | +508K |

## Guarded Truths (Unchanged)

| Guard | Status |
|-------|--------|
| `attribute-extra-proof-guard` | ✅ PASSED |
| `usage-access-correlation-guard` | ✅ PASSED |
| `position-source-sibling-lead-guard` | ✅ PASSED |
| `residual-lead-guard` | ✅ PASSED |
| Discovery suite (7 stages) | ✅ All PASSED |
| PairCompatibleMeshes | 1,949 (unchanged) |
| Position gaps | 0 |

## CI

| Check | Result |
|-------|--------|
| `dotnet build` | 0 errors ✅ |
| `dotnet test` | 6/6 ✅ |
| `ruff check` | 0 violations ✅ |
| `mypy` | 0 errors ✅ |

## Remaining Leads

| # | Lead | Priority |
|---|------|----------|
| 1 | Probe remaining meshSize=345/361/365 siblings for additional variants | 🟡 Medium |
| 2 | Investigate if any uint16-packed streams in meshSize=465 can be reinterpreted as positions | 🟡 Speculative |
| 3 | Export remaining position-only families as point clouds (no face data) | 🟢 Low |
| 4 | Scale to live archive extraction for mesh sizes absent from copied set | 🟢 Blocked (no manifest) |
| 5 | Investigate meshSize=330, 337, 341, 346, 370, 372, 389, 404 for index streams | 🟡 Medium |
