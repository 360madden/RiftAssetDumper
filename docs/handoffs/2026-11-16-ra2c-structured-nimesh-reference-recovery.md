# RA-2c — Constrained NiMesh 21-byte stream reference recovery

**Date:** November 16, 2026 (America/New_York)
**Host:** AMD-DESKTOP
**Repository:** C:\RIFT MODDING\Assets
**Branch:** feat/ra1-source-provenance
**Parent HEAD:** c9107f3 (RA-2b)
**Scope:** Small C# parser repair, synthetic negative tests and read-only source NIF acceptance. No RIFT gameplay, process memory, archive modification or RiftWorld/RR2 edits.

## Problem

The existing C# FindNifDataStreamReferenceCandidates scans candidate NiMesh offsets only at four-byte alignment. The SHA-bound RIFT terrain NIF (asset ID c8d4fe94a8f0ae8f) has five regularly spaced stream-reference candidates, 21 bytes apart. Four are not 4-byte aligned, so the old probe detected only NiDataStream #22, omitted #21 positions and #24 UVs, and returned 0 complete attribute sets.

## Constrained repair

A new internal FindConstrainedNiMeshStreamReferences helper detects a **run of at least three distinct validated NiDataStream IDs separated by exactly 21 bytes**, rather than all arbitrary unaligned integer values.

- Applied **only** to NiMesh blocks. All other NIF blocks keep existing four-byte-aligned scanning.
- Eligible target blocks must identify NiDataStream, fit inside the source file, have size at least 29 bytes and declare exactly the body length expected from a 29-byte stream header.
- Detection bounded to NiMesh payloads up to 16 KiB and at most 32 consecutive stream references.
- Interrupted sequences, duplicate target IDs and isolated aligned hits cannot trigger the unaligned extension.
- Existing 4-byte scanning is retained as fallback; recovered references are merged and sorted/deduplicated.
- Full 21-byte descriptor-field semantics have **not** yet been proved for every game NIF version. This is an evidence-backed, conservative source parser repair.

## Synthetic red-to-green tests

New tests: src/RiftAssetDumper.Tests/NiMeshStride21ReferenceTests.cs

Tests cover:
1. The five reference sequence 20, 21, 22, 23, 24 at offsets 134, 155, 176, 197, 218.
2. Refusal of interrupted sequences.
3. Refusal of repeated target IDs and solitary coincidental values.
4. Refusal when a target in the middle is not an eligible NiDataStream.

The initial synthetic test build failed before the helper was added. After the repair:
- **4/4** new focused tests PASS.
- **76/76** entire .NET tests PASS, zero skipped.
- dotnet build PASS, 0 warnings and 0 errors.
- dotnet format --verify-no-changes --no-restore PASS.
- git diff --check PASS.
- .NET 9 application runs using the already installed .NET 10 runtime with process-scoped DOTNET_ROLL_FORWARD=Major; no machine settings changed.

## Real NIF acceptance

Decoded source SHA-256:
39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69

Existing C# probe-nif-streams after the repair:
- candidateLinks **5**, before **1**.
- NiMesh #2 offsets 134 → NiDataStream #20, 155 → #21, 176 → #22, 197 → #23, 218 → #24.
- All five match independently scanned source offsets from RA-2b.

Existing C# probe-nif-mesh after the repair:
- candidateLinks **5**, before **1**.
- attributeSets **1**, before **0**.
- pairings (original index/vertex) **0**; topology still unqualified.
- Stream #20: uint16-compatible index *candidate*, confidence 25.
- Stream #21: position-float3-ror1-lead, confidence 75.
- Stream #22: normal-float3-ror1-lead, confidence 85.
- Stream #23: bytexvec4/u32 repeated packed-attribute candidate, confidence 25.
- Stream #24: uv-float2-ror1-lead, confidence 80.
- Complete source attribute set now includes position #21, normal #22, UV #24 and **16,641 vertices**, confidence 75.

RA-2b independently verified all 16,641 source positions/normals/UVs as a regular 129×129 terrain grid, with mean normal/gradient dot product 0.99999815. This C# repair makes the existing mesh analyzer discover the same source records.

## Strict truth boundary

The C# attributeSet output also gives an *implicit-triangle-list candidate* at confidence 40. **Do not promote that candidate**. The direct big-endian u16 interpretation of #20 in RA-2b produced two out-of-range indices and 7,477 degenerate triplets. No valid original triangles have been established, and node/world transforms and collision remain unqualified.

No OBJ/modelGeometryId/world scene, WorldPatch, navigation or game movement was generated.

Ignored outputs (not committed):
- Exports/ra2b/probe-nif-streams-mesh2-after-ref-fix.json
- Exports/ra2b/probe-nif-mesh-mesh2-after-ref-fix.json
- Earlier RA-2b terrain-grid-diagnostic.json

## Next ten optional actions

1. **RA-2d:** Investigate #20 native index layout offline with bounded, negative-tested samples.
2. Decode all 21-byte NiMesh descriptor fields sufficiently to confirm stream binding rather than just reference-index spacing.
3. Run parser on another independently verified NiMesh/NIF positive control and an unrelated negative control.
4. Add explicit malformed NiDataStream size/metadata rejection tests.
5. Verify NiTerrainNode #0 / NiMesh #2 transform and parent-child relationship with source offsets.
6. Preserve differences between source-space grid and world-space placement; never assume identity transforms.
7. Cross-check normal/UV/position grid correspondence on another terrain tile.
8. Require proper source triangle topology before any RiftWorld model descriptor or geometry hash.
9. Request separate consumer owner review of Assets source evidence after RiftWorld's active changes are reconciled.
10. Resolve the historical 17 generated-artifact-dependent Python failures only with real recovered/regenerated data.

**Gate:** Constrained NiMesh reference detection and source position/normal/UV attribute association are verified. Original source triangle topology and RiftWorld geometry/placement remain NOT qualified.
