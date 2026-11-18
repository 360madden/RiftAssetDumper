# RiftAssetDumper — November 2026 Re-entry Roadmap

**As of:** 2026-11-18 (America/New_York)\
**Owner/host:** AMD-DESKTOP  
**Local checkout:** `C:\RIFT MODDING\Assets`  
**Remote:** `https://github.com/360madden/RiftAssetDumper`  
**Planning branch:** `docs/assets-reentry-2026-11`  
**Git baseline:** `7e1d5a8699545b16bb4649d90f7d082cd55e1881` (`main`, 2026-07-11)  
**Current phase:** **RA-2 — Source-only contract compatibility and bounded model-root geometry proof**
**Status:** RA-0 environment restored; RA-1.1–1.5 and RA-2a–RA-2j delivered bounded source and terrain diagnostics. Build 1179 source requalification stands. RA-2j evaluated six non-promotional native INDEX triplet offset/byte-order controls on two distinct NIFs sharing an INDEX stream, with no qualifying interpretation. Prior .NET tests 91/91 passed; current full Python 1,274 passed/17 existing generated-artifact failures/70 skipped. Original INDEX topology, world frame and RiftWorld model/scene/patch readiness remain unqualified. See [RA-2j](../handoffs/2026-11-18-ra2j-index-triplet-phase-controls.md) and [RA-2i](../handoffs/2026-11-18-ra2i-postpatch-index-structure.md).

## Decision and scope

RiftAssetDumper's highest-value role is **authoritative, reproducible archive/NIF/texture/scene-source extraction and provenance**. Do not start by implementing another path planner.

The active `C:\work\RiftWorld` project already owns world assembly, Detour queries, candidate navigation, HKX collision qualification and offline waypoint planning. RR2 owns live-process identity, execution, STOP and feedback. Assets should feed these consumers reliable **data and evidence**, without duplicating their behavior.

Historical `NM-6 M6.1` (batch navmesh generation) remains shipped; its July handoff reported 1,227 Python tests passed, 3 deliberate skips, and a real 9-polygon single-zone build. These are **historical**, not November retest results. `NM-6 M6.2/M6.3` (zone graph and multi-zone routing) are **deferred pending an explicit non-duplicative consumer requirement**. Do not infer traversability from overlapping axis-aligned bounding boxes.

### Evidence recorded during re-entry

| Check | 2026-11-15 observation | Interpretation |
| --- | --- | --- |
| Host | Workbridge reported AMD-DESKTOP 0.16.5-dev | Correct machine verified |
| Checkout | Prior `C:\RIFT MODDING\Assets` directory absent; safely cloned public GitHub `main` to that exact missing path | Source code restored; not a restoration of ignored local data |
| Git | New checkout initially clean at `7e1d5a8`; planning branch created | No original local uncommitted state recovered or overwritten |
| Python | 3.14.6 | Interpreter available |
| Python test | `python -m pytest tests/test_build_all_navmeshes.py -q` failed: `No module named pytest` | Dev dependencies not installed on this fresh checkout |
| .NET build | SDK 10.0.302; `dotnet build RiftAssetDumper.slnx --nologo` passed, zero warnings/errors | `net9.0` source builds |
| .NET tests | `dotnet test ... --no-build` aborted; Microsoft.NETCore.App 9 runtime absent (3.1.32 and 10.0.10 present) | Install compatible .NET 9 runtime side-by-side or explicitly qualify retargeting; **not a source test failure** |
| Navmesh index | `build_all_navmeshes.py check-schema` reported missing `Exports/navmesh-phase6/navmesh-index.json` | Expected ignored artifact not restored by Git |
| Consumer working tree | `C:\work\RiftWorld` was `main` ahead of origin by 66 commits with tracked/untracked work | Preserve completely; no edits in this roadmap task |

Do **not** claim the original `Source/`, `Extracted/`, `Exports/`, asset payloads, caches or old Ghidra projects were recovered. Their location, presence and freshness must be separately established.

## Delivery sequence

| Priority | Milestone | Deliverable | Exit gate |
| --- | --- | --- | --- |
| Done (with data debt) | **RA-0: restore baseline** | Isolated Python environment, process-local .NET test compatibility, 244 actual game archive chunks, focused regression fixes, detailed handoff | Focused Python 65 passed / 5 skipped; .NET 56 passed; 17 historical full-suite data failures retained as blockers, not hidden |
| P1 | **RA-1: audit real asset coverage** | Reproducible, bounded manifest/NIF/texture/scene-source coverage report, with missing and unsupported classes | Sample IDs map to archive+entry+hash; counts and limitations verified against real accessible inputs |
| P1 | **RA-2: stabilize consumer source contract** | Versioned deterministic source manifest or adapter that **reuses** existing index/schema contracts wherever possible | Schema, repeatability and corruption/negative tests; source IDs, hashes, transforms and unknowns explicit |
| P2 | **RA-3: qualify highest-value gaps** | Narrow source-evidence packets for concrete RiftWorld needs: missing mesh/texture/material links, CDR placement joins or linked HKX resource identity | At least one previously unsupported/ambiguous source relationship becomes tested or is closed negative |
| P2 | **RA-4: verify cross-project handoff** | Assets fixture + contract example that RiftWorld can consume through its existing WorldPatch/model-scene interface | Round-trip schema/hash/coordinate tests; separate consumer owner reviews integration; no silent promotion |
| P3 | **RA-5: maintenance and throughput** | Bounded CLI modularization or incremental/restartable extraction **only where measured bottlenecks justify it** | Existing commands retain outputs, focused comparisons and full CI green |
| Defer | **RA-6: legacy navmesh extension** | Explicit keep/defer/retire decision on NM-6 M6.2/M6.3/M6.4 and NM-7 | No duplicate RiftWorld planner and no unproven cross-zone connections |

### RA-0 — next immediate work

1. Record `git status -sb`, branch, commit, SDK/runtime list, dependency and disk/source inventory. Do not overwrite old game files or generate huge outputs.
2. Create local ignored `.venv`, install the repo's declared Python development dependencies, then run `python -m pytest tests/test_build_all_navmeshes.py -q`; do not install packages globally.
3. Make `net9.0` tests runnable, preferably by side-by-side .NET 9 runtime installation. Keep installed .NET 10. Do not retarget to `net10.0` merely to bypass the missing runtime.
4. Run `dotnet test RiftAssetDumper.slnx --nologo`, `ruff check scripts/ tests/`, `mypy scripts/`, focused pytest and ultimately the documented project CI check suite. Distinguish environment failures from code regressions.
5. Locate accessible RIFT archive inputs and the original generated artifact storage **without making assumptions**. Validate actual paths and read-only sample hashes. If unavailable, record that blocker and run fixture-only tests.
6. Produce a short `docs/handoffs/` baseline with exact commands, results and next source-backed target. Only then begin RA-1.

**RA-0 go/no-go:** source archive samples available and tests reproducible -> RA-1. If source is absent -> prioritize locating source/acquisition inputs, not inventing generated reports.

### RA-1 — source inventory, not broad speculative discovery

**2026-11-16 RA-1.5c checkpoint:** Fixed jointly supplied `--id` and `--fnv` to require exactly one manifest record, rather than taking the first record by content ID. Four red-to-green synthetic tests plus 72/72 .NET tests pass. On the real 31,324-row shared DDS, ID+FNV selected name-specific row 386332/PAK 1719, while a mismatched FNV failed with no output. [Handoff](../handoffs/2026-11-16-ra1-5c-joint-content-name-selector.md). **Next:** RA-2a read-only consumer-contract comparison, no cross-project edits or premature world-geometry promotion. RA-1 source coverage remains bounded to qualified samples rather than complete for all assets.

**2026-11-16 RA-1.5b checkpoint:** Opt-in `--require-unique` now rejects ambiguous ID-only binary probes while explicitly matching manifest index continues to work. Synthetic tests demonstrate 1 prior failure fixed, and the complete 68-test .NET suite passes. A real content ID shared by **31,324** manifest rows was correctly refused with strict ID-only, then accepted with its name-specific row 386332 (PAK 1719). Bare-ID legacy behavior remains intentionally unchanged and is not filename-proof. [Handoff](../handoffs/2026-11-16-ra1-5b-opt-in-unique-id-probes.md). **Next:** RA-1.5c joint ID/FNV disambiguation; afterwards narrow Assets producer-to-RiftWorld contract.

**2026-11-16 RA-1.5a checkpoint:** The C# binary-probe selector now honors exact `--manifest-index` even when `--id` is provided and rejects conflicting ID/FNV selectors before output. Five synthetic red-to-green xUnit cases and full 66-test .NET suite passed. A real duplicate-ID sand DDS correctly selected name-specific manifest row 179255, while a mismatched row was refused. Bare-ID legacy first-match behavior remains for compatibility; do not use it as filename-specific evidence. [Handoff](../handoffs/2026-11-16-ra1-5a-exact-manifest-selection.md). **Next:** RA-1.5b opt-in uniqueness refusal and real 31,324-row negative control.

**2026-11-16 RA-1.4b checkpoint:** All 13 DDS strings in the exact terrain NIF were cross-joined to unique filename FNV/length manifest rows and independently verified as DDS payloads from one TWAD source entry per content ID. Three IDs have more than one manifest row; one uniform-black DDS content ID is referenced by **31,324** distinct filename hashes across 78 PAKs. The ID-first C# probe can therefore misattribute the name-specific PAK metadata. [Proof handoff](../handoffs/2026-11-16-ra1-4b-terrain-dds-links.md). **Next:** RA-1.5 exact manifest row selection, fail-closed ID/index disagreement, synthetic duplicate-control tests. No renderer material-slot or coordinate promotion.

**2026-11-16 RA-1.4a checkpoint:** The bounded sampler now supports an optional compression-code filter without changing the unfiltered output. Scanning 244 live TWAD metadata tables found 22,422 code-0 and 241,764 code-1 entries (no other codes). Two independent code-0 payloads satisfy SHA-1 prefix and archive-table hash relationships, but the Gamebryo NIF ID occurs in two distinct primary-manifest PAK rows. Preserve the ambiguous join, the variable manifest Hash semantics, and the distinction between extra-data-only NIF and a mesh. [Proof handoff](../handoffs/2026-11-16-ra1-4a-uncompressed-controls.md). **Next:** RA-1.4b terrain NIF DDS-name source matching; no navmesh duplication.

**Progress checkpoint (2026-11-15):** RA-1.1 qualified three TWAD source archives and 12 packed-byte samples. RA-1.2 matched three exact archive IDs to one primary-manifest row each with PAK paths. RA-1.3 independently verified three decoded payloads (one terrain-related NIF with 25 parsed blocks, two DDS): source table SHA-1 equals packed SHA-1; first eight bytes of decoded SHA-1 equals archive ID; decoded length equals manifest Size. These are sample-level findings, not a universal guarantee. Manifest Hash and CompressedSize semantics remain unresolved. Next RA-1.4: test additional compression/type controls and trace exact NIF-linked DDS asset identities, then plan a bounded producer-to-RiftWorld contract.

- Inventory existing producers: `build_live_archive_index.py`, NIF probe/extraction paths, `flythrough-index` builders, material/texture linking, semantic coverage, and CDR/resource reference paths.
- Reuse existing commands and schema definitions. Build a **coverage matrix**, not a second framework: sampled asset ID, archive file, manifest/entry index, byte and content hashes, asset type, model/mesh availability, linked textures, source coordinate frame and transforms, evidence status, and missing-reason code.
- Start with a small set of **real, named target assets from RiftWorld's currently active Sanctum Watch source investigation** only if exact source IDs/paths are available. Add one unrelated terrain/model control.
- Re-run or regenerate a small ignored report with explicit input hashes. Compare counts with historical docs, and label differences as changes or unavailable data rather than regressions by assumption.
- Exit with a ranked **top five concrete extraction gaps** and one selected to fix first.

### RA-2 — useful versioned consumer output

**2026-11-18 RA-2j checkpoint:** Six source-hash-bound fixed-triplet interpretations (BE/LE × leading word offsets 0/1/2) independently scored on two NIFs sharing the same raw INDEX bytes. For BE offset 2, duplicate/zero-area candidate groups drop to zero and local-neighbor groups increase to 14,952, but 2 out-of-range groups and ~16.2k negative-normal groups remain on each tile. Because shifted windows omit edge words and have inconsistent winding, original triangles are still unqualified. Ten new tests, 33 focused tests total, Ruff/mypy and two ignored real-source receipts passed; full Python 1,274 passed, 17 old generated-artifact failures, 70 skipped. [Handoff](../handoffs/2026-11-18-ra2j-index-triplet-phase-controls.md). **Next RA-2k:** bounded window/segment/polarity study with a distinct INDEX stream as independent control before any topology promotion.

**2026-11-18 RA-2i checkpoint:** Postpatch build 1179 confirmed through shared Update Helper evidence, unchanged terrain archive hashes, unique manifest joins and successful existing NIF probes. New SHA-bound INDEX structure inventory on two NIFs reports 98,304 words, exact six words per grid cell, big-endian two outliers (16765/16767), one missing vertex ID (16640) and 7,477 degenerate fixed triplets. Two real receipts + 12 new synthetic tests pass; no original topology promotion. [Handoff](../handoffs/2026-11-18-ra2i-postpatch-index-structure.md). **Next RA-2j:** bounded index ordering hypothesis with negative controls, no parser/export promotion.

**2026-11-16 RA-2h checkpoint:** Fixed C# NiMesh stream/mesh reporting to use the semantic string-index at byte +13 of the qualified 21-byte record instead of heuristically treating stream block IDs as string indexes. Two SHA-verified source NIFs now report INDEX, POSITION, NORMAL, COLOR, TEXCOORD for streams #20–#24 with string indexes 16–20; the former false TEXCOORD string for block #20 is suppressed. Eight synthetic tests, 91/91 full .NET tests, build/format and real NIF receipts passed. No topology/world-placement promotion. [Handoff](../handoffs/2026-11-16-ra2h-native-semantic-name-report.md). **Next RA-2i:** bounded shared INDEX stream format/ordering investigation, existing negative controls intact.

**2026-11-16 RA-2g checkpoint:** Two distinct SHA-verified terrain NIFs from TWAD assets.100, source IDs c8d4fe94a8f0ae8f and 70e3afc2555b8ee6, repeat the same five NiMesh 21-byte binding records with LE target indices #20–#24 and exact NIF string-table indices 16–20 naming INDEX/POSITION/NORMAL/COLOR/TEXCOORD. Raw INDEX and TEXCOORD stream-body SHA-256 are **identical** across the files; POSITION/NORMAL/COLOR differ. Parent NiTerrainNode translations (8960,0,6400) vs (8960,0,6656) differ by +256 Z source units. The strict second-tile normal-gradient comparison failed in localized steep regions (121 of 16,129 interior normals below dot 0.99); do not silently relax RA-2b. New source-bounded semantic verifier with 11 synthetic/negative tests, Ruff/mypy pass; full Python 1,252 passed, 17 historical generated-data failures, 70 skipped. [Proof handoff](../handoffs/2026-11-16-ra2g-nimesh-semantic-two-tiles.md). **Next RA-2h:** explain shared native INDEX encoding and independent normal-convention caveat before any topology promotion.

**2026-11-16 RA-2f checkpoint:** Source-hash-bound diagnostic compared NiDataStream #20 under four direct uint16 index interpretations (BE/LE triangle lists and continuous strips). All four fail explicit original-triangle acceptance: BE list has two out-of-range triangle groups and 7,477 degenerate groups; BE continuous strip has six out-of-range groups and 13,653 degenerate groups; LE list/strip have 30,720/96,254 groups with invalid indices. The observed normal/winding disagreement also blocks promotion. Eleven synthetic tests, full Ruff/mypy and reproducible real ignored report passed. Full Python suite 1,241 passed with 17 historical generated-data failures, 70 skipped. [Proof handoff](../handoffs/2026-11-16-ra2f-native-index-hypothesis-audit.md). **Next RA-2g:** decode source NiMesh 21-byte binding fields and independently qualify a second terrain NIF. Do not generate speculative original triangles.

**2026-11-16 RA-2e checkpoint:** Repaired existing C# probe-nif-scene-graph: NiTerrainNode now participates in scene-node discovery, correct NiAVObject extra/property/collision layout is consumed before child/effect arrays, malformed counts/transform values are rejected, and unproven first-node attachment fallback is removed. The exact SHA-bound source NIF now yields one NiTerrainNode #0, one NiMesh #2, and one explicit parent-child attachment; pre-fix probe returned 0 node/0 attachment. All 83 .NET tests passed, build/format clean; no Python changes or asset output committed. [Handoff](../handoffs/2026-11-16-ra2e-native-scenegraph-hierarchy.md). **Next RA-2f:** bounded native index source encoding investigation; preserve unqualified original topology and world frame.

**2026-11-16 RA-2d checkpoint:** Independently qualified source NiTerrainNode #0 → NiMesh #2 parent/child hierarchy and local transform for the SHA-verified terrain NIF. Node translation is (8960,0,6400), identity rotation and scale1; NiMesh local transform is identity and carries 5 stream refs. Node properties/mesh properties/extra data and no collision refs parsed with source bounds. This is parent-relative source evidence, NOT an authoritative RiftWorld global frame. Bounded Python tool plus 7 synthetic negative tests; full Python suite 1,230 passed/17 historical missing-artifact failures/70 skipped, Ruff/mypy pass. [Handoff](../handoffs/2026-11-16-ra2d-terrain-node-transform-proof.md). **Next RA-2e:** fix existing C# scene-graph probe's NiTerrainNode omission and property/collision field layout, with synthetic/real acceptance before any consumer geometry integration.

**2026-11-16 RA-2c checkpoint:** Fixed C# NiMesh stream discovery to recover a constrained sequence of at least 3 distinct validated NiDataStream refs at 21-byte intervals, only on NiMesh payloads; other aligned scanning unchanged. Four focused negative tests + 76/76 full .NET tests/build/format PASS. Real 25-block terrain NIF now reports five source-linked streams and one complete 16,641-vertex position/normal/UV set, rather than one stream and zero complete sets. No index/vertex pairing, node transform or original triangles promoted. [Handoff](../handoffs/2026-11-16-ra2c-structured-nimesh-reference-recovery.md). **Next RA-2d:** narrow offline index-data and node-transform qualification.

**2026-11-16 RA-2b checkpoint:** SHA-bound Gamebryo source NIF now independently supports a 129×129 source XYZ terrain grid, 16,641 matching unit normals and 16,641 UVs; slope-derived normals align across all 16,129 interior vertices (mean dot 0.99999815). Found five NiMesh candidate stream references separated by 21 bytes, whereas the existing C# 4-byte-stride scanner reports only the aligned one. Native index-triplet hypothesis failed with two out-of-range and 7,477 degenerate triangles; **topology remains explicitly unqualified**. New bounded Python diagnostic and 11 negative-controlled tests. Full Python suite 1,223 passed/17 historical missing-artifact failures/70 skipped. [Handoff](../handoffs/2026-11-16-ra2b-terrain-grid-source-evidence.md). **Next RA-2c:** constrained C# stream binding detection with synthetic/real acceptance; no WorldPatch, model geometry ID or collision promotion.

**2026-11-16 RA-2a checkpoint:** Read-only inspection of RiftWorld `riftworld.model/1`, `riftworld.scene/1`, `riftworld.patch/1` and external model-import receipt establishes that source NIF hashes and named DDS references are not model-root geometry, source matrices or qualified scene placement. Added an Assets-owned `riftassetdumper.source-evidence/1` packet with hash-bound NIF locator, 13 independently evidenced DDS links, explicit duplicate-manifest identity, and false downstream readiness. Synthetic fixture and Draft 2020-12 JSON Schema, 25 focused pytest tests, full Ruff/mypy pass and deterministic live-packet SHA-256 verified. Full suite at RA-2a: 1,212 passed, 17 historical artifact failures, 70 skipped. [Review and handoff](../handoffs/2026-11-16-ra2a-riftworld-source-contract.md). **Next RA-2b:** limited NiMesh stream/mesh geometry and transform provenance probe; do not generate a WorldPatch or infer gameplay collision.

- First compare `RiftWorld`'s existing `riftworld.model/1`, `riftworld.scene/1`, and `riftworld.patch/1` source contracts against Assets manifests. Prefer an adapter over new redundant schemas.
- Define exact boundaries: archive/member identity, raw file hash, original NIF resource path, model geometry hash, decoded material/texture references, local-to-world matrix and frame, provenance/evidence classification and extraction version.
- Make unsupported fields **explicitly unknown**, never fabricated zero or empty-success. Separate source existence, decoded geometry, assumed placement, qualified world position and game-native collision/traversal.
- Require deterministic sorting, stable relative paths, no username/absolute-path leaks, schema conformance, reproducible emissions, negative tests for tampered hashes and absent dependencies.
- Exit when a fixture and a real bounded sample both validate, and the format is reviewable by RiftWorld without any runtime integration.

### RA-3 — narrow source-evidence breakthrough

Select exactly one highest-impact issue exposed by RA-1/RA-2. Examples:
- A placed object's source archive/NIF/CDR chain is incomplete.
- A texture/material property is represented only as a neutral fallback.
- A render resource and HKX resource require an exact source/placement join.

Use saved source inputs and read-only analysis. Do **not** reimplement RiftWorld's Havok native collision or Detour. One proof packet must include source hashes, tested identities, negative controls, accepted/rejected interpretations, and an explicit parser/export promotion decision.

### RA-4 — controlled consumer integration

- Keep this repository's output producer-side. Make no automatic changes to `C:\work\RiftWorld` or RR2.
- Provide a sample adapter contract, compatibility tests and a written integration request. A separate consumer owner can run a small RiftWorld fixture test after its working tree is reconciled.
- Success is a verified source-to-model/scene/patch linkage with stable coordinates and unambiguous unknowns, **not** an automatically traversable route.

### RA-5 — measured engineering improvement

Only when profiling identifies a bottleneck: extract one coherent CLI/parser responsibility out of the large `Program.cs` while retaining identical CLI behavior and tests, or add bounded caching/restart safety to expensive extraction. Avoid speculative rewrites, sweeping class renames, new agent frameworks and duplicated orchestration.

## Validation and publication rules

- New Python tools; no new substantive PowerShell or CMD tooling.
- Do not stage `Source/`, `Extracted/`, `Exports/`, `Assets/build/`, caches, `bin/`, `obj/`, `.venv/` or game archives. Review `git diff --cached` before committing.
- Use separate narrow branches/PRs for source/contract milestones; owner reviews truth/promotion changes. Prefer a small team with non-overlapping files, not 36 workers on one source file.
- Do not alter proof guards, source promotion flags, existing parser semantics or consumer repos simply to get a green check.
- Keep copied game data local. No live game input, memory editing or incidental desktop automation in the Assets workflow.
- For each milestone capture `host, branch, HEAD, input hashes, exact tests, output location, uncertainties, commit` in a dated handoff.
- A normal commit on its own does not prove the generated inputs or consumer functionality were restored.

## Ten optional followups (ordered)

1. Repair the isolated Python test environment.
2. Install/verify a compatible .NET 9 runtime side by side.
3. Run and record full local test and lint baseline.
4. Locate the actual RIFT archive inputs and old ignored artifacts.
5. Audit current asset-index/NIF/material producers and document reuse paths.
6. Select one evidenced Sanctum Watch source ID and terrain control.
7. Emit a small deterministic coverage matrix with source hashes.
8. Define the smallest compatible RiftWorld source-manifest adapter.
9. Add contract fixtures, schema checks, and negative provenance tests.
10. Reconsider legacy NM-6 zone adjacency only after RiftWorld demonstrates a specific missing producer capability.

**First development target after this planning commit:** RA-0 environment and source-data requalification. **Do not jump to M6.2 routing based solely on July's handoff.**
