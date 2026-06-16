# Cycle 2 — C2-5 Exit Handoff (Consumer Validation Complete)

**Date**: 2026-06-16
**Status**: C2-5 DONE — ingestion test 144/144, OBJ path fix applied
**Phase**: C2-5 (Consumer Validation, C2-5.1..C2-5.5)
**Next**: C2-6 (Scale-out, C2-6.1)

---

## Deliverables

| Step | Output | Status |
|---|---|---|
| C2-5.1 | `ingestion-test.{json,md}` — 6-check consumer validator | ✅ 24/24 all-pass |
| C2-5.2 | Visual placement (transform finiteness + identity contrast) | ✅ 24/24 |
| C2-5.3 | Texture/material resolution (69 textures, 23 assets) | ✅ 24/24 |
| C2-5.4 | Mismatch taxonomy (0 mismatches) | ✅ |
| C2-5.5 | Schema-vs-consumer attribution | ✅ |

## Ingestion Test Results (144/144)

| Check | Pass | Details |
|---|---|---|
| `obj_path` | 24/24 | OBJ paths from flythrough-index; files exist on disk |
| `world_json` | 24/24 | Per-asset world.json sidecars present |
| `transform_finite` | 24/24 | No NaN/Inf in translation, rotation, or scale |
| `textures` | 24/24 | 69 linked textures across 23 assets found on disk |
| `flythrough_crossref` | 24/24 | Manifest linked_texture_count matches flythrough-index |
| `schema_valid` | 24/24 | All entries validate against locked v1 schema |

## Critical Fix — OBJ Path Resolution

**Before**: `build_scene_manifest.py` constructed OBJ paths as `REPO_ROOT / "Assets" / "build" / ...` (doubled `Assets/`) pointing to a path where no .obj files exist.

**After**: `build_geometry()` reads `obj_path` from the flythrough-index entry — the single source of truth carrying per-asset paths like `Exports/decode-nif-geometry-<hash>.json/decode-nif-geometry-mesh<#>.obj`. Falls back to constructed path only when no flythrough entry exists.

This was the single blocker preventing consumer ingestion from reaching 24/24 all-pass.

## Scripts Shipped

| Script | Version | Purpose |
|---|---|---|
| `scripts/build_ingestion_test.py` | v0.1 | Consumer ingestion validator (6 checks per asset) |

## State Machine

```
C2-V4P12: done (1/4 V4 Pro sessions)
C2-3.1: done
C2-4.1..C2-4.5: done → Phase C2-4 DONE
C2-5.1..C2-5.5: done → Phase C2-5 DONE
Current: C2-6 / C2-6.1
```

## Forward Reference — C2-6 Scale-out

C2-6.1 requires defining an expanded cohort of 200-500 assets. The current 24-asset cohort and ingestion validation infrastructure provide the foundation. Key questions for C2-6:

- Can `build_scene_manifest.py` scale to 200-500 assets without timing out?
- Does every asset have `obj_path` in flythrough-index?
- What's the runtime profile per asset?
- Can the deduper and ingestion validator handle 200-500 entries?

## Links

- Ingestion test: `Assets/Exports/discovery-plan/cycle-2/stage5/ingestion-test.json`
- Aggregate pack: `Assets/Exports/discovery-plan/cycle-2/stage4/scene-manifest-pack-v1.json`
- C2-4 exit: `docs/handoffs/2026-06-16-cycle-2-phase-4-exit.md`
- Plan: `docs/roadmap/cycle-2-scene-manifest-plan.md`
