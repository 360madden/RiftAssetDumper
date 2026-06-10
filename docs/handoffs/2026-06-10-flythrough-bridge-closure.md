# Flythrough Bridge Plan — Closure Handoff

**Status**: ✅ **COMPLETE** — FT-1 through FT-7 done, FT-8 skipped
**Date**: 2026-06-10
**Owner**: Assets repo (`RiftAssetDumper`)
**Consumer**: `C:\RIFT MODDING\RiftFlythrough` (sibling, v1.35.0)

## TL;DR — What RiftFlythrough gets

One file to consume them all: **`flythrough-index.json`** (144 KB)

| Artifact | Count | FT Phase |
|---|---|---|
| PNG textures | 12,954 (1.1 MB) | FT-1 |
| OBJ files | 350 raw, 217 unique | FT-2 |
| Per-OBJ metadata sidecars | Emitter proven (`asset-mesh-manifest-v1`) | FT-3 |
| World transforms (world.json) | 217 (100% coverage, 4 non-identity) | FT-4 |
| World-placed merged.obj | 2.5 MB, 17,483 vertices, 23,716 faces | FT-4+FT-8 |
| Pipeline orchestrator | `bulk_export_for_flythrough.py` + `flythrough_plan.py` | FT-5 |
| Validation suite | `ft6_validation.py` (5 checks, 100% cross-ref, PASS) | FT-6 |
| LOD manifest | 193/217 classified (88.9%, 10 MeshSize families) | FT-7 |
| MeshSize enrichment | 217/217 known (100%) | FT-8 |
| Unified flythrough-index.json | 217 assets, 100% cross-referenced | Closure |
| transform_loader.js | 4 KB, delivered to RiftFlythrough/js/ | Bridge |

## Phase completion summary

| Phase | Topic | Status | Key metric |
|---|---|---|---|
| FT-1 | DDS → PNG | ✅ | 12,954 textures, 83s |
| FT-2 | Bulk NIF → OBJ | ✅ | Pipeline ships; 7/56 probe subset |
| FT-3 | Metadata sidecar | ✅ | `asset-mesh-manifest-v1` schema + emitter |
| FT-4 | Scene graph (KEYSTONE) | ✅ | 217 world.jsons, 100% coverage |
| FT-5 | Pipeline integration | ✅ | `bulk_export_for_flythrough.py` subcommands |
| FT-6 | Validation suite | ✅ | 5 checks, 100% cross-ref, 6 orphan-mesh world.jsons |
| FT-7 | Zones + LOD | ✅ | LOD: 193/217 (88.9%), 10 families; Zones: negative |
| FT-8 | Mod-replacement bridge | ⏭️ **SKIPPED** | See rationale below |

## FT-8 skip rationale

The FT-8 mod-replacement bridge involves writing modified assets back into TWAD archives — recompressing, updating checksums, and potentially writing to the live game install. This directly contradicts the project's core mandate (read-only archive research). The Flythrough Bridge Plan itself marks FT-8 as **optional and safety-gated**.

**Decision**: Skip FT-8. The unified `flythrough-index.json` plus the existing per-NIF artifacts (OBJs, world.json, textures) provide everything RiftFlythrough needs as a viewer. If mod-injection becomes a priority, FT-8 can be resurrected from the plan with a full safety review.

## Unified flythrough-index.json structure

```json
{
  "schema": "flythrough-index-v1",
  "plan_status": "complete",
  "ft_phases_complete": ["FT-1",...,"FT-7"],
  "ft_8_skipped": true,
  "texture_count": 12954,
  "summary": {
    "total_asset_ids": 217,
    "coverages": {
      "world_json_pct": 100.0,
      "lod_pct": 88.9,
      "meshsize_pct": 100.0
    },
    "total_vertices": 17483,
    "total_faces": 23716
  },
  "assets": {
    "<16-char-hex>": {
      "vertex_count": ...,
      "world_json": "...",
      "lod_type": "...",
      "mesh_size": ...
    }
  }
}
```

## Key artifacts delivered

| Path | Description |
|---|---|
| `flythrough-index.json` | **Unified index** — single consumable file for RiftFlythrough |
| `flythrough/textures/converted/` | 12,954 PNG textures |
| `flythrough/objs/worlds/*.world.json` | 217 per-NIF scene graphs |
| `flythrough/lod-manifest.json` | LOD variant classification (193/217, 88.9%) |
| `flythrough/scene-graph-manifest.json` | World.json index (217 entries) |
| `flythrough/world-placed-merged.obj` | Hierarchy-aware merged OBJ (2.5 MB) |
| `flythrough/riftflythrough/transform_loader.js` | Runtime transform loader for RiftFlythrough (4 KB) |
| `evidence/ft7.2/EVIDENCE.md` | LOD detection findings |
| `evidence/ft7.1/EVIDENCE.md` | Zone metadata (negative result) |
| `evidence/ft6.2/validation-report.json` | FT-6 validation report (PASS, 100% cross-ref) |

## RiftFlythrough consumption

RiftFlythrough can load `flythrough-index.json` directly:

```javascript
const index = await fetch('flythrough-index.json');
// index.assets["cf54e712ff57eaac"] → { vertex_count: 6489, world_json: "...", lod_type: "same-nif" }
// index.texture_count → 12954
```

Each asset entry links to its world.json, OBJ path, LOD level, and MeshSize family.

## Known gaps (non-blocking)

| Gap | Detail | Impact |
|---|---|---|
| 6 orphan-mesh world.jsons | Meshes lack parent node refs — fall back to identity transform | Likely zero visual impact — identity transform is correct for root-level meshes without parent nodes |
| Probe-lookup subset limited | 7/56 (12.5%) export success; inventory built from deleted Source/ | Pipeline proven; needs fresh live-archive inventory for full coverage |
| Zone partitioning skipped | Zone metadata is render config, not terrain partitioning (FT-7.1 negative) | Deferred to RiftFlythrough-side zone discovery |
| FT-8 mod-injection skipped | Conflicts with read-only archive research mandate | Can be resurrected with safety review if needed |

## Validation snapshot (2026-06-10)

| Check | Result |
|---|---|
| pytest (all tests) | 119/119 ✅ |
| mypy (scripts + tests) | 0 errors ✅ |
| ruff (scripts + tests) | 0 errors ✅ |
| C# build | 0 errors ✅ |
| C# tests (xUnit) | 55/55 ✅ |
| FT-6 validation | PASS (100% cross-ref) ✅ |
| Pipeline smoke (build_world_placed_merge.py) | 217/217 processed, 0 errors ✅ |

## Resume markers

- `.state.json`: `plan_status: "complete"`, `current_phase: null`
- All 7 phases done, FT-8 skipped
- Plan: `docs/roadmap/flythrough-bridge-plan.md` (archived reference)
- Latest commit: `1cbcd99` (roadmap closure) — 356 total commits, 10 ahead of origin
