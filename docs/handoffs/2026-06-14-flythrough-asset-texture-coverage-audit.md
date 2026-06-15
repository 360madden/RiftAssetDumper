# Flythrough Asset + Texture Coverage Audit

**Generated**: 2026-06-15T01:46:01.435449Z

## Why this exists

The flythrough closure artifact is asset-ID centric (`217` unique assets), while the export manifest is file-level (`350` OBJ entries). This audit joins the file-level OBJ set to asset IDs and texture coverage so the remaining usability work stays focused on assets/textures instead of unrelated CI churn.

## Current coverage snapshot

| Surface | Count | Notes |
|---|---:|---|
| OBJ manifest entries | 350 | `Exports/export-manifest.json` |
| OBJ files currently on disk | 349 | 1 manifest path(s) missing |
| OBJ entries with asset IDs | 339 | Can inherit asset-level metadata/textures |
| OBJ entries without asset IDs | 11 | Need recovery/classification for full 350-file access |
| Id-less OBJ signature candidates | {'ambiguous-signature-match': 4, 'no-geometry-signature-match': 3, 'single-asset-signature-match': 4} | Geometry-only recovery hints |
| OBJ entries with texture links | 329 | File-level entries whose asset has linked textures |
| Full OBJ row manifest | 350 rows | Written in generated audit JSON under `obj_file_level.entries` |
| Indexed asset IDs | 217 | `Assets/build/flythrough/flythrough-index.json` |
| Indexed assets with textures | 212 | 5 without links |
| Texture-link JSONL rows | 713 | 211 model IDs |
| Unique linked PNGs available | 278/278 | Converted manifest mode: `smoke` |
| OBJ material refs | 0 | 0 `mtllib`, 0 `usemtl` |

## File-level OBJ gaps

### Missing manifest paths

- `Exports/Exports/decode-nif-geometry/decode-nif-geometry-mesh17.obj`

### OBJ entries without asset IDs

- `Exports/decode-264-v128/decode-nif-geometry/decode-nif-geometry-mesh6.obj` — mesh_block=6, verts=128, faces=318, batch=batch-264-v128, provenance=copied, candidate_status=ambiguous-signature-match, candidate_geometry_status=ambiguous-candidate-geometry-match, candidate_texture_set_status=single-candidate-texture-set, candidate_asset_ids=6fc01704d4a509d5, caa9a88e94ec8db0
- `Exports/decode-264-v128b/decode-nif-geometry/decode-nif-geometry-mesh6.obj` — mesh_block=6, verts=128, faces=318, batch=batch-264-v128b, provenance=copied, candidate_status=ambiguous-signature-match, candidate_geometry_status=ambiguous-candidate-geometry-match, candidate_texture_set_status=single-candidate-texture-set, candidate_asset_ids=6fc01704d4a509d5, caa9a88e94ec8db0
- `Exports/decode-264-v64/decode-nif-geometry/decode-nif-geometry-mesh6.obj` — mesh_block=6, verts=64, faces=82, batch=batch-264-v64, provenance=copied, candidate_status=single-asset-signature-match, candidate_geometry_status=single-candidate-geometry-match, candidate_texture_set_status=single-candidate-texture-set, candidate_asset_ids=dfa4b4fccd826b59
- `Exports/decode-264-v80/decode-nif-geometry/decode-nif-geometry-mesh6.obj` — mesh_block=6, verts=80, faces=78, batch=batch-264-v80, provenance=copied, candidate_status=single-asset-signature-match, candidate_geometry_status=single-candidate-geometry-match, candidate_texture_set_status=single-candidate-texture-set, candidate_asset_ids=0603cce7cee15eb8
- `Exports/decode-264-v95/decode-nif-geometry/decode-nif-geometry-mesh6.obj` — mesh_block=6, verts=95, faces=118, batch=batch-264-v95, provenance=copied, candidate_status=single-asset-signature-match, candidate_geometry_status=single-candidate-geometry-match, candidate_texture_set_status=single-candidate-texture-set, candidate_asset_ids=3de9c1236fe20520
- `Exports/decode-fallback-1/decode-nif-geometry/decode-nif-geometry-mesh6.obj` — mesh_block=6, verts=24, faces=0, batch=individual-export, provenance=copied, candidate_status=no-geometry-signature-match, candidate_geometry_status=no-candidate-geometry-match, candidate_texture_set_status=no-candidate-textures, candidate_asset_ids=none
- `Exports/decode-fallback-2/decode-nif-geometry/decode-nif-geometry-mesh6.obj` — mesh_block=6, verts=30, faces=0, batch=individual-export, provenance=copied, candidate_status=no-geometry-signature-match, candidate_geometry_status=no-candidate-geometry-match, candidate_texture_set_status=no-candidate-textures, candidate_asset_ids=none
- `Exports/decode-nif-geometry/decode-nif-geometry-mesh6.obj` — mesh_block=6, verts=128, faces=318, batch=individual-export, provenance=copied, candidate_status=ambiguous-signature-match, candidate_geometry_status=ambiguous-candidate-geometry-match, candidate_texture_set_status=single-candidate-texture-set, candidate_asset_ids=6fc01704d4a509d5, caa9a88e94ec8db0
- `Exports/discovery-plan/stage0-baseline/decode-nif-geometry/decode-nif-geometry-mesh6.obj` — mesh_block=6, verts=128, faces=318, batch=individual-export, provenance=copied, candidate_status=ambiguous-signature-match, candidate_geometry_status=ambiguous-candidate-geometry-match, candidate_texture_set_status=single-candidate-texture-set, candidate_asset_ids=6fc01704d4a509d5, caa9a88e94ec8db0
- `Exports/Exports/decode-nif-geometry/decode-nif-geometry-mesh17.obj` — mesh_block=17, verts=50, faces=0, batch=individual-export, provenance=copied, candidate_status=no-geometry-signature-match, candidate_geometry_status=no-source-geometry, candidate_texture_set_status=no-candidate-textures, candidate_asset_ids=none
- `Exports/test-fan-fallback/decode-nif-geometry/decode-nif-geometry-mesh6.obj` — mesh_block=6, verts=168, faces=166, batch=individual-export, provenance=copied, candidate_status=single-asset-signature-match, candidate_geometry_status=single-candidate-geometry-match, candidate_texture_set_status=single-candidate-texture-set, candidate_asset_ids=58eaafd0fd31fcaf

## Asset IDs without linked textures

- `0e0c61ad75d2af1e`
- `1601c1f75e0a6022`
- `1e8d2bcc6546b548`
- `35ca1d9dbad6d245`
- `b5dc665faa848f85`

## Downstream usability readout

- Texture PNG availability for linked assets is good: every unique linked PNG is present in the converted manifest and on disk.
- The generated audit JSON now contains one row per OBJ manifest entry with path, existence, asset ID, texture status, and linked PNG names.
- Id-less OBJ entries now include geometry-signature candidate matches where current exports contain same-shape asset-ID-backed rows.
- The original exported OBJs still do not reference `.mtl` files or `usemtl` assignments; generated bundles below materialize that downstream without modifying generated source exports.
- The second blocker is file-level coverage: the 217-asset index does not directly expose every one of the 350 manifest OBJ entries.
- The third blocker is recovery/classification of id-less OBJ entries and no-texture asset IDs.

## Downstream consumer artifact builder

`scripts/build_flythrough_obj_texture_manifest.py --write-bundle` turns this audit into generated, gitignored consumer artifacts:

| Artifact | Expected result from current audit | Purpose |
|---|---:|---|
| `Assets/build/flythrough/flythrough-obj-texture-manifest.json` | 350 rows | File-level OBJ manifest with texture roles, materialization status, candidate asset IDs, and bundle paths |
| `Assets/build/flythrough/flythrough-obj-texture-manifest.csv` | 350 rows | Spreadsheet-friendly triage view |
| `Assets/build/flythrough/obj-texture-bundle/objs/` | 329 OBJ files | Texture-linked OBJ copies with injected `mtllib`/`usemtl` lines |
| `Assets/build/flythrough/obj-texture-bundle/materials/` | 329 MTL files | Simple material sidecars pointing at converted PNGs |
| `Assets/build/flythrough/texture-triage-gallery/index.html` | 337 preview cards + 13 gap rows | Local HTML triage surface for materialized OBJ/MTL rows and remaining gaps |
| `Assets/build/flythrough/texture-triage-gallery-full-available/index.html` | 349 preview cards + 1 gap row | Full-available local HTML triage surface, including neutral materials for textureless existing OBJs |

Expected default bundle summary from this audit:

- 350 total manifest entries.
- 329 materializable OBJ entries.
- 329 generated OBJ files and 329 generated MTL files.
- 21 skipped entries: 20 without textures and 1 missing source OBJ.
- 13232 converted PNG paths available to the manifest.

Optional heuristic expansion:

`--allow-single-candidate-materials` borrows textures for id-less OBJ rows only when the geometry signature has exactly one asset-ID candidate. It does not promote that candidate to durable truth.

- 4 id-less OBJ entries are eligible for single-candidate texture borrowing.
- 333 total OBJ entries become materializable with that option.
- 17 entries remain skipped after heuristic expansion.
- `--allow-common-candidate-materials` additionally borrows textures for ambiguous candidate groups only when all geometry-matched candidates share the same linked texture set.
- 4 ambiguous id-less OBJ entries are eligible for common-candidate texture borrowing.
- 337 total OBJ entries become materializable with both candidate options.
- 13 entries remain skipped after both candidate options.
- `--allow-textureless-triage-materials` can use row-scoped converted DDS refs discovered by the textureless triage report.
- 0 neutral OBJ row(s) currently have converted textureless-triage DDS evidence.
- `--materialize-untextured` adds neutral MTLs for existing OBJ rows that still lack texture evidence; it does not claim texture coverage.
- 12 existing textureless OBJ rows still become neutral-materialized when triage textures plus neutral materials are enabled.
- 349 total OBJ entries become materializable with candidate borrowing plus neutral materials.
- 1 entry remains skipped: the missing source OBJ path.
- `scripts/build_flythrough_texture_triage_gallery.py --manifest Assets/build/flythrough/flythrough-obj-texture-manifest-full-available.json --out Assets/build/flythrough/texture-triage-gallery-full-available/index.html` renders the full-available local HTML triage gallery.
- `scripts/repair_flythrough_missing_objs.py --apply` attempts exact SHA-256 duplicate recovery for missing manifest OBJ paths and writes `Assets/build/flythrough/evidence/missing-obj-repair/repair-report.json`.
- Latest exact-hash repair report: 1 missing, 0 exact SHA-256 duplicate matches, 0 same-size file candidates, 0 repaired.
- Latest missing OBJ classifier: 8 similar existing candidate(s), 0 derived no-face variant(s) matching the expected SHA-256.
- 2026-06-15 source-access redrive: `decode-nif-geometry --write-obj` was blocked by an option-parse swap that assigned `--write-obj` to `GhidraBodyOffset`; this is fixed so linked-stream fallback exports can actually write OBJ files again.
- Isolated live redrive of high-similarity candidate `07f37c99a80da009` mesh block 17 succeeded through `--experimental-position-source --write-obj`: 50 vertices, 71 faces, 50 texcoords. This is a practical materialized candidate for review, not an exact SHA repair of the missing no-ID source path.
- Bulk redrive of the 14 prior FT-2 failed assets now exports 12/14 through linked-stream fallback into generated evidence (`Assets/build/flythrough/evidence/missing-obj-repair/bulk-redrive-failed-manifest.json`), and `bulk_export_for_flythrough.py verify` reports 12/12 exported entries OK; the 2 remaining failures have no float32 position candidates (`03dc62be8b1706fc`, `1183a447da3621f2`).
- `scripts/bulk_export_for_flythrough.py` now records nested generated OBJ paths relative to the output root and records the real experimental fallback command, so redriven OBJ artifacts are discoverable by status/verify tooling instead of being orphaned under subdirectories.
- `scripts/probe_flythrough_textureless_meshes.py` refreshes focused live-root `probe-nif-mesh` JSON for textureless-scope asset/mesh rows, so triage can find row-scoped DDS refs instead of guessing.
- Latest textureless probe refresh report: 6 asset/mesh targets, 0 commands run, 1 targets with mesh-level DDS refs, 2 unique mesh-level DDS refs.
- `scripts/triage_flythrough_textureless_assets.py` scans neutral-materialized rows for latent DDS references in probe JSON and writes `Assets/build/flythrough/evidence/textureless-assets/textureless-triage.json`.
- Latest textureless-asset triage report: 13 neutral rows, 1 rows with mesh-level DDS refs, 1 neutral asset IDs with refs, 2 unique DDS refs, 0 already converted, 2 missing converted PNGs, 0 of the missing refs catalog-backed.
- Missing converted DDS targets found in probe evidence: `n_ds_eternal_assault_flowers_01_c.dds`, `n_ds_eternal_assault_flowers_01_s.dds`.
- `scripts/recover_flythrough_textureless_dds.py` name-matches, extracts, converts, and records DDS refs from the textureless triage report.
- Latest textureless DDS recovery report: 2 refs, 2 currently missing conversion targets, 0 name matches, 2 unmatched target refs, 2 refs with visual fallback candidates, 0 newly converted PNGs, 0 failed conversions.
- Textureless DDS visual fallback review: `Assets/build/flythrough/evidence/textureless-assets/recovery/TEXTURELESS_DDS_RECOVERY.md`.
- `scripts/smoke_flythrough_obj_texture_bundle.py` parses the generated OBJ/MTL bundle, validates material directives, face indices, and MTL texture references before external viewer import.
- Latest OBJ/MTL bundle smoke report: pass=True, 349 checked entries, 0 OBJ issue entries, 0 MTL issue entries, 0 missing texture refs, 79 zero-face entries.
- `scripts/build_flythrough_combined_obj_package.py` turns the 349 materialized per-row OBJ/MTL files into one portable import package: one OBJ, one MTL, copied MTL-referenced textures, and `p` point directives for zero-face meshes.
- Latest combined OBJ package report: 349 combined entries, 1 skipped, 23371 vertices, 30864 faces, 79 point-cloud entries, 158 copied texture files, 0 missing source textures, verify_pass=True.
- `scripts/build_flythrough_obj_texture_manifest.py --source-substitutions ...` can now build a separate practical-access manifest that substitutes explicit generated review OBJs without claiming durable source truth.
- Practical 350 manifest: `Assets/build/flythrough/flythrough-obj-texture-manifest-practical-350.json` currently has 350/350 materializable entries, 0 effective missing source OBJs, 1 original source still missing, 1 source-substituted entry, and bundle_verify pass=True. The substitution row is manifest index 121, original `Exports/Exports/decode-nif-geometry/decode-nif-geometry-mesh17.obj`, replacement `07f37c99a80da009` mesh17 linked-stream redrive, `durable_truth=false`.
- Practical 350 smoke: `Assets/build/flythrough/evidence/practical-350/obj-texture-bundle-smoke.json` reports pass=True, 350 checked entries, 0 OBJ issues, 0 MTL issues, 0 missing textures, 79 zero-face entries.
- Practical 350 combined package: `Assets/build/flythrough/combined-obj-package-practical-350/combined.obj` reports 350 combined entries, 0 skipped, 23421 vertices, 30935 faces, 79 point-cloud entries, 158 copied texture files, verify_pass=True.
- `scripts/build_flythrough_obj_texture_manifest.py --texture-fallbacks ...` can now build a separate practical texture-fallback manifest that uses explicit visual fallback PNGs for missing DDS refs without claiming exact DDS recovery.
- Practical 350 + texture fallbacks manifest: `Assets/build/flythrough/flythrough-obj-texture-manifest-practical-350-texture-fallbacks.json` currently has 350/350 materializable entries, 1 source-substituted row, 1 texture-fallback materialized row, 2 active fallback refs, and bundle_verify pass=True.
- The texture fallback row is manifest index 118 (`fa78ee2d8c3abca7`): exact missing refs remain `n_ds_eternal_assault_flowers_01_c.dds` and `n_ds_eternal_assault_flowers_01_s.dds`; practical visual substitutes are `b3024468_n_ds_ruinouspassage_flowers_01_c.png` and `378ceef5_n_ds_ruinouspassage_flowers_01_s.png`, both `durable_truth=false`.
- Practical 350 + texture fallbacks smoke/package: `Assets/build/flythrough/evidence/practical-350-texture-fallbacks/obj-texture-bundle-smoke.json` reports pass=True, 350 checked entries, 0 OBJ issues, 0 MTL issues, 0 missing textures; `Assets/build/flythrough/combined-obj-package-practical-350-texture-fallbacks/combined.obj` reports 350 combined entries, 0 skipped, 23421 vertices, 30935 faces, 158 copied texture files, verify_pass=True.
- The practical 350 + texture fallbacks combined-package report/Markdown now explicitly lists practical source substitutions and texture fallbacks: 1 non-durable source substitution, 1 texture-fallback entry, 2 non-durable texture fallback refs, all marked `durable_truth=false` in `Assets/build/flythrough/combined-obj-package-practical-350-texture-fallbacks/COMBINED_OBJ_PACKAGE.md`.
- Practical 350 + texture fallbacks gallery: `Assets/build/flythrough/texture-triage-gallery-practical-350-texture-fallbacks/index.html` renders 350 materialized cards, 0 remaining rows, and explicit practical source substitution / texture fallback tables containing row 121, row 118, and `durable=false` labels.
- One-command rebuild: `python scripts/build_flythrough_practical_package.py` regenerates source substitutions, texture fallbacks, the 350-row manifest/CSV, per-row OBJ/MTL bundle, smoke report, combined OBJ package, gallery, a focused texture-gap report, and `Assets/build/flythrough/evidence/practical-350-texture-fallbacks/practical-package-build-report.json`; latest summary is 350/350 materializable, 1 source substitution, 2 texture fallback refs, 13 neutral material rows, 13 color-coded review materials, 2 unmatched exact DDS refs, bundle=True, smoke=True, combined=350, skipped=0, gallery=True.
- Practical texture-gap report: `Assets/build/flythrough/evidence/practical-350-texture-fallbacks/TEXTURE_GAP_REPORT.md` and `texture-gap-report.json` keep the remaining asset/texture work focused: 337 rows have non-neutral textures/fallbacks, 13 rows remain neutral, 10 neutral rows are backed by focused probes with no mesh-level DDS refs, 2 neutral rows are id-less with no texture candidate, and row 121 is the one source-substituted neutral row.
- Neutral review materials are explicitly non-durable visual aids in the generated MTLs: blue for asset-ID rows with no linked texture refs (10), orange for id-less rows with no texture candidate (2), and purple for the source-substituted row 121 (1). Each MTL records `Durable texture truth: false`.

## Top 10 next best actions

1. Smoke-import the portable combined full-available OBJ/MTL/textures package in Blender or an MTL-aware viewer.
2. Smoke-import the practical 350 combined package in Blender or an MTL-aware viewer and inspect the source-substituted mesh17 row.
3. Run `python scripts/build_flythrough_practical_package.py` when regenerating practical artifacts, then open `Assets/build/flythrough/texture-triage-gallery-practical-350-texture-fallbacks/index.html` and smoke-import the package.
4. Continue exact recovery/proof for the 2 `n_ds_eternal_assault_flowers_01_*` DDS refs; the practical fallbacks are not durable truth.
5. Decide whether any of the other 12/14 successful linked-stream redrives should feed a generated review bundle or remain evidence-only.
6. Investigate the two redrive failures with no float32 position candidates (`03dc62be8b1706fc`, `1183a447da3621f2`).
7. Investigate the remaining neutral-material rows that still lack row-scoped DDS refs.
8. Open the full-available texture triage gallery and review the 349 preview cards plus 1 missing-source gap.
9. Resolve/classify the 4 single-match id-less OBJ entries into asset IDs.
10. Verify the portable package in the target downstream importer once a Blender or MTL-aware viewer path is available.
