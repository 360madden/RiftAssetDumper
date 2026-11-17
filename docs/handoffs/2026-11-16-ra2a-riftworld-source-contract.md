# RA-2a — Assets source-provenance receipt / RiftWorld contract review

**Date:** 2026-11-16, America/New_York
**Machine:** AMD-DESKTOP
**Assets checkout:** C:\RIFT MODDING\Assets
**Assets branch:** feat/ra1-source-provenance
**Assets parent HEAD:** 7b956741e5076d86e561bb83ef6dc5c8a91e2ade (RA-1.5c)
**RiftWorld reviewed read-only:** C:\work\RiftWorld, main at 4bec5a73c7c2003f1196224732a42514cc21fad2. **RiftWorld had uncommitted changes in core.py, ROADMAP.md and other files; no consumer source files were changed here.** A later consumer integration owner must reread current versions.

## Decision

RiftAssetDumper now has a **small, versioned, producer-only source evidence packet**, not a RiftWorld model/scene/patch descriptor. Do not invent model-root geometry, transforms, world placements, or navigation readiness from raw NIF identity or texture references. The 13 texture links are source-qualified as retained evidence but are **not** renderer material-slot assignments.

The existing RiftWorld contracts already own geometry and world assembly:
- riftworld/models.py: MODEL_SCHEMA = riftworld.model/1; modelGeometryId is SHA-256 of a canonical semantic identity over **nonempty model-root vertex/triangle meshes, node matrices and representation/coordinate declarations**, *not* SHA-256 of the original NIF. Stored geometry is model.obj with its own verified SHA-256. Source names and capture details are deliberately excluded from model identity.
- riftworld/models.py: MODEL_RECEIPT_SCHEMA = riftworld.model-import-receipt/1; source evidence is stored in an **external model import receipt**, not the immutable model geometry descriptor. The current retained shared-model importer has a source locator kind observed-nif-filename and explicitly marks raw NIF hash unavailable. A new TWAD source locator is **proposed for review**, not assumed already supported by the consumer.
- riftworld/assembly.py: SCENE_SCHEMA = riftworld.scene/1. A valid scene requires model descriptor/geometry, sourceWorld authority, independent placement keys, duplicate ordinals and a 4x4 row-major matrix from model-root XYZ to source-world XYZ. Placement and coverage cannot be inferred from asset names.
- riftworld/core.py: PATCH_SCHEMA = riftworld.patch/1. WorldPatch load accepts only telara-fly or riftworld-scene providers, verifies geometry+source file hashes and scene/request context. An Assets source receipt cannot be loaded directly as a WorldPatch, must not change readiness, and is not authorization for a Detour/navmesh build.

The preferred future adapter is **Assets source packet → external model import/source receipt (consumer-reviewed) → qualified model geometry → qualified scene/placements → validated WorldPatch**, reusing RiftWorld's existing geometry/scene/patch contracts.

## Producer receipt

Builder: scripts/build_riftworld_source_receipt.py

Packet schema: riftassetdumper.source-evidence/1
Machine-checkable Draft 2020-12 JSON Schema: docs/schemas/riftassetdumper-source-evidence-v1.schema.json. Strict schema rejects unknown keys, promoted model/scene/patch geometry fields, non-false readiness flags and malformed content-hash types. It intentionally does **not** claim to validate game bytes or independently establish an existing RiftWorld descriptor.
Generated (ignored): Exports/ra2a/source-evidence.json

Reproducible generated packet SHA-256:
10ab3db433c91a743ba9d291e834a6a442c250e0e805895331b9e8048457aa76

The input proof files are earlier verified local outputs:
- Exports/ra1/live-archive-samples.json (RA-1.1)
- Exports/ra1/ra14b/dds-link-proof.json (RA-1.4b)
- Primary installed assets64.manifest (SHA-256 must match the link proof)
- Exact ignored, extracted Gamebryo NIF whose SHA-256 matches the link proof and whose SHA-1 prefix equals the TWAD asset ID.

The producer emits **only metadata and hashes**, with relative archive/PAK names and no copied game bytes or user paths. Input report SHA-256 hashes bind the retained evidence files; manifest and decoded NIF are rehashed when the command runs. **The live archive bytes are not rehashed on every RA-2a run**: their SHA-256 and sampled packed hashes come from the qualified RA-1 reports. This packet is not a new independent archive audit.

The emitted example has:
- Model source content ID: c8d4fe94a8f0ae8f; live TWAD locator Assets/assets.100 entry 0; raw decoded NIF SHA-256 39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69.
- Exact primary manifest hash: 6e3c79b453ce5a4caa2eb5eeddb0240c7dcad9d5d54f6ce2a0f3d532b468715c.
- 13 texture source links with NIF string indexes, DDS name candidates, unique filename FNV/length evidence, decoded content-ID prefix and SHA-256, live archive+entry+hash, and selected filename-specific manifest row/PAK path.
- 3 texture content IDs are **not unique manifest IDs**; selected filename rows are retained separately from first-by-content-ID rows.
- All model, scene, patch, navigation and traversal readiness flags are **false**.

### Field-level mapping (current evidence vs consumer acceptance)

| Qualified Assets packet field | Appropriate RiftWorld home | Current gate |
| --- | --- | --- |
| sourceModel.locator.archive/entryIndex/contentIdPrefix | External model-import receipt source locator / new reviewed kind | Available as source evidence, not geometry |
| sourceModel.rawSourceSha256 (decoded NIF bytes) | External model-import receipt source.rawSourceSha256 | Hash verified from source NIF; consumer importer must be extended/reviewed |
| sourceModel.locator.packedSha1/packedSha256/archiveSha256 | External receipt provenance | Captured from verified source receipts; source archive not freshly rehashed by packet run |
| textures[].decodedContentIdPrefix/decodedSha256/twad | External texture source evidence attachment | 13 qualified source bytes, but material-slot binding **unknown** |
| textures[].manifestRecord.index/filenameFnv1/pakIndex/pakPath | External name-specific manifest provenance | Name/FNV/length and content evidence qualified; PAK byte equivalence **unknown** |
| modelGeometryId / local vertices / triangles / node matrices | riftworld.model/1 | **Unavailable**: cannot substitute raw NIF SHA-256 for geometry ID |
| sourceWorld, placement key, 4x4 matrix | riftworld.scene/1 | **Unavailable**: no CDR placement or frame authority |
| patchId, geometry files, requestedBounds, coverage | riftworld.patch/1 | **Unavailable**: no qualified scene geometry |
| collision, walkability, navigation, traversal | RiftWorld / RR2 downstream evidence | **Unqualified**; must remain false/not-ready |

This is a producer-owned **intermediate receipt**, not a replacement, extension by fiat, or working import of the consumer's established schema. The consumer owner must decide whether to attach it to a new external receipt or add a compatible adapter.

## Tests and fixture

Committed synthetic input fixture: tests/fixtures/ra2a_source_evidence_synthetic.json

The fixture is explicitly marked synthetic; it uses fake hash strings and no game content. It covers one shared content ID referenced by a name-specific manifest row and intentionally leaves all downstream readiness flags false.

New test suite: tests/test_build_riftworld_source_receipt.py
- **25 passed, 0 failed** (including JSON Schema acceptance and promotion-refusal controls).
- Includes deterministic sorting, repeated-content-name preservation, contradictory manifest and NIF hashes, absent or unqualified source inputs, tampered DDS IDs, missing or unsafe PAK paths, duplicate NIF string references, and output confinement under ignored Exports/.
- CLI refuses a non-Gamebryo file claiming to be an NIF and rejects relative-PAK path traversal. Synthetic fixture is never an approved real-world geometry promotion.
- Validated the **real** 13-texture source packet against the same JSON Schema. Schema validation passed; its file SHA-256 remained exactly reproducible.

Ruff scripts/tests: PASS. mypy scripts: PASS.
Full Python suite: **1,212 passed, 17 failed, 70 skipped, 3 subtests passed**. Same 17 historical generated-file failures as RA-0 through RA-1.5. Full CI is **not** green; failures must not be erased or reclassified as successful tests.

Previous .NET baseline (not changed in this phase): 72/72 passed.

## Reproduction (AMD-DESKTOP)

Run in PowerShell from C:\RIFT MODDING\Assets:

~~~powershell
$manifest = "C:\Program Files (x86)\Glyph\Games\RIFT\Live\assets64.manifest"
$nif = Get-ChildItem -Path "Exports\ra1\decoded-assets\assets-100" -Recurse -Filter "*_c8d4fe94a8f0ae8f.nif" -File | Select-Object -First 1 -ExpandProperty FullName
.\.venv\Scripts\python.exe scripts\build_riftworld_source_receipt.py --manifest-file "$manifest" --nif-file "$nif" --out "Exports/ra2a/source-evidence.json"
.\.venv\Scripts\python.exe -m pytest tests\test_build_riftworld_source_receipt.py -q
~~~

Command above uses PowerShell interactively only to show how to reproduce; no new .ps1 tooling was created.

## Follow-up decision after RA-2a

**RA-2b recommended:** Inspect the existing Assets NIF/mesh decoder and the specific 25-block terrain NIF for **model-local vertex/triangle topology and node-transform qualification** in a bounded offline read-only experiment. Determine whether a real RiftWorld-compatible model-root mesh (not just a source NIF hash) can be produced with source proof. If not, make the blocker explicit and select one narrower descriptor/stream layout hypothesis. Do **not** write to RiftWorld, invent a sourceMatrix, claim source closure, or create a WorldPatch until a consumer owner approves the appropriate integration.

### Optional next ten actions (priority order)

1. Check existing NIF/mesh/stream CLI capabilities before implementing a new decoder.
2. Probe NiMesh block #2 in the exact source-hash-bound terrain NIF.
3. Verify vertex count, triangle indices and stream descriptor semantics independently.
4. Separate source node transforms from already-baked model-root vertices.
5. Record negative control for an incompatible stream or index layout.
6. Test a small, synthetic model-root triangle/transform fixture within Assets.
7. Compare qualified mesh fields with RiftWorld models.py without editing it.
8. Determine whether any source-to-model geometry adapter is actually justified.
9. Maintain explicit unknown placement/coordinate/collision flags until authoritative CDR evidence.
10. Reconcile the 17 historical generated-data test failures only when original artifacts are genuinely recovered.
