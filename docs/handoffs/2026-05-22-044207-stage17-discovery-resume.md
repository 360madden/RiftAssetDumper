# Stage 17 — Continued Discovery: OBJ Manifest + Remaining Unexplored Sizes

**Date:** 2026-05-22 04:42 UTC  
**Previous:** Stage 16 (4 new faced families, 73 OBJs)

## Summary

Systematic sweep of all remaining unexplored mesh sizes with index streams, plus comprehensive OBJ manifest with SHA256 hashes. **1 new faced family discovered** (meshSize=354), 3 mesh sizes confirmed dead ends (330, 370, 280). OBJ inventory: 73 → 76 (+3), faces: 7,744 → 7,766 (+22).

## New Discoveries

### New Faced Family: meshSize=354

| Sample | Vertices | Faces | Index Role | Confidence |
|--------|----------|-------|------------|------------|
| ed437d75014fa526 mesh#6 | 24 | 22 | `index-u16be-list-lead` | 90 |

Only 1 sample in inventory — fully exported.

### Confirmed Dead Ends

| Mesh Size | Sample | Vertices | Faces | Reason |
|-----------|--------|----------|-------|--------|
| 330 | 7ee756d33de2e6b6 mesh#6 | 16 | 0 | `index-u16be-lead` found but pairings below threshold |
| 370 | b2691b19bc1886f3 mesh#66 | 6 | 0 | `position-float3-ror1-lead` but no index stream |

### Methodology Refinement

Stage 16 proved that querying the inventory for **unexported mesh sizes with index streams** (`index-u16be-*`) is the optimal discovery strategy. Stage 17 applied this filter systematically across all 14 completely unexplored mesh sizes:

- **2 had index streams** (330, 354) → 1 produced faced OBJ
- **12 had no index streams** → confirmed as position-only families

## OBJ Manifest (`Exports/obj-manifest-stage17.json`)

Comprehensive structured inventory with SHA256 hashes for every OBJ:

| Field | Value |
|-------|-------|
| Format | JSON with per-entry SHA256, v/f/vt/vn counts, byte size |
| Total entries | 76 |
| Faced | 48 |
| Position-only | 28 |
| Total vertices | 4,695 |
| Total faces | 7,766 |
| Total bytes | 582,670 |

Each entry includes: `assetId`, `meshBlock`, `vertices`, `texcoords`, `normals`, `faces`, `faced`, `bytes`, `sha256`

## Inventory Evolution

| Metric | Stage 13 | Stage 14 | Stage 16 | Stage 17 |
|--------|----------|----------|----------|----------|
| Unique OBJs | 29 | 56 | 73 | **76** |
| Faced OBJs | 23 | ~23 | 47 | **48** |
| Position-only | 6 | ~33 | 26 | **28** |
| Total vertices | 1,881 | ~1,881 | 4,649 | **4,695** |
| Total faces | 3,177 | ~3,177 | 7,744 | **7,766** |
| Mesh families | 13 | 13 | 17 | **18** |
| Total bytes | ~71K | ~71K | 579K | **583K** |

## Guarded Truths

| Guard | Status |
|-------|--------|
| `attribute-extra-proof-guard` | ✅ PASSED |
| `usage-access-correlation-guard` | ✅ PASSED |
| `position-source-sibling-lead-guard` | ✅ PASSED |
| `residual-lead-guard` | ✅ PASSED |
| Discovery suite (7 stages) | ✅ All PASSED |
| PairCompatibleMeshes | 1,949 (unchanged) |

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
| 1 | Probe remaining zero-export sizes (303, 309, 311, 315, 322, 337, 341, 346, 372, 389, 404) — all confirmed as no-index-stream families | 🟢 Low |
| 2 | Investigate uint16-packed position reinterpretation for dead-end families | 🟡 Speculative |
| 3 | Build automated OBJ integrity checker (SHA256 regressions, index bounds, NaN sweep) | 🟡 Quality |
| 4 | Scale to live archive extraction for missing manifest entries | 🟢 Blocked |
