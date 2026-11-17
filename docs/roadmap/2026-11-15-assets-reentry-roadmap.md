# RiftAssetDumper — November 2026 Re-entry Roadmap

**As of:** 2026-11-15 (America/New_York)  
**Owner/host:** AMD-DESKTOP  
**Local checkout:** `C:\RIFT MODDING\Assets`  
**Remote:** `https://github.com/360madden/RiftAssetDumper`  
**Planning branch:** `docs/assets-reentry-2026-11`  
**Git baseline:** `7e1d5a8699545b16bb4649d90f7d082cd55e1881` (`main`, 2026-07-11)  
**Current phase:** **RA-1 — Bounded, real archive/source-provenance audit**
**Status:** RA-0 toolchain restored; RA-1.1 TWAD sampling, RA-1.2 manifest-ID join, and RA-1.3 decoded hash/type verification shipped locally. Full-suite historical artifact-dependent failures remain (17). See [RA-0](../handoffs/2026-11-15-ra0-development-and-source-baseline.md), [RA-1.1](../handoffs/2026-11-15-ra1-twad-source-provenance.md), [RA-1.2](../handoffs/2026-11-15-ra1-2-manifest-id-join.md), and [RA-1.3](../handoffs/2026-11-15-ra1-3-decoded-payload-hash-proof.md).

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
