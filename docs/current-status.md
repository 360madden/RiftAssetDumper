# Current Status — High-impact RIFT asset discoveries 🚀

Date: 2026-06-01

## 🐍 Python migration status (PS→Py phase 1)

| Component | Status | Notes |
|---|---|---|
| `scripts/rift_workflow_utils.py` (49 unit tests) | ✅ complete | All utility functions ported and tested |
| `scripts/rift_workflow.py` (orchestrator) | ✅ complete | Command dispatch, C# CLI integration, `generated_output_guard`, Python mode routing, `decode-geometry` with `--experimental-position-source` |
| `scripts/rift_workflow_reports.py` (reports) | ✅ complete | `show_report_summary` (8 mode branches), `semantic_hint_cross_tab`, `discovery_workbench` |
| `scripts/Invoke-RiftWorkflow.ps1` (thin wrapper) | ✅ updated | Translates legacy PS mode names → kebab-case Python commands |
| `scripts/rift_workflow_guards.py` (proof guards) | ✅ complete | `attribute_extra_proof_guard` (dual-path: fitness/stream) + `attribute_extra_sibling_proof_guard` (dual-path: index-role/body-role) ported from PS. Fitness path now validates @264 aggregate edge/area/normal/parity/strip-structure regressions. |
| Guard/report functions (remaining 11) | ⏳ deferred | `usage-access-correlation-guard`, `residual-lead-guard`, `residual-position-classifier-report`, `residual-position-cluster-probe-report`, `position-source-gap-report`, `position-source-sibling-lead-guard`, `position-source-sibling-family-report`, `position-source-sibling-probe-report`, `position-source-sibling-representative-probe-report`, `position-source-sibling-secondary-probe-report`, `position-source-sibling-extra-position-report` |
| `scripts/Invoke-RiftAssetWorkflow.ps1` (legacy) | ⚠️ deprecated | Still available as fallback for unported complex modes |

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
python scripts/rift_workflow.py attribute-extra-proof-guard --full --skip-build
python scripts/rift_workflow.py attribute-extra-sibling-proof-guard --id 6fc01704d4a509d5 --skip-build
python scripts/rift_workflow.py decode-geometry --id 6fc01704d4a509d5 --mesh-block 6 --full
python scripts/rift_workflow.py decode-geometry --id 6fc01704d4a509d5 --mesh-block 6 --experimental-position-source --write-obj
```

**Unported modes still use legacy PS:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Invoke-RiftAssetWorkflow.ps1 -Mode ResidualPositionClusterProbeReport
```

**2026-06-02 — Stage 2: Position-source fallback + triage + end-to-end validation (complete):**
- Extended `ExperimentalPositionSource` fallback to decode **normals** and **UVs** from linked NiDataStream blocks, not just positions. Candidates filtered by `Role.StartsWith("normal-")` and `Role.StartsWith("uv-")` for safer matching.
- Normals validated via `VectorLength` in console samples, identical to the attribute-set decode pattern.
- OBJ writing now produces `vn` (normals) and `vt` (UVs) lines for all fallback-decoded meshes.
- Summary line shows `"linked-stream fallback"` instead of `"0 attribute sets"` when the fallback path was used.
- Added `--write-obj` flag to Python workflow orchestrator (`rift_workflow.py`) — wired through `COMMAND_MAP`, `_run_dotnet_and_summarize`, and `decode-geometry` handler.
- **End-to-end validated on real 0-attribute-set meshes:**
  - `084c1e91726a2aea` mesh#6: 24 positions + 24 normals decoded, OBJ written ✅
  - `1601c1f75e0a6022` mesh#6: 30 positions + 30 UVs decoded, OBJ written ✅
  - Both produce OBJ with `v` / `vn` / `vt` lines + trivial fan faces
- Added `triage-fallback-candidates` Python command: reads fresh mesh-binding inventory and cross-references position/normal/UV float32 candidates across RoleGroups. Outputs classification (position-only vs position+normal+uv), top-16 sample listing, and ready-to-run test commands. Usage: `python scripts/rift_workflow.py triage-fallback-candidates --full`
- Full inventory analysis: **5,507 NiMesh blocks, 5,455 (99%) have 0 attribute sets**, 210 position-float3 candidates, 0 with complete position+normal+UV triple (companion streams don't co-occur in the same mesh block).
- Build: 0 errors, Tests: 6/6 pass, Code review: clean.

**Known limitations:**
- Faces are trivial triangle fan (vertex 0 to consecutive pairs) since no index stream is available in this fallback mode.
- Only the first float32 candidate per role (position/normal/UV) is used; multiple candidates are skipped.
- 5,455 meshes (99%) have 0 attribute sets — the fallback now handles these for meshes where linked streams contain float32 data.
- Output path overlap: `--write-obj` writes OBJ to subdirectory under the probe-report JSON path; this is cosmetic and pre-existing.

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
| Model format | ✅ major lead | Repeated Gamebryo payloads are now detected/extracted as `.nif` and parsed for NIF header/block/string-table evidence. |
| Filename/path recovery | ✅ proven lead | NIF string tables produced real `.dds` name candidates and high-confidence FNV1 manifest matches. |
| Asset signature/semantic index | ✅ new scaffold | `inventory-asset-signatures` now groups all copied payload signatures, and `build-asset-semantic-index` emits generated `asset-semantic-index/v1` packets under ignored `Exports/` with IDs, detected types, signatures, bounded references/snippets, `hint:*` semantic categories, category filters, XML tag/attribute name counts, and XML parse status/boundary metadata with no values/text/raw parse messages. |
| Model→texture graph | ✅ working | NIF references link `3,224` model assets to `2,514` unique texture manifest assets. |
| Bundle completion | ✅ newly actionable | A live-read-only archive planner found every currently missing NIF-linked texture asset and ranked the exact `assets.###` chunks needed. |
| Mesh stream binding | ✅ new proof lead | `inventory-nif-mesh-bindings` found `2,076` pair-compatible meshes and `4,468` same-mesh index/vertex-count-compatible links. |
| Mesh role decoding | ✅ new byte-order lead | Many coarse `uint16-compatible-body` streams now decode as rotate-right-1 `float3` normals and `float2` UVs. |
| Attribute-set topology | ✅ structural lead | Complete position/normal/UV sets are now ranked by implicit topology candidates; strongest family is `v=16`, strip-or-quad, `7` copied-set hits. |
| Attribute extra streams | ✅ split truth | Focused probing down-ranked low-variation `@272/#25` and `@296` side streams, while full mesh-binding inventory now finds four `@264/#15` explicit-index groups where segmented decoded-position, normal-delta, and triangle-area aggregate fitness favor raw-zero-based (`5/5` samples); UV deltas are neutral/no-worse, strip structure is consistently degenerate-bridge/stitch-like, first-segment proof samples include area/parity plus compact review flags, and the aggregate + focused sibling proof guards now fail if those proof signals silently flip. |
| Position source fallback (Stage 2) | ✅ complete | `--experimental-position-source` decodes normals+UVs+positions; `--write-obj` wired; end-to-end validated on 2 real fallback meshes; `triage-fallback-candidates` command added. Build/test/code-review clean. |

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

## Current safest next direction 🛡️

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
13. Scale to all 5 @264-indexed meshes (`meshSize=297` family, v=128/95/80/64) and batch-test.
14. Keep LZMA2 work focused on manifest/PAK reconstruction rather than `TWAD` entry extraction.
