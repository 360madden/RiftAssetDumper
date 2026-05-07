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
dotnet run --project "C:\RIFT MODDING\Assets\src\RiftAssetDumper\RiftAssetDumper.csproj" -- inventory-nif-blocks --root "C:\RIFT MODDING\Assets\Source" --out "C:\RIFT MODDING\Assets\Exports\nif-block-inventory.json"
```

## Current safest next direction 🛡️

1. Decode only declared stream bodies after the proven 29-byte `NiDataStream` header.
2. Prioritize `big-endian-u16-lead` stream bodies for index/triangle plausibility checks.
3. Preserve both little-endian and big-endian `uint16` views while testing compact/index-like bodies.
4. Decode repeated `NiMesh size=214` and `NiMesh size=193` families first.
5. Infer vertex/index stream roles for the top `NiDataStream` payload-size families.
6. Use the block map to decode `NiMesh` references to `NiDataStream` blocks.
7. Open the top-3 batch outputs in external NIF/Gamebryo tooling for visual validation.
8. Keep LZMA2 work focused on manifest/PAK reconstruction rather than `TWAD` entry extraction.
