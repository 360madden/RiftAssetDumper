# Cycle 2 — C2-4 Exit Handoff (Batch Reconstruction Complete)

**Date**: 2026-06-16
**Status**: C2-4 DONE — per-asset manifests, aggregate pack, dedup, stats all shipped
**Phase**: C2-4 (Batch Reconstruction, C2-4.1..C2-4.5)
**Next**: C2-5 (Consumer Validation)

---

## Deliverables

| Step | Output | Status |
|---|---|---|
| C2-4.1 | 24 per-asset manifests against locked v1 schema | ✅ 24/24 VALID |
| C2-4.2 | `scene-manifest-pack-v1.json` (aggregate pack, 24 entries) | ✅ |
| C2-4.3 | `dedupe-report.{json,md}` (1 exact group, 41 near-duplicate pairs) | ✅ |
| C2-4.4 | `summary-stats.{json,md}` (6 mesh_size families, 69 linked textures) | ✅ |
| C2-4.5 | This handoff | ✅ |

## Key Metrics

| Metric | Value |
|---|---|
| Cohort size | 24 (4 non-id + 20 identity) |
| Consumer-ready | 0/24 (geometry/material/texture extraction pending) |
| Linked textures | 69 across 23 assets |
| Textures source | 23 flythrough / 1 unknown |
| MeshSize families | 6 (193, 305, 321, 325, 329, null) |
| Unique fingerprints | 23/24 (1 exact duplicate pair: `2c85cfa` = `593ea32`) |
| Near-duplicate pairs | 41 (all sharing transform+mesh_size, differing only in textures) |

## Critical Fixes

- **`load_flythrough_entry`**: Changed from list-iteration to dict-key lookup — flythrough-index.json `assets` is a dict keyed by asset_id, not a list. This was the root cause of all 24 manifests showing `textures.source: "unknown"`.
- **`consumer_ready` gate**: Now requires `textures.source != "unknown"` in addition to existing vertex/face/material requirements.

## Schema

- **Locked v1 schema**: `Assets/Exports/discovery-plan/cycle-2/stage2/scene-manifest-v1.schema.json`
- **Draft preserved**: `scene-manifest-v1.draft.schema.json`
- **V4P12 decisions**: documented in `docs/handoffs/2026-06-16-c2-v4p12-output.md`

## Scripts Shipped

| Script | Version | Purpose |
|---|---|---|
| `scripts/build_scene_manifest.py` | v0.5 | Per-asset manifest builder (locked schema, textures.source, obj_sha1, scanned_at) |
| `scripts/build_aggregate_stats.py` | v0.2 | Aggregate pack + summary stats + dedup (C2-4.2..C2-4.4) |

## State Machine

```
C2-V4P12: done (1/4 V4 Pro sessions)
C2-3.1: done
C2-4.1: done → C2-4.2: done → C2-4.3: done → C2-4.4: done → C2-4.5: done
Phase C2-4: DONE
Current: C2-5 / C2-5.1
```

## Forward Reference — C2-5 Consumer Validation

C2-5.1 requires testing ingestion in RiftFlythrough: loading the `scene-manifest-pack-v1.json` and verifying the 24 assets render with correct transforms and texture linkage. The pack contains full `world_transform_summary` data (4 non-identity transforms) and 69 linked texture references (23 assets) ready for consumer-side validation.

## Links

- V4P12 output: `docs/handoffs/2026-06-16-c2-v4p12-output.md`
- C2-4.x contract: `docs/handoffs/2026-06-16-c2-4.x-contract-firing.md`
- Locked schema: `Assets/Exports/discovery-plan/cycle-2/stage2/scene-manifest-v1.schema.json`
- Aggregate pack: `Assets/Exports/discovery-plan/cycle-2/stage4/scene-manifest-pack-v1.json`
- Plan: `docs/roadmap/cycle-2-scene-manifest-plan.md`
