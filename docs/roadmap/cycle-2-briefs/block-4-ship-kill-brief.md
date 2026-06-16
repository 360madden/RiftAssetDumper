# Cycle 2 Ship-Kill Brief — C2-7.4 (v0.7 Enrichment Update)

**Date:** 2026-06-16
**Author:** DeepSeek V4 Pro (autonomous session)
**Decision:** **SHIP** — Cycle 2 complete with 153/217 (70.5%) consumer-ready assets

---

## Evidence Summary (Updated v0.7)

### C2-7.1 Validation Test Suite — 38/38 PASS

`tests/test_scene_manifest_validation.py` + `tests/test_build_scene_manifest.py`

### C2-7.2 Consumer Contract Guard — PASS

`scene_manifest_validation_guard()` — 241 manifests (217 stage6 + 24 stage2), 0 failures across all 10 checks

### Geometry Enrichment (v0.6)

| Metric | Value |
|--------|-------|
| vertex_count populated | 217/217 |
| face_count populated | 217/217 |
| mesh_block (M#N) | 217/217 |
| render_class = "faced" | 155 |
| render_class = "point-only" | 62 |
| obj_sha1 computed | 217/217 |

### Material Inference (v0.7)

| Metric | Value |
|--------|-------|
| material_status = "textured" | 212 |
| material_status = "material-or-vertex-color-only" | 2 |
| material_status = "unknown" | 3 |
| **consumer_ready (stage6)** | **153/217 (70.5%)** |
| consumer_ready (stage2) | 15/24 (62.5%) |

### Quality Gates

| Check | Result |
|-------|:---:|
| Schema validation (241 manifests) | ✅ |
| OBJ paths exist | ✅ |
| World.json paths exist | ✅ |
| Transform finiteness | ✅ |
| Texture source enum | ✅ |
| Producer version v0.7 | ✅ |
| Pack integrity | ✅ |
| Ingestion test (24 cohort) | 144/144 ✅ |
| Ruff | ✅ |
| Mypy | ✅ |
| Pytest (38 tests) | ✅ |

---

## Remaining Gaps (Non-Blocking)

- 2 faced assets lack texture linkage → consumer_ready blocked
- 62 point-only assets can never be consumer_ready (no face data)
- `texture_property_count`, `material_property_count`, `vertex_color_property_count` remain 0 (need NIF-level scan)
- `scanned_at` remains null
- `material_status` is inferred from texture linkage, not confirmed by NIF scan

---

## Recommendation

**SHIP.** 153/217 assets are consumer-ready with populated geometry, verified transforms, linked textures, and inferred materials. The remaining 64 assets have documented reasons for non-readiness tracked in `validation.warnings`. The scene-manifest/v1 consumer contract is intact across all 241 manifests.
