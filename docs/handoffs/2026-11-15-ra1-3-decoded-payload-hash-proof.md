# RA-1.3 — Decoded-payload SHA-1 and NIF/DDs type proof

**Date:** November 15, 2026 (America/New_York)
**Host:** AMD-DESKTOP
**Branch:** feat/ra1-source-provenance
**Input authority:** Installed RIFT Live source archives and primary assets64.manifest
**Upstream:** [RA-1.1](2026-11-15-ra1-twad-source-provenance.md) / [RA-1.2](2026-11-15-ra1-2-manifest-id-join.md)
**Outcome:** Three-sample qualified format evidence; not a universal asset-ID law or game-world placement proof.

## What was proved

The existing .NET extract-archives / probe-binary code was used to decode **one exact asset ID per selected TWAD archive**, with --archive, --id, --max-total 1 and --max-per-archive 1. Output was written only under ignored Exports/ra1/decoded-assets/.

Independently from the decoder, Python re-read the original packed entry bytes at the previously indexed offset, rehashed the entire source archive, and computed SHA-1/SHA-256 on the extracted decoded file.

All three tested records satisfy:

1. **SHA-1 of raw packed archive-entry bytes** = the archive-table stored 20-byte SHA-1 field.
2. **First eight bytes (16 hex chars) of SHA-1 of the decoded payload** = the archive-table ID prefix.
3. **Length of decoded payload** = the primary manifest entry's Size field.
4. Decoded byte magic matches the identified file format (NIF or DDS).

The archive-table packed size and manifest CompressedSize field are **not equal** in these samples. The manifest entry's separate Hash field matches **neither** computed packed SHA-1 nor decoded SHA-1. Do not infer semantics of the manifest Hash field or equate PAK offsets with TWAD offsets.

## Real evidence table

| Source | Table ID prefix | Decoded type | Decoded bytes | Packed SHA-1 (also archive table SHA-1) | Decoded SHA-1 |
| --- | --- | --- | ---: | --- | --- |
| assets.001 entry 0 | 1a157e1f7056ab59 | DDS | 1,152 | b3404ec55d3317379d173a8494568350dac0f6e7 | 1a157e1f7056ab598f929f265108e5f53a701b04 |
| assets.100 entry 0 | c8d4fe94a8f0ae8f | NIF | 797,915 | f78e188020456ac6e1d1f8469346316b438c66df | c8d4fe94a8f0ae8fab1a4c41c2f1be19d84a3186 |
| assets.200 entry 3 | 962c30ac0b6af596 | DDS | 349,680 | 57236ffbf9bc529c01907a54edd7605339fafa0b | 962c30ac0b6af59676cc361e4ded1f0bc910a8a9 |

Additional SHA-256 values for the decoded outputs:
- assets.001 DDS: 70c3beb5fdcbf2089dcb872d8e6150a2305103462db71cf61df7d639b89bcaac
- assets.100 NIF: 39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69
- assets.200 DDS: bdd7244e763fcc3c6cc628b1f9e170616c63f9c0c7baebee5dc74cd40ae565d5

The index evidence confirms each ID matches one manifest row with a manifest PAK path (see RA-1.2). This report now adds decoded format/identity evidence, but does not assert those decoded files are physically present at the manifest's PAK offset.

## Real NIF structural control

The bounded assets.100 NIF also passed the existing .NET probe-nif on its extracted file:
- Header: Gamebryo File Format, Version 20.6.0.0
- 25 blocks; 10 block types; little endian
- Reported header warnings: none
- Scene block types include NiTerrainNode, NiMesh, NiMaterialProperty, NiTexturingProperty, NiSourceTexture and vertex-color data
- String references include world2_terrain_8960_6400.dds, map_ec_dirt_01.dds, map_ec_rock_01.dds, map_ec_grass_01.dds, and map_ec_road_01.dds.

**Interpretation:** This is a strongly evidenced terrain-related NIF asset, suitable for a source-data follow-up with RiftWorld. The DDS names are references inside the NIF, not verified resolved texture IDs. The suffix numerals are NOT a qualified global coordinate or placement. No world patch, collision, route, or in-game traversal has been promoted.

Ignored header report:
Exports/ra1/nif-header-probe-assets-100.json

## Reusable verifier

New Python tool: scripts/verify_live_sample_hash_relationships.py

It requires and SHA256-reverifies the existing RA-1.1 source report and primary manifest input against the RA-1.2 join; checks full archive SHA-256, packed entry SHA-256 and SHA-1, decoded-file SHA-1 prefix and magic, decoded size versus manifest, and unique source identity. It rejects mismatch, duplicate decoded files, missing inputs, unknown magic, and unbounded payloads.

The verifier does **not** independently implement decompression; it consumes decoded files already produced by the existing .NET decoder. Its machine-readable flags explicitly retain this limitation, unknown manifest Hash semantics, and lack of placement/collision evidence.

Command from the Assets repo root:

~~~powershell
.\.venv\Scripts\python.exe scripts/verify_live_sample_hash_relationships.py
~~~

Private generated JSON under ignored Exports/ra1/hash-relationships.json
SHA-256: fbd7eac1cc7b8a727e1d22b53093342388dd8ebdd85a6cf525b76490ba594d6d

**Observed actual result:** RA-1.3: 3 verified (1 NIF, 2 DDS), manifest hash unresolved=3.

## Test and toolchain results

- New verifier tests: **10 passed** including synthetic NIF/DDS controls, altered packed/archive/decoded evidence, mismatch checks and output confinement.
- Ruff scripts/tests: PASS.
- mypy scripts: PASS.
- Full Python pytest: **1,183 passed, 17 failed, 70 skipped**; same 17 missing historical generated-artifact dependencies as RA-0/RA-1.1. Do **not** say all CI green.
- Previous .NET baseline after RA-1.2: **61/61 tests passed**, build/format PASS; RA-1.3 adds no .NET source changes.
- Original RIFT game installation was read only. All extracted payloads, C# probe JSON and verifiers are under ignored Exports; none will be committed.

## Next development action (RA-1.4)

1. Use one or two bounded additional archive cohorts with different compression codes / asset kinds as **independent controls** for the SHA-1 prefix and table-hash relationships. Do not generalize beyond validated inputs.
2. Preserve the 3/3 qualification record as a reproducible fixture contract (without committing any game assets).
3. Audit whether the exact terrain NIF's named DDS references can be mapped to actual manifest asset IDs using the existing filename-hash/name-linking tools. Compare with authoritative RiftWorld source requirements before creating a new consumer contract.
4. Investigate the separate manifest Hash / CompressedSize semantics only with focused proof; do not assume they describe the TWAD packed entry.

RiftWorld owns world assembly, HKX collision and navigation. RR2 owns live execution. No cross-repo modifications or movement were made.
