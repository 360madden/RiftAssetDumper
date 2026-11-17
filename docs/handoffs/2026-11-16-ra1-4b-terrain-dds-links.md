# RA-1.4b — Proven source linkage for 13 NIF DDS references

**Date:** 2026-11-16 (America/New_York)
**Host:** AMD-DESKTOP
**Branch:** `feat/ra1-source-provenance`
**Prior HEAD:** `94e1ee8` (RA-1.4a)
**Upstream:** [RA-1.3 NIF/decompressed-source proof](2026-11-15-ra1-3-decoded-payload-hash-proof.md), [RA-1.4a code-0 controls](2026-11-16-ra1-4a-uncompressed-controls.md)

## Milestone result

**All 13 DDS filenames in the exact RA-1.3 Gamebryo NIF reference list were independently source-located and decoded as DDS.** This is a qualified source name/content relationship, **not** a claim that all 13 are actively bound to a renderer material slot, used in game, or world-positioned.

Source NIF:
- Asset ID: `c8d4fe94a8f0ae8f`
- Decoded NIF SHA-256: `39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69`
- Existing .NET `probe-nif` reports Gamebryo 20.6.0.0, 25 blocks, 10 block types; `NiTerrainNode`, `NiMesh`, `NiMaterialProperty` and `NiTexturingProperty` among them.
- All **13** names are actual `Header.References[].Value` records in the parsed NIF probe, with distinct source string indexes (not guessed from directory patterns).

For each of the 13:
1. Existing `.NET match-names` found exactly one FNV-1 + filename-length manifest record, confidence 100, and the deliberately nonexistent negative-control filename yielded no match.
2. A read-only scan of all 244 live TWAD entry tables found **one** archive entry with that ID (per tested ID); no other source entry match was observed in the installed archive corpus.
3. The raw packed entry was independently read, its SHA-1 matched the TWAD entry-table stored SHA-1, and bounded independent Python zlib decompression returned DDS bytes.
4. The decoded bytes had DDS magic, decoded SHA-1 starting with the 16-character content ID, and exact decoded length matching the **name-specific** primary-manifest row.
5. The existing .NET `probe-binary` independently agreed on DDS type and decoded length.
6. The source archive was hashed as a whole in chunks and checked for size/mtime stability. Raw game files, NIF bytes and DDS bytes were never committed.

## Verified source links

| NIF reference string | Content ID (SHA-1 prefix) | TWAD source | Primary-manifest rows sharing ID |
| --- | --- | --- | ---: |
| `world2_terrain_8960_6400.dds` | `ace0ed63fdc5e93b` | `assets.096` entry 1034 | 1 |
| `map_ec_dirt_01.dds` | `e407f97924d5f8ef` | `assets.177` entry 199 | 1 |
| `map_ec_rock_01.dds` | `fce5eedffc149f06` | `assets.191` entry 6 | 1 |
| `map_ec_grass_01.dds` | `f56409b7179cb211` | `assets.177` entry 207 | 1 |
| `map_ec_road_01.dds` | `9b7ce0c5a0dbfa26` | `assets.191` entry 4 | 1 |
| `map_ec_sand_01.dds` | `d912c1ed48657bf4` | `assets.152` entry 505 | **3** |
| `map_minspec_ground_n.dds` | `7254b6dfbb24d461` | `assets.007` entry 881 | 1 |
| `map_ec_dirt_01_n.dds` | `5aef5495da127065` | `assets.177` entry 200 | 1 |
| `map_ec_rock_01_n.dds` | `e4d4159fcd7514ac` | `assets.191` entry 7 | 1 |
| `map_ec_grass_01_n.dds` | `b676050663af9463` | `assets.177` entry 204 | **2** |
| `map_ec_road_01_n.dds` | `a4390d18a4101732` | `assets.191` entry 5 | 1 |
| `map_ec_sand_01_n.dds` | `97f9826243f5bf1c` | `assets.191` entry 8 | 1 |
| `world2_terrain_8960_6400_baked.dds` | `202d25ec6d206c7a` | `assets.002` entry 1262 | **31,324** |

The name-specific manifest record is **uniquely selected by FNV-1 plus length**, but the *content ID* need not be unique in the manifest. Exact manifest-record/PAK identity is distinct from content ID and from physical TWAD entry identity.

## Significant deduplication / first-by-ID ambiguity

Three of the 13 IDs are shared among multiple primary-manifest rows:

| Filename | Name-specific manifest row | .NET ID-first probe row | ID duplicate count |
| --- | ---: | ---: | ---: |
| `map_ec_sand_01.dds` | 179255 | 32559 | 3 |
| `map_ec_grass_01_n.dds` | 385020 | 360176 | 2 |
| `world2_terrain_8960_6400_baked.dds` | 386332 | 109 | **31,324** |

The existing `probe-binary --id` chooses the first manifest row for that ID. Its `Source.ManifestEntryIndex` / `PakIndex` therefore need **not** identify the filename-specific manifest row, even when its decoded bytes are correct. This is a concrete **consumer provenance risk**, not a decompression failure.

The baked DDS content ID maps to **31,324 distinct FNV-1 filename hashes** across **78 PAK indices** in the primary manifest. Every row reports decoded `Size=65664`. There are 31,323 rows with `CompressedSize=0` and one with `CompressedSize=112`; the live TWAD entry's compressed payload is 123 bytes. All 31,324 manifest rows have the same manifest `Hash=36b37353005d76547534b6e68ee5cedb7fbbc9c1`, which is **not** the independently decoded SHA-1.

The independently decompressed payload is a valid **128×128, 32-bit DDS** with exactly 65,536 pixel-data bytes, all `0x00`. Pillow independently decoded it as **RGB 128×128, uniformly black** (bounding box null; all per-channel extrema 0). This establishes identical blank source content shared under many names. **Whether it is used intentionally as a placeholder, zero-filled baked output, or another convention remains unknown**.

## Durable machine-readable evidence and provenance

Ignored generated report (not committed):
`Exports/ra1/ra14b/dds-link-proof.json`

SHA-256: `3a59af3e5cf06d7b43e5b9eb7c8d5307b83009bcd727e539f167fc6b3768b9a0`

Report schema: `ra1-terrain-nif-dds-link-proof/v1`

The 13 rows preserve exact NIF string index, source archive/entry and archive SHA-256, packed SHA-1, decoded SHA-1/SHA-256, decoded byte count, name-specific manifest row/FNV/PAK path, total manifest ID multiplicity, and the first-by-ID probe row. Explicit evidence flags leave renderer binding, PAK payload equality, world position and collision/traversability **unqualified**.

Other ignored inputs retained under `Exports/ra1/ra14b/`: two `dds-*-matches.jsonl` outputs, exact-ID `manifest-id-*.jsonl`, and individual `probe-*.json`. All come from existing .NET CLI / live archive reads and are locally reproducible. No RIFT archive or decoded DDS is stored in Git.

Original primary manifest SHA-256:
`6e3c79b453ce5a4caa2eb5eeddb0240c7dcad9d5d54f6ce2a0f3d532b468715c`

Source archive SHA-256 values for all six contributing TWAD archives are stored in each report row.

## Validation and interpretation

- 13/13 source names resolved to exactly one filename FNV + length match.
- 13/13 referenced content IDs each found in exactly one physical TWAD source entry across 244 installed archive tables.
- 13/13 independently decompressed (bounded zlib) into DDS data, with SHA-1 and byte-length proof, and .NET decoder agreement.
- 10/13 content IDs had one manifest row; 3/13 were ambiguous by ID and were **not** automatically promoted to a filename-specific PAK based on ID alone.
- Baked texture blank-pixel finding independently confirmed with Pillow.
- No source changes were needed for this RA-1.4b analysis. The most recent code validation in RA-1.4a was 35 focused Python tests passed; full Python suite 1,187 passed, 17 historical generated-data failures, 70 skipped. **Do not call full CI green.**

## Next optimal milestone: RA-1.5

**Fix truth-preserving manifest row selection at the CLI boundary.** Focus on `ResolveTargetEntry` and `probe-binary` behavior:
1. Permit exact `--manifest-index` to select the intended primary-manifest row, including when `--id` is also specified; reject mismatched ID/index pairs rather than silently choosing a first ID match.
2. Make duplicate-content-ID ambiguity observable in source receipts or refuse ambiguous promotion where a unique manifest record is required. Avoid changing the global parser/extraction behavior without a focused compatibility test.
3. Test a synthetic manifest with two different FNV rows sharing one ID plus a negative mismatch control. Keep single-ID and no-filter behavior unchanged.
4. Re-run one of the three real ambiguous DDS samples as the acceptance control; the returned source manifest row must match the filename-specific FNV+length selection.
5. Commit in a separate bounded code slice. Preserve all evidence under ignored `Exports/`.

Keep RiftWorld, RR2, gameplay, static pointer work, navigation and collision untouched.
