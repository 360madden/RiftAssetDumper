# RiftAssetDumper workspace

[![CI](https://github.com/360madden/RiftAssetDumper/actions/workflows/ci.yml/badge.svg)](https://github.com/360madden/RiftAssetDumper/actions)

Read-only RIFT asset archive research workspace.

## Operating mode 🚀

This repo now uses the approved **Aggressive Evidence Workflow**: optimize for maximum real discovery speed, not reckless output. The durable workflow plan is in:

```text
docs\aggressive-discovery-workflow.md
```

Reasoning/model routing is governed by the repo safety policy:

```text
docs\task-routing-safety-policy.md
```

Short version: keep high/extra-high reasoning for truth, proof, schema, runtime, guard, cross-repo, live-game, exporter, and commit/push decisions. Use lower-intelligence execution only for reversible mechanical work after safety is practically guaranteed and the main high-reasoning lane reviews the result.

Current geometry priority: prove `NiMesh` → `NiDataStream` bindings, assign stream roles, validate `maxIndex < vertexCount`, and down-rank sentinel/mask side streams before any experimental OBJ/model export.

Optionized workflow helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshBindings -Full -PrivacyScan
```

Focused mesh probe helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshProbe -Id c841eb9a0ed1c95e -MeshBlock 6
```

Focused attribute extra-stream probe helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProbe -Id 75d5a06d7c0de1dd -MeshBlock 7 -ExtraOffset 272
```

Attribute-extra topology proof regression guard:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProofGuard -SkipBuild
```

Focused `@264/#15` sibling proof regression guard:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraSiblingProofGuard -SkipBuild
```

Prefer adding options/modes to this helper before creating new one-off helper apps.

## Ghidra static-analysis lane

Ghidra is integrated as an offline static-analysis support tool for bounded parser/format proof work. It is not part of the default discovery suite and should not replace parser tests or byte-level proof.

Preferred guarded workflow:

```powershell
python scripts/rift_workflow.py tools-status
python scripts/rift_workflow.py ghidra-dry-run --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project
python scripts/rift_workflow.py ghidra-run --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project --ghidra-timeout 900 --ghidra-script scripts/ghidra/FunctionSiteSurvey.java --ghidra-script-arg 0x1406e905f --ghidra-script-arg Exports/ghidra-reports/twad_site_survey.json
python scripts/rift_workflow.py ghidra-summarize --ghidra-report Exports/ghidra-reports/twad_site_survey.json --ghidra-summary-term TWAD
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
python scripts/rift_workflow.py ghidra-pairing-review-report --quick --limit 10
python scripts/rift_workflow.py ghidra-pairing-non-export-guard
python scripts/rift_workflow.py mesh-probe --review-rank 2 --skip-build
python scripts/rift_workflow.py ghidra-review-rank-probes --limit 14 --skip-build
python scripts/rift_workflow.py ghidra-attribute-candidate-report
python scripts/rift_workflow.py ghidra-attribute-candidate-guard
python scripts/rift_workflow.py ghidra-workflow-guard-suite
```

Current durable Ghidra truth:

- `docs/handoffs/2026-05-24-ghidra-anchor-survey.md` — retained `rift_x64.exe` anchor survey and NIF/NiDataStream/NiMesh leads.
- `docs/handoffs/2026-05-24-twad-ghidra-proof.md` — `TWAD` proven as archive file/header magic; no parser behavior change recommended.
- `docs/ai-driven-workflow.md` — validation gate, generated-output hygiene, and Ghidra lane rules.
- `.github/workflows/ci.yml` — CI runs all offline `scripts/test_*.py` workflow smoke tests, including Ghidra command wiring.
- `.tools.json` — local Ghidra/JDK registry; installed tools live outside the repo.

Keep Ghidra projects, reports, and one-off scripts under ignored `Exports/ghidra-*`. Prefer Java Ghidra scripts for this lane unless a future validation proves Python/Jython scripts work in the current headless launch mode.

`scripts/ghidra/FunctionSiteSurvey.java` emits the current reusable function-site JSON shape; `docs/schemas/ghidra-function-site-survey-v1.schema.json` documents that generated report contract. Use `ghidra-summarize` for reviewable Markdown summaries instead of committing raw `Exports/ghidra-reports/*.json`.

Use `nidatastream-layout` as the read-only bridge between Ghidra's `NiDataStream::LoadBinary()` evidence and copied/extracted NIF samples. It checks descriptor prefix bytes, declared payload bytes, and trailing flag bytes without changing decoder/export behavior.

C# stream reports now expose the same layout comparison side-by-side: legacy `HeaderBytes` / `RoleStats` remain unchanged, while `PayloadPrefixBytes`, `PayloadTrailerBytes`, `TrailingFlag`, and `Ghidra*` sidecar fields show the Ghidra-aligned interpretation for review. `inventory-nif-mesh-bindings` also emits `TopGhidraRoleDeltas`, a read-only legacy-role to Ghidra-role ranking grouped by mesh size, declared payload bytes, and usage/access metadata. Candidate-only Ghidra pairing counts are exposed separately as `GhidraPairCompatibleMeshes` / `GhidraPairCompatibleLinks` plus `TopGhidraPairings`; they do not replace the legacy pairing fields. `index-u16le-*` roles now carry separate little-endian index max/count stats so Ghidra-aligned pair comparisons no longer reuse big-endian index bounds. `GhidraSharedPairings`, `LegacyOnlyPairings`, `GhidraOnlyPairings`, and `TopGhidraPairingComparisons` expose the overlap/gap review surface before any promotion. `TopGhidraPairingReviewFindings` now ranks candidate-only Ghidra-only links ahead of shared pairings where the vertex semantic class changes, with pairing samples carrying stream offsets, usage/access, confidence, and first-byte evidence. `ghidra-pairing-review-report` turns those findings into ignored JSON/Markdown triage reports under `Exports/`, `mesh-probe --review-rank N` jumps directly from a review row to a focused probe, `ghidra-review-rank-probes` batch-refreshes ignored focused probe folders, `ghidra-attribute-candidate-report` groups Ghidra-only rows by sample mesh, `ghidra-attribute-candidate-guard` locks the current incomplete-group baseline, `ghidra-workflow-guard-suite` runs the Ghidra promotion brakes together, `ghidra-pairing-non-export-guard` fails closed if Ghidra evidence enters decode/export paths, and `probe-nif-mesh` emits per-mesh `GhidraPairings` side by side with legacy `Pairings`.

The current Ghidra pairing promotion checklist is tracked in `docs/ghidra-pairing-promotion-checklist.md`; the review-report schema is `docs/schemas/ghidra-pairing-review-v1.schema.json`, and the grouped attribute-candidate report schema is `docs/schemas/ghidra-attribute-candidate-v1.schema.json`.

## Privacy and path redaction

The CLI redacts Windows user-profile path segments by default in console output and JSON/JSONL reports. Paths under the current user's profile are emitted with an environment-variable placeholder:

```text
%USERPROFILE%\...
```

Other generic user-profile paths are emitted as:

```text
C:\Users\%USERNAME%\...
```

These placeholders preserve the path meaning without exposing the local account name. Use `--no-redact-paths` only for private local debugging when exact local paths are needed. Keep redaction enabled for artifacts that might be committed, shared, or pasted into public issues.

## Local source files

Copied game files live under:

```text
C:\RIFT MODDING\Assets\Source
```

Expected layout:

```text
Source\assets64.manifest
Source\assets64_dev.manifest
Source\assets64_debug.manifest
Source\manifest64.txt
Source\Assets\assets.###
```

`Source` is local copied game data. Do not commit it.

Current local sample set has 27 copied `Source\Assets\assets.###` archive chunks.

## Probe headers and manifest tables

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe --root "C:\RIFT MODDING\Assets\Source"
```

This validates:

- `TWAM` manifest headers
- manifest table references
- sample PAK listing rows
- sample manifest entry rows
- `TWAD` archive headers
- sample archive entries

It writes:

```text
Source\probe-report.json
```

unless `--no-json` is provided.

## Match archive entries to manifest rows

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- match-ids --root "C:\RIFT MODDING\Assets\Source"
```

Earlier validation proved copied entries in `assets.001`, `assets.020`, and `assets.032` all matched manifest Table 1 IDs. Manifest-aware extraction now uses the same ID lookup for every copied archive it processes.

This proves the copied `assets.###` files contain individual manifest Table 1 asset entries, not just anonymous blobs.

## Export manifest indexes

PAK listing sample:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- list-paks --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\paks.sample.jsonl" --limit 5
```

Entry listing sample:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- list-entries --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\entries.sample.jsonl" --limit 5
```

Omit `--limit` to export all rows. Output is JSON Lines, one record per line.

## Smoke-extract archive payloads

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Extracted\archive-payloads-smoke" --max-per-archive 2
```

Current extractor support:

- compression `0`: raw copy
- compression `1`: zlib/deflate fallback
- compression `2`: safe LZMA2 path; XZ-framed payloads are attempted with SharpCompress, raw/unproven LZMA2 reports `lzma2-raw-unhandled`

Extraction verifies:

- packed bytes SHA1 equals the 20-byte `TWAD` entry SHA
- unpacked bytes SHA1 begins with the 8-byte `TWAD` entry ID
- compression decode status is recorded in `extract-report.json`

Output names are manifest-aware when the ID is found:

```text
Extracted\archive-payloads-smoke\assets.001\000000_m305462_fnvc1385178_pak1428_off30016_9bf40aa6a3d8283c.bin
```

Extraction also writes:

```text
Extracted\archive-payloads-smoke\extract-report.json
```

## Targeted extraction

Extract one asset by 8-byte ID prefix:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Extracted\target-id" --id 9bf40aa6a3d8283c --max-total 1
```

Extract one asset by filename FNV1 hash:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Extracted\target-fnv" --fnv 0xc1385178 --max-total 1
```

Extract one asset by manifest Table 1 row:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Extracted\target-manifest" --manifest-index 305462 --max-total 1
```

Extract from one copied archive only:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Extracted\target-archive042" --archive 42 --max-per-archive 2
```

Supported extraction filters:

```text
--archive assets.042 | .042 | 42
--id <16 hex chars>
--fnv <decimal uint32 or 0xhex>
--manifest-index <zero-based Table 1 row>
--max-total <n>
```

Filters can be combined; matching is by manifest/asset ID after the selected manifest is loaded.

Optional recovered-name extraction:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Extracted\with-recovered-names" --use-recovered-names "C:\RIFT MODDING\Assets\RecoveredNames\recovered-names.jsonl"
```

Recovered names are only used when the JSONL match has high confidence, the manifest name length agrees, and any recovered extension agrees with the detected payload type. Existing manifest-aware fallback names are still used for unresolved or type-mismatched assets. Duplicate recovered paths get an asset-ID suffix instead of being overwritten.

LZMA2 mode:

```text
--lzma2-mode auto|xz-only|off
```

Default is `auto`. It only attempts known-safe XZ-framed LZMA2. Raw LZMA2 remains intentionally unhandled until real RIFT samples prove the required header/properties.

## Compression scan

Use `scan-compression` to lock down where compression kinds appear before attempting new decompression work:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- scan-compression --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\compression-scan.json"
```

Current copied-data truth:

```text
Manifest PAK compression: 0=736, 2=1340
Copied TWAD entry compression: 0=203, 1=40000
Copied TWAD non-null entries: 40,203
```

`scan-compression` also records one sample per compression kind, including copied-archive offsets and first bytes. If pointed at a live install with `--live-root`, it scans read-only; write the report to this workspace with `--out` instead of writing into the game install.

`scan-compression` uses streaming TWAD table reads, so it can inspect the full live install without reading every multi-GB archive payload into memory.

Full live install scan, read-only:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- scan-compression --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --out "C:\RIFT MODDING\Assets\Exports\live-compression-scan.json"
```

Current live-install truth:

```text
Live TWAD archive files scanned: 244
Live TWAD non-null entries: 263,957
Live TWAD entry compression: 0=22422, 1=241535
Manifest PAK compression: 0=736, 2=1340
```

Important conclusion: compression `2` has now been confirmed in manifest Table 0 logical PAK rows, but not in copied or full-live `TWAD` archive entries. The LZMA2 path should therefore focus on logical PAK/manifest layer reconstruction, not ordinary `assets.###` entry extraction.

## Current validated status

- The copied manifests are valid `TWAM` files.
- The copied archives are valid `TWAD` files.
- The probe successfully parses table counts/strides for all copied manifests.
- Copied archive entries can be matched to manifest Table 1 IDs.
- `list-paks` and `list-entries` produce JSONL exports.
- The smoke extractor successfully decompressed and SHA-verified zlib entries from all currently copied archives with `--max-per-archive 2`.
- Targeted extraction works by ID, FNV1 hash, manifest index, and archive number.
- Manifest-aware extraction records manifest row, FNV1 filename hash, PAK index, PAK offset, sizes, and SHA evidence in filenames/report records.
- LZMA2 is guarded: XZ-framed payloads are supported through SharpCompress, and raw/unproven LZMA2 is reported instead of guessed.
- Original filename recovery now has hash matching, confidence controls, JSONL output, and safe recovered-name extraction wiring. No real original paths have been recovered from placeholder candidates yet.
- Gamebryo/NIF model payloads are detected from the `Gamebryo File Format, Version 20.6.0.0` header and extracted with `.nif` extension.
- Geometry/model work is at evidence-gathering stage: binary signatures can be inventoried and one asset can be probed, but no OBJ/model export is claimed supported.
- The top attribute side streams split into negative guardrails and one stronger lead: `@272/#25` and repeated `@296` bodies are low-variation sentinel/repeated-pattern payloads, while full mesh-binding inventory now finds four `@264/#15` explicit-index groups where segmented decoded-position, normal-delta, and triangle-area aggregate fitness favor raw-zero-based (`5/5` samples, `0` subtract-one wins); UV deltas are neutral/no-worse, strip structure is consistently degenerate-bridge/stitch-like rather than `0xffff` sentinel-based, focused probes emit a bounded 24-triangle `FirstSegmentTriangles` proof packet per mapping with area, dominant signed plane, strip parity diagnostics, and compact proof-review flags, and aggregate + focused sibling proof guards now fail if the current proof signals silently regress; export remains blocked pending proof review/validation behind an explicit experimental gate.

## Filename hash/name recovery helpers

Hash one candidate path/name. Input is normalized to lowercase and `/` separators before hashing. Both FNV1 and FNV1a are printed because the manifest documentation calls the field FNV1, but the exact practical candidate set still needs validation from known filenames.

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- hash-name --name "Assets\Audio\Audio_0.pak"
```

Match a candidate filename list against manifest Table 1 hashes:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- match-names --root "C:\RIFT MODDING\Assets\Source" --names-file "C:\RIFT MODDING\Assets\Candidates\sample-names.txt" --out "C:\RIFT MODDING\Assets\Exports\sample-name-matches.jsonl" --algorithm both --only-length-match
```

Candidate file rules:

```text
one candidate path/name per line
blank lines are ignored
lines starting with # are ignored
backslashes normalize to forward slashes
leading slashes are removed
names are lowercased before hashing
```

Matching controls:

```text
--algorithm fnv1|fnv1a|both
--only-length-match
--require-unique
--min-confidence <0-100>
```

Default `match-names` output, when `--out` is omitted:

```text
C:\RIFT MODDING\Assets\RecoveredNames\recovered-names.jsonl
```

Each JSONL match records the candidate name, algorithm, hash, length agreement, confidence, collision count, manifest row, asset ID, PAK index/offset, and size fields.

A starter candidate list exists at:

```text
C:\RIFT MODDING\Assets\Candidates\sample-names.txt
```

Current validation: the sample candidates produce no manifest matches yet, which is expected because they are placeholders, not known original asset paths.

Mine path-like strings from already extracted `.bin`/`.txt` payloads:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- mine-strings --root "C:\RIFT MODDING\Assets\Source" --input "C:\RIFT MODDING\Assets\Extracted" --out "C:\RIFT MODDING\Assets\Exports\mined-names.jsonl"
```

The miner looks for normalized `assets/...`, `art/...`, `textures/...`, `models/...`, `audio/...`, `ui/...`, and similar paths ending in common asset extensions. Current local extracted sample produced zero mined candidates, so more/broader extraction is needed before this is useful.

## Archive inventory and type filtering

Inventory copied archives without writing payload files. This decompresses/verifies up to `--max-per-archive` matching entries per archive and counts detected types.

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-archives --root "C:\RIFT MODDING\Assets\Source" --archive 42 --max-per-archive 10 --out "C:\RIFT MODDING\Assets\Exports\inventory-archive042.json"
```

Validated result for copied `assets.042`:

```text
assets.042: entries=10 inspected=10 failed=0 types=[dds=10]
```

Inventory with a type filter:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-archives --root "C:\RIFT MODDING\Assets\Source" --archive 42 --type dds --max-per-archive 5 --out "C:\RIFT MODDING\Assets\Exports\inventory-archive042-dds.json"
```

Extract only detected DDS files from one archive:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Extracted\target-archive042-dds" --archive 42 --type dds --max-per-archive 2
```

Validated result:

```text
Done. written=2, skipped=0, failed=0
```

Currently detected types include at least:

```text
dds
riff
bin
txt
lua
xml
png
jpg
ogg
lzma2
nif
```

Archive-aware signature and semantic index commands:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-asset-signatures --root "C:\RIFT MODDING\Assets\Source" --max-total 500 --out "C:\RIFT MODDING\Assets\Exports\asset-signature-inventory-smoke.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- build-asset-semantic-index --root "C:\RIFT MODDING\Assets\Source" --max-total 200 --out "C:\RIFT MODDING\Assets\Exports\asset-semantic-index-smoke.json"
```

Filtered semantic triage can combine detected type and category filters:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AssetSemanticIndex -Type xml -SemanticCategory hint:map-zone -SmokeMaxTotal 200 -SkipBuild
```

Python discovery-matrix orchestration batches safe semantic/signature jobs and writes a compact summary under ignored `Exports\discovery-matrix`:

```powershell
python "C:\RIFT MODDING\Assets\scripts\rift_asset_discovery_matrix.py" --skip-build --jobs signature-baseline semantic-xml-map-zone semantic-bin-waypoint-poi --privacy-scan
```

The semantic index uses schema `docs\schemas\asset-semantic-index-v1.schema.json` and is generated under ignored `Exports/`. Its `hint:*` categories are search leads only, not parser-backed truth or runtime durability claims. Prefer type-bounded or `--max-total` smoke scans before wildcard `hint:*` scans across all binary payloads. XML summaries store tag-name and attribute-name counts plus parse status/boundary metadata; attribute values, element text, raw XML, and raw parse messages are intentionally omitted. New batching/orchestration helpers should be Python-first while the .NET dumper remains the parser/source of truth.

## Binary/model/geometry evidence tools

Group unknown binary payloads by repeated signatures and simple size/stride evidence:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-binary-signatures --root "C:\RIFT MODDING\Assets\Source" --archive 1 --max-total 10 --out "C:\RIFT MODDING\Assets\Exports\binary-signatures-archive001.json"
```

Current archive `assets.001` sample:

```text
Inspected bin payloads: 10
Groups: 2
00000000000000400000000002000000: count=9
000000000000c0410000000002000000: count=1
```

Probe one binary asset by asset ID, manifest index, FNV hash, or direct file path:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-binary --root "C:\RIFT MODDING\Assets\Source" --id 9bf40aa6a3d8283c --out "C:\RIFT MODDING\Assets\Exports\probe-binary-9bf40.json"
```

Current sample:

```text
Type: bin
Length: 5,764
Classification: bin.signature.000000000000c041
First16: 000000000000c0410000000002000000
```

The probe report includes first 64 bytes, little-endian `uint32`/`int32`/`float32` interpretations, and stride candidates. Classifications are intentionally conservative (`bin.signature.*`, `structured-bin-candidate`, `geometry-candidate`, etc.). No geometry/OBJ export is supported yet.

### Gamebryo/NIF model discovery

A larger copied-archive binary inventory found repeated Gamebryo model headers:

```text
47616d656272796f2046696c6520466f -> "Gamebryo File Fo"
```

Validated sample:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-archives --root "C:\RIFT MODDING\Assets\Source" --archive 32 --type nif --max-per-archive 3 --out "C:\RIFT MODDING\Assets\Exports\inventory-archive032-nif.json"
```

Current result:

```text
assets.032: entries=205 inspected=3 failed=0 types=[nif=3]
Format: Gamebryo File Format, Version 20.6.0.0
```

Targeted extraction now writes `.nif`:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --id 21900d2ee4f931ca --max-total 1 --out "C:\RIFT MODDING\Assets\Extracted\nif-detection-regression"
```

Example output:

```text
000202_m275055_fnvae05f146_pak0373_off36798_21900d2ee4f931ca.nif
```

This is the strongest model-format lead so far. Next model work should target NIF/Gamebryo structure and external NIF tooling compatibility before inventing a custom geometry decoder.

### NIF probe and inventory

Probe one NIF/Gamebryo payload by asset ID, manifest index, FNV hash, or direct file path:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif --root "C:\RIFT MODDING\Assets\Source" --id 21900d2ee4f931ca --out "C:\RIFT MODDING\Assets\Exports\probe-nif-21900d.json"
```

Validated sample:

```text
NIF: Gamebryo File Format, Version 20.6.0.0
Blocks: 29; block types: 16; parsed types: 16
Strings: 24; references: 4
Top block usage: NiDataStream\u00011\u000119 x6, NiFloatExtraData x3, NiIntegerExtraData x3
```

The NIF probe currently parses:

- header line, version, endian marker, user version
- block count and block type table
- per-block type usage counts
- block-size table summary and payload delta evidence
- per-block payload map with block index, type, data offset, size, first bytes, numeric prefixes, and string-index clues
- NIF string table
- path-like/source-art/texture references mined from the string table

Important discovery: NIF string tables contain original source-art references and texture names. Example references from the validated sample include source `.ma` paths under `art/project/...` plus referenced `.dds` texture names. This is now one of the strongest leads for original name/path recovery.

Validated richer block-map probe from a batch-extracted architectural bundle:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif --input "C:\RIFT MODDING\Assets\Extracted\nif-bundles-batch-top3\16ecac86a42d4d96\model\001234_m120931_fnv4ca650ce_pak1736_off1119528_16ecac86a42d4d96.nif" --out "C:\RIFT MODDING\Assets\Exports\probe-nif-blockmap-16ecac.json"
```

Current block-map evidence:

```text
Blocks: 139
Block data: offset=2756 totalSize=11242 delta=8
NiMesh blocks: 4
NiDataStream blocks: 36
NiSourceTexture blocks: 22
NiDataStream size histogram: 41=1, 45=1, 61=3, 69=2, 77=5, 109=6, 125=1, 149=8, 209=1, 317=1, 389=3, 569=4
```

Example mesh block string clues:

```text
#7 NiMesh size=387 -> pCubeShape409:0, normalTexture, tint0, tint1
#44 NiMesh size=387 -> pCubeShape409:1, normalTexture, A_PTW_bricks_base_mossy_01_n.dds
#79 NiMesh size=387 -> pCubeShape409:2, normalTexture, glow2Texture
#110 NiMesh size=387 -> pCubeShape409:3, normalTexture, glow2Texture
```

This is the first evidence-backed bridge from "NIF detected" to concrete model internals: exact block payload offsets, block sizes, mesh block identities, texture-linked strings, and repeated data-stream block families are now visible in JSON.

Inventory NIF block families across the full copied archive set:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-blocks --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-block-inventory.json"
```

Current full copied-set block inventory:

```text
Inspected payloads: 40,203
NIF payloads: 5,111
Total blocks: 137,973
Block types: 32
Mesh families: 435
DataStream families: 771
```

Top block families:

```text
NiDataStream\u00011\u000119 = 26,087 blocks in 5,087 NIFs
NiIntegerExtraData = 12,910 blocks
NiFloatExtraData = 11,047 blocks
NiMaterialProperty = 10,595 blocks
NiVertexColorProperty = 10,214 blocks
NiSourceTexture = 9,489 blocks
NiFloatsExtraData = 8,629 blocks
NiNode = 6,534 blocks
NiMesh = 5,507 blocks in 5,087 NIFs
```

Top repeated mesh payload families:

```text
NiMesh size=214 count=954
NiMesh size=193 count=719
NiMesh size=301 count=301
NiMesh size=325 count=263
NiMesh size=305 count=163
```

Top repeated data-stream payload families:

```text
NiDataStream\u00011\u000119 size=317 count=1,605
NiDataStream\u00011\u000119 size=221 count=920
NiDataStream\u00011\u000119 size=605 count=679
NiDataStream\u00011\u000119 size=77 count=663
NiDataStream\u00011\u000119 size=125 count=645
```

This identifies the highest-value repeated mesh/data-stream formats to decode first.

`probe-nif` also now records candidate `NiMesh` -> `NiDataStream` references by scanning block payload fields for values that point at `NiDataStream` blocks. These are marked as candidates because some fields can overlap with string-table indexes, but repeated offsets are strong decode leads. Console output appends `?` when the same numeric value could also be interpreted as a string-table index, and the JSON records include `MaybeStringIndex` plus `StringValue` for review.

Validated rich model candidate stream links:

```text
Model: 16ecac86a42d4d96
Mesh #7   -> @236:#37? size=77,  @312:#35? size=41, @320:#41? size=61
Mesh #44  -> @0:#37? size=77,    @236:#72 size=149, @312:#35? size=41, @320:#76 size=109
Mesh #79  -> @236:#103 size=569, @312:#35? size=41, @320:#107 size=389
Mesh #110 -> @236:#132 size=149, @312:#35? size=41, @320:#136 size=109
```

Validated smaller copied model candidate stream links:

```text
Model: 21900d2ee4f931ca
Mesh #6 -> @212:#24 size=1673, @288:#22? size=1649, @296:#28 size=1125
```

The repeated `NiMesh` payload offsets around `@236`, `@312`, and `@320` are now the next best concrete fields to decode.

Inventory candidate mesh-stream links across all copied NIF payloads:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-mesh-streams --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-mesh-stream-inventory.json" --limit 100
```

Current copied-data result:

```text
NIF payloads: 5,111
NiMesh blocks: 5,507
Mesh blocks with candidates: 5,507
Candidate stream links: 11,564
Ambiguous candidate links: 3,809
Top offsets: @168=1,811, @276=642, @280=523, @300=514, @196=505
Top pattern: meshSize=325 count=138 @216:size=317|@292:size=101?|@300:size=221
```

This makes `@168` the strongest copied-set lead for small repeated meshes, while the `meshSize=325` and `meshSize=321` three-stream patterns look like good next targets for vertex/index/attribute role inference.

Inventory mesh-bound streams with role scoring and pairing checks:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-mesh-bindings --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-mesh-binding-inventory.json" --limit 100
```

Current copied-data result:

```text
NIF payloads: 5,111
NiMesh blocks: 5,507
Candidate stream links: 11,564
Valid declared stream bodies: 11,564
Pair-compatible meshes: 2,076
Pair-compatible links: 4,468
Attribute-compatible meshes: 52
Attribute-compatible sets: 52
Top roles:
  uv-float2-ror1-lead=4,633
  normal-float3-ror1-lead=4,167
  index-u16be-strip-lead=2,101
Top pairing: meshSize=325 count=134 index-u16be-strip-lead -> normal-float3-ror1-lead, vertexCount=24, maxIndex=23
Top attribute set: meshSize=305 count=6 position=192 normal=192 uv=128 vertexCount=16 topology=implicit-strip-or-quad-candidate
Top attribute topology: implicit-strip-or-quad-candidate vertexCount=16 count=7 stripTriangles=14 quads=4
```

This is the first full copied-set mesh-binding proof that candidate index streams can be paired with same-mesh stream bodies where `maxIndex < vertexCount`. The former coarse `uint16-compatible-body` families now mostly decode as per-float byte-rotated streams: rotate each 4-byte word right by 1 byte to expose normal-like `float3` and UV-like `float2` values.

Probe one mesh with role and pairing evidence:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-mesh --root "C:\RIFT MODDING\Assets\Source" --id c841eb9a0ed1c95e --mesh-block 6 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-c841-mesh6.json"
```

Validated sample:

```text
Mesh #6 size=325
@216 -> #25 payload=288 role=normal-float3-ror1-lead
@292 -> #23 payload=72 role=index-u16be-strip-lead maxIndex=23
@300 -> #29 payload=192 role=uv-float2-ror1-lead
Pairings:
  index @292/#23 -> @216/#25 vertexCount=24 coverage=1.00
  index @292/#23 -> @300/#29 vertexCount=24 coverage=1.00
Mesh payload windows matching paired vertex count: 0
```

This creates the one-mesh proof packet needed before attempting any experimental geometry export. Current interpretation for the top family: `payload=72` is a big-endian strip-like index lead, `payload=288` is a byte-rotated normal `float3` lead, and `payload=192` is a byte-rotated UV `float2` lead. Position data is still not proven, and the mesh payload itself did not expose a simple matching float window in this sample.

Probe a complete position/normal/UV attribute set:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshProbe -Id 75d5a06d7c0de1dd -MeshBlock 7
```

Validated sample:

```text
Mesh #7 size=305
@188 -> #21 payload=192 role=position-float3-ror1-lead
@196 -> #22 payload=192 role=normal-float3-ror1-lead
@280 -> #26 payload=128 role=uv-float2-ror1-lead
Attribute set: position + normal + UV, vertexCount=16
Topology: implicit-strip-or-quad-candidate, strip/fan=14 triangles, quad=4, triangle-list rejected
```

This gives a second geometry lane: complete unindexed/separately-indexed attribute sets with structural topology candidates. The exporter remains blocked until strip/fan vs quad/separate-index rules are proven; the topology label is evidence for the next probe, not renderable-geometry support.

Probe the target data streams for one NIF mesh:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-streams --root "C:\RIFT MODDING\Assets\Source" --id c841eb9a0ed1c95e --mesh-block 6 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-streams-c841-mesh6.json"
```

Current stream-header proof:

```text
Top pattern sample: c841eb9a0ed1c95e mesh #6 size=325
@216 -> stream #25 size=317, declaredPayload=288, declaredOffset=29, plausible 12x24 / 24x12 / 32x9
@292 -> stream #23 size=101?, declaredPayload=72, declaredOffset=29, plausible 12x6 / 24x3
@300 -> stream #29 size=221, declaredPayload=192, declaredOffset=29, plausible 12x16 / 24x8 / 32x6
```

The first `uint32` in these `NiDataStream` blocks appears to declare stream payload bytes, with a repeated 29-byte block header in the sampled families. This is still a structural lead, not final vertex/index semantics.

Inventory the stream-header rule across all copied NIF payloads:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-stream-headers --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-stream-header-inventory.json" --limit 100
```

Current copied-data result:

```text
NiDataStream blocks: 31,777
Declared payload blocks: 31,777
Valid declared payload blocks: 31,777
Invalid declared payload blocks: 0
Top header byte counts: 29=31,777
Top stream families:
  size=317 payload=288 header=29 count=1,605
  size=221 payload=192 header=29 count=920
  size=605 payload=576 header=29 count=679
  size=77  payload=48  header=29 count=663
  size=125 payload=96  header=29 count=645
```

This upgrades the 29-byte `NiDataStream` header from a sampled lead to a copied-set invariant for the currently parsed NIF data streams.

Inventory only the declared stream bodies after that 29-byte header:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-stream-bodies --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-stream-body-inventory.json" --limit 100
```

Current copied-data result:

```text
NiDataStream blocks: 31,777
Valid stream bodies: 31,777
Invalid stream bodies: 0
Top payload sizes: 288=1,757, 192=1,094, 48=843, 96=813, 576=751
Top body signatures:
  payload=72  first16=00010002000200010003000400050006 count=352
  payload=96  first16=ffffffffffffffffffffffffffffffff count=328
  payload=288 first16=00803f00000000000000000000803f00 count=195
  payload=288 first16=000000000000000000803f0000000000 count=180
```

The body inventory reports coarse compatibility classes such as `uint16-compatible-body`, `float32-compatible-body`, and `strided-body`. These are ranking hints only; they are not final stream roles.

Probe one declared stream body with side-by-side interpretations:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif-stream-body --root "C:\RIFT MODDING\Assets\Source" --id c841eb9a0ed1c95e --stream-block 23 --out "C:\RIFT MODDING\Assets\Exports\probe-nif-stream-body-c841-23.json"
```

Current targeted body proof:

```text
c841eb9a0ed1c95e stream #23 payload=72 header=29
body first16: 00010002000200010003000400050006
uint16 little-endian: 256,512,512,256,768,1024,1280,1536
uint16 big-endian:    1,2,2,1,3,4,5,6
```

This gives an evidence-backed lead that at least some compact/index-like stream bodies read more naturally as big-endian 16-bit values. Keep it as a lead until correlated with mesh vertex counts and triangle layout.

Inventory that byte-order lead across all copied NIF stream bodies:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-stream-endianness --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-stream-endianness-inventory.json" --limit 100
```

Current copied-data result:

```text
Even-length stream bodies: 31,777
mixed-u16-body: 24,272
big-endian-u16-lead: 5,551
ambiguous-small-u16: 1,800
little-endian-u16-lead: 154
Top big-endian signature:
  payload=72 first16=00010002000200010003000400050006 count=352
```

This promotes big-endian `uint16` from a one-sample clue to a ranked copied-set lead. It is still not final index semantics until mesh vertex-count and triangle-layout checks agree.

Rank big-endian `uint16` bodies as index/triangle-layout candidates:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-index-candidates --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-index-candidate-inventory.json" --limit 100
```

Current copied-data result:

```text
Big-endian uint16 lead bodies: 5,551
Big-endian triangle-aligned bodies: 5,481
Triangle-strip less-degenerate bodies: 9,712
uint16be-triangle-aligned-lead: 5,481
uint16be-index-lead: 70
Top uint16be signature:
  payload=72 first16=00010002000200010003000400050006 count=352
```

The top `payload=72` signature has `12` big-endian `uint16` triples per body and max observed index `27`, but the average naive triangle-list degenerate ratio is about `0.50`. A sliding triangle-strip interpretation lowers that family to about `0.35`, and all `352` samples are less degenerate as strips than as fixed triples. Treat this as strong index/strip/fan-style evidence, not simple triangle-list proof.

Inventory all copied NIF payloads without writing extracted model files:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\inventory-nif-copied-full.json"
```

Current copied-data NIF inventory:

```text
Inspected payloads: 40,203
NIF payloads: 5,111
Layout groups: 817
Total mined references: 19,616
Dominant version: 20.6.0.0
Minor version family also seen: 20.3.0.9
```

The largest repeated NIF layout groups are small Gamebryo meshes with consistent `NiNode`, `NiStringExtraData`, material/property, `NiMesh`, and `NiDataStream` families. `inventory-nif` stores sample asset IDs, manifest rows, PAK indexes, block usage, string counts, and reference samples for each group.

Export NIF references as normalized candidate names for `match-names`:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- mine-nif-references --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-reference-candidates.txt"
```

Current copied-data result:

```text
Reference records: 19,616
Unique candidates: 7,063
```

Run those candidates through the manifest filename hash matcher:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- match-names --root "C:\RIFT MODDING\Assets\Source" --names-file "C:\RIFT MODDING\Assets\Exports\nif-reference-candidates.txt" --out "C:\RIFT MODDING\Assets\Exports\nif-reference-name-matches.jsonl" --algorithm both --only-length-match --require-unique
```

Current copied-data match result:

```text
Candidates: 7,063
Matches: 2,567
Algorithm: FNV1
Confidence: 100 for all matched rows
Matched extension family: .dds
```

Build a direct NIF model-to-texture manifest graph from those references:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- link-nif-textures --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl"
```

Current copied-data link result:

```text
NIF payloads: 5,111
NIF references: 19,616
Texture candidates: 9,489
Recovered texture links: 9,434
Unique models linked: 3,224
Unique textures linked: 2,514
```

Sample link:

```text
model 21900d2ee4f931ca -> sky_cape_jule_skygradient.dds -> texture 607910464790649f
```

Extract a texture bundle from the graph for one linked NIF model:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-linked-textures --root "C:\RIFT MODDING\Assets\Source" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --id cc1dff6de7d25ed1 --out "C:\RIFT MODDING\Assets\Extracted\linked-textures-cc1dff"
```

Validated copied-data bundle:

```text
Links: 3
Written: 3
recovered\mushr3_c.dds
recovered\mushr3_g.dds
recovered\mushr3_s.dds
```

Extract a complete NIF bundle: model file plus linked textures:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-nif-bundle --root "C:\RIFT MODDING\Assets\Source" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --id cc1dff6de7d25ed1 --out "C:\RIFT MODDING\Assets\Extracted\nif-bundle-cc1dff"
```

Validated copied-data NIF bundle:

```text
model\001104_m253891_fnva0a67ee3_pak0311_off1393297_cc1dff6de7d25ed1.nif
textures\recovered\mushr3_c.dds
textures\recovered\mushr3_g.dds
textures\recovered\mushr3_s.dds
```

Inventory which linked NIF bundles are complete in the current copied archive set:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-bundles --root "C:\RIFT MODDING\Assets\Source" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --out "C:\RIFT MODDING\Assets\Exports\nif-bundle-inventory.json"
```

Current copied-data completeness:

```text
Graph models: 3,224
Complete bundles: 6
Incomplete bundles: 3,218
Present texture refs: 66
Missing texture refs: 9,293
```

Meaning: the model→texture graph is rich, but the current copied archive subset only contains a small number of complete model+texture bundles. Copying/scanning the missing texture archives should unlock many more complete bundles.

Plan the exact live archive chunks needed to complete missing NIF texture bundles, without copying anything from the live install:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- plan-nif-bundle-archives --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --out "C:\RIFT MODDING\Assets\Exports\nif-bundle-archive-plan.json" --limit 200
```

Current live-read-only plan:

```text
Archives scanned: 244
Missing texture assets: 2,494
Found missing texture assets in live archives: 2,494
Archive recommendations: 132
Top archive: assets.002 covers 26 missing texture assets, affects 605 models, completes 339 bundles alone
Greedy selected archives: 132
Cumulative completed bundles after greedy plan: 3,218
```

This is the current highest-leverage archive-copy map: the generated JSON ranks which `assets.###` chunks contain missing NIF-linked textures and shows how many additional complete model+texture bundles each chunk unlocks. It is intentionally read-only against the live RIFT install.

Targeted NIF bundle extraction can now use `--live-root` as a read-only fallback for missing linked textures, without copying full live archive chunks into `Source\Assets`:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-nif-bundle --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --id 011267450ef6781f --out "C:\RIFT MODDING\Assets\Extracted\nif-bundle-011267-live-fallback"
```

Validated newly completed bundle:

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

This turns the archive planner into immediate extraction value: a bundle that was incomplete with copied data only can now be completed by reading the needed texture payload directly from the live install.

The live fallback path now builds a one-pass payload index for the requested model/texture IDs instead of rescanning archive tables for each linked texture. This enabled a larger architectural bundle smoke without copying any additional archive chunks:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-nif-bundle --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --id 16ecac86a42d4d96 --out "C:\RIFT MODDING\Assets\Extracted\nif-bundle-16ecac-live-fallback"
```

Validated larger live-fallback bundle:

```text
Indexed payload IDs: 23
Copied archives scanned: 27
Live fallback archives scanned: 244
Texture links: 22
Textures written: 22
Textures written from copied archives: 0
Textures written from live fallback: 22
Textures missing from copied archives: 22
Textures missing from selected sources: 0
Texture source archives: assets.152=9, assets.187=6, assets.129=4, assets.196=2, assets.171=1
```

Batch extraction can now pull the richest linked NIF bundles in one run:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-nif-bundles --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --input "C:\RIFT MODDING\Assets\Exports\nif-texture-links.jsonl" --out "C:\RIFT MODDING\Assets\Extracted\nif-bundles-batch-top3" --limit 3
```

Validated top-3 rich bundle batch:

```text
Selected models: 3
Indexed payload IDs: 41
Copied archives scanned: 27
Live fallback archives scanned: 244
Complete bundles: 3
Texture links: 54
Textures written: 54
Textures written from live fallback: 54
Textures missing from selected sources: 0
Output files: 3 .nif, 54 .dds, 4 .json reports
```

Selected model IDs:

```text
16ecac86a42d4d96 -> 22 textures
121c431473f2cc7e -> 16 textures
1342fd262740063b -> 16 textures
```

Validated recovered-name extraction smoke:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Extracted\nif-name-recovery-smoke" --id 3c85b176865a1014 --use-recovered-names "C:\RIFT MODDING\Assets\Exports\nif-reference-name-matches.jsonl" --max-total 1
```

Result:

```text
recovered\d_id_lava_boat_02_g.dds
```

This proves the NIF-reference pipeline can recover real manifest filename hashes and write recovered filenames without breaking the existing manifest-aware fallback naming.

## Group extracted output by detected type

Use `--group-by-type` with extraction to organize dumps under `<out>\<type>\<archive>\...` instead of only `<out>\<archive>\...`.

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Extracted\grouped-archive042" --archive 42 --type dds --max-per-archive 2 --group-by-type
```

Validated layout:

```text
Extracted\grouped-archive042\dds\assets.042\000000_m381523_fnvf1908255_pak1394_off1687646_c36001c7369862bf.dds
Extracted\grouped-archive042\dds\assets.042\000001_m003870_fnv0261e7cd_pak1394_off1688639_173396928ed9daa3.dds
```

## DDS and RIFF metadata in reports

Inventory and extraction report samples now include lightweight file metadata when available.

For DDS files, reports include:

```text
Width
Height
MipMapCount
Format
```

For RIFF files, reports include:

```text
RiffType
```

Validated DDS metadata command:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-archives --root "C:\RIFT MODDING\Assets\Source" --archive 42 --type dds --max-per-archive 2 --out "C:\RIFT MODDING\Assets\Exports\inventory-archive042-metadata.json"
```

Validated result:

```text
Entry 0: dds 48x48 mipMapCount=0 format=DXT1
Entry 1: dds 48x48 mipMapCount=0 format=DXT1
```

Extraction reports include the same metadata for extracted DDS files:

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Extracted\metadata-archive042" --archive 42 --type dds --max-per-archive 1 --group-by-type
```
