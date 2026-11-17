# RA-2h — C# NiMesh attribute semantics from actual binding record string indices

**Date:** November 16, 2026 (America/New_York)
**Host:** AMD-DESKTOP
**Repository:** C:\RIFT MODDING\Assets
**Branch:** feat/ra1-source-provenance
**Parent HEAD:** 6209e05 (RA-2g)
**Scope:** narrow native C# NIF stream/mesh probe correction with synthetic red-to-green tests and two verified offline source NIFs. No game input, memory attach, game-file writes, RiftWorld/RR2 edits or game assets committed.

## Bug and correction

The earlier FindNifDataStreamReferenceCandidates assigned MaybeStringIndex/StringValue by comparing the *stream target block index* with string-table bounds. This is only a heuristic and can be concretely false: target NiDataStream #20 numerically matches string-table index 20 ("TEXCOORD"), but the NiMesh record at offset 134 explicitly stores string-table index 16 ("INDEX") at offset +13.

New internal ResolveConstrainedNiMeshSemanticBindings inspects exactly five distinct 21-byte-spaced NiMesh candidate records in the already validated source profile and reads their actual name string indices at byte offset +13. It qualifies semantic names only if the corresponding NiMesh source records have the expected bounded structure: flag byte 0, two observed uint32 words equal to 1, trailing uint32 equal to 0, actual target index equals the constrained stream ID, and the NIF string table resolves the ordered exact names INDEX/POSITION/NORMAL/COLOR/TEXCOORD. Unknown layouts return no semantic names; no guesses from target block IDs.

The parser preserves existing aligned stream discovery, original NIF block record positional arguments and the previous target-index heuristic for **unqualified** cases. When qualified semantic evidence is available, the misleading old StringValue and MaybeStringIndex fields are cleared, leaving new optional SemanticNameStringIndex and SemanticName fields as the qualified values.

The new optional fields are propagated into:
- Native probe-nif NifBlockReferenceCandidate metadata.
- probe-nif-streams NifStreamTargetProbe reports.
- probe-nif-mesh NifMeshBoundStreamSummary reports.
- Human-readable CLI output for qualified source records.

No native triangle index parser, source-world/placement assumption, route planner or renderer was added.

## Test-first proof

New xUnit tests:
src/RiftAssetDumper.Tests/NiMeshSemanticNameTests.cs

Eight targeted tests passed. These cover:
- Successful source name resolution independently from the numerically misleading target block IDs.
- Incorrect name index, incorrect string table value, corrupted unknown binding fields, broken sequence and short/truncated binding payload.
- A synthetic altered string-table-index location (same semantic names, different indices), proving semantic identity is not hardcoded to exact numeric string IDs.
- No promotion when a structural record requirement fails.

The pre-fix build failed because the semantic record resolver did not exist. After correction:
- **8/8 focused tests passed.**
- **91/91 complete .NET suite passed**, zero skipped.
- dotnet build: PASS, zero warnings/errors.
- dotnet format --verify-no-changes --no-restore: PASS.
- No Python code changed. Last Python suite (RA-2g): **1,252 passed, 17 historic missing-artifact failures, 70 skipped**, 3 subtests passed. Full CI still not green.

## Two independent source NIF acceptances

Both source files were revalidated by SHA-256 before running the existing .NET probe-nif-mesh command. The 21-byte records remain the same SHA-verified records from RA-2g.

| Source | Decoded NIF SHA-256 | probe-nif-mesh output SHA-256 |
| --- | --- | --- |
| assets.100 entry 0, ID c8d4fe94a8f0ae8f | 39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69 | f85fa9bbe1b795d7b833c5f69d90a0c6e9f760fc527324068e0ccb2eab7d739f |
| assets.100 entry 2, ID 70e3afc2555b8ee6 | 1a65d2b3ab4a5c1521c87b473e2c957c7a3d47b3aeff20733b5627ab030c1ddc | e303f8f7bc87936b30c7ec818aba5ac4123f8438d0f6ec661849ce9339e5ec2a |

Observed *in both outputs*:

| Source NiMesh record byte offset | Stream target | Actual binding name index | SemanticName |
| ---: | ---: | ---: | --- |
| 134 | #20 | 16 | INDEX |
| 155 | #21 | 17 | POSITION |
| 176 | #22 | 18 | NORMAL |
| 197 | #23 | 19 | COLOR |
| 218 | #24 | 20 | TEXCOORD |

Every record has MaybeStringIndex=false and no StringValue field (null omitted by the serializer); every record has a valid SemanticName and SemanticNameStringIndex. Both reports retain one complete 16,641-vertex attribute set and zero native index/vertex pairings, **not** original topology authority.

Ignored generated reports (not committed):
- Exports/ra2h/a-verified-semantic-report.json
- Exports/ra2h/b-verified-semantic-report.json

## Safety/qualification boundary

The five semantic binding name indices are directly supported by the two tested source NIF string tables. The other 21-byte record fields are checked against an observed profile but their Gamebryo engineering meanings remain unknown. The INDEX stream's **native primitive/index encoding is still unresolved**. Four naïve BE/LE index list/strip hypotheses were rejected in RA-2f; RA-2g proves the identical INDEX body is shared across both terrain tiles. Neither source-world authority, renderer-native triangle topology, game collision nor RiftWorld model/scene/patch readiness has been promoted.

## Next ten high-value follow-ups

1. **RA-2i:** Bounded offline analysis of the shared INDEX NiDataStream #20 byte layout, looking for source-supported transformations with strict negative controls.
2. Search existing assets/tooling for index stream descriptor decoders before implementing a new one.
3. Investigate repeated index body patterns and how the 98,304 u16 values relate to 16,384 terrain cells without assuming consecutive triplets.
4. Check whether any portion of the index stream uses base-offset/delta encoding or reorder tables, with invalid-index counters at every test.
5. Compare a third independently SHA-verified terrain NIF, ideally from a different archive, for reused INDEX/TEXCOORD bytes.
6. Analyze second-tile steep-region source normals versus alternate smoothing/triangle weighting conventions; preserve RA-2b strict failure.
7. Extend semantic binding decoding only after another source variant supplies nontrivial (not all-1) 21-byte record fields.
8. Consider versioned source packet enrichment with semantic name evidence, after independent RiftWorld consumer review.
9. Do not create model.obj, WorldPatch, or native triangle faces until actual source topology and source-to-world conventions are proven.
10. Restore actual historical generated artifact inputs to address the 17 pre-existing Python failures without bypasses.

**Gate:** Source NiMesh semantic-name reporting corrected in the native C# probes and validated on two independently hashed NIFs. Original triangles and world coordinate authority remain unqualified.
