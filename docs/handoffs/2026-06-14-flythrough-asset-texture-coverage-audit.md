# Flythrough Asset + Texture Coverage Audit

**Generated**: 2026-06-14T23:55:19.377309Z

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
| OBJ entries with texture links | 323 | File-level entries whose asset has linked textures |
| Full OBJ row manifest | 350 rows | Written in generated audit JSON under `obj_file_level.entries` |
| Indexed asset IDs | 217 | `Assets/build/flythrough/flythrough-index.json` |
| Indexed assets with textures | 207 | 10 without links |
| Texture-link JSONL rows | 650 | 207 model IDs |
| Unique linked PNGs available | 222/222 | Converted manifest mode: `smoke` |
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
- `1ecdbaf5a2576ba5`
- `35ca1d9dbad6d245`
- `838831f8fb617ecc`
- `95d9b14a964e67c8`
- `b5dc665faa848f85`
- `cf54e712ff57eaac`
- `fa78ee2d8c3abca7`

## Downstream usability readout

- Texture PNG availability for linked assets is good: every unique linked PNG is present in the converted manifest and on disk.
- The generated audit JSON now contains one row per OBJ manifest entry with path, existence, asset ID, texture status, and linked PNG names.
- Id-less OBJ entries now include geometry-signature candidate matches where current exports contain same-shape asset-ID-backed rows.
- The main usability blocker is materialization: exported OBJs currently do not reference `.mtl` files or `usemtl` assignments.
- The second blocker is file-level coverage: the 217-asset index does not directly expose every one of the 350 manifest OBJ entries.
- The third blocker is recovery/classification of id-less OBJ entries and no-texture asset IDs.

## Downstream consumer artifact builder

`scripts/build_flythrough_obj_texture_manifest.py --write-bundle` turns this audit into generated, gitignored consumer artifacts:

| Artifact | Expected result from current audit | Purpose |
|---|---:|---|
| `Assets/build/flythrough/flythrough-obj-texture-manifest.json` | 350 rows | File-level OBJ manifest with texture roles, materialization status, candidate asset IDs, and bundle paths |
| `Assets/build/flythrough/flythrough-obj-texture-manifest.csv` | 350 rows | Spreadsheet-friendly triage view |
| `Assets/build/flythrough/obj-texture-bundle/objs/` | 323 OBJ files | Texture-linked OBJ copies with injected `mtllib`/`usemtl` lines |
| `Assets/build/flythrough/obj-texture-bundle/materials/` | 323 MTL files | Simple material sidecars pointing at converted PNGs |

Expected default bundle summary from this audit:

- 350 total manifest entries.
- 323 materializable OBJ entries.
- 323 generated OBJ files and 323 generated MTL files.
- 27 skipped entries: 26 without textures and 1 missing source OBJ.
- 13176 converted PNG paths available to the manifest.

Optional heuristic expansion:

`--allow-single-candidate-materials` borrows textures for id-less OBJ rows only when the geometry signature has exactly one asset-ID candidate. It does not promote that candidate to durable truth.

- 4 id-less OBJ entries are eligible for single-candidate texture borrowing.
- 327 total OBJ entries become materializable with that option.
- 23 entries remain skipped after heuristic expansion.
- `--allow-common-candidate-materials` additionally borrows textures for ambiguous candidate groups only when all geometry-matched candidates share the same linked texture set.
- 4 ambiguous id-less OBJ entries are eligible for common-candidate texture borrowing.
- 331 total OBJ entries become materializable with both candidate options.
- 19 entries remain skipped after both candidate options.

## Top 10 next best actions

1. Smoke-import the generated OBJ/MTL bundle in RiftFlythrough or Blender.
2. Resolve/classify the 4 single-match id-less OBJ entries into asset IDs.
3. Investigate the 4 ambiguous id-less OBJ groups with stronger hashes/signatures.
4. Investigate the 3 no-match id-less OBJ entries separately.
5. Fix or regenerate the missing manifest source path: `Exports/Exports/decode-nif-geometry/decode-nif-geometry-mesh17.obj`.
6. Investigate the 10 indexed asset IDs with no linked textures.
7. Improve material role inference for special maps such as glow, masks, and alpha.
8. Add thumbnails or a lightweight HTML gallery for textured bundle triage.
9. Keep generated OBJ/PNG/DDS artifacts out of git; commit only scripts, reports, and small fixtures.
10. Use CI only as a guardrail after asset-coverage scripts/docs change, not as the main workstream.
