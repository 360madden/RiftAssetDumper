# Session Handoff: Data-Driven Live Provenance + 2 New Live-Archive OBJs

**Date:** 2026-06-11
**Branch:** main
**Commit:** abc9021

## Summary

- **2 new live-archive OBJs exported**: meshSize=417 (110v, 335f, 18.8 KB) and meshSize=423 (124v, 376f, 21.9 KB) — both position-float3-lead, clean (0 NaN).
- **Data-driven live provenance**: Replaced hardcoded live IDs in `build_export_manifest.py` with `_load_live_exported_ids()` that reads `scripts/live-exported-ids.json` at runtime.
- **Manifest v3 now tracks 5 live OBJs** (from 4 asset IDs: cf54e712ff57eaac [357+362], 1ecdbaf5a2576ba5 [349], 838831f8fb617ecc [417], 95d9b14a964e67c8 [423]) and 345 copied-source OBJs.
- **Index-priority families exhausted**: meshSize=375, 383, 412 probed — all have UV+normal+index, no position. Only 417 and 423 had position data.
- **Code cleanup**: Removed dead isinstance check, unreachable KeyError, redundant str() conversion, dead path heuristic from manifest.

## Key files changed

| File | Change |
|------|--------|
| `scripts/build_export_manifest.py` | Added `_load_live_exported_ids()`, data-driven `detect_provenance()`, path moved to `scripts/` |
| `scripts/live-exported-ids.json` | New: data-driven registry of 4 live-exported asset IDs with mesh sizes |

## New OBJs

| MeshSize | Asset ID | Vertices | Faces | Size (B) |
|----------|----------|----------|-------|----------|
| 417 | 838831f8fb617ecc | 110 | 335 | 18,843 |
| 423 | 95d9b14a964e67c8 | 124 | 376 | 21,886 |

## Live Export Totals

- **5 OBJs** from **4 asset IDs** across **5 mesh sizes**: 349, 357, 362, 417, 423
- All exported via `--experimental-position-source` (0-attribute-set fallback path)

## Known remaining

- **21 new mesh-size families** remain in live inventory (from the original 23 discovered, minus 2 now exported)
- Families 271, 299, 311, 375, 383, 412 have normals/UVs/indexes but no position data
- To find position data in remaining families: probe additional mesh blocks within each NIF
- `scripts/live_family_scanner.py` can batch-probe and export with `--probe` and `--export` modes

## CI status

- ruff: clean
- mypy: clean
- dotnet build: passes
- dotnet test: 6/6 pass
