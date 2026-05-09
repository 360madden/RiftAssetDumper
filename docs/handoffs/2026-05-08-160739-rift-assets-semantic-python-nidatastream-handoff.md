# Handoff — Asset semantic discovery, Python orchestration, and Gamebryo NiDataStream normalization

Date: 2026-05-08
Repo: `C:\RIFT MODDING\Assets`
Branch: `main`

## TL;DR 🧭

This session expanded `RiftAssetDumper` from NIF/DDS-focused discovery into a broader asset semantic discovery lane, then pivoted new batching/orchestration to Python as requested. The latest targeted code slice normalized Gamebryo `NiDataStream<SOH>usage<SOH>access` block-type variants while preserving raw escaped names.

Generated outputs were written under ignored `Exports/`; no copied assets or generated extraction output were staged.

## Current git state 🌿

```text
## main...origin/main [ahead 1]
 M .gitignore
 M README.md
 M docs/aggressive-discovery-workflow.md
 M docs/current-status.md
 M scripts/Invoke-RiftAssetWorkflow.ps1
 M src/RiftAssetDumper/Program.cs
?? docs/asset-guided-runtime-reacquisition-strategy.md
?? docs/schemas/
?? scripts/rift_asset_discovery_matrix.py
!! Exports/
!! Extracted/
!! Source/
!! src/RiftAssetDumper/bin/
!! src/RiftAssetDumper/obj/
```

Latest commits at handoff time:

```text
106113c (HEAD -> main) Add policy resume handoff
99d52d3 (origin/main) Document safe reasoning task routing policy
8794ebe Guard NIF attribute extra topology proof
a9510e4 Inventory NIF attribute extra streams
bc02cee Score NIF attribute-set topology leads
```

`main` is still ahead of `origin/main` by one prior handoff commit.

## Files changed / added 📁

| Path | Purpose |
|---|---|
| `.gitignore` | Added Python cache ignores: `__pycache__/`, `**/__pycache__/`, `*.pyc`. |
| `README.md` | Documented asset signature/semantic commands and Python discovery matrix orchestration. |
| `docs/aggressive-discovery-workflow.md` | Added Python-first orchestration policy while keeping .NET dumper as parser/source of truth and PowerShell as compatibility. |
| `docs/current-status.md` | Updated date, semantic-index status, targeted matrix findings, and Gamebryo/NiDataStream normalization notes. |
| `docs/asset-guided-runtime-reacquisition-strategy.md` | New design doc for asset-guided runtime reacquisition and Gamebryo/NIF handling boundaries. |
| `docs/schemas/asset-semantic-index-v1.schema.json` | New schema for generated `asset-semantic-index/v1` packets. |
| `scripts/Invoke-RiftAssetWorkflow.ps1` | Added `AssetSignatures`, `AssetSemanticIndex`, `-Type`, `-SemanticCategory`, and XML parse summary output. |
| `scripts/rift_asset_discovery_matrix.py` | New Python-first matrix runner for safe batched semantic/signature discovery. |
| `src/RiftAssetDumper/Program.cs` | Added asset signature/semantic index commands, XML/Lua detection, XML family/parse metadata, semantic categories/filters, and normalized NiDataStream usage/access metadata. |

## Implemented capabilities ✅

### 1. Asset signature + semantic index

New CLI commands:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-asset-signatures --root "C:\RIFT MODDING\Assets\Source" --max-total 500 --out "C:\RIFT MODDING\Assets\Exports\asset-signature-inventory-smoke.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- build-asset-semantic-index --root "C:\RIFT MODDING\Assets\Source" --max-total 200 --out "C:\RIFT MODDING\Assets\Exports\asset-semantic-index-smoke.json"
```

Key output fields include:

- `SchemaVersion = asset-semantic-index/v1`
- `GeneratedOutputNotice`
- manifest/archive identity fields
- detected type + magic/signature fields
- semantic categories and category filters
- bounded name/reference/snippet samples
- XML tag-name and attribute-name counts
- XML parse status/warning/line/position/parsed-count metadata

Safety boundary: `hint:*` categories are search leads only, not parser-backed schema or runtime truth.

### 2. Python-first orchestration

New helper:

```powershell
python "C:\RIFT MODDING\Assets\scripts\rift_asset_discovery_matrix.py" --skip-build --jobs signature-baseline semantic-xml-map-zone semantic-bin-waypoint-poi --privacy-scan
```

Design:

- Python orchestrates only.
- .NET `RiftAssetDumper` remains parser/source of truth.
- Uses dataclasses, list-form subprocess args, timeouts, JSON parsing, optional `jsonschema`, fail-closed summaries, and privacy scanning.
- Writes generated outputs to ignored `Exports\discovery-matrix\`.
- Existing PowerShell workflow helper remains compatibility/workflow surface.

### 3. Gamebryo NiDataStream normalization

`RiftAssetDumper` now preserves raw escaped block-type names while normalizing Gamebryo datastream variants:

| Field | Example |
|---|---|
| `TypeName` / `NormalizedName` | `NiDataStream` |
| `TypeDisplayName` / `DisplayName` | `NiDataStream\u00011\u000119` |
| `DataStreamUsage` | `1` |
| `DataStreamAccess` | `19` |

Validated sample asset:

```text
21900d2ee4f931ca
```

Probe output showed raw block-type variants:

```text
NiDataStream\u00010\u000119 usage=0 access=19
NiDataStream\u00011\u000119 usage=1 access=19
```

while block families are grouped as normalized `NiDataStream`.

## Discovery evidence captured 🔎

### Full signature inventory evidence

Earlier full signature inventory reported:

| Type | Count |
|---|---:|
| `bin` | `21,928` |
| `dds` | `12,954` |
| `nif` | `5,111` |
| `riff` | `203` |
| `txt` | `1` |
| `xml` | `6` |

Total inspected: `40,203`; failed: `0`.

### Targeted matrix evidence

A bounded Python matrix run captured these targeted findings in `docs/current-status.md`:

| Job | Payloads inspected | Entries | Signature groups | Current read |
|---|---:|---:|---:|---|
| `semantic-xml-map-zone` | `6` | `6` | `1` | XML map-zone/UI/model hints exist, but all XML parses are `partial-with-warning`. |
| `semantic-bin-waypoint-poi` | `1,000` | `113` | `77` | Strongest current binary text-family lead for waypoint/POI-like terms. |
| `semantic-bin-map-zone` | `1,000` | `101` | `96` | Binary map/zone-like hints exist and overlap waypoint/actor refs. |
| `semantic-bin-actor-object` | `1,000` | `95` | `77` | Actor/object-like binary hints overlap waypoint/map/texture refs. |
| `semantic-bin-quest-objective` | `1,000` | `0` | `0` | No early-corpus quest/objective binary hits yet; keep as negative evidence only. |
| `semantic-nif-texture-refs` | `500` | `308` | `1` | NIF texture references remain high-value semantic labels. |
| `semantic-nif-model-refs` | `500` | `500` | `1` | NIF model reference extraction is broad and useful for graph enrichment. |

Note: `Exports\discovery-matrix\asset-discovery-matrix-summary.json` may be overwritten by later one-job smoke runs. The current-status doc preserves the useful 7-job matrix results.

### NIF block inventory smoke

Command shape:

```powershell
& "C:\RIFT MODDING\Assets\src\RiftAssetDumper\bin\Debug\net9.0\RiftAssetDumper.exe" inventory-nif-blocks --root "C:\RIFT MODDING\Assets\Source" --max-total 200 --limit 50 --out "C:\RIFT MODDING\Assets\Exports\nif-block-inventory-smoke.json"
```

Result:

```text
Inspected payloads: 3,380
NIF payloads: 200
Total blocks: 6,844
Block types: 20
Mesh families: 40
DataStream families: 132
Top block types: NiDataStream=1,280, NiFloatExtraData=876, NiIntegerExtraData=861, NiFloatsExtraData=710, NiSourceTexture=446, NiMaterialProperty=413, NiVertexColorProperty=401, NiBooleanExtraData=270
```

## Validation completed 🧪

| Check | Result |
|---|---|
| `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo` | ✅ Passed, 0 warnings/errors |
| `python -m py_compile "scripts\rift_asset_discovery_matrix.py"` | ✅ Passed |
| Python matrix smoke: `semantic-nif-texture-refs` | ✅ Passed |
| Python matrix smoke with `signature-baseline`, `semantic-xml-map-zone`, `semantic-bin-waypoint-poi` | ✅ Passed earlier this session |
| Targeted 7-job Python matrix | ✅ Passed earlier this session |
| `inventory-nif-blocks --max-total 200` | ✅ Passed |
| `probe-nif --id 21900d2ee4f931ca` | ✅ Passed and surfaced usage/access metadata |
| Discovery matrix JSON validation | ✅ `13` generated asset reports validated against `asset-semantic-index/v1` schema |
| `git diff --check` | ✅ Passed; only CRLF normalization warnings |
| Privacy grep/scan | ✅ Only existing placeholder `C:\Users\%USERNAME%\...` hit |

## Cross-repo reconnaissance 🛰️

Read-only sidecar recon found:

| Repo | State | Recommendation |
|---|---|---|
| `C:\RIFT MODDING\Riftscan` | Clean/idle on main | Best first integration target. |
| `C:\RIFT MODDING\RiftReader` | Main clean | Use later, after RiftScan emits compatible candidate artifacts. |
| `C:\RIFT MODDING\RiftReader_camera_feature` | Dirty WIP lane | Avoid touching unless explicitly authorized. |

Recommended integration path:

```text
Assets semantic index
→ RiftScan offline semantic context / ledger
→ RiftScan candidate evidence artifact
→ RiftReader importer / live proof gates
```

Do not feed Assets semantic hints directly into RiftReader as live truth.

## Safety boundaries / do not do 🚧

- Do not stage or commit `Source/`, `Extracted/`, `Exports/`, `bin/`, or `obj/`.
- Do not treat `hint:*` categories as parser-backed schema truth.
- Do not treat asset semantics as live runtime proof.
- Do not wire directly into RiftReader first; use RiftScan offline context/ledger first.
- Do not touch `RiftReader_camera_feature` WIP unless explicitly authorized.
- Do not enable OBJ/model export from this slice.

## Best next technical slice 🎯

Use the new NiDataStream usage/access metadata to improve stream discovery:

1. Add `DataStreamUsage` / `DataStreamAccess` fields to NIF stream-header/body inventory records and summaries.
2. Show usage/access beside `probe-nif-mesh` stream candidates.
3. Use usage/access-aware grouping to improve index/position/normal/UV candidate ranking.
4. Keep all claims as structural leads until mesh semantic/component-format parsing agrees.

## Optional top 10 next recommended actions 🚀

| # | Action |
|---:|---|
| 1 | Add usage/access grouping to `inventory-nif-stream-headers` and `inventory-nif-stream-bodies`. |
| 2 | Extend `probe-nif-mesh` output to show usage/access beside each stream candidate. |
| 3 | Add usage/access-aware scoring to current mesh/stream role heuristics. |
| 4 | Add Python unit tests for `rift_asset_discovery_matrix.py` job config and summary parsing. |
| 5 | Add `asset-discovery-matrix/v1` JSON schema. |
| 6 | Add a minimal `asset-semantic-context` packet shape for RiftScan offline import. |
| 7 | Add a RiftScan doc-only note: Assets semantic index is hint-only and must flow through offline ledger. |
| 8 | Build model/object/reference graph output from NIF texture/model refs. |
| 9 | Add category-aware prefiltering for binary semantic scans to reduce CPU-heavy full `hint:*` passes. |
| 10 | Commit this milestone after review, excluding ignored generated outputs. |

## Resume prompt for next session 📋

```text
Resume in C:\RIFT MODDING\Assets. Read AGENTS.md, docs/task-routing-safety-policy.md, docs/current-status.md, and newest docs/handoffs file only. Confirm git status/log. Continue targeted asset discovery with Python-first orchestration and .NET RiftAssetDumper as parser/source of truth. Start with NiDataStream usage/access-aware stream-header/body inventory and probe-nif-mesh summaries. Validate every script/code change with py_compile/build/smoke/privacy/diff checks. Do not stage Source/, Extracted/, Exports/, bin/, or obj/. Keep RiftScan integration offline/hint-only and do not wire directly into RiftReader.
```
