# RiftAssetDumper workspace

Read-only RIFT asset archive research workspace.

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
