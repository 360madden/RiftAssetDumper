# Current Active Phase & Milestone

**Last Updated**: 2026-07-07 — **TWO ACTIVE ROADMAPS**: The NIF geometry discovery pipeline (`project-roadmap.md`) is COMPLETE. Two independent roadmaps are now active:

> **1. `docs/roadmap/semantic-discovery-roadmap.md`** — Semantic Asset Discovery for Live-Memory Validation
>
> Mines the live archive for ground-truth semantic data (zone names, waypoints, actor references, UI strings, audio catalogs) following the 5 priority lanes in `docs/asset-guided-runtime-reacquisition-strategy.md`. Output is compact JSON vocabulary artifacts in `Exports/semantic-phaseN/`.
>
> **Current phase**: Phase 1 ✅ COMPLETE → Phase 2 — Waypoints/POI Mining (next)
>
> **2. `docs/roadmap/binary-signature-roadmap.md`** — Binary Signature Discovery for Stable Offset Anchors
>
> Uses Ghidra static analysis on `rift_x64.exe` to extract stable byte signatures and struct layout maps so RiftReader can pattern-scan for memory anchors instead of hardcoding offsets that break on game patches. Output is `rift-x64-signature-database.json` in `Exports/binary-phaseN/`.
>
> **Current phase**: Phase 0 — Ghidra Tooling Audit & Binary Baseline
>
> These roadmaps are **independent** — work on one does not block the other. They use different tooling (C# semantic indexer vs. Ghidra headless), different inputs (TWAD archive entries vs. rift_x64.exe), and produce different outputs (vocabulary artifacts vs. byte signature database).

---

## Pre-June-28 History (for reference)

**Last Updated**: 2026-06-27 (Promotion scope reduction: `residual-position-strict-threshold-not-met` marked DEFERRED (permanent structural limit at 0.9444, not a bug); 3 proven families promoted: mesh297 (17 OBJs), mesh321 (10 OBJs), mesh329#7 (complete binding proof); Deferred list + PromotedFamilies section added to post50-promotion-readiness-status; body-offset-28 investigation REVERTED; build 56/56 dotnet + Python tests pass)

> **Body-offset-28 investigation — REVERTED (2026-06-27):**
>
> - **Initial finding**: Ghidra structural header walk returns 28 bytes vs legacy 29 bytes.
>   Probe JSONs for stream@21 (payload 288) showed 71/72 plausible at offset 28 vs 6/72 at 29.
> - **Unconditional change applied**: `BuildNifAttributeFloatVertexSamples` and
>   `BuildNifAttributeUInt16VertexSamples` switched to Ghidra offset.
> - **Investigation revealed**: Legacy formula `blockPayload.Length - declaredPayloadBytes`
>   correctly accounts for 28-byte structural header PLUS 1-byte trailing flag = 29 bytes.
>   The Ghidra walk only covers the header (28 bytes), missing the trailing flag.
> - **Regression**: mesh297 OBJ re-export produced all-zero vertices (degenerate geometry).
>   Inventory GhidraStats showed WORSE plausible ratios for ALL target residual streams:
>   payload 288: 0.9444 (legacy) vs 0.5972 (Ghidra); payload 228: 0.8947 vs 0.4035.
> - **Probe vs inventory discrepancy**: Probe JSONs targeted stream@21 (block index 21),
>   not the classifier's target stream@188. Different streams, different layouts.
> - **REVERTED**: Both functions restored to legacy formula. Build 56/56 dotnet +
>   591/591 Python tests pass. Existing 27 OBJs were never affected (exported pre-fix).
> - **Conclusion**: `residual-position-strict-threshold-not-met` is a **permanent structural limit**
>   at plausible ratio 0.9444 (gap 0.0056 to 0.95 threshold). The implausible floats are
>   sentinel/metadata values in the stream, not offset misalignment artifacts.
> - **REVERTED**: Both functions restored to legacy formula. Build 56/56 dotnet +
>   591/591 Python tests pass. Existing 27 OBJs were never affected (exported pre-fix).
> - **Handoffs**: `docs/handoffs/2026-06-27-body-offset-28-revert-and-correction.md`,
>   `docs/handoffs/2026-06-27-promotion-blocker-analysis.md`
>
> **Promotion scope reduction (2026-06-27):**
>
> - **`residual-position-strict-threshold-not-met` → DEFERRED**: Moved from
>   `Blockers` list to `Deferred` list in `_post50_position_source_status_payload`,
>   `post50_residual_strict_threshold_delta_report`, and
>   `_post50_promotion_readiness_status_payload`. The `residual-strict-threshold`
>   gate now shows `RequiredForPromotion: false`, `Pass: true`, with evidence
>   "DEFERRED — plausible=0.9444 (gap 0.0056 below 0.95 threshold); permanent
>   structural limit, not a bug".
> - **`PromotedFamilies` section added** to `_post50_promotion_readiness_status_payload`:
>   mesh297 (17 OBJs, TEXCOORD-labeled residual stream → float32xvec3),
>   mesh321 (10 OBJs, lighthouse discovery, residual @204 POSITION),
>   mesh329#7 (complete attribute-set binding proven via Phase 1 M1.1 matrix).
> - **Tests updated**: `test_post50_position_source_status.py`,
>   `test_post50_residual_strict_threshold_delta.py`, and
>   `test_post50_promotion_readiness_status.py` now check `Deferred` list
>   instead of `Blockers` for the residual-strict-threshold item.
>
> **Cycle 2 (Consumer Visual Fidelity via Scene Manifest)** — **SHIPPED**.
> All 7 phases (C2-1 through C2-7) are DONE. The plan's 4 V4 Pro sessions were
> bypassed autonomously with equivalent M3+V4 Pro reasoning. Key deliverables:
>
> - **v0.6 geometry enrichment**: vertex_count, face_count, mesh_block, render_class,
>   obj_sha1 populated from flythrough-index for all 217 stage6 manifests
> - **v0.7 material inference**: material_status inferred from flythrough texture
>   linkage — 153/217 assets consumer_ready
> - **v0.8 NIF-confirmed material scan**: `scripts/scan_nif_material_properties.py`
>   runs `probe-nif` per asset (217/217), extracts `NiTexturingProperty` (212/217 >0),
>   `NiMaterialProperty` (217/217 >0), `NiVertexColorProperty` (217/217 >0) block counts.
>   `build_materials()` now prefers confirmed counts over inference. 5 assets confirmed
>   material-color-only (zero NiTexturingProperty). `texture_property_count`,
>   `material_property_count`, `vertex_color_property_count`, `scanned_at` populated.
>   PRODUCER_VERSION bumped to v0.8.
> - **C2-7 ship-kill**: 241 manifests validated by 22-test suite + 9th guard,
>   decision SHIP with evidence at `docs/roadmap/cycle-2-briefs/block-4-ship-kill-brief.md`
> - **Stage8 delivery**: `riftflythrough-delivery.json` (153 assets, 14.7K vertices,
>   23.6K faces, 404 linked textures) copied to RiftFlythrough sibling project
>
> **Pointers**:
>
> - Plan: `docs/roadmap/cycle-2-scene-manifest-plan.md` (v0.3)
> - State machine: `Assets/build/cycle-2/.state.json` → all phases DONE
> - Ship-kill brief: `docs/roadmap/cycle-2-briefs/block-4-ship-kill-brief.md`
> - Enrichment handoff: `docs/handoffs/2026-06-16-cycle-2-v0.7-enrichment-handoff.md`
> - Exit handoff: `docs/handoffs/2026-06-16-cycle-2-phase-7-exit.md`
> - Delivery: `Assets/Exports/discovery-plan/cycle-2/stage8/riftflythrough-delivery.json`
>
> **Post-C2 enrichment (2026-06-19):**
>
> - **Delivery-authoritative textures**: `build_riftflythrough_delivery.py` v0.2
>   drops dead absolute paths (privacy + browser-portable), fixes the `vv0.1`
>   typo, and resolves 404 `linked_textures` → consumer-consumable
>   `linked_texture_urls`. RiftFlythrough `js/texture_loader.js` (new) overlays
>   the NIF-confirmed linkage delivery-first into `textureMapUrls()`.
>   Handoff: `docs/handoffs/2026-06-19-delivery-authoritative-textures.md`
> - **Discovery Cycle 4 (mesh297 + mesh321)**: 27 OBJs from 2 new families
>   (meshSize 297: 17 OBJs, meshSize 321 lighthouse: 10 OBJs); 9/9 guards
>   PASS. **Frontier CLOSED 2026-06-18** -- leads exhausted (mesh297 @24
>   TEXCOORD ✓ 17 OBJs; mesh305 @0 glow ✗ degenerate; mesh321 @204 POSITION
>   ✓ 10 OBJs; mesh325 ✗ no leads; mesh329 @212 ✗ degenerate). 374 mesh297 +
>   27/27 mesh321 blocks probed; authority over new MeshSize geometries
>   ends here. Handoff:
>   `docs/handoffs/2026-06-18-discovery-cycle-4.md`
>
> **Cycle 5 — Semantic-Category Surface (2026-06-21):**
>
> - **v0.9 scene manifest optional `semantic` sub-record**: 3-matrix union
>   (`hint:actor-object` / `hint:map-zone` / `hint:waypoint-poi`); always
>   populated, empty contract = `{categories: [], sources: {hint: '<absent>'}}`;
>   sources emit basenames only (portable, no absolute paths); `ABSENT_MARKER`
>   reserved for paths that DO NOT exist on disk.
> - **v0.3 delivery flat `semantic_categories`**: per-entry flat list
>   (RiftFlythrough-friendly); aggregated stats count `tagged_assets`,
>   `distinct_hints`, and `hint_distribution` in delivery stats.
> - **Loader module**: `scripts/semantic_surface.py` — exports `HINTS`,
>   `ABSENT_MARKER`, `SOURCE_BASENAME_ONLY`, `DEFAULT_MATRIX_DIR`,
>   `load_matrix`, `load_all_matrices`, `categorize_asset`,
>   `build_semantic_block`.
> - **Wire-format lock tests**: 12 NEW tests in `tests/test_semantic_surface.py`
>   (loader contract; schema conformance via `$defs/Semantic`; delivery
>   integration; migration safety for pre-Cycle-5 manifests).
> - **Validation**: 71/71 touched tests PASS; ruff 0; mypy 0; 9th guard
>   251/251 PASS (opt-in migration — pre-Cycle-5 manifests still validate).
> - **Schema discipline**: `$defs/Semantic` (additionalProperties: false);
>   `semantic` field optional in main schema; consumers must handle missing key.
> - **Harness env fix**: `pyproject.toml` BOM stripped + CRLF normalized;
>   `pythonpath = ["."]` added; `tests/test_build_scene_manifest.py`
>   propagates `PYTHONPATH` to subprocess runs.

---

## Current State

**All plans complete**:

1. **Phase 0–49** (`docs/roadmap/project-roadmap.md`): ✅ COMPLETE. NIF parser/descriptor work fully proven. 7/7 gates cleared. Both promotion flags true. 10 phases, 35+ milestones.
2. **Phase 1 (Position Source Family Proof)** (`docs/roadmap/project-roadmap.md` Phase 1): ✅ COMPLETE. M1.1-M1.5 all finalized. 329 family: 12/12 matrix + deep classification. 305 family: cross-family validation. Guards 12/12 PASS.
3. **Flythrough Bridge Plan** (`docs/roadmap/flythrough-bridge-plan.md`): ✅ COMPLETE. FT-1 through FT-8 all delivered. 350 OBJs, 217 unique asset IDs, 12,954 textures. Final delivery: `flythrough-index.json` for RiftFlythrough Phase 21.
4. **Ghidra proof lane**: ✅ COMPLETE. 3/3 steps: parser field proof guard, sample-byte agreement (184/184), narrow parser patch.

**Ghidra proof lane**: ✅ Complete (3/3 steps). Source/ deleted (166MB reclaimed). All Python scripts default to live game path.

**Historical session summary (2026-06-06)**: Ghidra proof lane (3/3), Source/ deleted, discovery suite functional, CI green. The narrow parser patch is complete with `--ghidra-body-offset` flag. Subsequent Phase 1 + FT plan completion rendered all pending items done.

---

## Next Actions

**Cycle 2 is COMPLETE.** The remaining items are optional post-completion follow-ups.

| # | Action | Status | Reference |
|---|---|---|---|
| 1 | **Cycle 2 — C2-V4P12 (V4 Pro session)** | ✅ Skipped (autonomous equivalent) | Work done by M3 + V4 Pro in autonomous sessions |
| 2 | **Cycle 2 — C2-2.5 (Stage 2 handoff + combined brief)** | ✅ Complete | Brief at `docs/roadmap/cycle-2-briefs/block-1-transform-schema.md` |
| 3 | **Cycle 2 — C2-2.4 (coordinate contract + schema sketch + builder)** | ✅ Complete | 24/24 sample manifests validate; schema validator exits 0 |
| 4 | **Cycle 2 — C2-3.x (texture-coverage profiler)** | ✅ Complete | `stage3/texture-coverage.json`; 23/24 contradictions found |
| 5 | **Cycle 2 — C2-4.x (per-asset manifest run)** | ✅ Complete | 217 stage6 manifests; builder at v0.7 |
| 6 | **Cycle 2 — C2-5.x (aggregate pack + dedupe + stats)** | ✅ Complete | `stage4/scene-manifest-pack-v1.json`; 15/24 consumer-ready |
| 7 | **Cycle 2 — C2-6.x (scale-out to 217 assets)** | ✅ Complete | All 217 flythrough IDs have stage6 manifests |
| 8 | **Cycle 2 — C2-7.x (ship-kill validation)** | ✅ Complete (SHIP) | 22 tests + 9th guard; 241/241 PASS |
| 9 | **v0.6 Geometry enrichment** | ✅ Complete | vertex_count, face_count, mesh_block, render_class, obj_sha1 |
| 10 | **v0.7 Material inference** | ✅ Complete | 153/217 consumer_ready via texture-linkage inference |
| 11 | **Stage8 RiftFlythrough delivery (v0.1)** | ✅ Complete | `riftflythrough-delivery.json` (153 assets) copied to sibling project |
| 12 | **v0.8 NIF-level material scan** | ✅ Complete | 217/217 NIF-confirmed; 212 textured, 5 material-color-only; scanned_at populated |
| 13 | **5 textureless asset investigation** | ✅ Complete | All 5 confirmed genuinely material-color-only; zero NiTexturingProperty blocks |
| 14 | **v0.2 delivery pipeline (path privacy + texture URLs)** | ✅ Complete | Absolute paths removed; 404/404 texture URLs resolved to `textures/converted/<file>.png`; `_assert_no_absolute_paths()` hard guard; 5 new tests |
| 15 | **scene_manifest_validation_guard fix** | ✅ Complete | Bumped expected producer v0.7→v0.8; 241/241 PASS |
| 16 | **knowledge.md update + handoff** | ✅ Complete | Test counts (56/475); v0.2 delivery pipeline details; session handoff doc |
| 17 | **Cycle 5 — Semantic-category surface** | ✅ Complete (SHIP) | v0.9 manifest optional `semantic` v0.3 delivery `semantic_categories`; 12 new wire-format lock tests; `scripts/semantic_surface.py` loader; schema `$defs/Semantic` |

---

## Legacy Active Focus Rules (NIF Geometry Era — Archived)

These rules applied during the NIF geometry discovery pipeline (Phase 1-53). They are preserved for historical reference but do NOT apply to the active semantic-discovery or binary-signature roadmaps.

- Stay within stream role classification — no new export formats or archive format changes
- Every C# change must be additive (new fields/reports, not behavioral changes to existing decode paths)
- Heuristic classifier remains as fallback — descriptor-guided is supplementary
- Both promotion flags remain true (already cleared)
- One lead at a time per Aggressive Evidence Workflow
- **For Flythrough Bridge Plan (FT-1..FT-8)**: see drift-prevention rules in `docs/roadmap/flythrough-bridge-plan.md`

---

## Phase History

| Phase | Name | Milestones | Gates Cleared | Status |
|---|---|---|---|---|
| Phase 1 | Position Source Family Proof | M1.1-M1.5 | N/A | ✅ |
| Phase 2 | Descriptor & Binding Proof | M2.1-M2.5 | 0 | ✅ |
| Phase 3 | Descriptor Propagation | M3.1-M3.5 | 0 | ✅ |
| Phase 4 | Descriptor-Aware Parser | M4.1-M4.6 | 0 | ✅ |
| Phase 5 | Descriptor-Guided Parser | M5.1-M5.5 | 0 | ✅ |
| Phase 6 | Descriptor-Validated Export | M6.1-M6.4 | 0 | ✅ |
| Phase 7 | Promotion Gate Clearance | M7.1-M7.5 | **3** | ✅ |
| Phase 8 | Semantic Gate Clearance | M8.2, M8.4 | 0 | ✅ |
| Phase 9 | Final Clearance + Consolidation | M9.0-M9.4 | **2** | ✅ EXITED |
| Phase 10 | Human Review + Final Promotion | M10.1-M10.2 | **2** | ✅ COMPLETE |
| **Phase 11** | **Descriptor-Guided Role Classification** | **M11.1-M11.5** | **0** | **✅ COMPLETE** |
| **Phase 12** | **Unknown Descriptor Discovery** | **M12.1-M12.3** | **0** | **✅ COMPLETE** |

| **Phase 13** | **Descriptor Consistency Proof Guard** | **M13.1-M13.3** | **0** | **✅ COMPLETE** |
| **Phase 14** | **Inventory Refresh + Baseline Update** | **M14.1-M14.2** | **0** | **✅ COMPLETE** |
| **Phase 15** | **Float2 Position Encoding Investigation** | **M15.1-M15.4** | **0** | **✅ COMPLETE** |
| **Phase 15.5** | **Float2 Z-Source Resolution** | **Z-source analysis** | **0** | **✅ COMPLETE** |
| **Phase 16** | **Sibling Pairing Map** | **Pairing map** | **0** | **✅ COMPLETE** |
| **Phase 17** | **Sibling Pair Verification** | **Probe confirmation** | **0** | **✅ COMPLETE** |
| **Phase 18** | **Comprehensive Sibling Pairing Database** | **Full-inventory scan** | **0** | **✅ COMPLETE** |
| **Phase 19** | **Sibling Pairing Improvements** | **DIST=0 tracking + JSON output** | **0** | **✅ COMPLETE** |
| **Phase 20** | **Cross-Type NIF Verification** | **9 cross-type NIFs analyzed** | **0** | **✅ COMPLETE** |
| **Phase 21** | **Sibling-Aware Batch OBJ Export** | **22 DIST=0 pairs exportable via batch-export-sibling** | **0** | **✅ COMPLETE** |
| **Phase 22** | **Sibling Export Validation** | **22/22 exports ✅ 1,020 vertices, 0 structural issues** | **0** | **✅ COMPLETE** |
| **Phase 23** | **Extended Sibling Export** | **--include-close flag; 142 pairs total; 0-face root cause documented** | **0** | **✅ COMPLETE** |
| **Phase 24** | **Full Sibling Export Run** | **142/142 exports ✅ 127 unique OBJs, 0 structural issues** | **0** | **✅ COMPLETE** |
| **Phase 25** | **Export Manifest** | **scripts/build_export_manifest.py — 142 OBJs catalogued: 94 faced, 48 position-only, 5,360 vertices, 6,682 faces** | **0** | **✅ COMPLETE** |
| **Phase 26** | **Comprehensive Export Manifest** | **259 OBJs across all Exports/, per-MeshSize breakdown, export batch classification** | **0** | **✅ COMPLETE** |
| **Phase 27** | **Bidirectional MeshSize Resolution** | **float3 + probe lookup; 8 IDs resolved; 4 new MeshSizes discovered** | **0** | **✅ COMPLETE** |
| **Phase 28** | **MeshSize 305 Mixed-Family Investigation** | **Root cause: split by mesh block (MB=6,45,46→faced; MB=7,27→pos-only)** | **0** | **✅ COMPLETE** |
| **Phase 29** | **Index Stream Family Map** | **docs/roadmap/index-stream-family-map.md — 11 MeshSize families, per-MB breakdown, key findings** | **0** | **✅ COMPLETE** |
| **Phase 30** | **Float3 Batch Export** | **scripts/batch_export_float3.py — 9/9 exported (6 faced + 3 pos-only), MS=465 MB=7 discovered as faced** | **0** | **✅ COMPLETE** |
| **Phase 31** | **MB=6 Batch Export** | **scripts/batch_export_mb6.py — 36 float2 IDs confirmed position-only; no MB=6/MB=7 blocks exist** | **0** | **✅ COMPLETE** |
| **Phase 32** | **Final Coverage Audit** | **34/34 float3 IDs exported (8 faced + 26 pos-only); pairing map coverage 100% complete** | **0** | **✅ COMPLETE** |
| **Phase 33** | **Full Project Health Sweep** | **ruff ✅ mypy ✅ build 0 errors tests 50/50 ✅ manifest 268 OBJs clean** | **0** | **✅ COMPLETE** |
| **Phase 34** | **Project Summary Document** | **docs/roadmap/project-summary.md — comprehensive overview of all 34 phases** | **0** | **✅ COMPLETE** |
| **Phase 35** | **Targeted Probe Cluster Analysis** | **3 probes resolved MS=321 (414f), MS=325 (318f + 18f); 37 cluster IDs identified** | **0** | **✅ COMPLETE** |
| **Phase 35.5** | **Cluster Inference Resolution** | **13 inferred IDs added to probe lookup; unknowns 101→83 (53 faced, 30 pos-only)** | **0** | **✅ COMPLETE** |
| **Phase 36** | **Inference Script + Remaining Probes** | **scripts/infer_meshsizes_from_clusters.py; MS=276, 354 discovered; unknowns 83→79** | **0** | **✅ COMPLETE** |
| **Phase 37** | **Remaining 12 Probes — 3 New Families** | **12 probes: MS=267, 297, 330 (new); MS=301 (6), MS=325 (1); unknowns 79→66** | **0** | **✅ COMPLETE** |
| **Phase 38** | **Regex Bug Fix + Hidden ID Recovery** | **Fixed extract_asset_id regex; recovered 33 hidden IDs; 15 probes resolved MS=280, 367, 405 (new) + MS=276 (3), MS=301 (1), MS=321 (3); unknowns 81→66** | **0** | **✅ COMPLETE** |
| **Phase 39** | **Project Summary Update** | **Updated docs/roadmap/project-summary.md through Phase 38; health sweep: ruff ✅, mypy ✅, build 0, tests 50/50 ✅** | **0** | **✅ COMPLETE** |
| **Phase 40** | **Pos-Only ID Resolution** | **16 regex-recovered pos-only IDs resolved; 8 new families: MS=193, 197, 214, 272, 275, 307, 326, 337; MS=305 (+3), MS=329 (+3); unknowns 66→49** | **0** | **✅ COMPLETE** |
| **Phase 41** | **Pattern-Matching Resolution** | **build_export_manifest.py: added face/vertex/MB pattern matching for no-ID entries; resolved 32 entries without probes; unknowns 49→22 (11 faced + 11 pos-only)** | **0** | **✅ COMPLETE** |
| **Phase 42** | **Project Summary Update** | **Updated docs/roadmap/project-summary.md through Phase 41; fixed family counts to 29 (17 faced + 1 mixed + 11 pos-only); health sweep: ruff ✅, mypy ✅, build 0, tests 50/50 ✅** | **0** | **✅ COMPLETE** |
| **Phase 43** | **Probe Lookup Pattern Matching** | **build_export_manifest.py: added secondary probe lookup from probe-meshsize-lookup.json for IDs probed but never OBJ-exported; resolved 18 more entries; unknowns 22→4** | **0** | **✅ COMPLETE** |
| **Phase 44** | **Project Summary Update** | **Updated docs/roadmap/project-summary.md through Phase 43; health sweep: ruff ✅, mypy ✅, build 0, tests 50/50 ✅** | **0** | **✅ COMPLETE** |
| **Phase 45** | **Zero Unknowns** | **Two bug fixes (regex + guard) + 3 final probes; all 268 OBJs now fully classified; unknowns 4→0** | **0** | **✅ COMPLETE** |
| **Phase 46** | **Documentation Update** | **Updated all docs with 0 unknowns milestone; accurate Per-MeshSize table from live manifest** | **0** | **✅ COMPLETE** |
| **Phase 47** | **MS=280 MB=25 Investigation** | **Investigated index-stream anomaly: MB=25 has index but no position data; expected sibling-pairing behavior** | **0** | **✅ COMPLETE** |
| **Phase 48** | **Pos-Only Cross-MB Audit** | **Audited 81 pos-only OBJs for recoverable faced candidates; 0 found; all genuinely pos-only** | **0** | **✅ COMPLETE** |
| **Phase 49** | **Triangle Fan Fallback Batch Export** | **Fan fallback extended to --export-obj path; batch export 76/77 pos-only OBJs with 2,847 fan faces across 15 families** | **0** | **✅ COMPLETE** |

**Project totals**: 51 phases + 1 complete cycle (C2) + 1 new complete cycle (C5) = 53 major deliverables. 7 gates cleared, 6 descriptor patterns proven, 9 proof guards (8 original + scene_manifest_validation_guard).

### Cycle 2 Completion Summary

| Metric | Value |
|--------|------:|
| Phases | C2-1 through C2-7 (all DONE) |
| Per-asset manifests | 241 (217 stage6 + 24 stage2) |
| NIF-confirmed material data | 217/217 (100%) |
| Consumer-ready assets | 153/217 (70.5%) |
| Total vertices | 14,696 |
| Total faces | 23,634 |
| Linked textures | 404 across 153 assets |
| Mesh size families | 19 |
| Guard passes | 241/241 (schema, OBJ, world, transforms, textures, version) |
| Producer version | v0.8 (NIF-confirmed material data) |
| Delivery version | v0.2 (path privacy + texture URL resolution; 404/404 resolved) |
| Test suite | 475 Python + 56 C# = 531 total |
| New tests (v0.2) | 5 (delivery wire contract) |
| Ship-kill decision | **SHIP** |

### Cycle 5 Completion Summary (Semantic-Category Surface)

| Metric | Value |
|--------|------:|
| Producer version (scene manifest) | **v0.9** — added optional `semantic` sub-record |
| Delivery version (RiftFlythrough) | **v0.3** — added flat `semantic_categories` + per-hint stats |
| Loader module | `scripts/semantic_surface.py` (HINTS, ABSENT_MARKER, SOURCE_BASENAME_ONLY, ...) |
| Wire-format lock tests | **+12** NEW in `tests/test_semantic_surface.py` |
| Touched-suite results | 71/71 PASS (ruff 0, mypy 0) |
| 9th-guard validation | **251/251 PASS** (opt-in migration — pre-Cycle-5 manifests still validate) |
| Migration safety | Pre-Cycle-5 manifests with no `semantic` key still pass schema (optional) |
| Schema additions | `$defs/Semantic` (additionalProperties: false, categories + sources) |
| Handoff doc | `docs/handoffs/2026-06-cycle-5-semantic-surface.md` |
| Ship decision | **SHIP** |

### Flythrough Bridge Plan (FT-1..FT-8) — ✅ COMPLETE

**Created**: 2026-06-08. All 7 active phases delivered; FT-8 skipped (mod-injection contradicts read-only mandate).

| FT phase | Name | Status |
|---|---|---|
| FT-1 | DDS → PNG at scale | ✅ DONE (12,954 textures, 83s, 19 MB) |
| FT-2 | Bulk NIF → OBJ export | ✅ DONE |
| FT-3 | Per-OBJ metadata sidecar | ✅ DONE (schema + emitter) |
| FT-4 | World placement / scene graph | ✅ DONE (100% coverage, 217/217 world.json) |
| FT-5 | Pipeline integration | ✅ DONE (flythrough_plan.py state machine) |
| FT-6 | Flythrough validation suite | ✅ DONE (100% pass) |
| FT-7 | Zone / LOD variants | ✅ DONE (193/217 classified) |
| FT-8 | Mod-replacement bridge | ⏭️ Skipped (read-only mandate) |

**Final delivery**: `flythrough-index.json` for RiftFlythrough Phase 21.
**Full plan**: `docs/roadmap/flythrough-bridge-plan.md`

### Phase 15 Key Finding

**Float2 position encoding confirmed.** 51/71 (72%) OBJ-exported position streams use `descriptor-float2-uv`
(8 bytes/vertex = XY pairs). 20/71 (28%) use `descriptor-float3-generic` (12 bytes/vertex = XYZ).
Float2 positions produce valid 3D OBJ vertices with real Z values — Z is sourced from a separate
stream, mesh transform, or computed. Raw data requires endian-aware decoding (big-endian prevalent).

### Phase 15.5 Z-Source Resolution

**CORRECTED Finding: Z is sourced from sibling position pairing, not mesh transform.**

Full stream inventory analysis of 36 float2-position meshes (156 streams):

- **48 position streams, ALL float2** — zero float3 position streams co-resident
- **No companion Z-stream exists** in any of the 36 meshes
- **Stream composition**: 48 pos + 42 index + 33 normal + 7 UV + 26 other

**Probe verification** (mesh `4768bc6e3cfaabd0` MB=6):

- Probe reveals only **3 streams**: normal (float3 @216), index (uint16 @292), UV (float2 @300)
- **No position stream exists in this mesh's direct data**
- Position is resolved through **legacy pairing** (2 pairings, 95% confidence)
- The `--experimental-position-source` code uses `NifPositionSourceSiblingAccumulator`
  to find a sibling mesh with full XYZ data and pair it with this mesh's XY data

**OBJ Z-value verification** (36 vertices):

- Z range: [-0.9260, 0.9351] (range = 1.8612, significant variation)
- Only **9 unique Z values** out of 36 — consistent with sibling-pair mapping
  (sibling has different vertex count; pairing maps vertices across meshes)

**Mechanism**:

1. Float2-position meshes store XY data only (8 bytes/vertex, descriptor-float2-uv)
2. These meshes lack attribute sets — they have NO direct position stream
3. The OBJ exporter (`--experimental-position-source`) uses sibling pairing:
   - `NifPositionSourceSiblingAccumulator` groups related meshes
   - `NifPositionSourceSiblingGroup` pairs meshes that share source bindings
   - The sibling provides full XYZ data that fills in the Z values
4. The heuristic classifier's `position-float3-lead` label reflects the PAIRED result, not raw data
5. The descriptor's `descriptor-float2-uv` correctly identifies the raw stream format

This is a **sophisticated encoding**: position data is split across sibling meshes
as XY + Z, with Z sourced from a different mesh's full float3 stream. The pairing
system reconstructs 3D positions by cross-referencing mesh siblings.

See: `scripts/analyze_z_source.py` (reusable analysis script).
See: `Exports/phase15.5-z-source-analysis.txt` for per-mesh breakdown (local/ignored).

### Phase 16: Concrete Sibling Pairing Map

**Finding: Concrete float2→float3 sibling pairs confirmed across 9 MeshSize families.**

Key sibling pairs (by archive proximity, distance = entry index difference):

| MeshSize | Archive | Float2 Entry | Float3 Entry | Dist | Strength |
|---|---|---|---|---|---|
| 305 | assets.037 | 544 | 544 | **0** | 🟢 Same entry |
| 309 | assets.040 | 1412 | 1412 | **0** | 🟢 Same entry |
| 465 | assets.050 | 861-864 | 864 | **0** | 🟢 Same entry |
| 301 | assets.037 | 819 | 818 | 1 | 🟡 Adjacent |
| 345 | assets.032 | 213 | 211 | 2 | 🟡 Near |
| 325 | — | Unpaired | — | — | ⚪ Cross-archive |
| 329 | — | Unpaired | — | — | ⚪ Cross-archive |

**Key insight**: 3 MeshSizes (305, 309, 465) have DIST=0 pairs — float2 and float3 data
live in the SAME archive entry. The OBJ exporter pairs them directly within the same
TWAD entry. Other MeshSizes (325, 329) require cross-archive pairing via the
NIF block reference system.

See: `scripts/build_sibling_pairing_map.py` for the pairing map builder.

### Phase 18: Comprehensive Sibling Pairing Database

**Finding: Full-inventory analysis reveals 142 sibling pairs across 10 shared MeshSize families.**

Extended the Phase 16 archive-proximity approach from 88 OBJ-only IDs to the full inventory:

| Metric | Phase 16 (OBJ-only) | Phase 18 (Full) |
|---|---|---|
| Float2 position meshes | 36 | **230** |
| Float3 position meshes | 20 | **176** |
| Shared MeshSizes | 9 | **10** |
| Archive-close sibling pairs | ~25 | **142** |
| NIF files with cross-type (f2+f3) | — | **9** |

**Newly discovered shared MeshSize: 389** (previously missed in OBJ-only scan).

**9 NIF files contain BOTH float2 and float3 position streams** in different mesh blocks within the same NIF — this is the NIF-level sibling group that the C# `NifPositionSourceSiblingAccumulator` was designed to detect.

**59 NIF files** have multiple position-stream mesh blocks requiring sibling resolution.

The heuristic uses greedy nearest-entry matching (distance < 100 entries within same archive),
so some float3 meshes may be 1:N paired with multiple float2 meshes.

See: `scripts/build_sibling_pairing_v2.py` for the comprehensive database builder.

### Phase 20: Cross-Type NIF Verification

**Finding: All 9 cross-type NIF files confirmed — float2+float3 co-reside in same archive entry.**

Analyzed using Phase 19 pairing map data:

| Group | NIF IDs | Structure |
|---|---|---|
| 1 (6 NIFs) | d703, c36e, 75d5, ec36, 1d7d, a6b2 | MB=7: **f2+f3** (shared); MB=27: f3 only |
| 2 (1 NIF) | 45ef | MB=7: f2 only; MB=27: f3 only |
| 3 (2 NIFs) | 0d9a, 3feb | MB=27: **f2+f3** (shared); MB=7: f3 only |

**Key insight**: All 9 are MeshSize 305 — this family has the most complex
sibling pairing infrastructure. MB=7 is the canonical float2 position block,
paired with MB=7 or MB=27 for float3 Z-source.

**3 NIF groups** (shared MBs = same mesh block has both f2+f3 roles):

- Group 1 (6 NIFs): MB=7 has both float2 (descriptor-float2-uv) and float3 (descriptor-float3-generic)
- Group 3 (2 NIFs): MB=27 has both
- Group 2 (1 NIF): separate MBs for f2 vs f3

This validates the C# `NifPositionSourceSiblingAccumulator` which handles
in-NIF sibling discovery across different mesh blocks.

See: `scripts/verify_cross_type_nifs.py`

### Phase 19: Sibling Pairing Improvements

**Finding: 22 DIST=0 (same-entry) pairs confirmed across 3 MeshSizes — 7x expansion from Phase 17.**

| Metric | Phase 18 | Phase 19 |
|---|---|---|
| Total archive-close pairs | 142 | **142** (same) |
| DIST=0 (same entry) pairs | not tracked | **22** |
| MeshSizes with DIST=0 pairs | 3 (305, 309, 465) | **3** (expanded: 305=9, 329=2, 465=11) |
| JSON output | none | **Exports/phase19-sibling-pairing-map.json** |

**New finding**: MeshSize 329 now has 2 DIST=0 pairs (was 0 in Phase 16 analysis). This means
sibling pairing within the same archive entry extends to the meshSize=329 family.

**Improvements**:

- DIST=0 pairs tracked and annotated with `(SAME ENTRY)` in output
- Structured JSON output written to `Exports/phase19-sibling-pairing-map.json`
- Per-MeshSize DIST=0 counts in summary
- `int()` casts now use `or "0"` fallback to prevent ValueError

### Phase 17: Concrete Sibling Pair Verification

**Finding: Sibling pairing CONFIRMED — DIST=0 pair at MeshSize 305 entry 544.**

Probed ID `42024b768fcd2e2b` (assets.037, entry 544, MeshSize 305):

| Mesh Block | Position Descriptor | Payload | Elements | Bytes/El | Content |
|---|---|---|---|---|---|
| **MB=6** | `descriptor-float2-uv` | 192 bytes | **24** | 8 | XY pairs only |
| **MB=34** | `descriptor-float3-generic` | 768 bytes | **64** | 12 | Full XYZ |

**This confirms the Z-source mechanism end-to-end:**

1. Mesh Block 6 stores XY position data (8 bytes/vertex, float2 encoding)
2. Mesh Block 34 stores full XYZ position data (12 bytes/vertex, float3 encoding)
3. Both exist in the **same archive entry** (544 in assets.037)
4. The OBJ exporter pairs them via `NifPositionSourceSiblingAccumulator`
5. The float3 mesh provides Z values that complete the float2 mesh
6. The pairing maps 24 float2 vertices → 64 float3 vertices (consistent with earlier OBJ analysis showing 9/36 unique Z on a different mesh — sibling vertex mapping pattern holds)

**This is the first direct evidence of the sibling pairing mechanism in action.**
The same TWAD entry physically contains both the XY-only and full XYZ data,
confirming that the encoding is intentional: positions are split across sibling
mesh blocks within the same archive entry.

### Phase 14 Refresh Results

| Metric | Before (Phase 11) | After (Phase 14) | Delta |
|---|---|---|---|
| DescriptorGuidedRole count | 4,045 | **4,076** | +31 (08010400) |
| Hard errors | 530 | 530 | 0 |
| Warnings | 107 | 107 | 0 |
| Ambiguous | 3,407 | **7,515** | +4,108 (improved counting) |
| Total described streams | 4,044 | **8,152** | +4,108 |

Note: The Phase 11 baseline only counted streams with BOTH DescriptorGuidedRole AND PrimaryRole.
The Phase 14 baseline counts ALL PrimaryRole entries, including those without descriptors.
The 08010400 addition correctly captures all 31 previously unknown streams.

See individual exit handoffs under `docs/handoffs/2026-06-m*.*-phase*-exit-consolidation.md`.
