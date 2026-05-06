# RiftAssetDumper workspace

Read-only RIFT asset archive research workspace.

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
png
jpg
ogg
lzma2
nif
```

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
