# Session Handoff: Exhaustive Batch Probe + Live-Family Exhaustion

**Date:** 2026-06-11
**Branch:** main
**Commit:** 197dac3

## Summary

- **Enhanced `scripts/live_family_scanner.py`** with exhaustive batch probing: tries ALL mesh-block candidates per family sequentially until position data is found or all exhausted.
- **Auto-update registry**: `_update_live_registry()` appends newly exported IDs to `scripts/live-exported-ids.json` on successful export.
- **All 23 live families exhaustively probed**: 5 position-enabled (exported), 18 no-position (confirmed exhausted).
- **Live inventory position-bearing families are EXHAUSTED** — no new OBJ exports from remaining families.

## Key changes

| File | Change |
|------|--------|
| `scripts/live_family_scanner.py` | `extract_new_families()` now returns ALL unique (id, mb) candidates per family |
| `scripts/live_family_scanner.py` | New `batch_probe_family()` tries all MBs until position found |
| `scripts/live_family_scanner.py` | New `_load_live_registry()` / `_update_live_registry()` auto-update on export |
| `scripts/live_family_scanner.py` | New `--exhaustive` CLI flag for batch probing all mesh blocks |
| `scripts/live_family_scanner.py` | Removed dead `_candidate_role_score()`, fixed `datetime` import, consistent date format |

## Live family status (complete)

| Status | Count | Families |
|--------|-------|----------|
| **Exported** | 5 | 349, 357, 362, 417, 423 |
| **No position (probed)** | 6 | 271, 299, 311, 375, 383, 412 |
| **No position (exhaustive)** | 12 | 218, 243, 256, 282, 303, 333, 338, 341, 350, 380, 391, 396 |
| **Total** | 23 | All exhaustively probed |

## Total live OBJ exports

- **5 OBJs** from **4 asset IDs** across **5 mesh sizes**
- All exported via `--experimental-position-source`

## CI status

- ruff: clean
- mypy: clean
- dotnet build: 0 errors
- dotnet test: 50/50 pass
