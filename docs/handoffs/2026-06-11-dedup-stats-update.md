# Session Handoff: OBJ Duplicate Cleaner + Stats Update

**Date:** 2026-06-11
**Branch:** main
**Commit:** c29f42c

## Summary

- **Built `scripts/dedup_objs.py`** — safe SHA256-verified OBJ duplicate cleaner:
  - Groups by (asset_id, mesh_block) key, keeps largest per SHA256-identical group
  - Dry-run by default (`--execute` to delete)
  - Warns (does NOT delete) when files share same key but differ in content (different export runs)
  - Found 25 duplicate groups, 14 files to delete, 97 KB reclaimable
  - 11 content-mismatch warnings (different export runs preserved)
- **Updated `knowledge.md`** with current project stats:
  - 228 unique OBJs, 169 faced, 24,722 faces, 18,148 vertices
  - 5 live-archive OBJs (349, 357, 362, 417, 423)
  - 23 live families exhaustively probed
  - Added new tools to helper scripts table
- **Ran batch_sweep.py integrity check**: 0 structural issues (NaN, index bounds, negative indices all zero)
- **Confirmed candidate exhaustion**: 0 unexported candidates remain in copied-set inventory
- **CI green**: ruff 0, mypy 0, build 0 errors, tests 50/50
