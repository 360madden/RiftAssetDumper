# RA-2g — Source NiMesh semantics and independent terrain-NIF control

**Date:** November 16, 2026 (America/New_York)
**Host:** AMD-DESKTOP
**Repo:** C:\RIFT MODDING\Assets
**Branch:** feat/ra1-source-provenance
**Parent HEAD:** 8b30dce (RA-2f)
**Scope:** Read-only, source-SHA-bound inspection of two distinct Gamebryo terrain NIFs. No live-game input, debugger/process memory, RiftWorld/RR2 edits, navigation, collision claims or publication of game payloads.

## Breakthrough

The previously only partially understood five **21-byte NiMesh stream-binding records** have five explicit semantic string-table indices, not merely integer references resembling NiDataStream block numbers.

For BOTH source NIFs, record N at NiMesh #2 offset 134 + N*21 contains:

| Relative bytes | Type | Observed for both NIFs |
| --- | --- | --- |
| 0..3 | LE uint32 | NiDataStream block reference #20 through #24 |
| 4 | byte | 0 (meaning still unknown) |
| 5..8 | LE uint32 | 1 (field meaning unknown) |
| 9..12 | LE uint32 | 1 (field meaning unknown) |
| 13..16 | LE uint32 | String-table index 16 through 20 |
| 17..20 | LE uint32 | 0 (semantic ordinal candidate, not independently proven) |

Exact source semantics from the *parsed NIF header string table*, cross-checked against the raw 21-byte records:

| NiMesh-relative offset | Bound stream | String table index | Source semantic |
| ---: | ---: | ---: | --- |
| 134 | #20 | 16 | INDEX |
| 155 | #21 | 17 | POSITION |
| 176 | #22 | 18 | NORMAL |
| 197 | #23 | 19 | COLOR |
| 218 | #24 | 20 | TEXCOORD |

These records are **byte-for-byte identical across the two source NIFs** (same record SHA-256 for all five). Their source stream block contents are bound by independent SHA-256 as detailed below.

**Qualification:** stream target and semantic-name-string-index mapping are supported for the tested source pair. Other 21-byte field meanings and native index encoding are still unqualified; do not generalize this exact profile to all NIF versions without controls.

## Two distinct source NIFs

First terrain source:
- TWAD assets.100 entry 0, asset ID c8d4fe94a8f0ae8f.
- Decoded Gamebryo NIF SHA-256: 39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69.
- NiTerrainNode translation **(8960,0,6400)**, identity rotation and scale1.
- 25 source blocks, one NiTerrainNode #0, one NiMesh #2, five NiDataStream #20–#24 and 13 NiSourceTexture blocks.

Second terrain source:
- TWAD assets.100 entry **2**, asset ID **70e3afc2555b8ee6**.
- Independently re-read packed bytes, verified TWAD table SHA-1 and decoded SHA-1 prefix.
- Decoded SHA-1: 70e3afc2555b8ee6a4b7b26bb3e4cabb239221bc.
- Decoded Gamebryo NIF SHA-256: **1a65d2b3ab4a5c1521c87b473e2c957c7a3d47b3aeff20733b5627ab030c1ddc**.
- NiTerrainNode translation **(8960,0,6656)**, identity rotation and scale1; difference from first tile is +256 source units in Z.
- Also 25 blocks, one NiTerrainNode #0, one explicit NiMesh #2 child and five matching NiDataStream refs.

Both were decoded from the same installed archive, but are **different source assets with different decoded content hashes**. They are independent NIF content controls, not independent game/archive epochs or independent engine world-frame proofs.

## Matched and changing stream bodies

Each stream was independently extracted from the *source NIF bytes* using the existing 29-byte-header validation, not merely the manifest.

| Stream | Semantics | Source content comparison |
| --- | --- | --- |
| #20 | INDEX | **Identical SHA-256** in both NIFs |
| #21 | POSITION | Different SHA-256 |
| #22 | NORMAL | Different SHA-256 |
| #23 | COLOR | Different SHA-256 |
| #24 | TEXCOORD | **Identical SHA-256** in both NIFs |

Shared INDEX body SHA-256:
fab639976345b5c90f91e9de30ec2b12d842a882f23c1c89516a69e2b1fb6c07

Shared TEXCOORD body SHA-256:
2e1bebbc363b5384521f1da3c775ce1aedc2c1ac76e3c8220cac1ae1e92e39cf

This strongly supports a reusable terrain index/UV source layout. **It does not decipher** the native index encoding. The four direct BE/LE list/continuous-strip index interpretations in RA-2f remain rejected; because both tiles share exactly the same index-stream bytes, the invalid-index/degeneracy findings apply to the same raw blob in both.

## Second-tile strict normal gate (important negative control)

The pre-existing RA-2b Python grid validator and RA-2f index wrapper **refused** the second NIF, reporting disagreement between source normals and the inferred central-difference surface gradients. This failure was preserved, not bypassed or silently reclassified.

Independent bounded raw statistics show:
- The second tile has 16,641 coherent ROR1 positions and matching UV records on a 129×129 grid.
- X grid max error ~0.0075073; Z max error ~0.0000305; UV max error ~0.00001508.
- Source elevation range Y=**813.25 to 1230.625**, versus first tile Y ~760.36 to 817.45.
- All 16,641 decoded normals are approximately unit-length (magnitude 0.99998497..1.00003046).
- Among 16,129 interior gradient comparisons, dot-product mean **0.99956765**, median **0.99999239**, minimum **0.68315099**; **121** are below 0.99 and **zero** are negative.
- The largest disagreements cluster around steep gradients (sampled rows 47–53 / columns 95–108), suggesting that the exact normal-generation/geometry convention may differ there. This is a hypothesis, not a proven smoothing model.

**Do not weaken the first-tile RA-2b strict gate merely to pass the second.** Scene-node and NiMesh semantic source assertions are supported independently; *uniformly verified normal/gradient agreement* is not yet extended to the second tile.

## New bounded validator

New Python tool:
scripts/audit_nif_mesh_semantic_bindings.py

- Reads SHA-256-constrained source NIF and matching existing C# NIF header report.
- Validates NiMesh #2, its known bounded AVObject common prefix, record count 5, five 21-byte raw records, unique NiDataStream targets and actual stream byte lengths.
- Resolves each record's string-table index into INDEX/POSITION/NORMAL/COLOR/TEXCOORD; refuses missing, duplicate or changed semantic bindings.
- Preserves flag/unknown u32 fields as observed values without assigning unproven engine meaning.
- SHA-256 binds each raw 21-byte record and each decoded source stream body.
- Emits source-only metadata and explicitly marks native index encoding/triangles, world frame, RiftWorld model and full descriptor semantics as unavailable.

Generated files under ignored Exports (NOT committed):
- Exports/ra2g/decoded-second-terrain/ (exact one source NIF plus extraction receipt).
- Exports/ra2g/second-probe-nif.json, second-probe-nif-mesh.json, second-probe-nif-streams.json, second-probe-nif-scene-graph.json.
- Exports/ra2g/second-node-diagnostic.json (second parent translation evidence).
- Exports/ra2g/first-semantic-bindings.json; SHA-256 **6d9f91546c01918f99364595e61e8b5a02470b66780e5c3f93579c2a6ffac449**.
- Exports/ra2g/second-semantic-bindings.json; SHA-256 **d4ac345573b7eb0e9f52f3b8e030ee4d16959504a63088e8b0d37ca14866d94c**.

Second mesh, stream and scene graph probes ran via the existing .NET CLI using --input on the decoded hash-verified NIF, avoiding ambiguous ID-only manifest attribution.

## Tests and truth gates

- New tests: tests/test_audit_nif_mesh_semantic_bindings.py.
- **11 focused synthetic/negative tests passed**, including content-hash/record mismatches, invalid string-table semantic, unsafe count/fields, missing target/data, duplicate roles, stable INDEX/UV across changing POSITION bytes, and ignored-output confinement.
- Ruff scripts/tests: PASS; mypy scripts: PASS.
- Full Python: **1,252 passed, 17 failed, 70 skipped**; 3 subtests passed. Same 17 historical generated-artifact-dependent failures. Full CI still RED, not suppressed.
- Previous .NET baseline: 83/83 tests passed in RA-2e. No .NET source changed in RA-2g.
- All game-source files were read only; RiftWorld/RR2 untouched; game bytes not committed.

## Reproduction

From C:\RIFT MODDING\Assets, select either of the existing locally decoded NIF files under Exports/ra1 or Exports/ra2g, then run the Python validator with matching --nif-header-report and --expected-nif-sha256. Outputs must be under ignored Exports/.

Example first tile:

    $source = Get-ChildItem "Exports\ra1\decoded-assets\assets-100" -Recurse -Filter "*_c8d4fe94a8f0ae8f.nif" -File | Select-Object -First 1 -ExpandProperty FullName
    .\.venv\Scripts\python.exe scripts\audit_nif_mesh_semantic_bindings.py --nif "$source" --nif-header-report "Exports/ra1/nif-header-probe-assets-100.json" --expected-nif-sha256 39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69 --out "Exports/ra2g/first-semantic-bindings.json"

Do not publish local game files; this command writes a metadata-only report under ignored Exports/.

## Next 10 optional high-value actions

1. **RA-2h:** Investigate why source INDEX #20 is a reusable byte-identical blob but direct BE/LE uint16 triangle lists/strips fail; decode format/order using deterministic source constraints, not guessed triangles.
2. Distinguish source normal smoothing/weighted triangle normals from central-difference estimates in the steep second-tile region without weakening initial proof gates.
3. Add a third source-hash-verified terrain tile to test the repeated INDEX and TEXCOORD hashes; ideally choose an independent archive.
4. Extend C# probe-nif-mesh to report actual semantic name/index from the 21-byte binding record, replacing misleading target-index-as-string heuristic.
5. Verify whether the two unknown u32=1 fields correspond to submesh/region counts using cross-asset comparisons.
6. Inspect NiMesh primitive-type metadata at offsets 90..130, with proper schema controls and no inferred topology.
7. Explore source INDEX stream grouping or GPU packing only with quantitative negative controls for bad indices and local-neighbor constraints.
8. Recover an authoritative world-frame placement/area declaration before using node (8960,0,6400)/(8960,0,6656) translations in consumers.
9. Coordinate RiftWorld review of Assets source-evidence/1 without editing its active main working tree.
10. Recover true historical generated corpus inputs to clear the existing 17 Python CI failures without bypasses or fictional data.

**Go/no-go:** Source semantic bindings and reusable INDEX/TEXCOORD bytes supported on two distinct NIFs; steep-region normal convention and original triangle topology remain unresolved; no RiftWorld model/scene/patch promotion.
