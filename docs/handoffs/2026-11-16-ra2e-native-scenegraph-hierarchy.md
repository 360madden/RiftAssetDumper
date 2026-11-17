# RA-2e — C# scene-graph NiTerrainNode and explicit NiMesh parenting

**Date:** 2026-11-16 (America/New_York)
**Host:** AMD-DESKTOP
**Repository:** C:\RIFT MODDING\Assets
**Branch:** feat/ra1-source-provenance
**Parent HEAD:** a844bbc (RA-2d)
**Mode:** Small C# parser repair, test-first synthetic validation and source-hash-verified offline NIF acceptance. No live game, debugger, game-file writes, RiftWorld/RR2 edits or publication.

## Verified defect

Before RA-2e, probe-nif-scene-graph returned 0 NiNode, 1 NiMesh and 0 attachments on the known Gamebryo terrain NIF. Independent RA-2d source-byte analysis had already proven that NiTerrainNode #0 explicitly refers to NiMesh #2 as its child.

Causes:
1. The code filtered for exact NiNode and skipped NiTerrainNode.
2. Its child-list parser started directly after scale, but NiAVObject property-count, property refs and collision-ref fields occur before the children.
3. An unconditional fallback assigned otherwise-unattached meshes to the first node, creating unsupported parent evidence.

## Code correction

Modified C# source: src/RiftAssetDumper/Program.cs.

New internal ParseNifSceneGraphNodePayload helper reads bounded common NiObjectNET/NiAVObject fields, including name, dynamic extra refs, controller, 16-bit flags, finite translation/rotation, positive finite scale, properties, collision ref, children, optional sentinel and effects.

The CLI now accepts NiNode and NiTerrainNode, validates referenced block indices, and retains optional new output fields NodeTypeName, Properties, CollisionIndex and Flags. Bad field lengths/counts, non-finite transforms and invalid scales fail rather than writing misleading scene reports.

Only explicitly evidenced Children/Effects refs can now establish a mesh parent. The unconditional first-node fallback is removed.

Compatibility: nodes that terminate immediately after the child list remain valid; optional -1 effects sentinel is handled; truncated partial effects fields fail closed. Existing scene report record positional parameters remain unchanged.

## Real-source acceptance

Decoded RIFT NIF ID: c8d4fe94a8f0ae8f.
Source decoded NIF SHA-256:
39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69

**Before:** NodeCount=0, MeshCount=1, MeshesAttached=0.
**After:** NodeCount=1, MeshCount=1, MeshesAttached=1.

After source report:
- Node #0 type NiTerrainNode, translation [8960,0,6400], identity 3x3 rotation and scale 1.
- Node #0 property indices [1], collision index -1, flags 272 (0x110), explicit Children [2] and Effects [].
- Child #2 is NiMesh, and mesh #2 ParentNiNodeIndex=0.
- Fully agrees with independent RA-2d source-node transform proof.

Ignored generated reports (never committed):
- Exports/ra2e/pre-fix-scene-graph.json
- Exports/ra2e/post-fix-scene-graph.json
Post-fix report SHA-256:
880adb0514616771484825cdeabd2ee9cb0ceaa817b0905b147f93f5db4098c6

These observations prove a source-local hierarchy, not a RiftWorld world-coordinate frame, native triangles, game collision or traversal.

## Validation

New tests: src/RiftAssetDumper.Tests/NiTerrainSceneGraphTests.cs.
- 7 targeted synthetic tests passed (including variables, malformed counts/fields, optional effect count, NaN/zero scale).
- Entire .NET suite: **83 passed / 0 failed / 0 skipped**.
- dotnet build: PASS, zero warnings/errors.
- dotnet format --verify-no-changes: PASS.
- git diff --check: PASS.
- Reports confirmed ignored by Git.

No Python source changed in this milestone. Last full Python baseline (RA-2d) was **1,230 passed, 17 failed, 70 skipped** and three subtests passed. Those same 17 failures depend on unavailable historical generated artifacts. Full CI is not green.

## Reproduction from PowerShell 7

In C:\RIFT MODDING\Assets:

    $source = Get-ChildItem "Exports\ra1\decoded-assets\assets-100" -Recurse -Filter "*_c8d4fe94a8f0ae8f.nif" -File | Select-Object -First 1 -ExpandProperty FullName
    $env:DOTNET_ROLL_FORWARD = "Major"
    dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj --no-build -- probe-nif-scene-graph --input "$source" --out "Exports/ra2e/post-fix-scene-graph.json"
    Remove-Item Env:DOTNET_ROLL_FORWARD

No new PowerShell automation file was added. Runtime roll-forward is process-local in the tested commands.

## Next 10 optional actions (priority)

1. **RA-2f:** Investigate native NiDataStream #20 index semantics in short, read-only windows, with counterexamples against guessed index ordering.
2. Cross-check the five-stream parser and hierarchy against a second independently source-hash-verified terrain NIF.
3. Build end-to-end synthetic NIF controls where an explicit child is missing, ensuring no false mesh parent.
4. Decode the 21-byte NiMesh stream descriptor fields and primitive type hints, without assuming index interpretation.
5. Separate native topology from synthetic grid-derived triangles, which are not original game geometry.
6. Investigate the 16-byte NiTerrainNode suffix as candidate-only metadata.
7. Verify more node transforms including controlled nonidentity cases before generalizing.
8. Obtain consumer-authoritative source/world placement evidence before producing a model/scene.
9. Obtain RiftWorld owner review of the existing RA-2a source-only receipt, without changing RiftWorld.
10. Resolve the original 17 historical Python failures only by recovering or actually regenerating missing sources.

**Exit gate:** Native C# source parent/child and transform agree with source-bound RA-2d. Original topology and world-placement authority remain unqualified.
