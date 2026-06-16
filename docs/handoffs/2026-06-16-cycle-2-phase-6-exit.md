# Cycle 2 — C2-6 Exit Handoff (Scale-out Complete)

**Date**: 2026-06-16
**Status**: C2-6 DONE — 217/217 manifests at 0.013s/asset
**Phase**: C2-6 (Scale-out, C2-6.1..C2-6.5)
**Next**: C2-7 (Final Validation + V4 Pro Ship/Kill)

---

## Deliverables

| Step | Output | Status |
|---|---|---|
| C2-6.1 | Expanded cohort: all 217 flythrough-index assets | ✅ 217 manifests in stage6/ |
| C2-6.2 | Perf profile: wall-clock timing per asset | ✅ 2.7s / 0.013s per asset |
| C2-6.3 | Optimize batching: single-pass flythrough-index load, minimal per-asset work | ✅ |
| C2-6.4 | Scaled closure: 217/217 built, 0 invalid, 0 errors | ✅ |
| C2-6.5 | This handoff | ✅ |

## Scale-out Metrics

| Metric | Value |
|---|---|
| Total assets | 217 |
| Built successfully | 217 (100%) |
| Invalid (schema) | 0 |
| Errors (missing data) | 0 |
| Wall-clock | 2.7s |
| Per-asset time | 0.013s |
| Projected for 500 assets | ~6.5s |

## Key Fixes for Scale-out

- **`--all-flythrough` flag**: Added to `build_scene_manifest.py` — iterates all 217 flythrough-index asset IDs, outputs to `stage6/manifest-{id}.json`
- **`world_json` path resolution**: `load_world()` now resolves bare filenames from flythrough-index (e.g., `0603cce7cee15eb8.world.json`) against `WORLD_DIR`. Falls back to constructed path.
- **`build_world` signature**: Now accepts optional `flythrough_entry` parameter for world_json path resolution.
- **`load_world` signature**: Now accepts optional `flythrough_entry` parameter for path resolution.

## Scripts Updated

| Script | Version | Change |
|---|---|---|
| `scripts/build_scene_manifest.py` | v0.5 | `--all-flythrough`, `load_all_flythrough_ids()`, wall-clock timing, world_json path fix |

## State Machine

```
C2-V4P12: done (1/4 V4 Pro sessions)
C2-3.1: done
C2-4.1..C2-4.5: done → Phase C2-4 DONE
C2-5.1..C2-5.5: done → Phase C2-5 DONE
C2-6.1..C2-6.5: done → Phase C2-6 DONE
Current: C2-7 / C2-7.1
```

## Forward Reference — C2-7 Final Validation + Ship/Kill

C2-7 requires:

- C2-7.1: Scene manifest validation test
- C2-7.2: Validation guard (9th guard)
- C2-7.3: Full CI validation
- C2-7.4: Ship/kill brief
- C2-7.5: Final handoff + V4P5 decision

Exit criteria: 9/9 proof guards PASS, full CI green, V4P5 ship/kill decision.

## Links

- Scale-out manifests: `Assets/Exports/discovery-plan/cycle-2/stage6/manifest-*.json` (217 files)
- C2-5 exit: `docs/handoffs/2026-06-16-cycle-2-phase-5-exit.md`
- Plan: `docs/roadmap/cycle-2-scene-manifest-plan.md`
