# Cycle 5 — Semantic-Category Surface — Session Handoff

**Date**: 2026-06-21
**Status**: ✅ SHIP — Cycle 5 wire formats v0.9 (scene manifest) + v0.3 (delivery) live
**Files**: 2 new + 4 modified + 1 schema extension

## What Shipped

| File | Purpose |
|------|---------|
| `scripts/semantic_surface.py` (NEW) | Loader module: 3-matrix union, hint categorization, contract: `{categories: [...], sources: {...}}` |
| `tests/test_semantic_surface.py` (NEW) | 12 wire-format lock tests covering loader, scene-manifest injection, delivery integration |
| `docs/schemas/scene-manifest-v1.schema.json` | Added optional `semantic` property + `$defs/Semantic` (categories + sources) |
| `scripts/build_scene_manifest.py` | v0.9: injects `semantic` sub-record into every stage6 manifest via `_build_semantic_block(asset_id)` |
| `scripts/build_riftflythrough_delivery.py` | v0.3: surfaces flat `semantic_categories` list per delivery entry; stats counts `tagged_assets` + `distinct_hints` |
| `tests/test_build_scene_manifest.py` | Subprocess PYTHONPATH propagated so `scripts.` imports resolve under pytest |
| `pyproject.toml` | BOM stripped + CRLF normalized + `pythonpath = ["."]` for test runner |

## Wire-Format Contracts

### Scene Manifest v0.9 — Optional `semantic` Sub-Record

```json
{
  "semantic": {
    "categories": ["hint:map-zone", "hint:actor-object"],
    "sources": {
      "hint:map-zone": "semantic-nif-map-zone.json",
      "hint:actor-object": "semantic-nif-actor-object.json",
      "hint:waypoint-poi": "<absent>"
    }
  }
}
```

- **Always present** (never omitted) — empty contract = `{categories: [], sources: {hint:'<absent>'}}`
- Optional in schema; consumers must handle missing key (pre-Cycle-5 manifests)
- `HINTS = ("hint:actor-object", "hint:map-zone", "hint:waypoint-poi")` — canonical order in `categories`
- **`ABSENT_MARKER = "<absent>"`** — reserved for paths that DO NOT exist on disk
- Empty-but-existing file → basename (so consumers can tell "scanned but no hits" apart from "not scanned")

### Delivery v0.3 — Flat `semantic_categories` Per Entry

```json
{
  "asset_id": "abc1234567890abc",
  "semantic_categories": ["hint:map-zone", "hint:actor-object"],
  ...
}
```

- Top-level list (NOT nested under `semantic`) — matches RiftFlythrough consumer pattern
- Top-level stats: `tagged_assets` (entries with `semantic_categories` non-empty) + `distinct_hints` (union) + `hint_distribution` (per-hint count)

## Loader Contract (Cycle 5 Surface)

`scripts/semantic_surface.py` exposes:

| Symbol | Type | Purpose |
|--------|------|---------|
| `HINTS` | `tuple[str, ...]` | Canonical hint set (3 entries) — adding hints = wire-format extension |
| `ABSENT_MARKER` | `str` | Literal `'<absent>'` for missing matrix paths |
| `SOURCE_BASENAME_ONLY` | `bool` | `True` — sources emit basenames only (portable, no absolute paths) |
| `DEFAULT_MATRIX_DIR` | `Path` | Default `Assets/Exports/discovery-matrices/nif-semantic-hints/` |
| `load_matrix(hint, matrix_dir)` | `(str, Path) → list[dict]` | Load one matrix file; degrades to `[]` on missing/malformed |
| `load_all_matrices(matrix_dir)` | `(Path) → dict[str, list[dict]]` | Load all 3 matrices keyed by hint |
| `categorize_asset(asset_id, matrices=None)` | `(str, dict \| None) → list[str]` | Union of categories for asset_id across 3 matrices (case-insensitive AssetIdPrefix match) |
| `build_semantic_block(asset_id, matrix_dir=None)` | `(str, Path \| None) → dict` | The injection contract |

## Validation Results

| Check | Result |
|--------|--------|
| `pytest tests/test_semantic_surface.py tests/test_build_scene_manifest.py tests/test_build_riftflythrough_delivery.py tests/test_scene_manifest_validation.py tests/test_cycle4_lod_metadata.py` | **71/71 PASS** |
| `ruff check` on touched modules | **0 errors** |
| `mypy --no-error-summary` on touched modules | **0 errors** |
| `scene_manifest_validation_guard()` (9th guard) | **PASS — 251/251 manifests** (existing v0.6→v0.8 manifests still valid; opt-in migration) |

## Source-Drift Recalibration (Cycle 5 Specific)

The 3 source-binding families originally hardcoded in `_get_family_decision` for the deleted `Source/` copied-set were replaced with a generic "candidate-only" label — live-archive calibrated (2026-06-19). Original families (`mesh329 mesh#7/mesh#34 stream@212`, `mesh305 mesh#7/mesh#27 stream@188`, `mesh321 mesh#7/mesh#31 stream@204`) are no longer present; new families get the dynamic live-archive suffix `live-archive-calibrated-2026-06-19`.

## Migration Safety

- **Pre-Cycle-5 manifests** (already in `Assets/Exports/discovery-plan/cycle-2/stage6/`): `semantic` key absent. Validator accepts this — schema makes `semantic` optional. ✅
- **Cycle 5 manifests** (`build_scene_manifest.py` v0.9): `semantic` always populated (empty contract when no matrix data).
- **Delivery entries** (`build_riftflythrough_delivery.py` v0.3): `semantic_categories` always emitted as `list` (empty list when source manifest has no `semantic`).

## Resumption

```bash
# All-in-one validation (from session baseline)
python -m pytest tests/test_semantic_surface.py tests/test_build_scene_manifest.py tests/test_build_riftflythrough_delivery.py tests/test_scene_manifest_validation.py tests/test_cycle4_lod_metadata.py -q --tb=short
python -m ruff check scripts/semantic_surface.py scripts/build_scene_manifest.py scripts/build_riftflythrough_delivery.py tests/test_semantic_surface.py tests/test_build_scene_manifest.py
python -m mypy scripts/semantic_surface.py scripts/build_scene_manifest.py scripts/build_riftflythrough_delivery.py tests/test_semantic_surface.py tests/test_build_scene_manifest.py --no-error-summary

# Regenerate manifests with semantic surface (full cohort)
python scripts/build_scene_manifest.py --all-flythrough

# Regenerate delivery with semantic_categories
python scripts/build_riftflythrough_delivery.py

# Stage + commit (untracked files):
git add scripts/semantic_surface.py tests/test_semantic_surface.py \
        scripts/build_scene_manifest.py scripts/build_riftflythrough_delivery.py \
        docs/schemas/scene-manifest-v1.schema.json \
        tests/test_build_scene_manifest.py pyproject.toml \
        docs/handoffs/2026-06-cycle-5-semantic-surface.md \
        docs/roadmap/current-phase.md
git commit -m "feat: ship Cycle 5 semantic-category surface (v0.9 manifest + v0.3 delivery)"
```

## Files Modified in This Session (untracked → ready-to-commit)

- `scripts/semantic_surface.py` (NEW, 7,581 bytes)
- `tests/test_semantic_surface.py` (NEW, 18,058 bytes)
- `scripts/build_scene_manifest.py` (v0.9)
- `scripts/build_riftflythrough_delivery.py` (v0.3)
- `docs/schemas/scene-manifest-v1.schema.json` (added `$defs/Semantic` + optional `semantic`)
- `tests/test_build_scene_manifest.py` (PYTHONPATH propagation in subprocess)
- `pyproject.toml` (BOM strip + CRLF normalize + `pythonpath = ["."]`)
- `docs/handoffs/2026-06-cycle-5-semantic-surface.md` (this file)
- `docs/roadmap/current-phase.md` (Cycle 5 entry added)
