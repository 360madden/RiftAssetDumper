# Current Status — High-impact discoveries

Date: 2026-05-06

## TL;DR

| Lane | Status | Discovery |
|---|---:|---|
| Compression / LZMA2 | ✅ clarified | Full live `TWAD` archives use only compression `0` and `1`; manifest Table 0 still contains compression `2` logical PAK rows. |
| Model format | ✅ major lead | Repeated `Gamebryo File Format, Version 20.6.0.0` payloads were found and promoted to `.nif` detection. |
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

## Next best technical direction

1. Treat NIF/Gamebryo as the primary model path.
2. Test extracted `.nif` files against known NIF tooling/viewers.
3. Add NIF header parsing beyond the first line.
4. Inventory NIF version/class-name patterns by archive/PAK index.
5. Reframe LZMA2 as logical PAK reconstruction work, not TWAD entry extraction.
