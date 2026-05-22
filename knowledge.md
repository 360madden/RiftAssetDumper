# Project knowledge

## What this project is
Read-only **RIFT** game asset archive research workspace. Reverse-engineers the game's custom binary archive format (`TWAM` manifests + `TWAD` archives) to extract and decode assets — textures (DDS), models (Gamebryo NIF v20.6.0.0), audio (OGG/RIFF), XML data, etc. The primary goal is geometry/model export (OBJ) from NIF meshes via `NiMesh` → `NiDataStream` binding analysis.

## Quickstart

### .NET (main dumper CLI)

| Command | Purpose |
|---------|---------|
| `dotnet build RiftAssetDumper.slnx --nologo` | Build all C# projects |
| `dotnet test RiftAssetDumper.slnx --nologo` | Run xUnit tests |
| `dotnet format RiftAssetDumper.slnx --verify-no-changes` | Check formatting |
| `dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- --help` | Run CLI |

### PowerShell workflow helper (preferred runner)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/Invoke-RiftAssetWorkflow.ps1" -Mode <Mode> [options]
```

### Python (scripting/discovery orchestration)

| Command | Purpose |
|---------|---------|
| `python scripts/rift_asset_discovery_matrix.py --skip-build` | Run discovery matrix jobs |
| `ruff check scripts/` | Python lint |
| `mypy scripts/ --no-error-summary` | Python type check |
| `python scripts/test_rift_workflow_utils.py` | Python tests |

## Architecture

### .NET CLI (`src/RiftAssetDumper/`)
- **Target:** .NET 9.0, C# with nullable enabled, implicit usings
- **Key dependency:** `SharpCompress` (XZ/LZMA2 decompression)
- **Single-file entry point:** `Program.cs` (~15K lines, contains ALL command handlers inline)
- **Commands** dispatched via `AppOptions.Parse(args)` then `if/else if` chain in `Main()`
- **Key commands:** `probe`, `match-ids`, `list-paks`, `list-entries`, `extract-archives`, `hash-name`, `match-names`, `inventory-archives`, `scan-compression`, `mine-strings`, `probe-binary`, `probe-nif`, `probe-nif-streams`, `probe-nif-mesh`, `decode-nif-geometry`, `probe-nif-position-source`, `inventory-nif*`, `extract-nif-bundle`, `extract-nif-bundles`, `link-nif-textures`, `plan-nif-bundle-archives`
- **Tests:** xUnit in `src/RiftAssetDumper.Tests/`

### Python scripts (`scripts/`)
- **Target:** Python 3.14 (ruff + mypy strict)
- **Roles:** discovery orchestration, workflow helpers, guard/proof-validaton scripts
- **Scripts** use `scripts.__init__`; PS→Py ports use underscore-prefixed function names (allowed by ruff per-file-ignores)

### Key directories (gitignored)
| Path | Contents |
|------|----------|
| `Source/` | Local copied game files (`assets.manifest`, `Assets/assets.###` archives) |
| `Extracted/` | Decompressed payload dumps (NIF, DDS, etc.) |
| `Exports/` | JSON/JSONL reports, inventories, and matrices |
| `RecoveredNames/` | Generated filename matches (`recovered-names.jsonl`) |
| `Candidates/` | Candidate filename lists for hash matching |
| `docs/handoffs/` | Session handoff docs (AI-agent context resumption) |

### Data flow
1. **Manifest** (`TWAM`) → parse header + tables (PAK listing, entry table)
2. **Archive** (`TWAD`) → parse entry table, decompress (zlib/LZMA2/raw), detect type
3. **NIF probe** → parse Gamebryo block structure, extract `NiMesh` → `NiDataStream` bindings
4. **Geometry decode** → decode positions/normals/UVs from float32 or uint16-packed streams
5. **OBJ export** → experimental, behind `--experimental-position-source` flag

## Conventions

- **Formatting:** `dotnet format` (C#), `ruff` (Python)
- **Coding style:** 4-space indentation, `Allman` braces in C#, semicolons required
- **NIF identifiers:** Use hex IDs (16-char lowercase) — never truncate to 8 chars ambiguously
- **Redaction:** CLI redacts `%USERPROFILE%` paths by default; use `--no-redact-paths` for debugging
- **Records:** All data types are C# `record` types (immutable, positional) — never `class` for DTOs
- **JSON output:** JSON Lines (`.jsonl`) for row data, single JSON (`.json`) for reports
- **Geometry exports:** Blocked behind `--experimental-position-source` gate; never claim OBJ export without proof
- **LZMA2:** Only XZ-framed supported; raw LZMA2 is intentionally unhandled
- **Name recovery:** Uses FNV1/FNV1a hashing with confidence scoring; recoveries need `--use-recovered-names`
- **NIF block analysis:** 29-byte `NiDataStream` header invariant; roles classified as `*-ror1-lead`, `*-u16be-*`, etc.
- **CI:** Runs both .NET (build, format, test) and Python (ruff, mypy, test) on push/PR

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
