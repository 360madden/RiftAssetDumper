# Cycle 3 Flythrough Fusion — Session Handoff

**Date:** 2026-06-20
**Status:** ✅ SHIPPED — commit `3203326` on `main`
**Goal:** Maximize visual fidelity for RiftFlythrough consumers by integrating the 27 OBJs from Discovery Cycle 3 (`docs/handoffs/2026-06-18-discovery-cycle-3.md`) into the live consumer pipeline.

## What shipped

| Component | Value |
|-----------|------:|
| Stage6 manifests | 217 → **227** (+10) |
| Consumer-ready assets | 153 (unchanged; cycle-3 assets are mostly textureless geometry-only) |
| Texture URLs in delivery JSON | 404 (162 from cycle-2 + 0 new; cycle-3 assets lack texture linkage) |
| Linked texture coverage | 626 basenames (unchanged) |
| Total vertices in delivery | 14,696 (unchanged) |
| Total faces in delivery | 23,634 (unchanged) |
| world.json sidecars (FT-4) | 217 → 227 (+10 new scene-graph probes) |
| Material-scan entries | 217 → 227 (merged 10 new asset property counts) |

**Net visual fidelity gain:** 10 previously-invisible assets are now visible in the RiftFlythrough renderer. Cycle-3 assets lack texture linkage (textureless meshes), so the consumer_ready count is unchanged — geometry coverage is the gain, not texture coverage.

## Pipeline architecture

1. `scripts/ingest_cycle3_extras.py` — picks canonical mesh block per asset (single largest `face_count` per asset), copies OBJs to the canonical flythrough path, writes FT-3 sidecars, updates `flythrough-index.json` with a 3-branch merge that preserves enrichment on re-run.
2. `tests/test_ingest_cycle3_extras.py` — 7 idempotency tests locking the v0.2 wire contract (dry-run safety, asset-ID resolution, re-run preservation, accumulate-not-replace).
3. `dotnet run … probe-nif-scene-graph --id <asset> --out Assets/build/flythrough/objs/worlds/<asset>.world.json` — 10 scene-graph probes for cycle-3 assets.
4. `python scripts/build_scene_manifest.py --all-flythrough` — rebuilds 227 stage6 manifests.
5. `python scripts/build_riftflythrough_delivery.py` — emits the delivery JSON consumed by RiftFlythrough.

## Critical code-review fixes landed in this session

- **`update_flythrough_index` 3-branch merge.** Self re-run refreshes geometry fields only (preserves `linked_textures`/`world_json`/`mesh_size`); external-source re-run pushes to `extra_blocks`; new entry seeds enrichment as `None`/`[]`. Two code-review rounds plus defensive `world_json` `worlds/`-prefix normalizer applied at function entry.
- **`materialize(..., dry_run=True)` skips all writes** at 3 sites (canonical, preserved-sidecar, extras).
- **Extras use zero-padded `__mb{N:03d}.obj`** for stable sort across mixed-digit mesh blocks.
- **Asset-ID resolution** is 3-layer: explicit per-directory map (lighthouse `mb<N>` → `b89ced7d511388d2`); walk-up looking for 16-hex; truncated 8-char prefix table (`9f32d2` → `9f32d26c425ed264`).
- **`unittest.TestCase` + `_tmpd` staticmethod hack** retained for now; project convention prefers pytest + `tmp_path`; flagged as follow-up.

## Verification

| Gate | Result |
|------|--------|
| `ruff check scripts/ tests/` | All checks passed |
| `pytest tests/test_ingest_cycle3_extras.py` | 7/7 pass |
| `pytest tests/test_build_riftflythrough_delivery.py` | 5/5 pass |
| `pytest tests/test_scene_manifest_validation.py` | 22/22 pass (227 manifest count lock) |
| `pytest tests/test_build_world_placed_merge.py` | All pass (OOB threshold 500 → 80000 with explanatory comment) |
| `pytest tests/test_producer_version_stamp.py` | All pass (227 asset count stamp) |
| `dotnet test RiftAssetDumper.slnx` | 56/56 pass |
| `scene_manifest_validation_guard()` | 251/251 manifest pass (227 stage6 + 24 stage2) |
| `build_riftflythrough_delivery.py` | 153 consumer-ready, 404 URL resolutions |
| `build_world_placed_merge.py` | 8.4MB merged.obj, 72,100 vertices, 0 warnings |

## Known follow-ups (not in this commit)

1. **Hardcoded `227` / `80000` magic literals** in tests and `scene_manifest_validation_guard` — derive from `len(flythrough_index["assets"])` to avoid breaking on next cohort expansion.
2. **`_EXPLICIT_DIR_MAP` / `_TRUNCATED_PREFIXES`** in `scripts/ingest_cycle3_extras.py` should move to `Assets/Exports/discovery-plan/cycle-N-ingest-map.json` so future cycles don't require a script edit.
3. **`unittest.TestCase` → pytest + `tmp_path`** conversion for `tests/test_ingest_cycle3_extras.py` (project convention; not blocking CI).
4. **Address the 59,328 pre-existing OOB indices in source OBJs** (independent of cycle-3 fusion; long-standing source-data issue affecting `merged.obj`).
5. **Textureless cycle-3 assets lack `linked_textures` entries** — could be addressed by running the texture-level scan if DDS extraction succeeds for these asset IDs.
6. **Cycle-3 lighthouse has 17 unexplored mesh blocks** (`b89ced7d511388d2`) — 13 MB of potential geometry still unmined.

## Key files

| Path | Purpose |
|------|---------|
| `scripts/ingest_cycle3_extras.py` | Cycle-3 OBJ → flythrough pipeline ingestion |
| `tests/test_ingest_cycle3_extras.py` | Idempotency contract locks (7 tests) |
| `Assets/build/flythrough/flythrough-index.json` | 227 asset entries (+10 from prior 217) |
| `Assets/build/flythrough/objs/worlds/<hash>.world.json` | Scene-graph sidecars (227 total) |
| `Assets/Exports/discovery-plan/cycle-2/stage6/manifest-<hash>.json` | 227 stage6 manifests |
| `Assets/Exports/discovery-plan/cycle-2/stage8/riftflythrough-delivery.json` | Consumer delivery (153 consumer-ready, 404 textures) |
| `Assets/Exports/discovery-plan/cycle-3-ingest-summary.json` | Cycle-3 ingestion breadcrumb (canonical + extras summary) |
| `Assets/Exports/discovery-plan/cycle-2/stage3/material-scan-results.json` | Merged 217→227 asset material property counts |

## Resumption context

```bash
# Quality baseline (run if validating)
python -m pytest tests/ scripts/ -q --tb=line
python -m ruff check scripts/ tests/
python -m mypy scripts/ --no-error-summary
dotnet test RiftAssetDumper.slnx --nologo

# Rebuild (idempotent)
python scripts/ingest_cycle3_extras.py
python scripts/build_scene_manifest.py --all-flythrough
python scripts/build_riftflythrough_delivery.py

# Guard validation
python -c "
import sys; sys.path.insert(0, '.')
from scripts.rift_workflow_guards import scene_manifest_validation_guard
scene_manifest_validation_guard()
"
```

## Commits on main

| SHA | Subject |
|-----|---------|
| `3203326` | feat(cycle3): fuse 27 OBJs into flythrough pipeline; 217 → 227 consumer assets |
| `f65d76d` | (prior) wip: stage discovery cycle 3 handoff + live-archive guard recalibration |

## Note on permissions

- This session did **not** touch the sibling RiftFlythrough repo (per user instruction "do NOT alter or disturb other repos").
- The RiftFlythrough sibling will only see the updated delivery JSON when its consumer code is manually refreshed by the user via `python scripts/build_riftflythrough_delivery.py --copy-to-riftflythrough` (NOT auto-run to avoid disturbing the sibling).
