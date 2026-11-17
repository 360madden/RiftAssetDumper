# RA-2d — Exact NiTerrainNode → NiMesh source hierarchy and local transform

**Date:** November 16, 2026 (America/New_York)
**Machine:** AMD-DESKTOP
**Repo:** C:\RIFT MODDING\Assets
**Branch:** feat/ra1-source-provenance
**Parent HEAD:** fceaf94 (RA-2c)
**Scope:** Bounded, offline read-only source NIF parsing and synthetic tests. No live gameplay, debugger/process memory, archive modifications, navigation, or cross-repository changes.

## Qualified source result

The decoded Gamebryo NIF with content ID c8d4fe94a8f0ae8f, SHA-256:
39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69

contains a NiTerrainNode (#0) with explicit **NiMesh #2 child**, a source node transform and a local NiMesh transform. The common Gamebryo NiAVObject dynamic extra-data/property/collision fields were interpreted with bounds and type guards.

| Source field | NiTerrainNode #0 | NiMesh #2 |
| --- | --- | --- |
| Block size | 106 bytes | 243 bytes |
| Name index | -1 | -1 |
| Extra-data refs | None | #3 NiColorExtraData; #4 NiIntegersExtraData |
| Flags | 0x0110 | 0x0010 |
| Translation | **(8960, 0, 6400)** | **(0, 0, 0)** |
| Rotation | 3×3 identity | 3×3 identity |
| Scale | 1.0 | 1.0 |
| Property references | #1 NiVertexColorProperty | #6 NiTexturingProperty; #5 NiMaterialProperty |
| Collision object reference | -1 | -1 |
| Child refs | **#2 NiMesh** | No child list decoded |
| Effect refs | Zero | Not applicable |
| Stream refs | Not applicable | Five targets #20–#24 |

Key source offsets in NiTerrainNode block #0:
- Translation starts at relative byte offset 14, rotation at 26, scale at 62.
- Property count 1 at 66; property reference 1 at 70.
- Collision ref -1 at 74.
- Child count 1 at 78; child reference 2 at 82; effects count 0 at 86.
- After hierarchy ends at offset 90; remaining 16 bytes are unknown NiTerrainNode-specific fields and are not interpreted.

Key source offsets in NiMesh block #2:
- Two extra-data refs at offsets 8 and 12; controller -1 at 16; flags at 20.
- Local translation at 22, rotation at 34, scale at 70.
- Property count 2 at 74; properties 6 and 5 at 78/82; collision ref -1 at 86.
- Stream count **5** at offset 130, then exactly the five 21-byte-spaced stream references at 134, 155, 176, 197, 218 (RA-2c).

Source-NIF node-chain composition is unambiguous for this single file because both transforms have identity rotations and unit scales: **parent-relative composed translation (8960, 0, 6400)**. The terrain texture name world2_terrain_8960_6400.dds independently contains the same two numbers. This is supporting source naming evidence but **not** an authoritative mapping to RiftWorld world-coordinate semantics or physical traversal.

The current C# probe-nif-scene-graph filters nodes of exact type NiNode and therefore misses the NiTerrainNode entirely; it also does not skip the NiAVObject property/collision fields before parsing child lists. This is a clear and narrow follow-up parser issue, not proof that the scene graph was previously complete.

## Reusable Python diagnostic

Source-only tool: scripts/audit_nif_terrain_node_transform.py

Reads a locally extracted NIF plus the existing C# NIF header report. Validates:
- Source file SHA-256 matches the expected original decoded content hash.
- Bounded file and block offsets, Gamebryo magic and no NIF header report warnings.
- Variable extra-data list, controller, flags, finite translation/rotation/scale, bounded properties and collision fields.
- Correct reference target block types for node properties, NiMesh properties and extras.
- An exact single NiMesh #2 child under NiTerrainNode #0, zero effects, and five source mesh-stream refs.
- Conservative transform qualification: requires identity rotations and unit scales for this source-specific composition. Refuses other transforms rather than assuming a possibly incorrect convention.
- No modelGeometryId, RiftWorld sourceWorld, source placement matrix, collision or navigation promotion.

Ignored generated evidence:
Exports/ra2d/terrain-node-transform.json

Schema: ra2d-source-nif-transform/1
SHA-256: 3d6f21ce8eae0db27bea81beb219a20288a15e3f96819db0d993849e18af7de6

Reproduce in PowerShell from the Assets repo root:

    $source = Get-ChildItem "Exports\ra1\decoded-assets\assets-100" -Recurse -Filter "*_c8d4fe94a8f0ae8f.nif" -File | Select-Object -First 1 -ExpandProperty FullName
    .\.venv\Scripts\python.exe scripts\audit_nif_terrain_node_transform.py --nif "$source" --nif-header-report "Exports/ra1/nif-header-probe-assets-100.json" --expected-nif-sha256 39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69 --out "Exports/ra2d/terrain-node-transform.json"

The tool only writes an ignored JSON report inside Assets. No RIFT or RiftWorld source file was changed.

## Tests and known limits

- **7 synthetic/negative focused Python tests passed**. Tests cover raw variable-length AVObject parsing, child type and count, props/extras, source SHA/header failures, corrupt stream count, nonidentity scale/NaN rejection, and output confinement.
- Ruff scripts/tests: PASS; mypy scripts: PASS.
- Full Python suite: **1,230 passed, 17 failed, 70 skipped**, 3 subtests passed. The **same 17 historical missing-generated-artifact failures** remain from the fresh checkout. Full CI is not green; do not remove/suppress failures.
- Previous RA-2c .NET test baseline 76/76 passed; no new C# source changes during RA-2d.

**Readiness boundary:** Validated NIF node-relative structure and composed source local transform; no independent RiftWorld source-world frame, complete native triangle topology, game collision or pathfinding proof. The parent translation is source evidence, not authorized world-route coordinate truth.

## Next ten optional actions (priority order)

1. **RA-2e:** Repair the C# scene-graph probe to include NiTerrainNode and skip AVObject property/collision refs correctly, with synthetic and real NIF acceptance.
2. Add malformed property-count and child-list controls to the C# parser to fail closed.
3. Reconcile the C# scene-graph report against the independent RA-2d JSON SHA-bound node transform.
4. Inspect the remaining 16 bytes of the NiTerrainNode #0 source block without promoting unknown fields.
5. Prove whether NiMesh #2 stream list 21-byte record fields encode primitive/topology hints; use bounded offline decoding.
6. Investigate NiDataStream #20 native index encoding/ordering; reject interpretations with out-of-range indices or degenerate triangles.
7. Compare node transforms on a second source-hash-verified terrain NIF with an independent negative control.
8. Establish a world-frame/placement contract only with authoritative RiftWorld source and CDR/placement evidence.
9. Do not produce riftworld.model/1 or WorldPatch until valid original triangle topology, model-root transform and consumer-reviewed coordinate frame exist.
10. Recover historical generated inputs to address the 17 preexisting Python integration-test failures without fabricating data.

**Go/no-go:** Source NiTerrainNode → NiMesh hierarchy and node-local transform qualified; actual scene-world mapping and original native triangle topology remain unqualified.
