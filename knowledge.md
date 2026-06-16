# Project knowledge

## What this project is

Read-only **RIFT** game asset archive research workspace. Reverse-engineers the game's custom binary archive format (`TWAM` manifests + `TWAD` archives) to extract and decode assets — textures (DDS), models (Gamebryo NIF v20.6.0.0), audio (OGG/RIFF), XML data, etc. The primary goal is geometry/model export (OBJ) from NIF meshes via `NiMesh` → `NiDataStream` binding analysis.

The team follows an **Aggressive Evidence Workflow** (see `docs/aggressive-discovery-workflow.md`) — small focused probes → smoke runs → full copied-set inventory → ranked evidence → documented truth → commit → next lead. All task routing follows a safety policy (see `docs/task-routing-safety-policy.md`) that reserves high/extra-high reasoning for truth, proof, guards, runtime, and commit decisions.

**Consumer app**: `C:\RIFT MODDING\RiftFlythrough` (sibling project, v1.35.0, Phase 21/50 of its own roadmap) consumes this Assets repo's output (merged.obj + PNG textures). The **Flythrough Bridge Plan** (`docs/roadmap/flythrough-bridge-plan.md`, FT-1..FT-8) is **COMPLETE** — all 7 phases delivered, FT-8 skipped (mod-injection contradicts read-only mandate).

## Quickstart

### .NET (main dumper CLI)

| Command | Purpose |
|---------|---------|
| `dotnet build RiftAssetDumper.slnx --nologo` | Build all C# projects |
| `dotnet test RiftAssetDumper.slnx --nologo` | Run xUnit tests |
| `dotnet format RiftAssetDumper.slnx --verify-no-changes` | Check formatting |
| `dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- --help` | Run CLI |
| `dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- probe-nif-scene-graph --id <hex>` | Extract NIF scene graph (transforms, parent-child) to JSON (FT-4.2) |
| `dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- link-nif-textures --root <live>` | Extract NIF→texture reference links via FNV1 hash matching (9,434 links) |
| `dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- extract-linked-textures --root <live> --input <links.jsonl>` | Extract DDS textures from archives for linked references |

### PowerShell workflow helper (thin wrapper)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/Invoke-RiftWorkflow.ps1" -Mode <Mode> [options]
```

All complex modes have been ported to Python. **No new PowerShell or CMD scripting** (see `AGENTS.md`).

### Python (scripting/discovery orchestration — primary orchestrator)

**Entry points:** `scripts/rift_workflow.py` is the **spawner** entry point (33 commands that invoke `dotnet` / `RiftAssetDumper`, protected by the orphan-process guard). `scripts/rift_read_only.py` is the **read-only** peer entry point (41 commands: guards, reports, status checks — no `dotnet` spawns, no orphan guard). Use `rift_read_only.py` for read-only commands; use `rift_workflow.py` for spawner commands.

| Command | Purpose |
|---------|---------|
| `python scripts/rift_workflow.py <command> [options]` | Run any spawner command (kebab-case). Read-only commands on this entry point print a deprecation notice to stderr pointing at `rift_read_only.py`. |
| `python scripts/rift_read_only.py <command> [options]` | Run any of the 41 read-only commands (guard-free, no `dotnet` spawns). |
| `python scripts/rift_workflow.py discovery-suite --full` | Run unified 7-step pipeline |
| `python scripts/rift_workflow.py all --full` | Run all inventory commands |
| `python scripts/rift_workflow.py decode-geometry --id <hex> --mesh-block <n> --experimental-position-source --write-obj` | Decode + export OBJ |
| `python scripts/rift_workflow.py batch-export-264` | Batch export all @264-indexed meshes |
| `python scripts/rift_workflow.py mesh-probe --id <hex> --mesh-block <n>` | Probe one mesh |
| `python scripts/rift_workflow.py attribute-extra-proof-guard --full` | Run proof guard suite |
| `python scripts/rift_workflow.py discovery-workbench --privacy-scan` | Generate discovery workbench |
| `ruff check scripts/` | Python lint |
| `mypy scripts/ --no-error-summary` | Python type check |
| `python scripts/test_rift_workflow_utils.py` | Python tests |

### Flythrough Bridge (FT) pipeline scripts (Python, `scripts/`)

| Command | Purpose | FT |
|---------|---------|:---:|
| `python scripts/dump_textures_for_flythrough.py [--limit N] [--dry-run]` | DDS → PNG conversion at scale for RiftFlythrough | FT-1 |
| `python scripts/link_flythrough_textures.py` | Texture-linking bridge: converts extracted DDS→PNG, populates `linked_textures` in flythrough-index.json | FT-textures |
| `python scripts/link_flythrough_textures.py --status` | Show texture-link coverage stats for flythrough models | FT-textures |
| `python scripts/build_texture_map.py` | Build RiftFlythrough `texture_map.js` from flythrough-index.json linked_textures (626 entries, 207 assets) | FT-textures |
| `python scripts/build_texture_map.py --copy-textures` | Also sync linked PNG textures to RiftFlythrough `textures/converted/` | FT-textures |
| `python scripts/bulk_export_for_flythrough.py run [--limit N] [--use-probe-lookup] [--resume] [--out <dir>]` | Bulk NIF → OBJ export with two-pass decode, mesh-block retry, dedup | FT-2 |
| `python scripts/bulk_export_for_flythrough.py status / verify / clean` | Inspect / verify / clean a bulk-export run | FT-2 |
| `python scripts/bulk_export_for_flythrough.py --help` | Full subcommand help | FT-2 |
| `python scripts/flythrough_plan.py` | Machine-checkable FT plan state machine with phase exit criteria | FT-all |
| `python scripts/ft6_validation.py` | FT-6 validation suite (OBJ integrity, cross-reference, byte bounds) | FT-6 |
| `python scripts/ft7_lod_detector.py` | LOD variant detector (same-NIF, MeshSize-family, descriptor-based) | FT-7 |
| `python scripts/ft8_final_manifest.py` | Unified `flythrough-index.json` combining all FT-1..FT-7 outputs | FT-8 |
| `python scripts/infer_meshsizes.py` | Pattern-matching mesh_size inference from (vertex_count, face_count) | FT-8 |
| `python scripts/build_world_placed_merge.py` | Hierarchy-aware world-placed merged OBJ builder — applies world.json transforms, builds `world-placed-merged.obj` for RiftFlythrough | FT-8 |
| `python scripts/validate_meshsize_inference.py` | Cross-validates vc_proximity mesh_size inferences against ground truth (100% high-confidence) | FT-8 |
| `pytest tests/test_bulk_export_for_flythrough.py` | Bulk export unit tests (13) | FT-2 |
| `pytest tests/test_dump_textures_for_flythrough.py` | Texture dump unit tests (3) | FT-1 |
| `pytest tests/test_ft6_validation.py` | FT-6 validation unit tests | FT-6 |
| `pytest tests/test_ft7_lod.py` | FT-7 LOD detector unit tests (23) | FT-7 |
| `pytest tests/test_flythrough_plan.py` | FT plan state machine tests | FT-all |

### Python helper scripts (direct)

| Command | Purpose |
|---------|---------|
| `python scripts/batch_sweep.py` | 4-phase OBJ integrity + candidate discovery + batch export + manifest |
| `python scripts/dedup_objs.py` | Safe SHA256-verified OBJ duplicate cleaner with dry-run mode |
| `python scripts/live_family_scanner.py` | Exhaustive batch probe of live-archive families with auto-update registry |
| `python scripts/build_export_manifest.py` | Full OBJ manifest with SHA256 hashing, provenance detection, mesh-size breakdown |
| `python scripts/rift_asset_discovery_matrix.py --skip-build` | Run discovery matrix jobs |
| `python scripts/rift_position_gap_report.py <inventory.json>` | Generate position gap report |
| `python scripts/extract_live_nifs.py` | Extract NIFs from live TWAD archives |
| `python scripts/flatten_nifs.py` | Flatten NIFs into single directory |
| `python scripts/live_inventory.py` | Live archive NIF inventory |
| `python scripts/discovery_workbench.py` | Aggregated discovery workbench |
| `python scripts/build_world_placed_merge.py` | Hierarchy-aware world-placed merged OBJ for RiftFlythrough — applies world.json Scale→Rotate→Translate transforms to 217 OBJs |
| `python scripts/validate_meshsize_inference.py` | Cross-validation of vc_proximity mesh_size inferences against ground truth |

## Architecture

### .NET CLI (`src/RiftAssetDumper/`)

- **Target:** .NET 9.0, C# with nullable enabled, implicit usings
- **Key dependency:** `SharpCompress` v0.41.0 (XZ/LZMA2 decompression)
- **Single-file entry point:** `Program.cs` (~15K lines, contains ALL command handlers inline)
- **Commands** dispatched via `AppOptions.Parse(args)` then `if/else if` chain in `Main()`
- **Key commands (inventory):** `inventory-nif-mesh-bindings`, `inventory-nif-mesh-streams`, `inventory-nif-stream-headers`, `inventory-nif-stream-bodies`, `inventory-nif-stream-endianness`, `inventory-nif-index-candidates`, `inventory-nif-blocks`, `inventory-asset-signatures`, `inventory-archives`
- **Key commands (probe):** `probe-nif-mesh`, `probe-nif-streams`, `probe-nif-stream-body`, `probe-nif-attribute-extra`, `probe-nif`, `probe-nif-scene-graph` (FT-4.2), `probe-binary`, `probe`
- **Key commands (export):** `decode-nif-geometry` (supports `--experimental-position-source`, `--write-obj`, `--export-obj`, `--out`)
- **Key commands (bundle):** `extract-nif-bundle`, `extract-nif-bundles`, `plan-nif-bundle-archives`, `link-nif-textures`, `extract-linked-textures`
- **Key commands (utility):** `hash-name`, `match-ids`, `match-names`, `list-paks`, `list-entries`, `scan-compression`, `mine-strings`
- **Tests:** xUnit in `src/RiftAssetDumper.Tests/` (55 tests, all pass — includes 4 NifSceneGraph record smoke tests for FT-4.2)

### Python scripts (`scripts/`)

- **Target:** Python 3.14 (ruff + mypy strict)
- **Roles:** discovery orchestration, workflow helpers, guard/proof-validation scripts, reports, batch sweep, FT pipeline
- **Entry point:** `scripts/rift_workflow.py` — kebab-case command dispatch with 30+ commands
- **Guards:** `scripts/rift_workflow_guards.py` — 4 proof guards (attribute-extra, usage-access-correlation, position-source-sibling-lead, residual-lead)
- **Reports:** `scripts/rift_workflow_reports.py` — 10+ report functions (gap, sibling, classifier, cluster, crosstab, workbench)
- **Utils:** `scripts/rift_workflow_utils.py` — checked_run, load_json_report, generated_output_guard, JSON access helpers
- **Batch sweep:** `scripts/batch_sweep.py` — 4-phase tool for OBJ integrity validation (SHA256, index bounds, NaN, negative indices), candidate discovery, batch export, and manifest building
- **Tests:** `scripts/test_rift_workflow_utils.py` (49) + `tests/test_bulk_export_for_flythrough.py` (13) + `tests/test_dump_textures_for_flythrough.py` (3) + `tests/test_ft6_validation.py` + `tests/test_ft7_lod.py` (23) + `tests/test_flythrough_plan.py` = 88+ Python tests
- **All 12 PowerShell complex modes fully ported to Python** — `complex_modes` set is now empty

### Proof guards (Python, `scripts/rift_workflow_guards.py`)

| Guard | Purpose | Status |
|-------|---------|--------|
| `attribute_extra_proof_guard` | Validates @264 aggregate edge/area/normal/parity/strip-structure regressions against 4 vertex-count groups | ✅ PASSED |
| `attribute_extra_sibling_proof_guard` | Validates focused sibling probes (v=128) have exact stream/block shape, index prefix, mapping candidates, stitch structure | ✅ PASSED |
| `usage_access_correlation_guard` | Validates 5 roles + 0 pairing exceptions | ✅ PASSED |
| `position_source_sibling_lead_guard` | Validates guarded leads intact for sibling families | ✅ PASSED |
| `residual_lead_guard` | Validates residual position classifier baselines (meshSize=305: 119 residuals, 5 @188 candidates) | ✅ PASSED |
| `ghidra_function_site_target_guard` | Fails closed on unsafe/duplicated FunctionSiteSurvey report paths | ✅ PASSED |
| `ghidra_pairing_non_export_guard` | Fails closed if Ghidra evidence enters decode/export paths | ✅ PASSED |
| `ghidra_attribute_candidate_guard` | Locks the current incomplete-group baseline for Ghidra attribute candidates | ✅ PASSED |
| `scene_manifest_validation_guard` | Validates all 241 stage6+stage2 scene manifests across schema, OBJ paths, world paths, transform finiteness, texture.source enum, producer version | ✅ PASSED (241/241) |

### Discovery suite (`discovery-suite` command)

A unified 7-step pipeline orchestrator in `rift_workflow.py`:

1. Mesh-binding inventory (or reuse via `--quick`)
2. Position-source gap report
3. Position-source sibling family report
4. Residual position classifier report
5. Proof guards (3 inline: usage-access-correlation, residual-lead, position-source-sibling-lead)
6. Discovery workbench
7. Summary report + structured JSON output

Supports `--quick` (reuse inventory) and `--skip-build`. Single command runs all 7 stages.

### Flythrough Bridge (FT) plan overview

`docs/roadmap/flythrough-bridge-plan.md` v2.0 — an agentic, machine-checkable plan. State lives in `Assets/build/flythrough/.state.json` (gitignored). Each phase has its own handoff in `docs/handoffs/2026-MM-DD-ft{N}-exit.md`.

| Phase | Topic | Status |
|-------|-------|:---:|
| FT-1 | DDS → PNG texture pipeline at scale | ✅ DONE (12,954 textures, 83s, 19 MB) |
| FT-2 | Bulk NIF → OBJ export | ✅ DONE (pipeline ships; 7/56 on probe-lookup subset) |
| FT-3 | Per-OBJ metadata sidecar (`asset-mesh-manifest-v1`) | ✅ DONE (schema + emitter) |
| FT-4 | Scene graph / world placement (KEYSTONE) | ✅ DONE (`probe-nif-scene-graph`, `world.json`, 50-NIF pilot, 65% coverage) |
| FT-5 | Single-command pipeline integration | ✅ DONE (`flythrough_plan.py` state machine) |
| FT-6 | Flythrough-specific validation suite | ✅ DONE (OBJ integrity + scene graph + cross-reference + byte bounds) |
| FT-7 | Zone boundaries, LOD variants | ✅ DONE (7→10 high-confidence LOD groups, 193/217 assets classified) |
| FT-8 | Mod-replacement bridge (optional, safety-gated) | ⏭️ SKIPPED (contradicts read-only mandate) |

### Key directories (gitignored)

| Path | Contents |
|------|----------|
| `Extracted/` | Decompressed payload dumps (NIF, DDS, etc.) and NIF texture bundles |
| `Exports/` | JSON/JSONL reports, inventories, matrices, and OBJ exports |
| `Assets/build/flythrough/` | FT pipeline output: `objs/`, `textures/converted/`, `flythrough-index.json`, `world-placed-merged.obj`, `lod-manifest.json`, `scene-graph-manifest.json`, `.state.json`, `evidence/ft{N}.{M}/`, `riftflythrough/transform_loader.js` |
| `RecoveredNames/` | Generated filename matches (`recovered-names.jsonl`) |
| `Candidates/` | Candidate filename lists for hash matching |
| `docs/handoffs/` | Session handoff docs (AI-agent context resumption) |

> **Note:** `Source/` (local copied game files, 166MB) was deleted 2026-06-06. All Python scripts now default to the live game path (`C:/Program Files (x86)/Glyph/Games/RIFT/Live`). The live archive (26GB, 244 archive files, 263,957 entries) is used directly.

### Data flow

1. **Manifest** (`TWAM`) → parse header + tables (PAK listing, entry table) from live game directory
2. **Archive** (`TWAD`) → parse entry table, decompress (zlib/LZMA2/raw), detect type
3. **NIF probe** → parse Gamebryo block structure, extract `NiMesh` → `NiDataStream` bindings
4. **Geometry decode** → decode positions/normals/UVs from float32 or uint16-packed streams
5. **OBJ export** → behind `--experimental-position-source` (fallback) or `--export-obj` (attribute-set @264) flags
6. **FT-4:** scene graph probe → per-NIF `world.json` with NiNode transforms + parent/child tree
7. **FT-8 closure:** `build_world_placed_merge.py` → hierarchy-aware world transform accumulation → `world-placed-merged.obj` for RiftFlythrough

All operations read directly from the live game install (see Key directories note above).

### CI pipeline (`.github/workflows/ci.yml`)

Four parallel jobs (3 on `windows-latest`, 1 on `ubuntu-latest`) + 1 final summary job:

- **.NET job:** `dotnet build`, `dotnet format --verify-no-changes`, `dotnet test` (pwsh shell)
- **Python job:** syntax check, `ruff check`, `mypy --no-error-summary`, Python tests (`py_compile` + pytest)
- **Orphan Guard Regression job:** `test_rift_workflow_orphan_guard*`, `test_bulk_export_orphan_guard`, `test_rift_read_only_no_spawn`
- **Docs Lint job:** `markdownlint-cli2` via `DavidAnson/markdownlint-cli2-action@v19`
- **Summary job:** aggregates all 4 results (Ubuntu); fails if any job fails
- **Triggers:** `push` to main, `pull_request` to main, and `workflow_dispatch` (added 2026-06-13 for manual CI re-runs via `gh workflow run`)

### Current project state (Flythrough Bridge Plan COMPLETE)

- **350 OBJ files, 270 faced, 80 position-only, 30,864 faces, 23,421 vertices across 30 MeshSize families. 217 unique asset IDs. 0 structural issues. 0 unexported candidates remain.**
- **FT-1 ✅** — 12,954 DDS → PNG converted, 83s wall-clock, 19MB output, loaded into RiftFlythrough cleanly
- **FT-2 ✅** — `bulk_export_for_flythrough.py` pipeline ships; 7/56 (12.5%) on probe-lookup subset; two-pass decode (export-obj → experimental), mesh-block retry chain `[6,7,8,9,10,27,31,25,17,0]`, atomic manifest writes, dedup, resume via `.state.json`
- **FT-3 ✅** — `asset-mesh-manifest-v1.schema.json` (20+ fields) + sidecar emitter integrated into bulk exporter; FT-4/FT-7 fields pre-wired as nulls
- **FT-4 ✅** — `probe-nif-scene-graph` C# command shipped (NiNode transforms, parent-child tree, mesh attachment map); `scene-graph-v1.schema.json`; 50-NIF pilot; **217/217 assets (100%) have world.json** with `ParentNiNodeIndex` mesh-parent references; `build_world_placed_merge.py` hierarchy-aware world transform accumulation (Scale→Rotate→Translate) identifying 4 assets with non-identity transforms; record types smoke-tested (4 new xUnit tests)
- **FT-5 ✅** — `flythrough_plan.py` state machine with phase exit criteria, `.state.json` transitions
- **FT-6 ✅** — `ft6_validation.py` suite: OBJ integrity (SHA256, bounds, NaN), scene-graph cross-reference, byte bounds; 100% pass
- **FT-7 ✅** — `ft7_lod_detector.py` 3-axis LOD detector: **10 high-confidence MeshSize-family groups**, 1 same-NIF chain (158x reduction), 2 descriptor LOD groups; **193/217 (88.9%)** assets classified after mesh_size enrichment
- **FT-8 ⏭️** — Skipped: mod-injection bridge contradicts read-only mandate. `ft8_final_manifest.py` built unified `flythrough-index.json` (118.5 KB, 217 assets, 100% cross-referenced) as plan closure artifact
- **MeshSize enrichment** — `infer_meshsizes.py` boosted probe lookup from 176→318 entries, **100% coverage** (43 exact matches, 87 VC-proximity, 12 sibling-pair)
- **Live archive** (26GB, 244 files, 263,957 entries) used directly — `Source/` deleted (166MB reclaimed). All Python scripts default to live game path.
- **Ghidra proof lane complete** (3/3 steps): parser field proof guard, sample-byte agreement (184/184 blocks pass), narrow parser patch (`--ghidra-body-offset` flag wired through all 4 body-slicing sites)
- - All 9 proof guards PASSED on full inventory
- Endian-analysis root-cause fix (Stage 9): `PairCompatibleMeshes` restored to **1,949**
- Triangle fan fallback implemented: pos-only OBJs now get approximate faces via `--experimental-position-source --write-obj`
- Discovery suite: 6/7 steps functional against live archive (position-source-gap-report needs inventory rebuild)
- **Final delivery**: `flythrough-index.json` — single consumable file linking OBJs, world.json, LOD, MeshSize, **textures** (207/217 assets, 626 linked PNGs) for RiftFlythrough Phase 21
- **Texture discovery pipeline**: `link-nif-textures` → 9,434 NIF→texture links → filtered to 650 flythrough links (222 unique DDS) → `extract-linked-textures` (222 DDS extracted, 0 failures) → `link_flythrough_textures.py` (DDS→PNG conversion, populates `linked_textures` in flythrough-index.json)
- **RiftFlythrough bridge**: `build_world_placed_merge.py` → `world-placed-merged.obj` (2.5MB, 72,976 lines, 217 assets, 4 non-identity transforms) copied to `C:\RIFT MODDING\RiftFlythrough\merged.obj`; `transform_loader.js` (4KB) copied to `RiftFlythrough/js/` for runtime manifest-based transform application
- CI green: build 0 errors, dotnet test 55/55 (C#), pytest 332/332 (Python), ruff 0, mypy 0, dotnet format clean, markdownlint 233 files, generated-output guard clean
- **CI green sequence (2026-06-13, 4 commits)**: `910b168` (MD032 docs fix) → `88af1a9` (test1 fixture) → `ac7db4c` (test2 fixture) → `4187892` (test3 fixture) resolved pre-existing Python test fixture gaps masked by the Docs Lint failure. The `POST50_POSITION_SOURCE_REPORTS` registry in `rift_workflow.py:6235` grew from 10 to 11 reports (added `mesh329-family-attribute-role-matrix.json` from Phase 1 M1.1); 3 affected test files patched. Handoff: `docs/handoffs/2026-06-13-ci-green-4-commit-sequence.md`.
- **Documentation alignment (2026-06-13, 6 commits)**: `a1ab091` (6 draft- handoff filenames finalized) → `31b1839` (stale note fixes) → `210624d` (7 handoff deliverables ticked) → `ef7525b` (19 convention/CI items ticked) → `673a3d2` (18 CI/build/format items ticked) → current. Total: 44 `[ ]` → `[x]` across 20+ planning docs. 1 intentional forward reference (`2026-06-12-cycle-2-phase-1-exit.md` in cycle-2 prompt template).

## Conventions

- **Formatting:** `dotnet format` (C#), `ruff` (Python)
- **Coding style:** 4-space indentation, `Allman` braces in C#, semicolons required
- **NIF identifiers:** Use hex IDs (16-char lowercase) — never truncate to 8 chars ambiguously
- **Redaction:** CLI redacts `%USERPROFILE%` paths by default; use `--no-redact-paths` for debugging
- **Records:** All data types are C# `record` types (immutable, positional) — never `class` for DTOs
- **JSON output:** JSON Lines (`.jsonl`) for row data, single JSON (`.json`) for reports
- **Geometry exports:** Behind `--experimental-position-source` (0-attribute-set fallback — normals+UVs+positions with fan faces) and `--export-obj` (attribute-set @264 indexed path — degenerate-bridge strip faces) gates; never claim OBJ export without proof
- **LZMA2:** Only XZ-framed supported; raw LZMA2 is intentionally unhandled
- **Name recovery:** Uses FNV1/FNV1a hashing with confidence scoring; recoveries need `--use-recovered-names`
- **NIF block analysis:** 29-byte `NiDataStream` header invariant; roles classified as `*-ror1-lead`, `*-u16be-*`, etc.
- **CI:** Runs both .NET (build, format, test) and Python (ruff, mypy, test) on push/PR
- **Command naming:** Kebab-case for Python CLI (e.g., `mesh-bindings`), PascalCase for PS mode names (e.g., `MeshBindings`)
- **OBJ face generation:** Uses degenerate-bridge triangle-strip walking with raw-zero-based (+1 OBJ) indexing for @264 indexed meshes; pairing-based for 0-attribute-set meshes with index streams
- **Schemas:** JSON Schema 2020-12, `additionalProperties: false`, `const` for `SchemaVersion` discriminators, `^[0-9a-f]{16}$` for NIF hashes. New schemas go in `docs/schemas/`.
- **Commit prefix convention:** `ft{N}.{M}: <short description>` for FT-plan work; `docs: <title>` for handoffs; `ft2.5: <title>` style for phase-exit commits
- **No new PowerShell/CMD scripts** — Python only (see `AGENTS.md`)
- **FT plan state:** `Assets/build/flythrough/.state.json` (gitignored) is the single source of truth for "what's next"
- **FT evidence:** Every FT step writes evidence to `Assets/build/flythrough/evidence/ft{N}.{M}/`

## Key discoveries

### NiDataStream header

Every `NiDataStream` block in the copied set follows: `blockSize - firstUInt32 == 29` (31,777/31,777 blocks). The first uint32 is the declared payload byte count.

### Stream endianness

After the Stage 9 endian-analysis fix (line 9322: `ReadUInt16BigEndian` → `ReadUInt16LittleEndian`):

- **5,551** big-endian u16 lead bodies
- **24,272** mixed-u16 bodies
- **1,800** ambiguous-small-u16 bodies
- **154** little-endian u16 lead bodies

### Top stream roles (full copied-set, 5,507 NiMesh blocks)

| Role | Count |
|---|---|
| `uv-float2-ror1-lead` | 4,633 |
| `normal-float3-ror1-lead` | 4,167 |
| `index-u16be-strip-lead` | 2,101 |
| `position-float3-ror1-lead` | 210 |
| `index-u16be-list-lead` | 112 |

### @264 explicit-index extra streams

The strongest positive proof lead: 5 meshes at meshSize=297 with `@264/#15` extra streams, `index-u16be-strip-lead`, raw-zero-based mapping preferred (5/5), degenerate-bridge-stitch strip structure. All 5 exported to OBJ via `batch-export-264`.

### meshSize=305 stream@188 residual-position dead end

Deep probe of 5 payload variants (96, 180, 192, 288, 396) at stream@188 found magic 43606 (0xAA56) u16le pattern driving 0.9444 plausible rating — but float32 decode produces denormal garbage (10⁻²⁷ to 10⁻³⁹). **Not position data.** All 8 target rows failed strict classifier (below 0.95 threshold). Remains candidate-only ranking evidence; export blocked.

### Position-source sibling families

5 shared-source sibling groups confirmed:
| Mesh size | Groups | Decision |
|---|---|---:|
| 329 | 23 | repeated source-binding family |
| 305 | 15 | repeated source-binding family |
| 321 | 11 | repeated source-binding family |
| 325 | 1 | shifted sibling position-source clue |
| 329 | 1 | shifted sibling position-source clue |

### Compression truth

| Scope | Count | Compression |
|---|---|---:|
| Full live TWAD entries | 263,957 | `0=22422`, `1=241535`, `2=0` |
| Manifest Table 0 PAK rows | 2,076 | `0=736`, `2=1340` |

LZMA2 is real in the manifest/PAK layer but not in ordinary TWAD entry payloads seen so far.

## Gotchas

- `Program.cs` is extremely large (~15K lines) — prefer targeted `str_replace` edits over rewrites
- All C# commands run via string matching in `Main()` — adding a new command requires adding an `if` block (see `probe-nif-scene-graph` precedent in `Program.cs`)
- The solution file is `.slnx` (new XML format) — not `.sln`
- `Source/` (local copied game files) has been **deleted** — all scripts read directly from the live game install at `C:\Program Files (x86)\Glyph\Games\RIFT\Live` (read-only)
- Python scripts are all in `scripts/` root (no subpackages) with flat module structure
- `ruff` ignores E501 (line length) since it's enforced by formatter; several naming conventions relaxed for PS→Py ports
- Always use `--experimental-position-source` for meshes without direct attribute sets
- The `@264/#15` extra-stream pattern is the strongest geometric index lead for mesh faces
- The `Invoke-RiftWorkflow.ps1` wrapper translates legacy PS mode names to kebab-case Python commands
- `dotnet build` is implicit for most workflow commands unless `--skip-build` is passed
- The `generated_output_guard` runs at the start of every Python command — it checks that no generated/ignored files have been accidentally committed
- `.agents/` directory contains Codebuff agent type definitions (`types/agent-definition.ts`, `types/tools.ts`, `util-types.ts`) — the schema types for building custom Codebuff agents
- `batch_sweep.py` is a standalone 4-phase script (not a workflow command) for OBJ integrity, candidate discovery, batch export, and manifest generation
- `bulk_export_for_flythrough.py` two-pass decode: tries `--export-obj` (attribute-set @264 indexed, faced) first; on "no attribute sets" stderr, falls back to `--experimental-position-source --write-obj` (fan faces, pos-only)
- The bulk exporter's mesh-block retry chain `[6, 7, 8, 9, 10, 27, 31, 25, 17, 0]` runs when the probe-lookup value fails with "not found" — the first successful non-"not found" response wins
- `Assets/build/flythrough/.state.json` is gitignored but never deleted — it's the resume token for the FT plan
- `asset-mesh-manifest-v1.schema.json` requires `nif_hash` (`^[0-9a-f]{16}$`) and `obj_sha1` (`^[0-9a-f]{40}$`) patterns
- FT-2 probe-lookup subset success rate is data-limited (probe lookup built from deleted `Source/`), not pipeline-limited — pipeline proven functional
- For multi-mesh NIFs, the `probe-nif-scene-graph` command may emit child refs into both `Children` and `Effects` lists — the parser walks both and resolves to the block type
- `world.json` mesh-parent relationships use `ParentNiNodeIndex` (direct node index reference), NOT `Children[]` arrays. `build_world_placed_merge.py` uses this field to walk the scene graph hierarchy from mesh → parent node → root, accumulating Scale×Rotate×Translate at each step

## Recent Phase 1 milestones

- **M1.1 (329-family attribute/role matrix)** — ✅ COMPLETE. 12 IDs / 12 paired comparisons / 24 matrix rows. Handoff: `docs/handoffs/2026-06-m1.1-329-matrix.md`. Artifacts: `Exports/mesh329-family-attribute-role-matrix.{json,md,csv}`. Schema: `docs/schemas/329-family-attribute-role-matrix-v1.schema.json`. Key finding: mesh#7 variants have `AttributeSets=1`, mesh#34 variants have `AttributeSets=0` with @304 re-scored as position-float3-ror1-lead (c=75) in 12/12 paired cases.
- **M1.2 (@304 extra stream classification on mesh#34)** — ✅ COMPLETE. Builds on M1.1 matrix. Handoff: `docs/handoffs/2026-06-m1.2-@304-extra-stream-classification.md`. Uses M1.1 `IDsCovered` as controlled target list. 10/10 scoped classification, 12/12 matrix patterns confirmed.
- **M1.3 (sibling source-binding guard)** — ✅ COMPLETE. Builds on M1.1 + M1.2. Handoff: `docs/handoffs/2026-06-m1.3-sibling-source-binding-guard.md`. Uses M1.1 matrix IDs as targets. Guards 12/12 PASS, validation suite 9/9 PASS.
- **M1.4 (305-family comparison)** — ✅ COMPLETE. Handoff: `docs/handoffs/2026-06-m1.4-305-family-comparison.md`. Cross-family structural comparison: attrSets=1/0 pattern confirmed across families.
- **M1.5 (Phase 1 exit consolidation)** — ✅ COMPLETE. Handoff: `docs/handoffs/2026-06-m1.5-phase1-exit-consolidation.md`. Comprehensive Phase 1 capstone handoff with unified cross-family evidence.

## Recent Cycle 2 (C2) advances (COMPLETE — all 7 phases DONE; SHIPPED)

> **Cycle 2 is COMPLETE.** All phases C2-1 through C2-7 delivered, ship-kill decision SHIP.
> 153/217 (70.5%) assets are consumer-ready with geometry, transforms, textures, and materials.
> Stage8 RiftFlythrough delivery JSON shipped to sibling project.

- **C2-2.4 ✅** — `scripts/build_scene_manifest.py` (~295 lines) + `tests/test_build_scene_manifest.py` (17 tests) + 24/24 sample manifests built at `Assets/Exports/discovery-plan/cycle-2/stage2/sample-manifest-*.json`. Generators: `--asset-id`, `--all-non-id`, `--all-flythrough`, `--out`, `--validate-only`. Validates against `scene-manifest-v1.draft.schema.json` (JSON Schema 2020-12, 24/24 exit 0).
- **C2-2.5 ✅** (DONE; V4P12 FIRED) — `docs/roadmap/cycle-2-briefs/block-1-transform-schema.md` is the durable V4 Pro brief; `docs/handoffs/2026-06-16-c2-2.5-v4p12-fired.md` is the session-start handoff.
- **Cohort dedupe (C2-2.4 follow-on)** — `transform-examples.json` identity_examples collapsed 22 → 20 (removed 2 internal duplicate pairs). Cohort definition = **24** (4 non-id + 20 distinct id), matching 24 on-disk files.
- **C2-3.1 ✅** — `scripts/build_texture_coverage.py` (~310 lines) + `tests/test_build_texture_coverage.py` (17 tests) + `Assets/Exports/discovery-plan/cycle-2/stage3/texture-coverage.{json,md}`. **Critical finding: 23/24 cohort assets show `scene.linked_texture_count=0` vs `fly.linked_textures.count>0`** — direct evidence the scene-manifest v1 draft schema lacks a `textures.source` discriminant.
- **C2-4 ✅** — `build_scene_manifest.py --all-flythrough` generates 217 per-asset stage6 manifests.
- **C2-5 ✅** — Aggregate pack built: `stage4/scene-manifest-pack-v1.json` (24 entries, 15/24 consumer-ready).
- **C2-6 ✅** — Scale-out to full 217-asset cohort.
- **C2-7 ✅ (SHIP)** — `tests/test_scene_manifest_validation.py` (22 tests) + `scene_manifest_validation_guard()` (9th guard, 241/241 PASS) + ship-kill brief at `docs/roadmap/cycle-2-briefs/block-4-ship-kill-brief.md`.
- **v0.6 Geometry enrichment** — `build_geometry()` populates `vertex_count`, `face_count`, `has_faces`, `mesh_block` (M#N), `mesh_size`, `render_class` (faced/point-only/unknown), and `obj_sha1` from flythrough-index. 155 faced, 62 point-only, 217/217 with obj_sha1 + M#N.
- **v0.7 Material inference** — `build_materials()` infers `material_status` from flythrough texture linkage: `linked_textures` non-empty → "textured" (212 assets), faced but no textures → "material-or-vertex-color-only" (2 assets), otherwise "unknown" (3 assets). **153/217 (70.5%) assets consumer_ready** — up from 0/217.
- **v0.8 NIF-confirmed material scan** — `scripts/scan_nif_material_properties.py` runs `probe-nif` per asset (217/217), extracts `NiTexturingProperty`/`NiMaterialProperty`/`NiVertexColorProperty` block counts from NIF block type tables. `build_materials()` now prefers confirmed counts over v0.7 inference (falls back when scan data absent). **217/217 NIF-confirmed, 212 textured (NiTexturingProperty>0), 5 material-color-only. 153/217 consumer-ready.** Property counts (`texture_property_count`, `material_property_count`, `vertex_color_property_count`) and `scanned_at` timestamp populated in all 217 stage6 manifests. PRODUCER_VERSION bumped to v0.8.
- **Stage8 RiftFlythrough delivery** — `scripts/build_riftflythrough_delivery.py` filters 153 consumer-ready assets into `riftflythrough-delivery.json` (14,696 vertices, 23,634 faces, 404 linked textures, 19 mesh families) + markdown report. Copied to `C:\RIFT MODDING\RiftFlythrough\js\riftflythrough-delivery.json`.
- **9th proof guard** — `scene_manifest_validation_guard()` validates all 241 manifests across schema, OBJ paths, world paths, transform finiteness, texture.source enum, and producer version. 241/241 PASS.
- **Current-phase overrides** — `docs/roadmap/current-phase.md` updated 2026-06-16: all C2 phases marked DONE, Cycle 2 marked COMPLETE with SHIP decision.
- **CI green sequence (post-C2)** — Commits `accff2b` through `72866a6` (C2-3.1 profiler + handoff fixes). All pushed to `origin/main`.

## Agent model strategy

The `.agents/` directory contains 10 custom agent definitions with a tiered model strategy:

| Agent | Model | Best for |
|-------|-------|----------|
| `nif-probe-agent` | DeepSeek V4 Flash (high) | NIF mesh analysis, stream role probing |
| `discovery-orchestrator` | DeepSeek V4 Flash | Pipeline orchestration (build→inventory→guards) |
| `program-cs-editor` | DeepSeek V4 Flash (high) | Routine C# edits, simple gate changes |
| `proof-guard-agent` | DeepSeek V4 Flash (high) | Guard suite maintenance & validation |
| `obj-export-validator` | DeepSeek V4 Flash | OBJ structural integrity checks |
| `handoff-summarizer` | DeepSeek V4 Flash (high) | Session handoff document generation |
| `safety-guardian` | DeepSeek V4 Flash (high) | Pre-commit safety audits |
| `autonomous-worker` | DeepSeek V4 Flash | Task queue executor (delegates to all above) |
| `cs-architect-gpt` | **OpenAI GPT-5.5** (high) | **Complex C# changes** needing deep reasoning (new decode paths, subtle bugs, algorithm design) |
| `investigator-gpt` | **OpenAI GPT-5.1** (high) | **Stream data investigation** (half-float decode, magic-byte analysis, position source discovery) |

**Strategy:**

- Default to Flash agents for speed/cost on routine work
- Deploy `cs-architect-gpt` when a C# change requires multi-step reasoning across the ~15K-line `Program.cs` (complex algorithm changes, subtle stream classification bugs, new geometry decode paths)
- Deploy `investigator-gpt` for binary stream analysis requiring pattern recognition and experimental decode prototyping
- DeepSeek V4 Pro is not yet available — once it is, upgrade `program-cs-editor` to Pro
- **FT-4 keystone phase:** all new C# work should use `cs-architect-gpt`; all binary investigation should use `investigator-gpt`

## Third-party tools integration

Tools are installed at the sibling `C:\RIFT MODDING\Tools\` directory (outside the git repo) and registered in `.tools.json` at the project root.

### Config file (`.tools.json`)

JSON registry mapping tool names to their paths (relative to project root), with `installed` status verified by actual file existence.

```json
{
  "tools_root": "..\\Tools",
  "tools": {
    "x64dbg": { "path": "..\\Tools\\x64dbg\\...", "installed": true },
    "jdk21": { "path": "..\\Tools\\jdk-21.0.11+10\\bin\\java.exe", "installed": true },
    "ghidra": { "path": "..\\Tools\\ghidra_12.1_PUBLIC\\support\\analyzeHeadless.bat", "installed": true },
    ...
  }
}
```

### Loading tools in Python

```python
from scripts.rift_workflow_utils import load_tools_config, show_tools_status

config = load_tools_config()
show_tools_status(config)

if config["tools"]["ghidra"]["installed"]:
    ghidra_path = config["tools"]["ghidra"]["resolved_path"]
    # use it...
```

### Registered tools

| Tool | Category | Purpose |
|------|----------|---------|
| **x64dbg** | Debugger | Attach to RIFT client, observe archive read behavior at runtime |
| **Ghidra** | Static analysis | Decompile RIFT DLLs to extract NiDataStream/TWAD parsing logic |
| **Blender** | 3D viewer | Visually inspect OBJ exports for structural correctness |
| **NifSkope** | NIF viewer | Inspect NiMesh block tree, NiDataStream bindings, raw bytes |
| **ImHex** | Hex editor | Analyze binary stream bodies, identify magic constants |
| **jq** | CLI | Slice/dice large JSON/JSONL inventories for pattern analysis |
| **GIMP** | Image editor | Open DDS textures to verify texture→model bindings |
| **HxD** | Hex editor | Inspect multi-GB TWAD archives, find magic bytes and compression boundaries |

### Adding a new tool

1. Install it in `C:\RIFT MODDING\Tools\ToolName\`
2. Add an entry to `.tools.json` under `tools` with `path`, `description`, and `category`
3. `load_tools_config()` automatically detects and sets `installed: true`

### Commands

| Purpose | Command |
|---------|---------|
| Show installed tools status | `python scripts/rift_workflow.py tools-status` |
| Verify Ghidra/JDK wiring without launching analysis | `python scripts/rift_workflow.py ghidra-dry-run` |
| Dry-run a retained-project script rerun | `python scripts/rift_workflow.py ghidra-dry-run --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project` |
| Run a retained-project Ghidra script | `python scripts/rift_workflow.py ghidra-run --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project --ghidra-timeout 900 --ghidra-script scripts/ghidra/FunctionSiteSurvey.java --ghidra-script-arg 0x1406e905f --ghidra-script-arg Exports/ghidra-reports/twad_site_survey.json` |
| First-pass full Ghidra import/analysis | Use `ghidra-run` with `--ghidra-import <binary>` and `--ghidra-timeout 14400`; keep projects under ignored `Exports/ghidra-projects/`. |
