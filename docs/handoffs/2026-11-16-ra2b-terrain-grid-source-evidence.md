# RA-2b — Qualified source terrain grid; native topology still rejected

**Date:** November 16, 2026 (America/New_York)
**Host:** AMD-DESKTOP
**Repo:** C:\RIFT MODDING\Assets
**Branch:** feat/ra1-source-provenance
**Parent HEAD:** e4aa523 (RA-2a)
**Operation:** Offline/read-only analysis of one source-hash-verified NIF. No live gameplay, process memory, cross-repository edits, WorldPatch export, or game-archive writes.

## Milestone result

Decoded source Gamebryo NIF ID: c8d4fe94a8f0ae8f, TWAD assets.100 entry 0.
Decoded source SHA-256: 39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69.

**Positively qualified:** A common 129×129 grid of 16,641 local XYZ terrain positions, 16,641 corresponding unit surface normals, and 16,641 aligned UV coordinates. The matching normal field agrees with independent surface-gradient estimates at all 16,129 interior grid vertices with minimum dot product 0.99991059 and mean 0.99999815.

**Not qualified:** Original vertex-index topology, a definitive NiMesh stream-binding schema, source node-to-model-root transform, authoritative world placement, navigation or collision. Do not promote this source to RiftWorld model/scene/patch readiness.

## Independently decoded NiDataStream bodies

The exact NIF has 25 source blocks, including NiTerrainNode #0, NiMesh #2 and NiDataStream #20 through #24. The five data streams each have a 29-byte metadata header and validated declared byte lengths.

| Block | Body bytes | Tested layout | Evidence |
| --- | ---: | --- | --- |
| #20 | 196,608 | 98,304 big-endian uint16 values | Candidate triangle encoding REJECTED for topology promotion |
| #21 | 199,692 | 16,641 ROR1-encoded float3 | Grid XYZ positions QUALIFIED |
| #22 | 199,692 | 16,641 ROR1-encoded float3 | Corresponding unit normals QUALIFIED |
| #23 | 66,564 | 16,641 × 4-byte records | Packed attribute UNQUALIFIED |
| #24 | 133,128 | 16,641 ROR1-encoded float2 | Corresponding grid UVs QUALIFIED |

Existing C# float decoder applies the ROR1 byte transform; the Python diagnostic independently uses the same byte order mapping. Naive little-endian float3 decoding of #21/#22 produces implausible values; ROR1 decoding produces coherent terrain records.

Position XYZ bounds (source units):
- X: 0 to 256.0076904296875
- Y: 760.359375 to 817.453125
- Z: 0 to 256.000030517578125

Source grid X approximates 2 × column with maximum error 0.0076904296875.
Source grid Z approximates 2 × row with maximum error 0.000030517578125.
UV approximates (column / 129, row / 129) with maximum error 0.0000150809.
All 16,641 position, normal and UV sample counts agree.

For 16,129 interior positions, slope-based normals were independently formed from central differences along grid X/Z and compared to original #22 source normals. Minimum dot product 0.99991059; mean dot product 0.99999815. Strongly establishes a shared terrain surface; the normal calculation used the inferred regular-grid neighborhood and does not establish original rendered triangle topology.

## NiMesh reference stride discovery and parser gap

NiMesh #2 byte size 243; file byte offset 992. Five little-endian 32-bit integers are present 21 bytes apart:

| NiMesh-relative offset | Target NiDataStream |
| ---: | ---: |
| 134 | #20 |
| 155 | #21 |
| 176 | #22 |
| 197 | #23 |
| 218 | #24 |

This is one unique five-reference pattern in the source payload. It is a **structured reference hypothesis**, not proof of all 21-byte descriptor fields. The old C# FindNifDataStreamReferenceCandidates loop advances 4 bytes at a time and detected only aligned offset 176 → #22. The preexisting probe-nif-mesh consequently reported one linked stream, zero index pairings and zero attribute sets. A narrow negative-tested C# parser repair is recommended next. Do not globally scan all unaligned four-byte integer matches without structural gates.

## Native index hypothesis rejected

Interpreting NiDataStream #20 as consecutive big-endian UInt16 triplets yields 98,304 values and 32,768 proposed triangles, but the actual data FAILS safety gates:
- Two out-of-range index references (max observed index 16,767 vs valid vertex indices 0..16,640).
- 7,477 degenerate in-range triplets.
- Inconsistent triangle winding/normal agreement, and sequential raster-order cell pattern fails.
- The index block may have a special ordering, encoding, or auxiliary semantics; this remains unknown. A coincidental first valid triangle is insufficient for topology promotion.

The diagnostic marks nativeIndexHypothesis.promotion = rejected and originalTopologyQualified=false. No OBJ, modelGeometryId, nodeMatrix or WorldPatch is generated.

## Source-bound diagnostic tool

New Python-only tool:
scripts/audit_nif_terrain_grid.py

Reads the exact .NET NIF header report and decoded source NIF, requires the immutable source NIF SHA-256, verifies block type/offset/length gates and the unique 21-byte-reference pattern, independently checks finite position/normal/UV samples, square grid and quantitative normal agreement, and preserves the rejected native-index result and false downstream readiness.

Private generated output (ignored by Git):
Exports/ra2b/terrain-grid-diagnostic.json

Schema: ra2b-terrain-grid-evidence/v1
Output SHA-256: d41f88f3d2291e5c090f2826276a13da1998dfe754c5223a252a02cadbac22df

Repro (from the Assets root in PowerShell interactive terminal):

    $source = Get-ChildItem "Exports\ra1\decoded-assets\assets-100" -Recurse -Filter "*_c8d4fe94a8f0ae8f.nif" -File | Select-Object -First 1 -ExpandProperty FullName
    .\.venv\Scripts\python.exe scripts\audit_nif_terrain_grid.py --nif "$source" --nif-header-report "Exports/ra1/nif-header-probe-assets-100.json" --expected-nif-sha256 39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69 --out "Exports/ra2b/terrain-grid-diagnostic.json"

The diagnostic does not read process memory or modify game files.

## Validation and blockers

- 11 synthetic/negative focused Python tests passed for ROR1 float, 3×3 terrain correspondence, reference stride detection, SHA/magic/bounds mismatches, corrupt stream lengths, invalid normals/UVs, candidate index out-of-range and ignored-output confinement.
- Ruff for scripts/tests: PASS.
- mypy scripts: PASS.
- Full Python suite: **1,223 passed, 17 failed, 70 skipped**, 3 subtests passed. Same 17 historic missing-generated-artifact failures as before. Full CI remains red; do not suppress or reclassify them.
- Previous RA-1.5c .NET baseline 72/72 passed. This RA-2b slice did not edit C#.
- Consumer RiftWorld has separate uncommitted work and was not changed.

## Next ten optional follow-ups, prioritized

1. **RA-2c**: Add constrained 21-byte NiMesh stream reference detection to the C# scanner with synthetic and real negative controls; avoid blind global scanning.
2. Prove the rest of the 21-byte NiMesh record layout and how it binds usage/access/attribute semantics.
3. Compare C# stream role classifier on all five streams to independent Python source diagnostic; preserve explicit candidate roles.
4. Investigate the native #20 index-data encoding or ordering offline; do not emit triangles with invalid indices.
5. Verify source NiTerrainNode/NiMesh relationship and node-to-model transform fields; do not assume an identity matrix.
6. Repeat the exact diagnostic on an independently hashed adjacent terrain tile, retaining source-specific bounds.
7. Add a negative geometry control from an unrelated NIF lacking aligned normals.
8. Once original topology AND transforms are proven, consider one qualified model-root mesh fixture for consumer review.
9. Have RiftWorld owner review producer receipt version riftassetdumper.source-evidence/1; do not mutate its working tree.
10. Recover historical generated Flythrough/signature inputs to clear the 17 already documented full-suite failures without faking evidence.

**Go/no-go:** Source terrain XYZ/normal/UV correspondence qualified. Original topology and downstream RiftWorld model geometry **not yet ready**.
