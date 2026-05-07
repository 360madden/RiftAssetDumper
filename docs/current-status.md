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
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-blocks --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-block-inventory.json"
```

## Current safest next direction 🛡️

1. Decode repeated `NiMesh size=214` and `NiMesh size=193` families first.
2. Infer vertex/index stream roles for the top `NiDataStream` size families.
3. Use the block map to decode `NiMesh` references to `NiDataStream` blocks.
4. Open the top-3 batch outputs in external NIF/Gamebryo tooling for visual validation.
5. Keep LZMA2 work focused on manifest/PAK reconstruction rather than `TWAD` entry extraction.
