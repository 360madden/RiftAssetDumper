# Project knowledge

## What this project is

Read-only **RIFT** game asset archive research workspace. Reverse-engineers the game's custom binary archive format (`TWAM` manifests + `TWAD` archives) to extract and decode assets — textures (DDS), models (Gamebryo NIF v20.6.0.0), audio (OGG/RIFF), XML data, etc. The primary goal is geometry/model export (OBJ) from NIF meshes via `NiMesh` → `NiDataStream` binding analysis.

The team follows an **Aggressive Evidence Workflow** (see `docs/aggressive-discovery-workflow.md`) — small focused probes → smoke runs → full copied-set inventory → ranked evidence → documented truth → commit → next lead. All task routing follows a safety policy (see `docs/task-routing-safety-policy.md`) that reserves high/extra-high reasoning for truth, proof, guards, runtime, and commit decisions.

## Quickstart

### .NET (main dumper CLI)

| Command | Purpose |
|---------|---------|
| `dotnet build RiftAssetDumper.slnx --nologo` | Build all C# projects |
| `dotnet test RiftAssetDumper.slnx --nologo` | Run xUnit tests |
| `dotnet format RiftAssetDumper.slnx --verify-no-changes` | Check formatting |
| `dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- --help` | Run CLI |

### PowerShell workflow helper (thin wrapper)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/Invoke-RiftWorkflow.ps1" -Mode <Mode> [options]
```

All complex modes have been ported to Python.

### Python (scripting/discovery orchestration — primary orchestrator)

| Command | Purpose |
|---------|---------|
| `python scripts/rift_workflow.py <command> [options]` | Run any workflow command (kebab-case) |
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

## Architecture

### .NET CLI (`src/RiftAssetDumper/`)

- **Target:** .NET 9.0, C# with nullable enabled, implicit usings
- **Key dependency:** `SharpCompress` v0.41.0 (XZ/LZMA2 decompression)
- **Single-file entry point:** `Program.cs` (~15K lines, contains ALL command handlers inline)
- **Commands** dispatched via `AppOptions.Parse(args)` then `if/else if` chain in `Main()`
- **Key commands (inventory):** `inventory-nif-mesh-bindings`, `inventory-nif-mesh-streams`, `inventory-nif-stream-headers`, `inventory-nif-stream-bodies`, `inventory-nif-stream-endianness`, `inventory-nif-index-candidates`, `inventory-nif-blocks`, `inventory-asset-signatures`, `inventory-archives`
- **Key commands (probe):** `probe-nif-mesh`, `probe-nif-streams`, `probe-nif-stream-body`, `probe-nif-attribute-extra`, `probe-nif`, `probe-binary`, `probe`
- **Key commands (export):** `decode-nif-geometry` (supports `--experimental-position-source`, `--write-obj`, `--export-obj`)
- **Key commands (bundle):** `extract-nif-bundle`, `extract-nif-bundles`, `plan-nif-bundle-archives`, `link-nif-textures`
- **Key commands (utility):** `hash-name`, `match-ids`, `match-names`, `list-paks`, `list-entries`, `scan-compression`, `mine-strings`
- **Tests:** xUnit in `src/RiftAssetDumper.Tests/` (50 tests, all pass)

### Python scripts (`scripts/`)

- **Target:** Python 3.14 (ruff + mypy strict)
- **Roles:** discovery orchestration, workflow helpers, guard/proof-validation scripts, reports, batch sweep
- **Entry point:** `scripts/rift_workflow.py` — kebab-case command dispatch with 30+ commands
- **Guards:** `scripts/rift_workflow_guards.py` — 4 proof guards (attribute-extra, usage-access-correlation, position-source-sibling-lead, residual-lead)
- **Reports:** `scripts/rift_workflow_reports.py` — 10+ report functions (gap, sibling, classifier, cluster, crosstab, workbench)
- **Utils:** `scripts/rift_workflow_utils.py` — checked_run, load_json_report, generated_output_guard, JSON access helpers
- **Batch sweep:** `scripts/batch_sweep.py` — 4-phase tool for OBJ integrity validation (SHA256, index bounds, NaN, negative indices), candidate discovery, batch export, and manifest building
- **Tests:** `scripts/test_rift_workflow_utils.py` (49 unit tests)
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

### Key directories (gitignored)

| Path | Contents |
|------|----------|
| `Source/` | Local copied game files (`assets.manifest`, `Assets/assets.###` archives) |
| `Extracted/` | Decompressed payload dumps (NIF, DDS, etc.) and NIF texture bundles |
| `Exports/` | JSON/JSONL reports, inventories, matrices, and OBJ exports |
| `RecoveredNames/` | Generated filename matches (`recovered-names.jsonl`) |
| `Candidates/` | Candidate filename lists for hash matching |
| `docs/handoffs/` | Session handoff docs (AI-agent context resumption) |

### Data flow

1. **Manifest** (`TWAM`) → parse header + tables (PAK listing, entry table)
2. **Archive** (`TWAD`) → parse entry table, decompress (zlib/LZMA2/raw), detect type
3. **NIF probe** → parse Gamebryo block structure, extract `NiMesh` → `NiDataStream` bindings
4. **Geometry decode** → decode positions/normals/UVs from float32 or uint16-packed streams
5. **OBJ export** → behind `--experimental-position-source` (fallback) or `--export-obj` (attribute-set @264) flags

### CI pipeline (`.github/workflows/ci.yml`)

Two parallel jobs on `windows-latest`:

- **.NET job:** `dotnet build`, `dotnet format --verify-no-changes`, `dotnet test` (pwsh shell)
- **Python job:** syntax check, `ruff check`, `mypy --no-error-summary`, Python tests (`py_compile` + pytest)
- **Final job:** aggregates both results (Ubuntu)

### Current project state (latest — Phase 49 + live-archive exhaustion)

- **350 OBJ files, 270 faced, 80 position-only, 30,864 faces, 23,421 vertices across 30 MeshSize families. 217 unique asset IDs. 345 copied + 5 live provenance. 0 structural issues. 0 unexported candidates remain.**
- `scripts/dedup_objs.py` — safe SHA256-verified duplicate cleaner with dry-run mode and content-mismatch warnings
- `scripts/live_family_scanner.py` — exhaustive batch probe mode (`--exhaustive`) with auto-update registry integration
- `scripts/build_export_manifest.py` v3 — data-driven live provenance via `scripts/live-exported-ids.json`
- `batch_sweep.py` — 4-phase tool for OBJ integrity (SHA256, index bounds, NaN, negative indices), candidate discovery, batch export, manifest building
- All 8 proof guards PASSED on full inventory
- Endian-analysis root-cause fix (Stage 9): `PairCompatibleMeshes` restored to **1,949**
- Triangle fan fallback implemented: pos-only OBJs now get approximate faces via `--experimental-position-source --write-obj`
- Cross-MB audit (Phase 48): no recoverable faced candidates found across all pos-only OBJs
- CI green: build 0 errors, tests 50/50 (C#) + 50 (Python), ruff 0, mypy 0

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
|---|---|---:|---|
| 329 | 23 | repeated source-binding family |
| 305 | 15 | repeated source-binding family |
| 321 | 11 | repeated source-binding family |
| 325 | 1 | shifted sibling position-source clue |
| 329 | 1 | shifted sibling position-source clue |

### Compression truth

| Scope | Count | Compression |
|---|---|---:|---|
| Copied TWAD entries | 40,203 | `0=203`, `1=40000`, `2=0` |
| Full live TWAD entries | 263,957 | `0=22422`, `1=241535`, `2=0` |
| Manifest Table 0 PAK rows | 2,076 | `0=736`, `2=1340` |

LZMA2 is real in the manifest/PAK layer but not in ordinary TWAD entry payloads seen so far.

## Gotchas

- `Program.cs` is extremely large (~15K lines) — prefer targeted `str_replace` edits over rewrites
- All C# commands run via string matching in `Main()` — adding a new command requires adding an `if` block
- The solution file is `.slnx` (new XML format) — not `.sln`
- Local game data (`Source/`) must be manually copied; it is never committed
- Live game install (`C:\Program Files (x86)\Glyph\Games\RIFT\Live`) is read-only; use `--live-root`
- Python scripts are all in `scripts/` root (no subpackages) with flat module structure
- `ruff` ignores E501 (line length) since it's enforced by formatter; several naming conventions relaxed for PS→Py ports
- Always use `--experimental-position-source` for meshes without direct attribute sets
- The `@264/#15` extra-stream pattern is the strongest geometric index lead for mesh faces
- The `Invoke-RiftWorkflow.ps1` wrapper translates legacy PS mode names to kebab-case Python commands
- `dotnet build` is implicit for most workflow commands unless `--skip-build` is passed
- The `generated_output_guard` runs at the start of every Python command — it checks that no generated/ignored files have been accidentally committed
- `.agents/` directory contains Codebuff agent type definitions (`types/agent-definition.ts`, `types/tools.ts`, `util-types.ts`) — the schema types for building custom Codebuff agents
- Agent definition files were rebuilt from scratch in `.agents/` (see `.agents.bak2/` for original reference)
- `batch_sweep.py` is a standalone 4-phase script (not a workflow command) for OBJ integrity, candidate discovery, batch export, and manifest generation

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
