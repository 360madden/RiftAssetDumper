# Current Status — High-impact discoveries

Date: 2026-05-06

## TL;DR

| Lane | Status | Discovery |
|---|---:|---|
| Compression / LZMA2 | ✅ clarified | Full live `TWAD` archives use only compression `0` and `1`; manifest Table 0 still contains compression `2` logical PAK rows. |
| Model format | ✅ major lead | Repeated `Gamebryo File Format` payloads were promoted to `.nif`, then parsed for block usage and NIF string-table references. |
| Filename/path recovery | ✅ new strongest lead | NIF string tables expose source-art paths and referenced texture names; copied sample yielded `19,616` mined references. |
| Live-scale scanning | ✅ improved | Compression scan and binary probe paths now avoid loading huge `assets.###` files wholesale where possible. |

## Compression truth

| Scope | Files / rows | Compression counts |
|---|---:|---|
| Copied `TWAD` entries | 40,203 non-null entries | `0=203`, `1=40000`, `2=0` |
| Full live `TWAD` entries | 263,957 non-null entries across 244 archives | `0=22422`, `1=241535`, `2=0` |
| Manifest Table 0 logical PAK rows | 2,076 rows | `0=736`, `2=1340` |

Conclusion: LZMA2 is still real, but the available evidence points to the logical PAK/manifest layer, not per-entry `TWAD` payloads.

## Gamebryo / NIF discovery

Large binary signature inventory over copied archives found this repeated header:

```text
47616d656272796f2046696c6520466f
```

ASCII:

```text
Gamebryo File Fo
```

Validated full header:

```text
Gamebryo File Format, Version 20.6.0.0
```

The dumper now classifies this payload family as:

```text
nif
```

New NIF probe/inventory support parses the Gamebryo header beyond magic-byte detection:

| Parsed field | Evidence now captured |
|---|---|
| Version/endian/user version | `20.6.0.0`, little-endian, user version `0` in the validated sample |
| Block layout | block count, block type table, per-type usage counts |
| String table | string count, max string length, raw strings |
| References | path-like source-art names and texture filenames mined from NIF strings |

Validated probe sample:

```text
NIF: Gamebryo File Format, Version 20.6.0.0
Blocks: 29; block types: 16; parsed types: 16
Block data: offset=1149 totalSize=10916 delta=8
Strings: 24; references: 4
Top block usage: NiDataStream\u00011\u000119 x6, NiFloatExtraData x3, NiIntegerExtraData x3
```

Big recovery lead: the NIF string table includes source-art references such as `art/project/.../*.ma` and texture names such as `*.dds`. These are not yet proven to be the manifest's exact original packed names, but they are real embedded names from the model payloads and should seed the filename-recovery candidate pipeline.

Full copied-set NIF inventory:

| Metric | Value |
|---|---:|
| Inspected copied payloads | 40,203 |
| NIF payloads | 5,111 |
| NIF layout groups | 817 |
| Mined NIF references | 19,616 |
| Dominant NIF version | `20.6.0.0` |
| Additional observed version family | `20.3.0.9` |

After promoting Gamebryo files to `.nif`, the unknown-binary inventory still shows a repeated geometry-like family:

```text
57e0e05710c0c0100000000007000000
```

Current copied-archive sample count in the first 5,000 unknown `.bin` payloads:

```text
geometry-candidate count=202
size range=1,440..15,536
```

Validated sample:

| Field | Value |
|---|---|
| Archive | `assets.032` |
| Entry | `202` |
| ID prefix | `21900d2ee4f931ca` |
| Manifest row | `275055` |
| FNV | `0xae05f146` |
| PAK index | `373` |
| Output extension | `.nif` |

## Commands validated

```powershell
dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- scan-compression --root "C:\RIFT MODDING\Assets\Source" --live-root "C:\Program Files (x86)\Glyph\Games\RIFT\Live" --out "C:\RIFT MODDING\Assets\Exports\live-compression-scan.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-archives --root "C:\RIFT MODDING\Assets\Source" --archive 32 --type nif --max-per-archive 3 --out "C:\RIFT MODDING\Assets\Exports\inventory-archive032-nif.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- extract-archives --root "C:\RIFT MODDING\Assets\Source" --id 21900d2ee4f931ca --max-total 1 --out "C:\RIFT MODDING\Assets\Extracted\nif-detection-regression"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- probe-nif --root "C:\RIFT MODDING\Assets\Source" --id 21900d2ee4f931ca --out "C:\RIFT MODDING\Assets\Exports\probe-nif-21900d.json"
```

```powershell
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\inventory-nif-copied-full.json"
```

## Next best technical direction

1. Treat NIF/Gamebryo as the primary model path.
2. Test extracted `.nif` files against known NIF tooling/viewers.
3. Feed mined NIF references into `match-names` as a real candidate set.
4. Inventory NIF reference folder families by archive/PAK index.
5. Reframe LZMA2 as logical PAK reconstruction work, not TWAD entry extraction.
