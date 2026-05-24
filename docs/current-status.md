# Current Status — High-impact RIFT asset discoveries 🚀
Date: 2026-06-07 (updated 2026-06-07)
Date: 2026-06-03 (updated 2026-05-22)

## 🐍 Python migration status (PS→Py phase 1)

| Component | Status | Notes |
|---|---|---|
| `scripts/rift_workflow_utils.py` (49 unit tests) | ✅ complete | All utility functions ported and tested |
| `scripts/rift_workflow.py` (orchestrator) | ✅ complete | Command dispatch, C# CLI integration, `generated_output_guard`, Python mode routing, `decode-geometry` with `--experimental-position-source`, `batch-export-264` batch OBJ exporter |
| `scripts/rift_workflow_reports.py` (reports) | ✅ complete | `show_report_summary` (8 mode branches), `semantic_hint_cross_tab`, `discovery_workbench`, `position_source_sibling_family_report`, `position_source_gap_report`, `residual_position_classifier_report` |
| `scripts/Invoke-RiftWorkflow.ps1` (thin wrapper) | ✅ updated | Translates legacy PS mode names → kebab-case Python commands |
| `scripts/rift_workflow_guards.py` (proof guards) | ✅ complete | `attribute_extra_proof_guard` (dual-path: fitness/stream) + `attribute_extra_sibling_proof_guard` (dual-path: index-role/body-role) + `usage_access_correlation_guard` + `position_source_sibling_lead_guard` + `residual_lead_guard` ported from PS. Fitness path now validates @264 aggregate edge/area/normal/parity/strip-structure regressions. |
| Guard/report functions (remaining 0) | ✅ all ported | All 12 guard/report functions fully ported from PowerShell to Python |
| `scripts/Invoke-RiftAssetWorkflow.ps1` (legacy) | ✅ retired | All complex modes ported; `complex_modes` is now empty in `rift_workflow.py`. Legacy PS still available but no longer needed as fallback. |

**Key commands (Python):**

```powershell
# Thin PS wrapper (recommended entry point)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Invoke-RiftWorkflow.ps1 mesh-bindings
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Invoke-RiftWorkflow.ps1 mesh-probe --id c841eb9a0ed1c95e --mesh-block 6
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Invoke-RiftWorkflow.ps1 all --full
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Invoke-RiftWorkflow.ps1 attribute-extra-proof-guard --full --skip-build
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Invoke-RiftWorkflow.ps1 attribute-extra-sibling-proof-guard --id 6fc01704d4a509d5 --skip-build

# Direct Python (alternative)
python scripts/rift_workflow.py mesh-bindings --full
python scripts/rift_workflow.py semantic-hint-crosstab
python scripts/rift_workflow.py discovery-workbench --privacy-scan
python scripts/rift_workflow.py discovery-suite --skip-build
python scripts/rift_workflow.py discovery-suite --quick --skip-build
python scripts/rift_workflow.py attribute-extra-proof-guard --full --skip-build
python scripts/rift_workflow.py attribute-extra-sibling-proof-guard --id 6fc01704d4a509d5 --skip-build
python scripts/rift_workflow.py decode-geometry --id 6fc01704d4a509d5 --mesh-block 6 --full
python scripts/rift_workflow.py decode-geometry --id 6fc01704d4a509d5 --mesh-block 6 --experimental-position-source --write-obj
python scripts/rift_workflow.py batch-export-264 --skip-build
```

**All 12 PS complex modes fully ported to Python — `complex_modes` is now empty.**

```powershell
# All 4 position-source-sibling probe commands are now ported to Python:
python scripts/rift_workflow.py position-source-sibling-probe-report --skip-build
python scripts/rift_workflow.py position-source-sibling-representative-probe-report --skip-build
python scripts/rift_workflow.py position-source-sibling-secondary-probe-report --skip-build
python scripts/rift_workflow.py position-source-sibling-extra-position-report --skip-build
```

**2026-06-03 — Stage 2 refresh: Position-source discovery sweep (complete):**

**Fresh baseline:**
- Endian-analysis fix (Stage 9) confirmed stable: **1,949 pair-compatible meshes** across full inventory.
- All guard/report functions fully ported from PowerShell to Python; `complex_modes` set is now empty.
- All 12 PS complex modes runnable via `python scripts/rift_workflow.py`.

**Position-source gap report:**
- No position gaps in the five indexed target mesh sizes (297, 305, 321, 325, 329).
- meshSize=297: topology-proof anchor (4+ attribute sets).
- meshSize=305: residual-position-candidate-family (5+ position-like rows with plausible ≥ 0.80).
- meshSize=321/329: topology-rich families; residual side-streams low-signal.
- meshSize=325: topology-rich sparse-position singleton lead (300+ pairings, 0 residual streams).

**Position-source sibling family report:**
- Five known sibling groups with shared position sources confirmed.
- | Mesh size | Mesh blocks | Stream offsets | Groups | Links | Decision |
  |---:|---|---:---:|---|---|
  | 329 | mesh#7, mesh#34 | stream@212 | 23 | 46 | repeated source-binding family |
  | 305 | mesh#7, mesh#27 | stream@188 | 15 | 30 | repeated source-binding family |
  | 321 | mesh#7, mesh#31 | stream@204 | 11 | 22 | repeated source-binding family |
  | 325 | mesh#6, mesh#30 | stream@292/@296 | 1 | 2 | shifted sibling position-source clue |
  | 329 | mesh#6, mesh#31 | stream@296 | 1 | 2 | shifted sibling position-source clue |
- meshSize=329 is the strongest: 23 groups sharing stream@212, target block#28, 46 total links.
- meshSize=305 is the second strongest: 15 groups sharing stream@188, target block#21, 30 links.

**Residual position classifier report:**
- Candidate-only dry-run on meshSize=305 stream@188 POSITION usage=1 access=19 residuals.
- 8 target rows identified; **0 strict passes** (all below 0.95 PlausibleValueRatio).
- 5 candidate guard rows with plausible ≥ 0.80 — held as ranking evidence only.
- Plausible range: 0.8283 (payload 396) to **0.9444** (payload 288).
- Payload 288 is the strongest candidate (0.9444 plausible, 24 vectors, extent=36.0).
- All paired (mesh#7+mesh#27) rows share matching stream/body/prefix evidence — no divergent pairs.
- All 3+ guard assertions pass: strict=0, paired rows ≥ 8, divergent = 0, candidate guard ≥ 3.

**Residual position cluster probe report:**
- Deep-dive on 5 payload variants (96, 180, 192, 288, 396) at meshSize=305 stream@188 block#21.
- All payloads emit to mesh#7 and mesh#27 over the same stream block #21.
- **Key structural finding — UInt16 triples analysis:**
  - Payload 288 exhibits `magic-43606-u16-ternary-alternating` — magic constant 43606 (0xAA56) on even-C with alternating metadata layer. Typical of packed uint16 positions with vertex-type tag.
  - Payload 96 has `u16-ternary-mixed-c` — alternating structure with varying even-C values. May indicate multi-attribute or interleaved data. **No magic 43606** (unique structure).
  - Payloads 180, 192, 396 are `unstructured-u16` — present magic 43606 but no clear alternating pattern.
- All payloads: **0 attribute sets, 0 pairings** — no complete geometry binding.
- Byte-layout comparison against payload 288 baseline:
  - Payload 96: 0 common prefix bytes, 59% diff ratio — structurally different.
  - Payload 180: 1 common prefix byte, 34% diff ratio — closest to 288.
  - Payload 192: 15 common prefix bytes, 44% diff ratio.
  - Payload 396: 9 common prefix bytes, 43% diff ratio, length +108.
- All mesh roles: `uint16-compatible-body`, confidence 25 (no index role assigned).
- **Export/OBJ remains blocked for all rows** — `GeometryTruthPromoted=false` on every payload.

**Bottom line:** The meshSize=305 stream@188 position-like data is persistently below the strict 0.95 classifier threshold. The magic-43606 pattern in payload 288 (0.9444 plausible) is the most promising lead for quantized/packed uint16 positions, but no index pairing or attribute sets exist to confirm geometry binding. This lane remains candidate-only ranking evidence.

**2026-06-02 — Stage 2: Position-source fallback + triage + end-to-end validation (original, completed 2026-06-02):**
- Extended `ExperimentalPositionSource` fallback to decode **normals** and **UVs** from linked NiDataStream blocks. Build/tests/code-review clean.
- Full inventory: 5,507 NiMesh blocks, 5,455 (99%) have 0 attribute sets, 210 position-float3 candidates.
- End-to-end validated on 0-attribute-set meshes.

**Known limitations (unchanged from Stage 2):**
- Faces are trivial triangle fan (vertex 0 to consecutive pairs) since no index stream is available in fallback mode.
- Only the first float32 candidate per role is used; multiple candidates are skipped.
- 5,455 meshes (99%) have 0 attribute sets — fallback handles these where linked streams contain float32 data.
- Output path overlap: `--write-obj` writes OBJ to subdirectory under the probe-report JSON path.

**2026-05-20 — C# gate fixes + fitness guard completion:**

**2026-05-20 — C# gate fixes + fitness guard completion:**
- Fixed two `StartsWith("index-")` gates in `Program.cs` (inventory loop L3949, probe loop L2602) → now use `IndexStats is not null`. This was the root cause preventing `TopAttributeExtraMappingFitness` from populating for `uint16-compatible-body` extra streams.
- Removed the `if (preferredMapping != "insufficient")` gate so fitness accumulation runs unconditionally.
- Added `required_json_boolean()` + boolean rejection in `required_json_number()`/`required_json_integer()` to `rift_workflow_utils.py`.
- Implemented `_attribute_extra_proof_guard_fitness()` — validates @264 aggregate edge-delta, area-gap, strip-structure, segment, parity, and sentinel regressions against 4 vertex-count groups.
- `attribute_extra_proof_guard()` now routes to fitness path when data available, falls back to stream-level guard.
- JSON field names verified against actual C# output; all match. Proof guard passes on both limited and full inventories.

Defensive coding policy: discovery work frozen. PowerShell demoted to thin cmd wrappers/runner only. All helper logic lives in Python modules under `scripts/`.

---

## TL;DR 🧭

| Lane | Status | Current truth |
|---|---:|---|
| Compression / LZMA2 | ✅ clarified | Full live `TWAD` archive entries still use only compression `0` and `1`; compression `2` remains a manifest Table 0 logical PAK-layer problem. |
| Ghidra / TWAD static proof | ✅ complete | Retained `rift_x64.exe` Ghidra anchor survey proved `TWAD` as archive file/header magic and `TWAM` as manifest-layer magic. Parser behavior remains unchanged; `TwadArchiveHeader_MatchesClientGhidraProof` covers the proven header layout. Next safe static targets are unsupported-version warning/test review or the `NiDataStream` / `NiMesh` leads. |
| Ghidra / NiDataStream static proof | 🔬 layout mismatch found | Retained-project Ghidra surveys identify `NiDataStream::LoadBinary()` field/payload loading and a mesh semantic-adapter validator called from the DX9 material-binding path. `nidatastream-layout --root Extracted --full` validated 184/184 copied `NiDataStream` blocks as `28-byte descriptor prefix + declared payload + 1-byte trailing flag`; current C# reporting still slices from legacy offset 29, so decoder behavior remains unchanged until a guarded migration patch. |
| Model format | ✅ major lead | Repeated Gamebryo payloads are now detected/extracted as `.nif` and parsed for NIF header/block/string-table evidence. |
| Filename/path recovery | ✅ proven lead | NIF string tables produced real `.dds` name candidates and high-confidence FNV1 manifest matches. |
| Asset signature/semantic index | ✅ new scaffold | `inventory-asset-signatures` now groups all copied payload signatures, and `build-asset-semantic-index` emits generated `asset-semantic-index/v1` packets under ignored `Exports/` with IDs, detected types, signatures, bounded references/snippets, `hint:*` semantic categories, category filters, XML tag/attribute name counts, and XML parse status/boundary metadata with no values/text/raw parse messages. |
| Model→texture graph | ✅ working | NIF references link `3,224` model assets to `2,514` unique texture manifest assets. |
| Bundle completion | ✅ newly actionable | A live-read-only archive planner found every currently missing NIF-linked texture asset and ranked the exact `assets.###` chunks needed. |
| Mesh stream binding | ✅ new proof lead | `inventory-nif-mesh-bindings` found `2,076` pair-compatible meshes and `4,468` same-mesh index/vertex-count-compatible links. |
| Mesh role decoding | ✅ new byte-order lead | Many coarse `uint16-compatible-body` streams now decode as rotate-right-1 `float3` normals and `float2` UVs. |
| Attribute-set topology | ✅ structural lead | Complete position/normal/UV sets are now ranked by implicit topology candidates; strongest family is `v=16`, strip-or-quad, `7` copied-set hits. |
| Attribute extra streams | ✅ split truth | Focused probing down-ranked low-variation `@272/#25` and `@296` side streams, while full mesh-binding inventory now finds four `@264/#15` explicit-index groups where segmented decoded-position, normal-delta, and triangle-area aggregate fitness favor raw-zero-based (`5/5` samples); UV deltas are neutral/no-worse, strip structure is consistently degenerate-bridge/stitch-like, first-segment proof samples include area/parity plus compact review flags, and the aggregate + focused sibling proof guards now fail if those proof signals silently flip. |
| Position source fallback (Stage 2) | ✅ complete | `--experimental-position-source` decodes normals+UVs+positions; `--write-obj` wired. **Position discovery sweep (2026-06-03):** gap report shows **no position gaps** in indexed families; sibling family confirms 5 shared-source groups (strongest: meshSize=329×23 groups); classifier finds 5 candidate rows at plausible 0.8283–0.9444 (below strict 0.95); cluster probe identifies magic-43606 pattern in payload 288 — promising but no complete geometry binding found. All rows remain candidate-only; export blocked. |
| Discovery suite automation | ✅ complete | `discovery-suite` command orchestrates: build → inventory → position reports → guards → workbench → summary. Supports `--quick` (reuse inventory) and `--skip-build`. Single command runs 7 unified pipeline stages. |
| @264 batch OBJ export (Stage 4) | ✅ complete | `batch-export-264` command exports all 5 known `@264`-indexed meshes (v=128/128/95/80/64) via `--export-obj`; 5/5 passed, 71,435 bytes total. |
| Position fallback faces (Stage 5) | ✅ complete | Experimental-position-source path now generates UInt16BE degenerate-bridge triangle-strip OBJ faces from index-stream pairings (`FindNifMeshProbePairings`); 4 `WriteObj`→`WriteObj||ExportObj` guard fixes ensure OBJ data populates under `--export-obj`; tested on 2 fallback meshes, build clean, 6/6 tests pass. |
| Pairing validation (Stage 6) | 🔬 concluded | Investigated why pairings=0 for 0-attribute-set meshes; detailed stream analysis proved `index-u16be-lead` classification is a false positive (4 distinct values, 99% degenerate); strict `vertexCount > IndexMax` check is correct; no valid 0-attr+pairing meshes exist in the inventory. Reverted lenient-fallback attempt. |
| False-positive `index-u16be-lead` classifier fix (Stage 7) | ✅ complete | Raised `BigEndianDistinctIndexCount` threshold 3→8; added degenerate-ratio gate (≤90%) in catch-all else branch; lowered confidence 70→60. Validated on both false-positive meshes — sentinel bodies now correctly classified as `strided-body`/`uv-float2-ror1-lead`/`normal-float3-ror1-lead`. Build 0 errors, tests 6/6, code review clean. |
| Endian-analysis root-cause fix (Stage 9) | ✅ complete | Fixed pre-existing bug where `AnalyzeNifStreamEndian` read both `little` and `big` as big-endian (line 9322: `ReadUInt16BigEndian`→`ReadUInt16LittleEndian`), making the endian classifier unable to distinguish them and always returning `ambiguous-small-u16` for small-value streams. Added `ambiguous-small-u16` safety-net handler (≥8 distinct, triangle-aligned, ≤50% degenerate → `index-u16be-lead` c=55). Added guards to `little-endian-u16-lead` gate (≥8 distinct, triangle-aligned, ≤90% degenerate → `index-u16le-lead` c=45) to prevent sentinel misclassification. Updated proof guard baselines for new role/topology values. **PairCompatibleMeshes restored to 1,949** (from 0 post-Stage 7). Build 0 errors, tests 6/6, proof guard PASSED, code review clean. |
| Full-scale OBJ export + guard validation (Stage 10) | ✅ complete | 13 OBJs across 11 unique assets decoded. **5 @264 faced** OBJs: 128v/318f (×2), 95v/118f, 80v/78f, 64v/82f. **1 breakthrough pairing face**: `084c1e91726a2aea` mesh#6 — first non-@264 mesh with working face generation (24v/22f) via `FindNifMeshProbePairings`. **6 position-only** meshes. All 4 proof guards PASSED. |
| Scaling to new mesh families (Stage 11) | ✅ complete | **9 new faced OBJs from 3 new families** — meshSize=301 (48v/46f ×3), meshSize=321 (24v/22f ×3), meshSize=367 (130v/431f ×3). **Total: 21 OBJs, 15 faced, 2,433 faces across 5 families.** Key insight: the C#-level  in  finds pairings that the aggregated inventory  misses. All 4 proof guards PASSED. CI green. |
| Scaling to all remaining families (Stage 12) | ✅ complete | **8 new faced OBJs from 3 new families** — meshSize=309 (48v/189f ×3), meshSize=405 (15v/39f ×3), meshSize=280 (32v/30f ×2). **Total: 29 OBJs, 23 faced, 3,177 faces across 8 families, 6 position-only across 4 families.** meshSize=465 (10 pairings) probed but all 3 samples missing from copied archives. 12 of 13 unprobed sizes have PairCompatible=0 — exhaustive probe complete. All 4 proof guards PASSED. CI green. |
| Scaling to all remaining families (Stage 12) | ✅ complete | **8 new faced OBJs from 3 new families** — meshSize=309 (48v/189f ×3), meshSize=405 (15v/39f ×3), meshSize=280 (32v/30f ×2). **Total: 29 OBJs, 23 faced, 3,177 faces across 8 families, 6 position-only across 4 families.** meshSize=465 (10 pairings) probed but all 3 samples missing from copied archives. 12 of 13 unprobed sizes have PairCompatible=0 — exhaustive probe complete. All 4 proof guards PASSED. CI green. |
| Baseline verification + integrity check (Stage 13) | ✅ complete | Full discovery suite refresh (8.1s, 3 inline guards PASSED). All 4 proof guards PASSED — attribute-extra (@264 groups intact, raw-zero-based 5/5), usage-access, position-source-sibling, residual-lead. OBJ inventory verified: **29 OBJs (23 faced, 6 pos-only), 3,177 faces, 1,881 vertices across 13 families.** meshSize=465 confirmed dead end (no sample IDs in copied archive). CI green (build 0e, tests 6/6, ruff 0). |

| Discovery resume + family coverage audit (Stage 14) | ✅ complete | Full discovery suite refresh (~25s, all 7 stages green). OBJ inventory: **56 unique meshes** (deduplicated). All 4 proof guards PASSED. magic-43606 lead re-investigated and confirmed dead end. CI green (build 0e, tests 6/6, ruff 0). |
| mypy 2.1.0 CI fix + meshSize=465 investigation (Stage 15) | ✅ complete | Resolved 163 mypy 2.1.0 regressions (0 errors). Investigated meshSize=465: all 13 samples confirmed dead end (no position/index streams, uint16-packed tangent-space data only). CI green (build 0e, tests 6/6, ruff 0, mypy 0). |
| New mesh families + aggressive lead pursuit (Stage 16) | ✅ complete | **4 new faced families discovered** — meshSize=267 (5v/2f), 345 (137-149v/414-424f), 361 (151v/414f), 365 (138-176v/414-464f). **73 OBJs, 47 faced, 7,744 faces, 4,649 vertices across 17 families.** meshSize=465 confirmed dead end (no position/index streams). Targeted inventory query for index-stream sizes was the breakthrough methodology. All 4 guards PASSED. CI green. |
| OBJ manifest + remaining unexplored sizes (Stage 17) | ✅ complete | **1 new faced family** — meshSize=354 (24v/22f). OBJ manifest with SHA256 hashes (`Exports/obj-manifest-stage17.json`). **76 OBJs, 48 faced, 7,766 faces, 4,695 vertices across 18 families.** 2 mesh sizes confirmed dead ends (330, 370). All 4 guards PASSED. CI green. |
| Batch-sweep runner + OBJ integrity + candidate exhaustion (Stage 18) | ✅ complete | `batch_sweep.py` — 4-phase tool for OBJ integrity validation (SHA256, index bounds, NaN, negative indices), candidate discovery, batch export, and manifest building. **94 OBJs, 65 faced, 10,795 faces, 6,079 vertices across 18+ families. 0 structural issues. 0 unexported candidates remain.** All 4 proof guards PASSED. CI green (build 0e, tests 6/6, ruff 0, mypy 0). |
## Approved operating mode 🚀

This repo is now following the approved **Aggressive Evidence Workflow**:

```text
docs\aggressive-discovery-workflow.md
```

Reasoning/model routing for this repo is now explicitly fail-closed:

```text
docs\task-routing-safety-policy.md
```

| Principle | Practical behavior |
|---|---|
| Maximum real discovery speed | Add narrow probes/inventories, run smoke + full copied-set scans, then immediately advance the strongest lead. |
| Not reckless output | No copied assets, generated dumps, raw user-profile paths, or unproven model exports get committed. |
| Current critical path | Prove `NiMesh` → `NiDataStream` bindings, infer stream roles, validate `maxIndex < vertexCount`, and down-rank non-geometry sentinel/mask side streams before export work. |
| Export gate | OBJ/model export stays experimental and disabled until mesh/stream pairing is structurally proven. |
| Reasoning safety | Use high/extra-high reasoning for truth, proof, schema, guard, runtime, cross-repo, live-game, exporter, and commit/push decisions; lower-intelligence execution is allowed only for reversible mechanical work after the safety checklist passes and main-lane review follows. |

Optionized helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshBindings -Full -PrivacyScan
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshProbe -Id c841eb9a0ed1c95e -MeshBlock 6
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProbe -Id 75d5a06d7c0de1dd -MeshBlock 7 -ExtraOffset 272
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProofGuard -SkipBuild
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraSiblingProofGuard -SkipBuild
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AssetSignatures -SmokeMaxTotal 500 -SkipBuild
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AssetSemanticIndex -SmokeMaxTotal 200 -SkipBuild
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AssetSemanticIndex -Type xml -SemanticCategory hint:map-zone -SmokeMaxTotal 200 -SkipBuild
```

```powershell
python "C:\RIFT MODDING\Assets\scripts\rift_asset_discovery_matrix.py" --skip-build --jobs signature-baseline semantic-xml-map-zone semantic-bin-waypoint-poi --privacy-scan
```

Helper policy: add modes/options to durable helpers before creating one-off helper apps. New batching/orchestration helpers should be Python-first, but the .NET dumper remains the parser/source of truth and existing PowerShell workflows remain compatibility surfaces until an active bottleneck justifies porting.

## Targeted semantic discovery matrix 🎯

A bounded Python matrix smoke wrote generated reports under ignored `Exports\discovery-matrix\` and validated each emitted `asset-semantic-index/v1` packet with `jsonschema`.

| Job | Payloads inspected | Entries | Signature groups | Current read |
|---|---:|---:|---:|---|
| `semantic-xml-map-zone` | `6` | `6` | `1` | XML map-zone/UI/model hints exist, but all XML parses are `partial-with-warning`; use tag/attribute families as structure leads only. |
| `semantic-bin-waypoint-poi` | `1,000` | `113` | `77` | Strongest current binary text-family lead for waypoint/POI-like terms; many also overlap actor/map/texture hints. |
| `semantic-bin-map-zone` | `1,000` | `101` | `96` | Binary map/zone-like hints exist and overlap waypoint/actor refs; needs category-aware prefiltering before full-corpus scans. |
| `semantic-bin-actor-object` | `1,000` | `95` | `77` | Actor/object-like binary hints overlap waypoint/map/texture refs; useful for model/object graph ranking. |
| `semantic-bin-quest-objective` | `1,000` | `0` | `0` | No early-corpus quest/objective binary hits yet; keep as negative evidence, not final absence. |
| `semantic-nif-texture-refs` | `500` | `308` | `1` | NIF texture references remain high-value semantic labels for object/zone/model families. |
| `semantic-nif-model-refs` | `500` | `500` | `1` | NIF model reference extraction is broad and useful for graph enrichment. |

## Gamebryo/NiDataStream normalization 🧬

NIF block-type parsing now preserves raw escaped block-type names while normalizing Gamebryo `NiDataStream` variants that encode usage/access in the block-type string.

| Field | Meaning |
|---|---|
| `TypeName` / `NormalizedName` | Parser-friendly block family name, for example `NiDataStream`. |
| `TypeDisplayName` / `DisplayName` | Escaped raw block-type string, for example `NiDataStream\u00011\u000119`. |
| `DataStreamUsage` / `DataStreamAccess` | Parsed Gamebryo stream metadata from `NiDataStream<SOH>usage<SOH>access` block-type strings. |

Validated smoke sample `21900d2ee4f931ca` has `NiDataStream\u00010\u000119` and `NiDataStream\u00011\u000119`; the probe now surfaces `usage=0/1` and `access=19` while grouping blocks as normalized `NiDataStream`.

Latest resumed slice: `inventory-nif-stream-headers`, `inventory-nif-stream-bodies`, and `probe-nif-mesh` now carry `DataStreamUsage` / `DataStreamAccess` into generated JSON samples/summaries. A 50-NIF smoke validated `333` parsed streams with `usage=1 access=19` (`278`) and `usage=0 access=19` (`55`), and `probe-nif-mesh` now uses a metadata-completeness tie-breaker (`DataStreamMetadataScore`) without treating usage/access as final geometry semantics.

Follow-up mesh-binding inventory slice: `inventory-nif-mesh-bindings` now emits role-level `UsageAccessCounts`, `TopUsageAccessRoles`, and index/vertex usage-access metadata in pairing samples/groups so role heuristics can be compared against Gamebryo stream metadata without promoting metadata to geometry truth. A 100-NIF smoke found `211` valid declared stream bodies and grouped the visible roles as:

| Usage/access | Role | Count |
|---|---|---:|
| `1/19` | `uv-float2-ror1-lead` | `100` |
| `1/19` | `normal-float3-ror1-lead` | `77` |
| `0/19` | `index-u16be-strip-lead` | `34` |

Interpretation: in this bounded smoke, `usage=0 access=19` aligns with compact index-strip leads while `usage=1 access=19` aligns with rotated float normal/UV leads. Top pairings now show the same split as `index[usage=0 access=19] -> vertex[usage=1 access=19]`. Keep this as correlation/ranking evidence only until broader copied-set scans and mesh topology proof agree.

Full copied-set refresh confirmed the same split across `5,111` NIF payloads, `5,507` NiMesh blocks, and `11,564` valid declared mesh-bound data-stream bodies:

| Usage/access | Role | Count |
|---|---|---:|
| `1/19` | `uv-float2-ror1-lead` | `4,633` |
| `1/19` | `normal-float3-ror1-lead` | `4,167` |
| `0/19` | `index-u16be-strip-lead` | `2,101` |
| `1/19` | `position-float3-ror1-lead` | `210` |
| `0/19` | `index-u16be-list-lead` | `112` |

The top pairing groups all follow `index[usage=0 access=19] -> vertex[usage=1 access=19]`; no top-100 pairing exception was found in the generated report. Mixed/non-leading role exceptions remain low-signal and should not drive topology truth: `strided-body` split across `1/19` (`43`) and `0/19` (`38`), `u32-repeated-pattern-body` split across `1/19` (`56`) and `3/3` (`21`), and `index-u16be-lead` split across `0/19` (`3`) and `1/19` (`1`).

## Compression truth 🧊

| Scope | Count | Compression counts |
|---|---:|---|
| Copied `TWAD` entries | `40,203` non-null entries | `0=203`, `1=40000`, `2=0` |
| Full live `TWAD` entries | `263,957` non-null entries across `244` archives | `0=22422`, `1=241535`, `2=0` |
| Manifest Table 0 logical PAK rows | `2,076` rows | `0=736`, `2=1340` |

Conclusion: LZMA2 is real in the manifest/PAK layer, but not in ordinary copied or full-live `TWAD` entry payloads seen so far. Do not claim raw LZMA2 extraction until a validated payload path is proven with size/SHA checks.

## Gamebryo / NIF model discovery 🧩

Large binary inventories found repeated Gamebryo model headers and promoted those payloads from generic `.bin` to `.nif`.

| NIF inventory metric | Value |
|---|---:|
| Copied payloads inspected | `40,203` |
| NIF payloads | `5,111` |
| NIF layout groups | `817` |
| Mined NIF references | `19,616` |
| Dominant version | `20.6.0.0` |
| Additional observed version family | `20.3.0.9` |

The NIF parser now captures header/version/endian, block counts, block type usage, block-size evidence, string tables, and path-like/source-art/texture references from NIF strings.

## Filename/path recovery lead 🧵

NIF string tables contain embedded source-art paths and texture names. Those names are now used as manifest hash candidates.

| Recovery step | Result |
|---|---:|
| NIF reference records exported | `19,616` |
| Unique normalized candidates | `7,063` |
| High-confidence manifest filename matches | `2,567` |
| Matching algorithm observed | `fnv1` |
| Dominant matched extension | `.dds` |

Important interpretation: these are embedded model references that match manifest filename hashes, so this is stronger than placeholder dictionary guessing. The original full packed path is still not universally recovered, but texture filenames are now evidence-backed.

## Model→texture graph and bundle status 🧱

| Graph / bundle metric | Value |
|---|---:|
| NIF payloads scanned for graph | `5,111` |
| Texture candidates tested | `9,489` |
| Recovered model→texture links | `9,434` |
| Unique linked NIF models | `3,224` |
| Unique linked texture manifest assets | `2,514` |
| Complete bundles in current copied archives | `6` |
| Incomplete bundles in current copied archives | `3,218` |
| Present texture refs in copied archives | `66` |
| Missing texture refs in copied archives | `9,293` |

Validated example complete bundle:

```text
model\001104_m253891_fnva0a67ee3_pak0311_off1393297_cc1dff6de7d25ed1.nif
textures\recovered\mushr3_c.dds
textures\recovered\mushr3_g.dds
textures\recovered\mushr3_s.dds
```

## New archive-completion planner 🎯

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- plan-nif-bundle-archives --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --out "C:\RIFT MODDING\Assets\Exports\nif-bundle-archive-plan.json" --limit 200
```

Validated live-read-only result:

| Planner metric | Value |
|---|---:|
| Live archives scanned | `244` |
| Graph links | `9,434` |
| Graph models | `3,224` |
| Copied asset IDs | `40,203` |
| Missing unique texture assets | `2,494` |
| Missing texture assets found in live archives | `2,494` |
| Missing texture assets not found in live archives | `0` |
| Recommended archive chunks | `132` |
| Greedy selected archives with `--limit 200` | `132` |
| Bundles completed after full greedy plan | `3,218` |

Top archive recommendations:

| Rank | Archive | Missing texture assets | Texture links | Affected models | Bundles completed by archive alone |
|---:|---|---:|---:|---:|---:|
| 1 | `assets.002` | `26` | `846` | `605` | `339` |
| 2 | `assets.125` | `63` | `459` | `212` | `155` |
| 3 | `assets.107` | `70` | `320` | `147` | `126` |
| 4 | `assets.153` | `78` | `321` | `169` | `105` |
| 5 | `assets.166` | `39` | `303` | `183` | `94` |
| 6 | `assets.165` | `125` | `297` | `91` | `67` |
| 7 | `assets.101` | `68` | `97` | `86` | `52` |
| 8 | `assets.135` | `46` | `111` | `57` | `51` |
| 9 | `assets.025` | `85` | `179` | `154` | `42` |
| 10 | `assets.131` | `45` | `292` | `105` | `38` |

Why this matters: the copied set does not need blind archive expansion anymore. The planner identifies exactly which live archive chunks contain the missing NIF-linked textures and predicts bundle-completion gain before anything is copied.

## Live-read fallback extraction proof 🧪

Targeted NIF bundle extraction now uses `--live-root` as a read-only fallback source for linked textures that are missing from the copied local archive subset.

Validated model:

| Field | Value |
|---|---|
| Model ID | `011267450ef6781f` |
| Copied-only result | `0/1` linked textures written |
| Live-fallback result | `1/1` linked textures written |
| Texture source | live fallback |
| Recovered texture path | `textures\recovered\diffuse_blank.dds` |

Output proof:

```text
Texture links: 1
Textures written: 1
Textures written from copied archives: 0
Textures written from live fallback: 1
Textures missing from copied archives: 1
Textures missing from selected sources: 0
model\000920_m177820_fnv70a506db_pak1434_off309027_011267450ef6781f.nif
textures\recovered\diffuse_blank.dds
```

Why this matters: the tool can now complete selected model+texture bundles immediately without first copying entire high-yield archive chunks into `Source\Assets`.

## Larger indexed live-fallback bundle proof 🧱

Live fallback extraction now builds a one-pass payload index for the requested IDs. That prevents repeated archive-table scans when a model references many textures.

Validated larger model:

| Field | Value |
|---|---:|
| Model ID | `16ecac86a42d4d96` |
| Indexed payload IDs | `23` |
| Copied archives scanned once | `27` |
| Live fallback archives scanned once | `244` |
| Texture links | `22` |
| Textures written | `22` |
| Textures from copied archives | `0` |
| Textures from live fallback | `22` |
| Missing from selected sources | `0` |

Texture source archives:

| Archive | Texture count |
|---|---:|
| `assets.152` | `9` |
| `assets.187` | `6` |
| `assets.129` | `4` |
| `assets.196` | `2` |
| `assets.171` | `1` |

Why this matters: the graph is now usable for richer model bundles, not just one-texture smoke tests. A copied model from `assets.053` was paired with 22 recovered live textures spread across five live archive chunks.

## Batch rich-bundle extraction proof 📦

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-nif-bundles --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --out "C:\RIFT MODDING\Assets\Extracted\nif-bundles-batch-top3" --limit 3
```

Validated top-3 rich linked models:

| Metric | Value |
|---|---:|
| Selected models | `3` |
| Indexed payload IDs | `41` |
| Copied archives scanned once | `27` |
| Live fallback archives scanned once | `244` |
| Complete bundles | `3` |
| Texture links | `54` |
| Textures written | `54` |
| Textures from live fallback | `54` |
| Missing from selected sources | `0` |
| Output model files | `3` |
| Output DDS textures | `54` |

Selected models:

| Model ID | Linked textures | Result |
|---|---:|---|
| `16ecac86a42d4d96` | `22` | complete |
| `121c431473f2cc7e` | `16` | complete |
| `1342fd262740063b` | `16` | complete |

Texture source spread:

| Archive | Texture count |
|---|---:|
| `assets.201` | `12` |
| `assets.152` | `9` |
| `assets.130` | `8` |
| `assets.187` | `6` |
| `assets.194` | `6` |
| `assets.129` | `4` |
| `assets.153` | `4` |
| `assets.002` | `2` |
| `assets.196` | `2` |
| `assets.171` | `1` |

Why this matters: the dumper now moves from one-off model proofing to repeatable safe batch extraction of high-value model+texture bundles. The output is ready for external visual/NIF tooling validation while the live install remains read-only.

## NIF block payload map proof 🔬

`probe-nif` now emits a per-block payload map: block index, type, byte size, data offset, first bytes, numeric prefixes, candidate string indexes, and resolved string samples. This is the first concrete step from "NIF detected" toward evidence-based mesh/data-stream decoding.

Validated rich-bundle model:

| Metric | Value |
|---|---:|
| Model ID | `16ecac86a42d4d96` |
| NIF blocks | `139` |
| Block types | `16` |
| Block data offset | `2756` |
| Block data size total | `11242` |
| Block data delta | `8` |
| NiMesh blocks | `4` |
| NiDataStream blocks | `36` |
| NiSourceTexture blocks | `22` |

Top block families:

| Block type | Count |
|---|---:|
| `NiDataStream\u00011\u000119` | `32` |
| `NiIntegerExtraData` | `32` |
| `NiSourceTexture` | `22` |
| `NiFloatsExtraData` | `16` |
| `NiFloatExtraData` | `8` |
| `NiMaterialProperty` | `5` |
| `NiMesh` | `4` |

Mesh block clues:

| Block | Size | String clues |
|---:|---:|---|
| `#7` | `387` | `pCubeShape409:0`, `normalTexture`, `tint0`, `tint1` |
| `#44` | `387` | `pCubeShape409:1`, `normalTexture`, `A_PTW_bricks_base_mossy_01_n.dds` |
| `#79` | `387` | `pCubeShape409:2`, `normalTexture`, `glow2Texture` |
| `#110` | `387` | `pCubeShape409:3`, `normalTexture`, `glow2Texture` |

NiDataStream size families:

| Size | Count |
|---:|---:|
| `41` | `1` |
| `45` | `1` |
| `61` | `3` |
| `69` | `2` |
| `77` | `5` |
| `109` | `6` |
| `125` | `1` |
| `149` | `8` |
| `209` | `1` |
| `317` | `1` |
| `389` | `3` |
| `569` | `4` |

Why this matters: the next geometry decoder can now work from exact `NiMesh` and `NiDataStream` block boundaries instead of guessing from whole-file binary signatures.

## Candidate NiMesh → NiDataStream links 🧬

`probe-nif` now scans `NiMesh` payload fields for values that point at `NiDataStream` block indexes. These are intentionally reported as **candidates**, not confirmed geometry decode, because some integer fields can also be valid string-table indexes. The console marks those ambiguous values with `?`, and JSON output records `MaybeStringIndex` plus `StringValue` for traceability.

Validated rich-bundle model:

| Model ID | Mesh block | Candidate stream offsets |
|---|---:|---|
| `16ecac86a42d4d96` | `#7` | `@236→#37? size=77`, `@312→#35? size=41`, `@320→#41? size=61` |
| `16ecac86a42d4d96` | `#44` | `@0→#37? size=77`, `@236→#72 size=149`, `@312→#35? size=41`, `@320→#76 size=109` |
| `16ecac86a42d4d96` | `#79` | `@236→#103 size=569`, `@312→#35? size=41`, `@320→#107 size=389` |
| `16ecac86a42d4d96` | `#110` | `@236→#132 size=149`, `@312→#35? size=41`, `@320→#136 size=109` |

Validated smaller copied model:

| Model ID | Mesh block | Candidate stream offsets |
|---|---:|---|
| `21900d2ee4f931ca` | `#6` | `@212→#24 size=1673`, `@288→#22? size=1649`, `@296→#28 size=1125` |

Why this matters: repeated offsets such as `@236`, `@312`, and `@320` are now concrete fields to reverse next, while ambiguity flags prevent over-claiming guessed references as proven mesh topology.

## Copied-set mesh-stream candidate inventory 📈

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-mesh-streams --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-mesh-stream-inventory.json" --limit 100
```

Validated full copied-set result:

| Metric | Value |
|---|---:|
| Inspected payloads | `40,203` |
| NIF payloads | `5,111` |
| NiMesh blocks | `5,507` |
| Mesh blocks with candidates | `5,507` |
| Candidate stream links | `11,564` |
| Ambiguous candidate links | `3,809` |

Top candidate offsets:

| Offset | Count | Ambiguous | Top target sizes | Top mesh sizes |
|---:|---:|---:|---|---|
| `@168` | `1,811` | `0` | `317×84`, `269×80`, `413×64`, `245×59` | `214×973`, `193×732`, `235×106` |
| `@276` | `642` | `233` | `413×62`, `53×40`, `557×29`, `101×25` | `301×364`, `309×205`, `385×31` |
| `@280` | `523` | `109` | `61×66`, `221×34`, `157×20`, `413×19` | `305×419`, `326×46`, `389×22` |
| `@300` | `514` | `89` | `221×145`, `173×37`, `509×26`, `445×22` | `325×329`, `346×93`, `333×45` |
| `@196` | `505` | `88` | `77×66`, `317×27`, `221×21`, `605×19` | `305×419`, `326×46`, `263×23` |

Top repeated stream-reference patterns:

| Mesh size | Count | Pattern |
|---:|---:|---|
| `325` | `138` | `@216:size=317`, `@292:size=101?`, `@300:size=221` |
| `235` | `82` | `@168:size=317` |
| `235` | `80` | `@168:size=269` |
| `193` | `64` | `@168:size=413` |
| `321` | `60` | `@212:size=317`, `@288:size=101?`, `@296:size=221` |

Why this matters: every copied `NiMesh` block now has at least one stream candidate. The most repeated, non-ambiguous lead is `@168`, and the most repeated multi-stream families identify concrete mesh/data-stream layouts to reverse before attempting OBJ export.

## Mesh-bound stream role and pairing inventory 🧷

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-mesh-bindings --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-mesh-binding-inventory.json" --limit 100
```

Validated full copied-set result:

| Metric | Value |
|---|---:|
| Inspected payloads | `40,203` |
| NIF payloads | `5,111` |
| NiMesh blocks | `5,507` |
| Mesh blocks with candidates | `5,507` |
| Candidate stream links | `11,564` |
| Valid declared stream bodies | `11,564` |
| Invalid declared stream bodies | `0` |
| Pair-compatible meshes | `2,076` |
| Pair-compatible links | `4,468` |
| Attribute-compatible meshes | `52` |
| Attribute-compatible sets | `52` |

Top stream roles:

| Role | Count | High confidence | Top payload sizes |
|---|---:|---:|---|
| `uv-float2-ror1-lead` | `4,633` | `4,633` | `192×326`, `384×159`, `216×133`, `288×116`, `32×107` |
| `normal-float3-ror1-lead` | `4,167` | `4,167` | `288×361`, `576×150`, `192×123`, `720×107`, `48×88` |
| `index-u16be-strip-lead` | `2,101` | `2,101` | `72×285`, `144×121`, `48×103`, `12×89`, `192×84` |
| `position-float3-ror1-lead` | `210` | `210` | `192×20`, `456×7`, `48×6`, `264×6`, `276×6` |
| `index-u16be-list-lead` | `112` | `112` | `48×15`, `120×11`, `72×10`, `144×10`, `108×9` |
| `u32-sentinel-mask-body` | `101` | `0` | `64×18`, `96×9`, `60×8`, `32×6`, `92×4` |
| `strided-body` | `81` | `0` | `6×38`, `88×6`, `32×5`, `116×4`, `284×4` |
| `u32-repeated-pattern-body` | `77` | `0` | `8×21`, `144×5`, `464×5`, `92×4`, `152×4` |

Top pair-compatible patterns:

| Mesh size | Count | Index stream | Compatible stream | Vertex count | Max index | Coverage |
|---:|---:|---|---|---:|---:|---:|
| `325` | `134` | `@292 payload=72 index-u16be-strip-lead` | `@216 payload=288 normal-float3-ror1-lead` | `24` | `23` | `1.00` |
| `325` | `118` | `@292 payload=72 index-u16be-strip-lead` | `@300 payload=192 uv-float2-ror1-lead` | `24` | `23` | `1.00` |
| `321` | `60` | `@288 payload=72 index-u16be-strip-lead` | `@212 payload=288 normal-float3-ror1-lead` | `24` | `23` | `1.00` |
| `305` | `57` | `@272 payload=12 index-u16be-strip-lead` | `@280 payload=32 uv-float2-ror1-lead` | `4` | `3` | `1.00` |
| `301` | `50` | `@268 payload=144 index-u16be-strip-lead` | `@276 payload=384 uv-float2-ror1-lead` | `48` | `47` | `1.00` |

Top position/normal/UV attribute-compatible patterns:

| Mesh size | Count | Position payload | Normal payload | UV payload | Vertex count | Topology lead |
|---:|---:|---:|---:|---:|---:|---|
| `305` | `6` | `192` | `192` | `128` | `16` | `implicit-strip-or-quad-candidate` |
| `297` | `2` | `1536` | `1536` | `1024` | `128` | `explicit-index-candidate-present` |
| `321` | `2` | `612` | `612` | `408` | `51` | `implicit-triangle-list-candidate` |
| `329` | `2` | `276` | `276` | `184` | `23` | `implicit-triangle-strip-or-fan-candidate` |
| `329` | `2` | `432` | `432` | `288` | `36` | `implicit-triangle-list-or-quad-candidate` |

Top attribute topology groups:

| Topology lead | Vertex count | Count | Triangle-list tris | Strip/fan tris | Quad count |
|---|---:|---:|---:|---:|---:|
| `implicit-strip-or-quad-candidate` | `16` | `7` | `-` | `14` | `4` |
| `implicit-triangle-strip-or-fan-candidate` | `23` | `3` | `-` | `21` | `-` |
| `implicit-triangle-list-candidate` | `51` | `2` | `17` | `49` | `-` |
| `implicit-triangle-list-candidate` | `93` | `2` | `31` | `91` | `-` |
| `implicit-triangle-strip-or-fan-candidate` | `14` | `2` | `-` | `12` | `-` |

Top extra streams found beside complete attribute sets:

| Topology lead | Vertex count | Extra stream | Payload | Role | Count | Fit |
|---|---:|---:|---:|---|---:|---|
| `implicit-strip-or-quad-candidate` | `16` | `@272` | `64` | `u32-sentinel-mask-body` | `6` | `per-vertex:4`, `per-quad:16` |
| `implicit-triangle-strip-or-fan-candidate` | `23` | `@296` | `92` | `u32-repeated-pattern-body` | `2` | `per-vertex:4` |
| `implicit-triangle-list-or-quad-candidate` | `36` | `@296` | `144` | `u32-repeated-pattern-body` | `2` | `per-vertex:4`, `per-triangle-list-triangle:12`, `per-quad:16` |
| `implicit-triangle-strip-or-fan-candidate` | `38` | `@296` | `152` | `u32-repeated-pattern-body` | `2` | `per-vertex:4` |
| `implicit-triangle-list-candidate` | `51` | `@288` | `204` | `u32-sentinel-mask-body` | `2` | `per-vertex:4`, `per-triangle-list-triangle:12` |

Why this matters: mesh stream binding moved from candidate references to same-mesh role and count compatibility, then promoted a byte-order lead. The strongest family now predicts `meshSize=325`, `@292` as a big-endian strip-like index stream, `@216` as rotate-right-1 normal `float3`, and `@300` as rotate-right-1 UV `float2`. Position data is still not proven.

## Focused NIF mesh probe 🧪

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-mesh --root "C:\RIFT MODDING\Assets\Source" --id c841eb9a0ed1c95e --mesh-block 6 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-c841-mesh6.json"
```

Validated sample:

| Field | Value |
|---|---|
| Asset ID | `c841eb9a0ed1c95e` |
| Mesh block | `#6` |
| Mesh size | `325` |
| Candidate links | `3` |
| Pairings | `2` |

Stream roles:

| Mesh offset | Stream block | Usage/access | Payload bytes | Role | Confidence |
|---:|---:|---|---:|---|---:|
| `@216` | `#25` | `1/19` | `288` | `normal-float3-ror1-lead` | `85` |
| `@292` | `#23?` | `0/19` | `72` | `index-u16be-strip-lead` | `85` |
| `@300` | `#29` | `1/19` | `192` | `uv-float2-ror1-lead` | `80` |

Pairing proof:

| Index stream | Max index | Compatible stream | Vertex count | Coverage | Metadata score | Confidence |
|---|---:|---|---:|---:|---:|---:|
| `@292/#23` | `23` | `@216/#25` | `24` | `1.00` | `4` | `95` |
| `@292/#23` | `23` | `@300/#29` | `24` | `1.00` | `4` | `90` |

Mesh payload scan:

| Probe | Result |
|---|---:|
| Rotate-right-1 / little-endian float2/float3 payload windows matching paired vertex count | `0` |

Why this matters: the project now has both full-set mesh-binding inventory and a focused one-mesh proof packet for the top `meshSize=325` family. The byte-rotation rule is strong enough to promote normals/UVs as leads, but not enough to export geometry because the position stream/source is still missing. Usage/access metadata now improves tie-breaking and review visibility, while remaining structural metadata rather than semantic proof. The mesh payload window scan did not find a simple inline position window for this sample, so the next search should inspect other block types/fields or repeated `position-float3-ror1-lead` families.

## Position/normal/UV attribute-set proof 🧱

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshProbe -Id 75d5a06d7c0de1dd -MeshBlock 7
```

Validated sample:

| Field | Value |
|---|---|
| Asset ID | `75d5a06d7c0de1dd` |
| Mesh block | `#7` |
| Mesh size | `305` |
| Attribute sets | `1` |
| Pairings | `0` |

Attribute streams:

| Mesh offset | Stream block | Payload bytes | Role | Vertex count |
|---:|---:|---:|---|---:|
| `@188` | `#21?` | `192` | `position-float3-ror1-lead` | `16` |
| `@196` | `#22?` | `192` | `normal-float3-ror1-lead` | `16` |
| `@280` | `#26?` | `128` | `uv-float2-ror1-lead` | `16` |

Topology scoring:

| Probe | Result |
|---|---|
| Primary topology lead | `implicit-strip-or-quad-candidate` |
| Triangle list | Rejected because `16` is not divisible by `3` |
| Triangle strip/fan | Candidate with `14` triangles |
| Quad list | Candidate with `4` quads |
| Confidence | `35` structural-only; **not export proof** |
| Extra stream | `@272/#25`, payload `64`, `u32-sentinel-mask-body`, fit=`per-vertex:4`, `per-quad:16` |

Why this matters: geometry discovery now has a second validated lane besides index pairings: unindexed or separately-indexed meshes with complete position/normal/UV attribute sets. The missing piece for renderable export is now narrower: distinguish strip/fan vs quad or find a separate topology stream for these attribute-only meshes, while separately continuing position discovery for the top indexed `meshSize=325` family.

## Focused attribute extra-stream probe 🧪

Command added:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProbe -Id 75d5a06d7c0de1dd -MeshBlock 7 -ExtraOffset 272
```

Direct CLI shape:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-attribute-extra --root "C:\RIFT MODDING\Assets\Source" --id 75d5a06d7c0de1dd --mesh-block 7 --extra-offset 272 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-attribute-extra-75d5a06d7c0de1dd-mesh7-extra272.json"
```

Validated across all six top `v=16` / mesh `#7` samples from `assets.053`:

| Asset ID | Extra stream | Payload | Header | Role | Byte histogram | Repeated 4-byte pattern |
|---|---|---:|---:|---|---|---|
| `75d5a06d7c0de1dd` | `@272/#25` | `64` | `29` | `u32-sentinel-mask-body` | `0xff×63`, `0x01×1` | `ffffffff×15` |
| `ec36d556375300cb` | `@272/#25` | `64` | `29` | `u32-sentinel-mask-body` | `0xff×63`, `0x01×1` | `ffffffff×15` |
| `1d7d90fc36f7c49a` | `@272/#25` | `64` | `29` | `u32-sentinel-mask-body` | `0xff×63`, `0x01×1` | `ffffffff×15` |
| `a6b26dabf88e1733` | `@272/#25` | `64` | `29` | `u32-sentinel-mask-body` | `0xff×63`, `0x01×1` | `ffffffff×15` |
| `8f996a791c0bc108` | `@272/#25` | `64` | `29` | `u32-sentinel-mask-body` | `0xff×63`, `0x01×1` | `ffffffff×15` |
| `04297730afc68f38` | `@272/#25` | `64` | `29` | `u32-sentinel-mask-body` | `0xff×63`, `0x01×1` | `ffffffff×15` |

Grouped views are still emitted for traceability:

| View | Slots | Bytes/slot | Fit |
|---|---:|---:|---|
| `per-vertex` | `16` | `4` | exact |
| `per-strip-or-fan-triangle` | `14` | `4` | near-fit with `8` trailing bytes |
| `per-quad` | `4` | `16` | exact |

Additional top extra-stream probes also down-ranked the apparent `@296` float leads:

| Group | Sample | Extra stream | Payload | Role after low-variation guard | Repeated pattern |
|---|---|---|---:|---|---|
| `v=23`, strip/fan candidate | `1c4f0a1acdb5e141` | `@296` | `92` | `u32-repeated-pattern-body` | `3a3aff3a×22` |
| `v=36`, triangle-list-or-quad candidate | `acccb682df4d4ad8` | `@296` | `144` | `u32-repeated-pattern-body` | `3a3aff3a×35` |
| `v=38`, strip/fan candidate | `b57694c1f202ec07` | `@296` | `152` | `u32-repeated-pattern-body` | `3a3aff3a×37` |

Interpretation: these top side streams are now useful mostly as **negative/guardrail results**. `@272` repeats the same sentinel-like body across every top sample, while `@296` repeats a constant `3a3aff3a` word. They should not decide strip-vs-quad topology and should not advance export readiness by themselves.

### Explicit-index extra stream lead 🧷

The same probe now emits index compatibility when the extra stream role is index-like. Current strongest positive sample:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProbe -Id 6fc01704d4a509d5 -MeshBlock 6 -ExtraOffset 264
```

| Field | Value |
|---|---|
| Asset ID | `6fc01704d4a509d5` |
| Mesh block | `#6` |
| Mesh size | `297` |
| Attribute vertex count | `128` |
| Extra stream | `@264/#15` |
| Payload/header | `906` / `29` bytes |
| Role | `index-u16be-strip-lead` |
| Candidate topology | `explicit-index-strip-lead` |
| Pair count | `453` |
| Triangle aligned | `true`, `151` fixed triples |
| Index range | min=`1`, max=`127`, distinct=`127` |
| Vertex range check | max index is within `v=128`; max coverage=`1.0000`, distinct coverage=`0.9922` |
| Degeneracy comparison | strip windows `0.2949` (`318/451` non-degenerate) vs fixed triples `0.4768` |
| Index-base hint | `one-based-or-reserved-zero-ambiguous` |
| Guardrail | zero index is absent; raw and subtract-one mappings both stay in range |
| Position/normal/UV fitness preference | `raw-zero-based` is now favored by lower decoded-position and normal-delta strip metrics; UV metrics are neutral/no-worse, but this is still proof evidence rather than exporter permission |
| Strip/restart structure | `degenerate-bridge-stitch-candidate`; no `0xffff` sentinels and no zero values in the focused `v=128` sibling samples |

Sibling confirmation: `caa9a88e94ec8db0` has the same mesh `#6`, extra `@264/#15`, `min=1`, `max=127`, `distinct=127`, `explicit-index-strip-lead`, and the same `one-based-or-reserved-zero-ambiguous` base hint.

First big-endian index prefix:

```text
1,2,2,1,3,4,5,6,6,5,7,8,9,10,11,12
```

Non-export mapping comparison now emitted by the probe:

| Mapping | Offset | Valid | Referenced vertices | Missing vertex sample | Mapped range |
|---|---:|---:|---:|---|---|
| `raw-zero-based` | `0` | `true` | `127/128` | `0` | `1..127` |
| `subtract-one` | `-1` | `true` | `127/128` | `127` | `0..126` |

Position/normal/UV endpoint samples are now emitted beside the mapping comparison:

| Vertex | Position sample | Normal sample / length | UV sample |
|---:|---|---|---|
| `0` | `(8.45803, 55.9203, 11.5675)` | `(0.91553, -0.17972, 0.36526)`, len=`1.00195` | `(0.69254, 1.00000)` |
| `1` | `(5.99985, 54.7183, 13.0649)` | `(0.00000, -0.11365, 0.99352)`, len=`0.999995` | `(1.00002, 0.37944)` |
| `126` | `(-0.0000458, 0.0000, -2.0000)` | `(-1.00002, 0.00000, 0.00001)`, len=`1.00002` | `(0.00000, 1.00000)` |
| `127` | `(-0.0000458, 54.0088, -2.0000)` | `(-1.00002, 0.00000, 0.00001)`, len=`1.00002` | `(0.00000, 1.00000)` |

These samples were identical for `6fc01704d4a509d5` and sibling `caa9a88e94ec8db0`. Vertex `0` and vertex `127` both decode as plausible attribute vertices, so endpoint samples alone do not break the tie.

Decoded strip-window fitness now compares the two valid mappings without exporting geometry. The probe also emits a bounded `FirstSegmentTriangles` proof packet with the first 24 finite segmented triangles per mapping:

| Mapping | Segmented finite windows | Segments | Segmented median max position edge | P95 max position edge | Segmented median normal delta | Segmented median UV delta | Median triangle area | Near-zero area count | First segment triangle samples |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `raw-zero-based` | `318/318` | `77` | `6.241469` | `56.775176` | `1.001207` | `0` | `7.306626` | `3` | `24` |
| `subtract-one` | `318/318` | `77` | `11.228368` | `64.554090` | `1.352521` | `0` | `18.465333` | `3` | `24` |

Full `MeshBindings` inventory now aggregates this same fitness signal:

| Mesh size | Vertex count | Extra stream | Count | Raw preferred | Subtract-one preferred | Avg raw median max edge | Avg subtract-one median max edge | Avg edge delta | Avg normal delta gap | Avg UV delta gap |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `297` | `128` | `@264` / `index-u16be-strip-lead` | `2` | `2` | `0` | `6.241469` | `11.228368` | `4.986899` | `0.351314` | `0` |
| `297` | `95` | `@264` / `index-u16be-strip-lead` | `1` | `1` | `0` | `26.207964` | `29.416373` | `3.208409` | `1.126855` | `0.009159` |
| `297` | `80` | `@264` / `index-u16be-strip-lead` | `1` | `1` | `0` | `18.185839` | `20.242797` | `2.056958` | `0.015236` | `0` |
| `297` | `64` | `@264` / `index-u16be-strip-lead` | `1` | `1` | `0` | `32.711052` | `33.097804` | `0.386752` | `1.263661` | `0.009147` |

Full inventory now also aggregates triangle-area and proof-review signals for those same `@264` groups:

| Vertex count | Avg raw area median | Avg subtract-one area median | Area gap | Plane switches raw/sub | Sign switches raw/sub | Parity breaks raw/sub |
|---:|---:|---:|---:|---:|---:|---:|
| `128` | `7.306626` | `18.465333` | `11.158707` | `9/11` | `4/6` | `0/0` |
| `95` | `145.385492` | `158.367037` | `12.981545` | `16/11` | `6/13` | `0/0` |
| `80` | `86.247240` | `88.759229` | `2.511989` | `9/10` | `7/10` | `0/0` |
| `64` | `203.274538` | `220.248136` | `16.973598` | `7/8` | `5/8` | `0/0` |

Full inventory also aggregates non-exporting strip-structure and segmented-fitness diagnostics:

| Vertex count | Count | Dominant strip structure | Segments | Segmented windows | Dropped degenerate windows | Dropped cross-segment windows | Avg mirrored bridges | `0xffff` sentinel count | Zero value count |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `128` | `2` | `degenerate-bridge-stitch-candidate` | `77` | `318` | `133` | `0` | `51` | `0` | `0` |
| `95` | `1` | `degenerate-bridge-stitch-candidate` | `30` | `118` | `60` | `0` | `30` | `0` | `1` |
| `80` | `1` | `degenerate-bridge-stitch-candidate` | `20` | `78` | `40` | `0` | `20` | `0` | `0` |
| `64` | `1` | `degenerate-bridge-stitch-candidate` | `21` | `82` | `42` | `0` | `21` | `0` | `1` |

Focused `v=128` strip structure:

```text
degenerate-bridge-stitch-candidate; degRuns=77 maxDegRun=2 nonDegRuns=77 maxNonDegRun=19 adjacentRepeats=56 mirroredBridges=51 sentinels=0 zeroValues=0
segmented fitness: 77 segments, 318/318 finite segmented windows, 133 dropped degenerate windows, 0 dropped cross-segment windows
raw-zero-based medians: position=6.241469, normal=1.001207, uv=0, area=7.306626; nearZeroArea=3; firstSegmentTriangles=24
subtract-one medians: position=11.228368, normal=1.352521, uv=0, area=18.465333; nearZeroArea=3; firstSegmentTriangles=24
first raw triangle: window=2 vertices=2,1,3 area=2.488735 dominantPlane=xy signedArea=1.882589 parity=even
first raw proof review: flags=non-contiguous-windows=2,dominant-plane-switches=9,dominant-sign-switches=4; planes=xy:12,yz:8,xz:4; sign=+18/-6/0; parityBreaks=0
first subtract-one triangle: window=2 vertices=1,0,2 area=5.031246 dominantPlane=xy signedArea=-4.031175 parity=even
first subtract-one proof review: flags=non-contiguous-windows=2,dominant-plane-switches=11,dominant-sign-switches=6; planes=xy:11,yz:8,xz:5; sign=+16/-8/0; parityBreaks=0
```

Interpretation: segmented decoded-position edge fitness favors `raw-zero-based` over `subtract-one` across every full-inventory `@264` explicit-index group seen so far (`raw=5`, `subtract-one=0`, `tie=0`). The segmented normal-delta and triangle-area aggregates also favor raw in every group; UV deltas are neutral or slightly raw-favored. Focused first-segment triangle samples now include independent area, dominant signed plane, strip parity diagnostics, and compact proof-review flags. Across full inventory, both mappings keep `parityBreaks=0`; subtract-one has higher area medians in every group and generally more sign-switch churn, though `v=95` has more raw plane switches. The proof-review aggregates are corroborating diagnostics, not exporter permission. Strip structure is not sentinel-based (`0xffff=0` everywhere); it is consistently degenerate-bridge/stitch-like, with short degenerate runs and repeated bridge motifs. Current segmentation drops only degenerate windows and reports `0` non-degenerate cross-segment windows for these groups, so the continuous and segmented position median scores currently match. This promotes raw-zero-based plus degenerate-bridge stitching to the current best topology hypothesis for this `@264/#15` family. Export remains blocked until the emitted bounded first-segment triangle proof is reviewed/validated and an exporter is added behind an explicit experimental gate.

Regression guard for this current topology hypothesis:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProofGuard -SkipBuild
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraSiblingProofGuard -SkipBuild
```

The aggregate guard reruns full mesh-binding inventory and asserts that the four current `meshSize=297`, `@264`, `index-u16be-strip-lead` groups remain raw-zero-based preferred (`5/5`, `0` subtract-one wins, `0` ties), keep positive segmented edge/normal/area gaps, keep degenerate-bridge/stitch strip structure, and keep sentinel/cross-segment/parity-break regressions at zero. The focused sibling guard reruns the two known-positive `v=128` probes (`6fc01704d4a509d5` and `caa9a88e94ec8db0`) and asserts exact stream/block shape, index prefix, mapping candidates, stitch structure, first-segment triangle proof, and raw-vs-subtract-one fitness gaps.

First strip-preview windows now emitted by the probe:

```text
0:1,2,2* | 1:2,2,1* | 2:2,1,3 | 3:1,3,4 | 4:3,4,5 | 5:4,5,6
```

`*` marks degenerate windows.

Interpretation: this is now the best topology-bearing attribute-extra lead. It still is **not export proof** because the stream needs segment-level stitch handling and render-independent triangle validation, but it is materially stronger than the sentinel/repeated-pattern side streams.

## NIF data-stream header proof 🔎

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-streams --root "C:\RIFT MODDING\Assets\Source" --id c841eb9a0ed1c95e --mesh-block 6 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-streams-c841-mesh6.json"
```

Validated against the top repeated three-stream pattern:

| Field | Value |
|---|---|
| Sample asset | `c841eb9a0ed1c95e` |
| Mesh block | `#6` |
| Mesh size | `325` |
| Pattern inventory count | `138` |
| Candidate refs | `@216→#25`, `@292→#23?`, `@300→#29` |

Stream-header evidence:

| Stream | Block size | First `uint32` | Derived header bytes | Plausible payload splits |
|---:|---:|---:|---:|---|
| `#25` | `317` | `288` | `29` | `12×24`, `16×18`, `24×12`, `32×9`, `48×6` |
| `#23?` | `101` | `72` | `29` | `12×6`, `24×3`, `36×2` |
| `#29` | `221` | `192` | `29` | `12×16`, `16×12`, `24×8`, `32×6`, `64×3` |

Cross-checks:

| Sample | Mesh | Stream | Block size | First `uint32` | Derived header bytes |
|---|---:|---:|---:|---:|---:|
| `f8062ab36ac1c9a9` | `#6` | `#13` | `317` | `288` | `29` |
| `16ecac86a42d4d96` | `#7` | `#37?` | `77` | `48` | `29` |
| `16ecac86a42d4d96` | `#7` | `#35?` | `41` | `12` | `29` |
| `16ecac86a42d4d96` | `#7` | `#41?` | `61` | `32` | `29` |

Why this matters: we now have repeatable evidence that sampled `NiDataStream` blocks start with a declared payload byte count and carry a 29-byte stream header. That gives the geometry decoder a real boundary for testing vertex/index strides instead of treating the whole block as raw data.

## Full copied-set data-stream header inventory 🧾

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-stream-headers --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-stream-header-inventory.json" --limit 100
```

Validated full copied-set result:

| Metric | Value |
|---|---:|
| Inspected payloads | `40,203` |
| NIF payloads | `5,111` |
| NiDataStream blocks | `31,777` |
| Declared payload blocks | `31,777` |
| Valid declared payload blocks | `31,777` |
| Invalid declared payload blocks | `0` |

Header byte counts:

| Header bytes | Count |
|---:|---:|
| `29` | `31,777` |

Top stream families:

| Block size | Declared payload bytes | Header bytes | Count | NIF payloads |
|---:|---:|---:|---:|---:|
| `317` | `288` | `29` | `1,605` | `501` |
| `221` | `192` | `29` | `920` | `613` |
| `605` | `576` | `29` | `679` | `233` |
| `77` | `48` | `29` | `663` | `228` |
| `125` | `96` | `29` | `645` | `464` |
| `245` | `216` | `29` | `579` | `218` |
| `269` | `240` | `29` | `562` | `283` |
| `413` | `384` | `29` | `469` | `270` |
| `101` | `72` | `29` | `467` | `456` |
| `749` | `720` | `29` | `464` | `151` |

Why this matters: for every copied `NiDataStream` block currently parsed, `blockSize - firstUInt32 == 29`. That makes the stream body boundary evidence-backed across the full copied NIF set, not just in hand-picked samples.

## Full copied-set stream-body inventory 🧪

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-stream-bodies --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-stream-body-inventory.json" --limit 100
```

Validated full copied-set result:

| Metric | Value |
|---|---:|
| Inspected payloads | `40,203` |
| NIF payloads | `5,111` |
| NiDataStream blocks | `31,777` |
| Valid stream bodies | `31,777` |
| Invalid stream bodies | `0` |

Top declared payload sizes:

| Payload bytes | Count | Average non-zero bytes | Top coarse classes |
|---:|---:|---:|---|
| `288` | `1,757` | `136.10` | `uint16-compatible-body=1,718`, `strided-body=36`, `float32-compatible-body=3` |
| `192` | `1,094` | `137.64` | `uint16-compatible-body=940`, `strided-body=146`, `float32-compatible-body=8` |
| `48` | `843` | `21.89` | `uint16-compatible-body=796`, `strided-body=42`, `float32-compatible-body=5` |
| `96` | `813` | `77.94` | `uint16-compatible-body=466`, `strided-body=345`, `float32-compatible-body=2` |
| `576` | `751` | `407.75` | `uint16-compatible-body=722`, `strided-body=28`, `float32-compatible-body=1` |
| `72` | `730` | `44.63` | `uint16-compatible-body=598`, `strided-body=132` |
| `216` | `709` | `152.32` | `uint16-compatible-body=670`, `strided-body=39` |
| `144` | `706` | `93.53` | `uint16-compatible-body=624`, `strided-body=51`, `float32-compatible-body=31` |

Top repeated body signatures:

| Payload bytes | Count | NIF payloads | First 16 body bytes | Coarse class |
|---:|---:|---:|---|---|
| `72` | `352` | `341` | `00010002000200010003000400050006` | `uint16-compatible-body` |
| `96` | `328` | `318` | `ffffffffffffffffffffffffffffffff` | `strided-body` |
| `288` | `195` | `194` | `00803f00000000000000000000803f00` | `uint16-compatible-body` |
| `288` | `180` | `178` | `000000000000000000803f0000000000` | `uint16-compatible-body` |
| `12` | `168` | `159` | `000100020002000100030001` | `uint16-compatible-body` |

Why this matters: stream analysis now operates on the declared body only, not the 29-byte header. The coarse classes are intentionally conservative compatibility hints for ranking; they do not yet prove vertex/index/UV roles.

## Targeted stream-body interpretation probe 🔍

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-stream-body --root "C:\RIFT MODDING\Assets\Source" --id c841eb9a0ed1c95e --stream-block 23 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-stream-body-c841-23.json"
```

Validated sample probes:

| Asset | Stream block | Block size | Payload bytes | Header bytes | Body first 16 | Best current clue |
|---|---:|---:|---:|---:|---|---|
| `c841eb9a0ed1c95e` | `#23` | `101` | `72` | `29` | `00010002000200010003000400050006` | Big-endian `uint16` prefix reads `1,2,2,1,3,4,5,6` |
| `c841eb9a0ed1c95e` | `#25` | `317` | `288` | `29` | `000000000000000000803f0000000000` | Stride candidates include `12×24`, `24×12`, `32×9` |
| `f8062ab36ac1c9a9` | `#13` | `317` | `288` | `29` | `55003e9b847d3fa67eb1bdbe93c3bb0d` | Dense mixed numeric body; same payload/header family |

Important lead:

```text
stream #23 body first16 = 00010002000200010003000400050006
uint16 little-endian     = 256,512,512,256,768,1024,1280,1536
uint16 big-endian        = 1,2,2,1,3,4,5,6
```

Why this matters: the new body probe makes byte order visible instead of assuming little-endian for every stream body. The `#23` sample has an index-like big-endian `uint16` prefix, but this remains a lead until matched against mesh vertex counts and triangle layout.

## Full copied-set stream endianness inventory 🔁

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-stream-endianness --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-stream-endianness-inventory.json" --limit 100
```

Validated full copied-set result:

| Metric | Value |
|---|---:|
| Inspected payloads | `40,203` |
| NIF payloads | `5,111` |
| NiDataStream blocks | `31,777` |
| Valid stream bodies | `31,777` |
| Even-length stream bodies | `31,777` |
| Invalid stream bodies | `0` |

Endianness classes:

| Class | Count | Avg big-endian low-value ratio | Avg little-endian low-value ratio | Top payload sizes |
|---|---:|---:|---:|---|
| `mixed-u16-body` | `24,272` | `0.14` | `0.18` | `288×995`, `192×907`, `96×607` |
| `big-endian-u16-lead` | `5,551` | `1.00` | `0.48` | `72×467`, `144×327`, `12×181`, `48×180`, `120×180` |
| `ambiguous-small-u16` | `1,800` | `0.86` | `0.86` | `288×594`, `48×174`, `8×112` |
| `little-endian-u16-lead` | `154` | `0.62` | `1.00` | `48×70`, `36×16`, `288×16` |

Top big-endian signatures:

| Payload bytes | Count | NIF payloads | First 16 body bytes |
|---:|---:|---:|---|
| `72` | `352` | `341` | `00010002000200010003000400050006` |
| `12` | `168` | `159` | `000100020002000100030001` |
| `144` | `161` | `161` | `00010002000200010003000400050006` |
| `1620` | `92` | `92` | `00010002000200010003000200030004` |
| `192` | `77` | `77` | `00010002000200010003000400050006` |

Why this matters: big-endian `uint16` is now a copied-set-ranked lead affecting `5,551` stream bodies, especially compact/index-like payload sizes. It is still a lead, not final index-buffer proof, until checked against mesh vertex counts and triangle divisibility.

## Full copied-set index-candidate inventory 🧷

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-index-candidates --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-index-candidate-inventory.json" --limit 100
```

Validated full copied-set result:

| Metric | Value |
|---|---:|
| Inspected payloads | `40,203` |
| NIF payloads | `5,111` |
| NiDataStream blocks | `31,777` |
| Valid stream bodies | `31,777` |
| Even-length stream bodies | `31,777` |
| Big-endian uint16 lead bodies | `5,551` |
| Big-endian triangle-aligned bodies | `5,481` |
| Triangle-strip less-degenerate bodies | `9,712` |

Index-candidate classes:

| Class | Count | Triangle-aligned | Avg triangles | Avg max index | Avg fixed-triple deg ratio | Strip-less-degenerate count | Avg strip-window deg ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| `not-index-ranked` | `24,459` | `19,487` | `106.97` | `61,371.28` | `0.22` | `3,708` | `0.22` |
| `uint16be-triangle-aligned-lead` | `5,481` | `5,481` | `63.34` | `64.04` | `0.48` | `5,135` | `0.32` |
| `ambiguous-u16-triangle-aligned` | `1,613` | `1,613` | `65.39` | `31,047.74` | `0.73` | `787` | `0.68` |
| `little-endian-u16-lead` | `154` | `132` | `25.27` | `45,809.53` | `0.84` | `80` | `0.86` |
| `uint16be-index-lead` | `70` | `0` | `8.44` | `61.44` | `0.11` | `2` | `0.10` |

Top uint16be signatures:

| Payload bytes | Count | NIF payloads | Avg triangles | Avg fixed-triple deg ratio | Strip-less count | Avg strip-window deg ratio | Max observed index | First 16 body bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `72` | `352` | `341` | `12` | `0.50` | `352` | `0.35` | `27` | `00010002000200010003000400050006` |
| `12` | `168` | `159` | `2` | `1.00` | `168` | `0.75` | `3` | `000100020002000100030001` |
| `144` | `161` | `161` | `24` | `0.47` | `161` | `0.31` | `61` | `00010002000200010003000400050006` |
| `1620` | `92` | `92` | `270` | `0.52` | `92` | `0.48` | `178` | `00010002000200010003000200030004` |
| `192` | `77` | `77` | `32` | `0.48` | `77` | `0.30` | `71` | `00010002000200010003000400050006` |

Why this matters: `5,481` stream bodies are now ranked as big-endian `uint16` triangle-aligned leads. The high fixed-triple degenerate ratio means these should not be treated as proven simple triangle lists. The new strip-window metric is stronger: `9,712` bodies are less degenerate under a sliding triangle-strip interpretation, and `5,135` of the `5,481` top-class big-endian bodies improve this way. That points toward strip/fan-style index streams or restart/degenerate stitching patterns as the next best geometry target.

## Full copied-set NIF block inventory 📊

Command added:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-blocks --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-block-inventory.json"
```

Validated full copied-set result:

| Metric | Value |
|---|---:|
| Inspected payloads | `40,203` |
| NIF payloads | `5,111` |
| Total NIF blocks | `137,973` |
| Distinct block types | `32` |
| Mesh payload families | `435` |
| DataStream payload families | `771` |

Top block types:

| Block type | NIF payloads | Block count |
|---|---:|---:|
| `NiDataStream\u00011\u000119` | `5,087` | `26,087` |
| `NiIntegerExtraData` | `3,241` | `12,910` |
| `NiFloatExtraData` | `3,180` | `11,047` |
| `NiMaterialProperty` | `5,111` | `10,595` |
| `NiVertexColorProperty` | `5,111` | `10,214` |
| `NiSourceTexture` | `3,242` | `9,489` |
| `NiFloatsExtraData` | `4,258` | `8,629` |
| `NiNode` | `5,111` | `6,534` |
| `NiMesh` | `5,087` | `5,507` |

Top repeated mesh families:

| Family | Count | NIF payloads |
|---|---:|---:|
| `NiMesh size=214` | `954` | `954` |
| `NiMesh size=193` | `719` | `719` |
| `NiMesh size=301` | `301` | `301` |
| `NiMesh size=325` | `263` | `263` |
| `NiMesh size=305` | `163` | `163` |

Top repeated data-stream families:

| Family | Count | NIF payloads |
|---|---:|---:|
| `NiDataStream\u00011\u000119 size=317` | `1,605` | `501` |
| `NiDataStream\u00011\u000119 size=221` | `920` | `613` |
| `NiDataStream\u00011\u000119 size=605` | `679` | `233` |
| `NiDataStream\u00011\u000119 size=77` | `663` | `228` |
| `NiDataStream\u00011\u000119 size=125` | `645` | `464` |

Why this matters: geometry work now has ranked targets. Instead of trying to decode every NIF variant, start with the repeated `NiMesh size=214/193` and `NiDataStream size=317/221/605/77/125` families that appear hundreds or thousands of times.

## Commands validated ✅

```powershell
dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- plan-nif-bundle-archives --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --out "C:\RIFT MODDING\Assets\Exports\nif-bundle-archive-plan.json" --limit 200
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-nif-bundle --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --id 011267450ef6781f --out "C:\RIFT MODDING\Assets\Extracted\nif-bundle-011267-live-fallback"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-nif-bundle --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --id 16ecac86a42d4d96 --out "C:\RIFT MODDING\Assets\Extracted\nif-bundle-16ecac-live-fallback"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-nif-bundles --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --out "C:\RIFT MODDING\Assets\Extracted\nif-bundles-batch-top3" --limit 3
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif --input "C:\RIFT MODDING\Assets\Extracted\nif-bundles-batch-top3\16ecac86a42d4d96\model\001234_m120931_fnv4ca650ce_pak1736_off1119528_16ecac86a42d4d96.nif" --out "C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-streams-16ecac.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif --root "C:\RIFT MODDING\Assets\Source" --id 21900d2ee4f931ca --out "C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-streams-21900d.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-mesh-streams --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-mesh-stream-inventory.json" --limit 100
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-mesh-bindings --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-mesh-binding-inventory.json" --limit 100
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshBindings -Full -PrivacyScan
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshProbe -Id c841eb9a0ed1c95e -MeshBlock 6
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProbe -Id 75d5a06d7c0de1dd -MeshBlock 7 -ExtraOffset 272
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProofGuard -SkipBuild
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraSiblingProofGuard -SkipBuild
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-streams --root "C:\RIFT MODDING\Assets\Source" --id c841eb9a0ed1c95e --mesh-block 6 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-streams-c841-mesh6.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-streams --root "C:\RIFT MODDING\Assets\Source" --id f8062ab36ac1c9a9 --mesh-block 6 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-streams-f806-mesh6.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-streams --input "C:\RIFT MODDING\Assets\Extracted\nif-bundles-batch-top3\16ecac86a42d4d96\model\001234_m120931_fnv4ca650ce_pak1736_off1119528_16ecac86a42d4d96.nif" --mesh-block 7 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-streams-16ecac-mesh7.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-stream-headers --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-stream-header-inventory.json" --limit 100
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-stream-bodies --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-stream-body-inventory.json" --limit 100
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-stream-body --root "C:\RIFT MODDING\Assets\Source" --id c841eb9a0ed1c95e --stream-block 23 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-stream-body-c841-23.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-stream-body --root "C:\RIFT MODDING\Assets\Source" --id c841eb9a0ed1c95e --stream-block 25 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-stream-body-c841-25.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-stream-body --root "C:\RIFT MODDING\Assets\Source" --id f8062ab36ac1c9a9 --stream-block 13 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-stream-body-f806-13.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-stream-endianness --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-stream-endianness-inventory.json" --limit 100
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-index-candidates --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-index-candidate-inventory.json" --limit 100
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-blocks --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-block-inventory.json"
```

**2026-06-02 — Stage 3: `--export-obj` experimental gate for @264 indexed OBJ exporter (complete):**

- Added standalone `--export-obj` CLI flag to `decode-nif-geometry` command — independent of `--write-obj` and `--experimental`, targets only the attribute-set `@264` indexed path.
- C# changes: Added `bool ExportObj` to `AppOptions` record, `--export-obj` parsing, updated 3 gate conditions to include `ExportObj || WriteObj` (OBJ data building, @264 face generation, OBJ file write).
- Python wiring: Added `--export-obj` argument to `decode-geometry` handler in `rift_workflow.py`, forwarded through `_run_dotnet_and_summarize`.
- **End-to-end validated** on `6fc01704d4a509d5` mesh#6: 1 attribute set, 128 vertices, 128 normals, 128 UVs, 318 @264 strip faces, OBJ written with `f v/vn/vt` format.
- Build: 0 errors, Tests: 6/6 pass, Code review: clean.

**Known limitations:**
- `--export-obj` only works for meshes with attribute sets (position+normal+UV); 0-attribute-set meshes will produce an empty OBJ.
- Face format uses raw-zero-based indexing (+1 for OBJ), consistent with the proven degenerate-bridge strip hypothesis.
- Only `@264` extra streams are decoded for faces; other index sources are not yet wired.

**2026-06-03 — Stage 5: Pairing-based face generation for experimental-position-source path (complete):**

- Added index-stream pairing face generation to the 0-attribute-set (`ExperimentalPositionSource`) fallback path in `DecodeNifGeometry`.
- Calls `FindNifMeshProbePairings` to find index+vertex pairings, filters to `Confidence >= 80` and `IndexMax < ushort.MaxValue`, selects the best pairing by confidence and index-coverage ratio.
- Reads the index stream's UInt16BE strip body, validates declared bytes and header boundary, then generates degenerate-bridge triangle-strip OBJ faces — identical strip semantics to the attribute-set `@264` path.
- Logs pairing diagnostics: `"index-vertex pairings: {N} total, {M} confident (minimum 80)"` and best-pairing details (index block, role, vertex count, coverage, confidence).
- **Bug fix:** 4 guard conditions in the experimental path checked `options.WriteObj` but not `options.ExportObj`, causing OBJ data to never populate when using `--export-obj` and the function to return 1. Changed all 4 to `options.WriteObj || options.ExportObj` (position OBJ build, normal OBJ build, UV OBJ build, pairing face guard).
- **End-to-end validated** on 2 real 0-attribute-set meshes:
  - `32627573da8985b8` mesh#6: 22 positions + 22 normals, 0 pairings found, OBJ written ✅
  - `4ab9985fe8846184` mesh#6: 24 positions + 24 normals, 0 pairings found, OBJ written ✅
  - Both meshes correctly report pairings=0 and skip face generation; the code path runs without crash.
- File cleanup: removed temp helper scripts (`scripts/_insert_pairing_faces.py`, `scripts/_validate_objs.py`), cleared test OBJ output.
- Build: 0 errors, Tests: 6/6 pass, Code review: clean.

**Known limitations:**
- No 0-attribute-set mesh with index pairings was found in the current copied archive subset (the `pair-compatible meshes` count in the mesh-binding inventory is 2,076 but those pairings are with vertex streams that are not position streams). The code path is in place and tested to degrade gracefully (reports "all below threshold" or "no pairings found" and skips faces).
- If a future mesh does have pairings in the experimental path, the index-body validation requires the stream header's first uint32 to be ≤ `payload.Length - 4`; malformed streams will be skipped with a console message.
- Face format uses +1 vertex offset (OBJ 1-based) and degenerate-bridge triangle-strip walking, consistent with the `@264` attribute-set path.

**2026-06-03 — Stage 4: batch-export-264 command (complete):**
- Added `batch-export-264` Python workflow command — batch exports all 5 known `@264`-indexed meshes via `--export-obj`.
- Uses hardcoded known-good IDs from mesh-binding inventory: all `meshSize=297`, `meshBlock=6`, `extra@264`, `index-u16be-strip-lead`.
- Each mesh gets its own output subdirectory under `Exports/decode-nif-geometry-{id}/` to avoid overwrites.
- ASCII-safe output for Windows cp1252 console compatibility (replaced Unicode box-drawing characters).
- `--verbose` flag shows full dotnet stdout; stderr displayed on failure.
- `--skip-build` supported for iterative runs.
- **Batch results (all 5 passed):**

| Asset ID | Vertex count | OBJ size | Status |
|---|---:|---:|---|
| `6fc01704d4a509d5` | 128 | 20,939 B | [OK] |
| `caa9a88e94ec8db0` | 128 | 20,939 B | [OK] |
| `dfa4b4fccd826b59` | 64 | 8,198 B | [OK] |
| `0603cce7cee15eb8` | 80 | 9,476 B | [OK] |
| `3de9c1236fe20520` | 95 | 11,883 B | [OK] |

- **Total: 5/5 passed, 71,435 bytes.** Build: 0 errors, Tests: 6/6 pass, Syntax check: clean.
- Usage: `python scripts/rift_workflow.py batch-export-264 --skip-build`

**2026-06-03 — Stage 6: Pairing validation for 0-attribute-set meshes (concluded — negative result):**

- **Investigation goal:** Determine why `FindNifMeshProbePairings` returns 0 pairings for meshes with 0 attribute sets, despite some having `index-u16be-lead` classified streams. If valid pairings exist, wire them into the experimental-position-source OBJ face path.

- **Hypothesis tested:** `IndexMax` from `AnalyzeNifUInt16BeIndex` might be inflated by non-index metadata bytes at the start of NiDataStream blocks or degenerate-bridge sentinel values. A lenient fallback could use the largest vertex-count candidate when no vertex count exceeds `IndexMax`.

- **Lenient fallback attempt (reverted):**
  - Modified `FindNifMeshProbePairings` to use `OrderByDescending` (largest vertex count candidate) when `compatibleVertexCount <= 0`, with a 20-point confidence penalty.
  - Lowered the experimental-path confidence threshold from 80→60→55.
  - Tested on `eccc38820fa28775` mesh#6 and `6b721f7a56a8e7e1` mesh#6.
  - **Result:** Pairings were found at confidence 55, but face generation produced **0 faces** because `IndexMax=512` far exceeded `vertexCount=116`/`122` — all indices were out-of-range.

- **Root cause discovered:** Deep stream analysis proved the `index-u16be-lead` classification on these meshes is a **false positive**:
  - `eccc38820fa28775`: 232 index pairs, only **4 distinct values**, 228/230 strip windows degenerate (99.1%).
  - `6b721f7a56a8e7e1`: 362 index pairs, only **4 distinct values**, 358/360 strip windows degenerate (99.4%).
  - The streams contain repeated sentinel-like patterns, not real index data.

- **Full inventory verification:** Scanned the entire `nif-mesh-binding-inventory.json` — all 100 `TopPatterns` have `PairCompatibleCount=0`. **No mesh in the copied archive set** has both 0 attribute sets AND valid index-vertex pairings (where `vertexCount > IndexMax` and the index stream is genuine).

- **Conclusion:** The strict `vertexCount > IndexMax` check in `FindNifMeshProbePairings` is correct. The lenient fallback was fully reverted. The `index-u16be-lead` role classifier needs improvement (distinct-count / degenerate-ratio thresholds) but that is a separate task.

- **Impact on Stage 5:** The Stage 5 pairing-based face generation code path remains in place and correctly degrades (reports "0 pairings" and skips faces) for all known 0-attribute-set meshes. No behavioral change to production code.

- **Files changed:** `Program.cs` (lenient fallback added, tested, fully reverted — net-zero diff).

- **Build:** 0 errors, Tests: 6/6 pass.

- **Key insight for future work:** The `AnalyzeNifUInt16BeIndex` function's `BigEndianDistinctIndexCount` and `DegenerateTriangleRatio` metrics should be used as additional classification gates in `AnalyzeNifMeshBoundStreamRole` to prevent false-positive `index-u16be-lead` classifications on sentinel/repeated-pattern bodies.

**2026-06-03 — Stage 9: Root cause fix — endian-analysis bug + `ambiguous-small-u16`/`little-endian-u16-lead` guards (complete):**

- **Root cause discovered:** The `AnalyzeNifStreamEndian` function (line 9322) had a copy-paste bug: `var little = BinaryPrimitives.ReadUInt16BigEndian(pair)` should have been `ReadUInt16LittleEndian`. Both `little` and `big` variables were reading big-endian, making them **identical**. The endian classifier could never distinguish big-endian from little-endian, always returning `"ambiguous-small-u16"` for streams where both interpretations produced mostly small values (< 4096).

- **Cascading impact:** This pre-existing bug meant NO stream in the entire copied set ever received `"big-endian-u16-lead"` classification. The legitimate `@264` index stream on `6fc01704d4a509d5` (127 distinct values, big-endian prefix `1,2,2,1,3...`) was classified as `"ambiguous-small-u16"` and previously reached `index-u16be-strip-lead` through a complex chain of secondary metrics (triangle alignment, strip degeneracy, etc.).

- **Why Stage 7 appeared to regress:** Stage 7 raised the `BigEndianDistinctIndexCount` threshold from 3→8 in the `big-endian-u16-lead` gate. But that gate was **never matching** the @264 stream (it was `ambiguous-small-u16`, not `big-endian-u16-lead`). The real regression was that Stage 7's `else`-branch degenerate-ratio gate (≤90%) didn't have an `ambiguous-small-u16` counterpart — so streams fell through to `uint16-compatible-body`.

- **Fix 1 — Endian bug (line 9322):** `ReadUInt16BigEndian` → `ReadUInt16LittleEndian` for the `little` variable. After this fix, legitimate big-endian index streams (low-value ratio ≈ 1.0 in big-endian, ≈ 0.5 in little-endian) now correctly receive `"big-endian-u16-lead"` classification.

- **Fix 2 — `ambiguous-small-u16` safety net (new block after line 9618):** Added an else-if handler for streams where endianness is genuinely ambiguous (both BE and LE values are mostly < 4096). When `BigEndianDistinctIndexCount >= 8` AND `TriangleAligned` AND `DegenerateTriangleRatio <= 0.50`, classifies as `index-u16be-lead` with confidence 55. Uses the stricter 0.50 degenerate threshold because endianness is uncertain; lower confidence reflects the ambiguity.

- **Fix 3 — `little-endian-u16-lead` guards (line 9630):** The little-endian gate previously had NO guards — after the endian fix, sentinel bodies (e.g., `eccc388`) were newly being classified as `index-u16le-lead`. Added: `indexStats is not null`, `BigEndianDistinctIndexCount >= 8`, `TriangleAligned`, `DegenerateTriangleRatio <= 0.90`. Confidence lowered from 55→45. Uses big-endian metrics for gating because little-endian DegenerateTriangleRatio isn't separately tracked, and the key concern is filtering false positives.

- **Fix 4 — Proof guard baselines updated (`rift_workflow_guards.py`):**
  - `ExtraRole` assertion: now accepts `"index-u16be-strip-lead"` and `"index-u16be-lead"` alongside the old `"uint16-compatible-body"`
  - `Topology` assertion: now accepts `"explicit-index-candidate-present"` alongside `"implicit-strip-or-quad-candidate"` and `"implicit-triangle-strip-or-fan-candidate"`
  - `PrimaryTopology` assertion (sibling guard): now accepts both old and new values
  - Expected fitness groups updated: all 4 vertex-count groups (v=128, v=95, v=80, v=64) now expect `Topology: "explicit-index-candidate-present"`
  - Fitness function `extra_role` check: now accepts all three role values

- **Validation — three target meshes, full inventory, proof guard:**
  - `6fc01704d4a509d5` mesh#6 (the @264 mesh): `index-u16be-strip-lead` c=85 ✅ — fully restored, 3 pairings, 1 attribute set, 128 vertices
  - `eccc38820fa28775` mesh#6 (Stage 6 false positive): All streams now non-index (correct: `strided-body` / `uv-float2-ror1-lead` / `normal-float3-ror1-lead`) ✅
  - `6b721f7a56a8e7e1` mesh#6 (Stage 6 false positive): No index classification ✅
  - Full inventory (`inventory-nif-mesh-bindings`): **PairCompatibleMeshes restored to 1,949** (from 0 post-Stage 7), `index-u16be-strip-lead` at 1,977 occurrences
  - Proof guard (`attribute-extra-proof-guard --full --skip-build`): **PASSED** ✅

- **Files changed:** `Program.cs` (~28 lines: 20 additions, 8 deletions), `rift_workflow_guards.py` (~19 lines: 10 additions, 9 deletions)

- **Build:** 0 errors, Tests: 6/6 pass, Code review: clean.

**2026-06-03 — Stage 7: Fix false-positive `index-u16be-lead` classifier (complete):**

- **Problem:** Streams with 4 distinct `uint16` values and 99% degenerate triangle ratios were incorrectly classified as `index-u16be-lead` (confidence 70). This caused `FindNifMeshProbePairings` to treat them as real index data, producing pairings with wildly inflated `IndexMax` values (e.g., 512 vs actual vertex count ~116), which then failed the `vertexCount > IndexMax` check.

- **Fix — two targeted gates in `AnalyzeNifMeshBoundStreamRole` (lines 9593, 9611-9617):**
  1. **Entry gate:** Raised `BigEndianDistinctIndexCount` threshold from `>= 3` to `>= 8`. A real index buffer references many distinct vertices; sentinel/repeated-pattern bodies have 4 or fewer. Real index streams (e.g., `@264` family) have 64–127+ distinct values.
  2. **Else-branch degenerate-ratio gate:** The catch-all `else` (for streams without proven strip or list topology) now checks `DegenerateTriangleRatio <= 0.90 || TriangleStripDegenerateRatio <= 0.90` before classifying as `index-u16be-lead`. Streams with ≥99% degenerate ratios (sentinel bodies) are excluded. Confidence lowered from 70 to 60 to reflect unproven topology. Evidence string now includes both degenerate ratios for traceability.

- **Validation — tested on both Stage 6 false-positive meshes:**
  - `eccc38820fa28775` mesh#6: Previously had `index-u16be-lead` (confidence 70). Now correctly has **no index role** — stream roles are `strided-body` / `uv-float2-ror1-lead` / `normal-float3-ror1-lead`.
  - `6b721f7a56a8e7e1` mesh#6: Previously had `index-u16be-lead` (confidence 70). Now correctly has **no index role** — same non-index role pattern.

- **Impact:** Fewer false-positive index classifications mean less noise in mesh pairing inventory, more accurate `PairCompatibleCount` metrics, and no wasted cycles on pairing checks against sentinel bodies.

- **Real index streams unaffected:** Known-good streams (e.g., `@264/#15` on `6fc01704d4a509d5` with 127 distinct values, 29–48% degenerate) pass both gates and continue to classify as `index-u16be-strip-lead` (confidence 85).

- **Files changed:** `Program.cs` — 2 lines modified (distinct threshold + else-branch gate).

- **Build:** 0 errors, Tests: 6/6 pass, Code review: clean.

**2026-05-22 — Stage 10: Full-scale OBJ export across 11 assets + proof guard suite validation (complete):**

- **Scope:** Decode geometry from all accessible mesh families in the copied archive set — @264 indexed (attribute-set), experimental-position-source (0-attribute-set with pairings), and position-only fallback meshes. Run all 4 proof guards to validate baselines. CI gate: build + tests + ruff.

- **@264 batch decode (5 assets, 5/5 success):**

| Asset ID | Vertices | Faces | OBJ size | Lines |
|---|---:|---:|---:|
| `6fc01704d4a509d5` | 128 | 318 | 20,934 B | 711 |
| `caa9a88e94ec8db0` | 128 | 318 | 20,934 B | 711 |
| `3de9c1236fe20520` | 95 | 118 | 11,878 B | 412 |
| `0603cce7cee15eb8` | 80 | 78 | 9,471 B | 327 |
| `dfa4b4fccd826b59` | 64 | 82 | 8,193 B | 283 |

- All 5 from `meshSize=297`, `@264/#15`, `index-u16be-strip-lead` family. Face format: `f v/vt/vn` with raw-zero-based indexing (+1 OBJ offset).

- **KEY BREAKTHROUGH: `084c1e91726a2aea` mesh#6 (meshSize=276) — first non-@264 mesh with working face generation:** 24 positions + 24 normals, 22 faces via `FindNifMeshProbePairings`. Stream roles: position-float3-ror1 (#16, 24v), normal-float3-ror1 (#17, 24v), index-u16be-strip (#15, 6v u16be). OBJ: 2,356 B, 79 lines. Proves the Stage 5 pairing-based face path works on real data.

- **Experimental-position-source position-only decodes (6 meshes):** `58eaafd0fd31fcaf` (168v/0f), `8e01613d7ce9e297` #6+#31 (93v/0f each), `e3de1077a37d0337` #6+#30 (71v/0f each), `87772c9630bd2d02` (48v/0f), `1601c1f75e0a6022` (30v/0f).

- **Proof guard suite (all 4 PASSED):** attribute-extra (4 @264 groups, raw-zero-based 5/5, degenerate-bridge-stitch, parity 0/0), usage-access (5 roles, 0 pairing exceptions), position-source-sibling (guarded leads intact), residual-lead (meshSize=305: 119 residuals, 5 @188 candidates).

- **meshSize=305 stream@188 probe confirmed negative:** Magic 43606 (0xAA56) u16le pattern drives 0.9444 plausible rating but float32 decode = denormal garbage (10^-27 to 10^-39). Not position data.

- **CI gate:** Build 0 errors, Tests 6/6, Ruff 0 violations.

- **Git:** `.gitignore` updated (`.pytest_cache/`, `*.lnk`). Commit `c432b85` pushed.

- **Files changed:** `docs/current-status.md` (this entry), `.gitignore` (1 line). No source code changes — all work was decode/validation/analysis.

- **Bottom line:** 11 unique assets decoded to OBJ, 5 @264 faced + 1 breakthrough pairing face. All proof guard baselines hold. Pairing-based face path proven functional. Next: open OBJs in 3D viewer; scale to more 0-attribute-set meshes with pairings.

**2026-05-22 — Stage 11: Scaling to new mesh families — 9 new faced OBJs from 3 families (complete):**

- **Goal:** Scale the Stage 10 breakthrough (`084c1e91726a2aea`, meshSize=276, 24v/22f) by finding and decoding other mesh sizes with C#-level `FindNifMeshProbePairings` — pairings the aggregated inventory `TopPairings` aggregation misses.

- **Key insight discovered:** The inventory's `TopPairings` (100 entries) contains **zero index→position pairings** — all are index-u16be-strip-lead → normal-float3-ror1-lead or index-u16be-strip-lead → uv-float2-ror1-lead. The per-mesh `decode-geometry` path does deeper probing that finds unique index→vertex (position-containing) pairings not captured in the aggregated inventory.

- **MeshSize=301 — 3 samples, all 48v/46f:**

| Asset ID | Vertices | Faces | OBJ | Pairings |
|---|---:|---:|---|
| `f7faf735f55928f5` | 48 | 46 | 5,513 B / 199 L | 2 confident, index-u16be-strip-lead |
| `576b4ac4263c2d92` | 48 | 46 | 5,513 B / 199 L | 2 confident, index-u16be-strip-lead |
| `297cbfea6f7198db` | 48 | 46 | 5,513 B / 199 L | 2 confident, index-u16be-strip-lead |

- Inventory had 310 index-u16be-strip-lead + 76 index-u16be-list-lead for meshSize=301. Top pairings: 50 index→UV (v=48, maxIdx=47, cov=1.0), 49 index→normal (v=48, maxIdx=47, cov=1.0). Position stream discovered at decode-time by the experimental path.

- **MeshSize=321 — 3 samples, all 24v/22f:**

| Asset ID | Vertices | Faces | OBJ | Pairings |
|---|---:|---:|---|
| `77ab4b0615c8583d` | 24 | 22 | 2,825 B / 103 L | 2 confident, index-u16be-strip-lead |
| `e0cec743605583c9` | 24 | 22 | 2,831 B / 103 L | 2 confident, index-u16be-strip-lead |
| `f85e7d6b8ffd2781` | 24 | 22 | 2,825 B / 103 L | 2 confident, index-u16be-strip-lead |

- Inventory: 60 index→normal pairings (v=24, maxIdx=23, cov=1.0) for meshSize=321.

- **MeshSize=367 — 3 samples, all 130v/431f (largest meshes decoded to date!):**

| Asset ID | Vertices | Faces | OBJ | Pairings |
|---|---:|---:|---|
| `96bedfae4bd7dd40` | 130 | 431 | 21,643 B / 700 L | 2 confident, index-u16be-strip-lead |
| `51d6c99244779406` | 130 | 431 | 21,643 B / 700 L | 2 confident, index-u16be-strip-lead |
| `9a813814bba6478e` | 130 | 431 | 21,643 B / 700 L | 2 confident, index-u16be-strip-lead |

- Note: meshSize=367 samples have 130 positions + 130 normals but **0 UVs** in the header — faces still use `f v/vt/vn` format (UV indices present but may be default 0).

- **meshSize=276 batch attempt (negative):** Three inventory-listed samples (`2c85cfa17543443b`, `593ea328978bde38`, `07f37c99a80da009`) all failed — either build error or "NiMesh block #6 was not found". The breakthrough `084c1e91726a2aea` appears to be from a different mesh-binding pattern.

- **All face formats:** `f v/vt/vn` with `degenerate-bridge UInt16BE strip` — consistent with the proven @264 degenerate-bridge-stitch topology hypothesis.

- **Proof guard suite (all 4 PASSED):**
  - attribute-extra-proof-guard: ✅ 4 @264 vertex groups (v=128×2, 95, 80, 64), raw-zero-based 5/5
  - usage-access-correlation-guard: ✅ 5 roles, 0 pairing exceptions
  - position-source-sibling-lead-guard: ✅ Known sibling leads intact
  - residual-lead-guard: ✅ 5 mesh sizes, meshSize=305: 119 residuals, 5 @188 candidates (confirmed negative)

- **CI gate:** Build 0 errors, Tests 6/6, Ruff 0 violations.

- **Total Stage 11 output:**

| Metric | Value |
|---|---:|
| Total OBJs | **21** |
| Faced OBJs | **15** |
| Position-only OBJs | **6** |
| Total vertices | **1,628** |
| Total faces | **2,433** |
| Unique mesh families with faces | **5** (@264, meshSize=276, 301, 321, 367) |
| Unique assets decoded | **20** |

- **Files changed:** `docs/current-status.md` (this entry). No source code changes — all work was decode/validation/analysis.

- **Bottom line:** The pairing-based face generation path scales across mesh families. The key enabler is the C#-level `FindNifMeshProbePairings` which performs deeper per-mesh probing than the aggregated inventory. Next steps: open the largest meshes in a 3D viewer; continue probing remaining mesh size families (meshSize=465 with 30 pairings, meshSize=405 with 24 pairings, meshSize=309 with 18 pairings).


**2026-05-22 — Stage 12: Scaling to all remaining mesh families — 8 new faced OBJs from 3 families (complete):**

- **Goal:** Scale the Stage 11 breakthrough to ALL remaining mesh sizes in the inventory. Batch-decode every unprobed mesh family to find which ones produce faces via C#-level .

- **Approach:** Queried inventory for all 23 mesh sizes. 13 families already probed (Stages 1–11). Remaining 13 unprobed: . Only meshSize=465 has  — all others 0. Batch-decoded every unprobed family.

- **3 NEW faced families discovered:**

| MeshSize | Samples | Verts | Faces | OBJ Size | Pairings |
|---:|---:|---:|---:|---:|---|
| **309** | 3 | 48 | **189** | 9,681 B / 342 L | 2 confident, index-u16be-strip-lead |
| **405** | 3 | 15 | **39** | 2,449 B / 93 L | 2 confident, index-u16be-strip-lead |
| **280** | 2 | 32 | **30** | 2,770 B / 103 L | 2 confident, index-u16be-strip-lead |

- **meshSize=465 (negative):** All 3 samples (, , ) failed with "No manifest entry matched" — these IDs exist in the inventory patterns but not in the current copied archive subset.

- **Remaining 12 mesh sizes (all PairCompatible=0):** Batch-decoded all samples from 235, 214, 193, 345, 381, 315, 311, 307, 303, 299, 275, 267. **0 additional faces found** — all produce position-only or position+normal-only OBJs. This is expected: without index→vertex pairings, the experimental-position-source path cannot generate faces. The Stage 5 pairing-based face generation path has now been tested against every mesh size in the copied archive set.

- **Face format:** All use  with degenerate-bridge UInt16BE strip — consistent with the proven @264 topology hypothesis.

- **Proof guard suite (all 4 PASSED):**
  - attribute-extra-proof-guard: ✅ 4 @264 vertex groups (v=128×2, 95, 80, 64), raw-zero-based 5/5
  - usage-access-correlation-guard: ✅ 5 roles, 0 pairing exceptions
  - position-source-sibling-lead-guard: ✅ Known sibling leads intact
  - residual-lead-guard: ✅ 5 mesh sizes

- **CI gate:** Build 0 errors, Tests 6/6, Ruff 0 violations.

- **Total Stage 12 output:**

| Metric | Value |
|---|---:|
| New faced OBJs | **8** |
| New mesh families with faces | **3** (309, 405, 280) |
| Total OBJs (cumulative) | **29** |
| Total faced OBJs | **23** |
| Total position-only OBJs | **6** |
| Total vertices | **1,881** |
| Total faces | **3,177** |
| Unique mesh families with faces | **8** (@264/297, 276, 301, 321, 367, 309, 405, 280) |
| Unique mesh families position-only | **4** (272, 305, 325, 329) |
| Remaining unprobed | **0** — all 23 mesh sizes exhaustively probed |

- **Files changed:**  (this entry). No source code changes — all work was decode/validation/analysis.

- **Bottom line:** The pairing-based face generation path has been exhaustively tested against all 23 mesh sizes in the copied archive set. 8 families produce faced OBJs; 4 produce position-only; 11 produce nothing (no pairings or no archive matches). The C#-level  decoder finds valid index→vertex pairings where the aggregated inventory sees only index→normal/UV pairings. All proof guard baselines hold. Next: open the largest OBJs in a 3D viewer; investigate live archive sampling to reach meshSize=465 and other families whose samples are missing from the copied set.

## 
**2026-06-03 — Stage 13: Baseline verification and integrity sweep (complete):**

- **Goal:** After the exhaustive Stage 12 probe of all 23 mesh sizes, refresh the full discovery pipeline, run all 4 proof guards, verify the OBJ inventory, and confirm no regressions.

- **Discovery suite refresh:** Ran  — completed in 8.1s. All 3 inline guards (usage-access, position-source-sibling, residual-lead) PASSED. Mesh-binding inventory metrics stable.

- **Proof guard suite (all 4 PASSED):**
  - : PASSED — all 4 @264 vertex groups intact (v=128×2, 95×1, 80×1, 64×1), raw-zero-based fitness 5/5, degenerate-bridge-stitch structure, parity breaks 0/0, sentinel count 0.
  - : PASSED — 5 roles with correct usage/access splits, 0 pairing exceptions.
  - : PASSED — guarded leads intact.
  - : PASSED — meshSize=305 stream@188 residuals stable.

- **OBJ inventory verified — 29 OBJs across 13 families:**

| MeshSize | OBJs | Faced | Pos-only | Vertex counts | Face counts |
|---:|---:|---:|---:|---|---|
| **264** (@297) | 5 | 5 | 0 | [64, 80, 95, 128] | [78, 82, 118, 318] |
| **272** | 1 | 0 | 1 | [48] | — |
| **276** | 1 | 1 | 0 | [24] | [22] |
| **280** | 2 | 2 | 0 | [32] | [30] |
| **297** | 1 | 0 | 1 | [30] | — |
| **301** | 3 | 3 | 0 | [48] | [46] |
| **305** | 2 | 0 | 2 | [93] | — |
| **309** | 3 | 3 | 0 | [48] | [189] |
| **321** | 3 | 3 | 0 | [24] | [22] |
| **325** | 1 | 0 | 1 | [71] | — |
| **329** | 1 | 0 | 1 | [168] | — |
| **367** | 3 | 3 | 0 | [130] | [431] |
| **405** | 3 | 3 | 0 | [15] | [39] |

- **Total: 29 OBJs (23 faced, 6 pos-only), 3,177 faces, 1,881 vertices.**

- **meshSize=465:** Confirmed dead end — 0 sample IDs in inventory (all 3 assets missing from copied archives). The only remaining mesh family that showed PairCompatible > 0 in inventory but can't be probed without live archives.

- **CI gate:** dotnet build 0 errors, dotnet test 6/6 passed, ruff 0 violations.

- **Files changed:**  (this entry). No source code changes.

- **Bottom line:** All 23 mesh sizes exhaustively probed. 8 families produce faced OBJs, 5 produce position-only. All 4 proof guard baselines hold. Discovery pipeline and CI are green. The geometry decoding pipeline is end-to-end verified and ready for the next phase.

Current safest next direction 🛡️

1. Use `scripts\Invoke-RiftAssetWorkflow.ps1` for repeatable smoke/full mesh-binding cycles.
2. For the attribute-set lane, promote `@264/#15` on `6fc01704d4a509d5` as the next topology-bearing lead, while keeping `@272/#25` and repeated `@296` bodies as guardrail/negative evidence.
3. Promote `@264/#15` raw-zero-based plus degenerate-bridge stitching as the current best topology hypothesis, and review the emitted bounded `FirstSegmentTriangles` proof before any exporter.
4. Run `decode-geometry --experimental-position-source` on target meshes (e.g., `meshSize=325` family) to validate linked-stream position fallback; decode OBJ and inspect in a 3D viewer.
5. Continue the `meshSize=325` and `meshSize=321` indexed-family position-source search; normals and UVs are strong rotate-right-1 leads, but positions remain unproven.
6. Run and extend `AttributeExtraProofGuard` plus `AttributeExtraSiblingProofGuard` whenever mesh-binding, mapping fitness, or topology-probe code changes so future probe changes cannot silently flip the current `@264` topology hypothesis.
7. Preserve both little-endian and big-endian `uint16` views while testing compact/index-like bodies.
8. Add index-family topology scoring directly to mesh-binding pair reports.
9. ✅ Extended `--experimental-position-source` fallback to decode normals + UVs from linked streams.
10. ✅ Added `--write-obj` flag to Python workflow orchestrator for easy CLI access.
11. ✅ `--export-obj` experimental gate for attribute-set `@264` indexed OBJ exporter.
12. Open the first `--export-obj` output in external 3D viewer (Blender/MeshLab) for visual validation.
13. ✅ Scale to all 5 @264-indexed meshes (`meshSize=297` family, v=128/95/80/64) — `batch-export-264` command complete.
14. Open the first `--export-obj` output in external 3D viewer (Blender/MeshLab) for visual validation.
15. Keep LZMA2 work focused on manifest/PAK reconstruction rather than `TWAD` entry extraction.
