# Current Status — High-impact RIFT asset discoveries 🚀

Date: 2026-05-06

## TL;DR 🧭

| Lane | Status | Current truth |
|---|---:|---|
| Compression / LZMA2 | ✅ clarified | Full live `TWAD` archive entries still use only compression `0` and `1`; compression `2` remains a manifest Table 0 logical PAK-layer problem. |
| Model format | ✅ major lead | Repeated Gamebryo payloads are now detected/extracted as `.nif` and parsed for NIF header/block/string-table evidence. |
| Filename/path recovery | ✅ proven lead | NIF string tables produced real `.dds` name candidates and high-confidence FNV1 manifest matches. |
| Model→texture graph | ✅ working | NIF references link `3,224` model assets to `2,514` unique texture manifest assets. |
| Bundle completion | ✅ newly actionable | A live-read-only archive planner found every currently missing NIF-linked texture asset and ranked the exact `assets.###` chunks needed. |

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

## Current safest next direction 🛡️

1. Use live-read fallback for targeted bundle proofing before copying large archive chunks.
2. Copy only the highest-yield archive chunks locally when repeated extraction of the same texture families becomes useful.
3. Re-run `inventory-nif-bundles` after each copy batch to verify predicted bundle-completion gains.
4. Extract a few newly complete bundles and validate them in external NIF/Gamebryo tooling.
5. Keep LZMA2 work focused on manifest/PAK reconstruction rather than `TWAD` entry extraction.
