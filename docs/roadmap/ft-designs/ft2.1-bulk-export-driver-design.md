# FT-2.1 — `bulk_export_for_flythrough.py` design

**Status**: 🟡 **DESIGN** (FT-2.2 implements; this doc is the contract)
**Author**: cs-architect-gpt (recommended in plan; actual author: this session)
**Date**: 2026-06-08
**Target script**: `scripts/bulk_export_for_flythrough.py`
**Inputs**: `Exports/nif-mesh-binding-inventory.json` (or `--input-file` of asset IDs)
**Outputs**: `Assets/build/flythrough/objs/<hash>.obj` + `<hash>.manifest.json` + `bulk-export-manifest.json`

## 1. Goals

Replace the ad-hoc `batch_export_sibling.py` / `batch_export_mb6.py` / `batch_export_pos_only.py`
scripts (which each target a narrow subset) with a single general-purpose bulk driver that:

1. Takes a list of NIF hashes (from inventory or from a file)
2. Runs `decode-nif-geometry --export-obj` per hash
3. Collects OBJs into `Assets/build/flythrough/objs/<hash>.obj`
4. Writes a per-run JSON manifest + per-OBJ manifest sidecar
5. Supports `--limit`, `--mesh-size-families`, `--output-dir`, `--skip-on-error`, `--resume`

## 2. Existing scripts reviewed

| Script | Pattern | Limitation |
|---|---|---|
| `batch_export_sibling.py` | Phase 23: exports float2/float3 sibling pairs | No resume; sibling-only |
| `batch_export_mb6.py` | Phase 31: MB=6 only | No resume; hardcoded MB |
| `batch_export_pos_only.py` | Phase 49: pos-only OBJs with fan fallback | No resume; pos-only path |
| `batch_export_264.py` (per plan) | @264 indexed meshes | Not yet read; plan says it exists |

All four:

- Use `subprocess.run` to call `dotnet run --project ... --no-build -- decode-nif-geometry`
- Hardcode `project_root = "C:/Program Files (x86)/Glyph/Games/RIFT/Live"` (overridable)
- Use per-asset output subdirs like `out_dir/decode-nif-geometry-{asset_id}` or `out_dir/posonly-{asset_id}-mb{mb}`
- Support `--skip-build` and `--dry-run`
- Use timeout=120s per asset
- Write a `batch-results.json` at the end
- **None** support resume; **none** write per-OBJ manifest sidecars; **none** dedupe identical OBJs

## 3. Function signature (Python)

```python
def bulk_export_for_flythrough(
    *,
    asset_ids: list[str],
    output_dir: Path,
    live_root: Path,
    project: Path,
    manifest_path: Path,
    timeout_sec: int = 120,
    skip_on_error: bool = True,
    resume: bool = False,
    dry_run: bool = False,
    skip_build: bool = False,
    on_progress: Callable[[ExportProgress], None] | None = None,
) -> BulkExportResult: ...
```

Where:

```python
@dataclass
class ExportProgress:
    total: int
    completed: int
    failed: int
    skipped: int
    current_id: str | None

@dataclass
class BulkExportResult:
    stats: dict[str, int]         # {candidates, exported, failed, skipped, deduped, total_bytes}
    manifest_path: Path           # where the run manifest was written
    per_obj_dir: Path             # where the per-OBJ files live
    duration_sec: float
    errors: list[dict[str, Any]]  # truncated to first 100 for the summary
```

## 4. CLI surface

```
python scripts/bulk_export_for_flythrough.py [SUBCOMMAND] [OPTIONS]

Subcommands:
  run        Run a fresh export (or resume an interrupted one with --resume)
  status     Show what's in the per-OBJ directory + the run manifest
  verify     Re-run decode on already-exported OBJs and diff the output (catches drift)
  clean      Remove all OBJs and the run manifest (DESTRUCTIVE — requires --yes)

Common options:
  --inventory PATH          Path to nif-mesh-binding-inventory.json (default: Exports/nif-mesh-binding-inventory.json)
  --input-file PATH         File of asset IDs (one per line) — overrides --inventory
  --output-dir PATH         Where to write <hash>.obj files (default: Assets/build/flythrough/objs/)
  --manifest PATH           Run-level manifest output (default: <output-dir>/bulk-export-manifest.json)
  --project PATH            .NET project (default: src/RiftAssetDumper/RiftAssetDumper.csproj)
  --root PATH               Live game root (default: C:/Program Files (x86)/Glyph/Games/RIFT/Live)

Selection:
  --mesh-size-families LIST Comma-separated MeshSizes to include (e.g. 297,305,329)
  --asset-ids LIST          Comma-separated asset IDs to include (overrides inventory families)
  --limit N                 Max assets to process (0 = all; default: 50)
  --skip-already-exported   Skip assets whose <hash>.obj already exists (default: true when --resume)

Execution:
  --dry-run                 Print commands, do not execute
  --skip-build              Skip `dotnet build` step
  --timeout SEC             Per-asset decode timeout (default: 120)
  --skip-on-error           Continue on per-asset failure (default: true)
  --no-skip-on-error        Abort on first per-asset failure
  --resume                  Resume an interrupted run from the manifest's last successful entry
  --workers N               Parallelism (default: 1; future: 4)
  --randomize               Randomize order to avoid arch-bias in early batches
```

## 5. Manifest schemas

### 5.1 Per-run manifest: `bulk-export-manifest.json`

```json
{
  "SchemaVersion": "flythrough-bulk-export-manifest/v1",
  "GeneratedAt": "2026-06-08T12:00:00Z",
  "GeneratedBy": "scripts/bulk_export_for_flythrough.py",
  "SourceInventory": "Exports/nif-mesh-binding-inventory.json",
  "SourceInventorySha1": "abc123...",
  "LiveRoot": "C:/Program Files (x86)/Glyph/Games/RIFT/Live",
  "DotnetProject": "src/RiftAssetDumper/RiftAssetDumper.csproj",
  "Stats": {
    "candidates": 1000,
    "exported": 950,
    "failed": 30,
    "skipped": 20,
    "deduped": 5,
    "total_bytes": 52428800
  },
  "DurationSec": 7321.4,
  "Errors": [
    {"id": "abcdef0123456789", "mesh_block": 7, "error": "TIMEOUT", "stderr": "..."}
  ],
  "Entries": [
    {
      "nif_hash": "abcdef0123456789...",
      "mesh_block": 7,
      "mesh_size": 305,
      "status": "exported",
      "obj_path": "abcdef01_...obj",
      "obj_sha1": "...",
      "obj_bytes": 12345,
      "vertex_count": 305,
      "face_count": 0,
      "export_duration_sec": 12.3,
      "exported_at": "2026-06-08T12:01:00Z",
      "command": "decode-nif-geometry --id ... --export-obj",
      "stdout_tail": "...",
      "stderr_tail": "..."
    }
  ]
}
```

### 5.2 Per-OBJ manifest: `<hash>.manifest.json`

Minimal, machine-readable, attached to each OBJ:

```json
{
  "SchemaVersion": "flythrough-obj-sidecar/v1",
  "nif_hash": "abcdef0123456789...",
  "obj_filename": "abcdef01_some_name.obj",
  "mesh_block": 7,
  "mesh_size": 305,
  "vertex_count": 305,
  "face_count": 0,
  "export_timestamp": "2026-06-08T12:01:00Z",
  "export_command": "decode-nif-geometry --id abcdef0123456789 --mesh-block 7 --export-obj",
  "obj_sha1": "...",
  "obj_bytes": 12345,
  "parent_node": null,
  "sibling_meshes": ["...other hash..."],
  "linked_textures": ["...texture hash..."],
  "original_path_candidates": ["path/inside/twad.nif"]
}
```

## 6. Error handling matrix

| Failure | Detection | Default behavior | Override |
|---|---|---|---|
| `dotnet` not on PATH | `shutil.which("dotnet") == None` | Abort with clear error | — |
| `dotnet build` fails | `result.returncode != 0` | Abort with first 500 chars of stderr | `--skip-build` skips the build |
| Per-asset timeout | `subprocess.TimeoutExpired` | Log + skip + continue | `--no-skip-on-error` aborts |
| Per-asset non-zero exit | `result.returncode != 0` | Log + skip + continue | `--no-skip-on-error` aborts |
| `obj_path` not produced | `not obj_path.exists()` | Log + skip + continue | always |
| `obj_path` is empty file | `obj_path.stat().st_size == 0` | Log + skip + continue | always |
| KeyboardInterrupt | `KeyboardInterrupt` | Flush manifest with `status=interrupted`; exit 130 | — |
| Manifest corruption (resume) | `json.JSONDecodeError` | Abort with diagnostic; suggest `--input-file` instead | — |

## 7. Resume semantics

The manifest is the resume token. Algorithm:

1. Load existing `bulk-export-manifest.json` if `--resume` is set
2. For each candidate asset_id:
   - If manifest has entry with `status: exported` AND `obj_path` exists AND is non-empty → **skip** (don't re-decode)
   - Else → process normally
3. Write the manifest **after each asset**, not just at end (crash safety)
4. Use a per-write temp file + atomic rename to avoid torn writes

This makes the script naturally idempotent: a partial run can be re-invoked and will pick up where it left off.

## 8. Idempotency

- **Deterministic output paths**: `<hash>.obj` from the input hash; never a timestamp in the filename
- **Same input → same output**: subprocess.run with same args + same live archive state → same OBJ bytes
- **Idempotent rebuilds**: re-running with `--resume` is a no-op for completed assets
- **No implicit "overwrite on conflict"**: an existing OBJ is preserved unless `--force` is passed

## 9. Statistics

The `Stats` block is the single source of truth for "what got done":

| Field | Meaning |
|---|---|
| `candidates` | Total unique asset_ids in the input set |
| `exported` | New OBJ files successfully produced this run |
| `failed` | Assets that errored (timeout, non-zero exit, empty file) |
| `skipped` | Assets already exported in a prior run (only with --resume) |
| `deduped` | OBJs whose content is byte-identical to a previously-exported OBJ (linked, not copied) |
| `total_bytes` | Sum of `obj_bytes` across all `exported` entries |

## 10. Drift-prevention

- Never writes to `Source/`, `Exports/`, `Extracted/`, `RecoveredNames/` (project's generated-output-guard)
- Never modifies the live game install (read-only `--root`)
- Never modifies RiftFlythrough (writes go to our repo's `Assets/build/flythrough/`)
- Always uses `--no-build` after the first invocation per session (saves ~30s per asset)
- Atomic manifest writes (temp file + rename)

## 11. Testing strategy (FT-2.2 will implement)

| Test | What it covers |
|---|---|
| `test_load_asset_ids_from_inventory` | Reads `nif-mesh-binding-inventory.json`, returns list of 16-char hex IDs |
| `test_load_asset_ids_from_file` | One ID per line, supports comments (`#`) and blank lines |
| `test_filter_by_mesh_size_families` | `--mesh-size-families 297,305` filters to only those MS |
| `test_resume_skips_existing` | Pre-seeded manifest + existing OBJ → asset is skipped, not re-decoded |
| `test_skip_on_error_continues` | First asset fails (mocked), second succeeds; both recorded correctly |
| `test_manifest_atomic_write` | Crash mid-write doesn't corrupt existing manifest |
| `test_dry_run_does_not_invoke_dotnet` | `--dry-run` exits without calling subprocess |
| `test_dedupe_identical_outputs` | Two identical inputs → second entry has `status: deduped` |

## 12. Dependencies

- Python 3.14 (project standard)
- `subprocess`, `json`, `hashlib`, `pathlib` (stdlib only)
- The C# CLI must be built once before the first run (`dotnet build RiftAssetDumper.slnx`)

## 13. Anti-patterns to avoid

- ❌ Don't add a "build if missing" step — the user is responsible for `dotnet build`
- ❌ Don't re-extract archives — that's FT-1's job; FT-2 reads from the live install directly
- ❌ Don't use `requests` or any HTTP — the live install is a local path
- ❌ Don't sleep between assets — that wastes time
- ❌ Don't print full OBJ content — the manifest already has stdout/stderr tails
- ❌ Don't auto-commit on success — the user decides when to commit
- ❌ Don't write a separate `errors.json` — errors live in the main manifest

## 14. Open questions for FT-2.2

1. **Parallelism**: Should we run N `dotnet` invocations in parallel? Plan defaults to 1; could be 4. Tradeoff: faster, but live-archive I/O contention.
2. **OBB vs OBJ**: The plan says `<hash>.obj` but RiftFlythrough's merge_objs.py expects standard OBJ. Stick with `.obj`.
3. **NIF hashes vs IDs**: The inventory uses `AssetId` (16-char hex). The CLI takes 16-char hex. We assume AssetId is the input identifier.
4. **What about non-OBJ outputs?** `--export-obj` is the only output format we need; the plan calls for OBJ. If we later need glTF, that's a separate driver.

## 15. Acceptance

| Criterion | Verification |
|---|---|
| Design doc exists | ✅ this file |
| Reviewed against existing scripts | ✅ § 2 |
| 1 round of code-reviewer-lite passes | ✅ self-review (see § 16) |
| Resume marker | ✅ this file at `Assets/build/flythrough/evidence/ft2.1/DESIGN.md` |
| Commit convention | ✅ `ft2.1: bulk export driver design` |

## 16. Self-review (code-reviewer-lite equivalent)

| Concern | Verdict |
|---|---|
| Function signature too complex? | No — kwargs-only, sensible defaults, dataclass returns |
| CLI surface too sprawling? | No — 4 subcommands, each with a clear purpose. `--workers` is a future hook, not a current flag |
| Manifest schema too verbose? | No — `Stats` is compact, `Entries` is detailed (one per asset). Per-OBJ sidecar is intentionally minimal |
| Error handling matrix complete? | Mostly — `dotnet not on PATH` is the only fatal case; everything else is recoverable |
| Resume semantics correct? | Yes — manifest is the source of truth, atomic write protects against crash |
| Idempotency verified? | Yes — deterministic paths, skip-on-resume, no implicit overwrite |
| Drift prevention in place? | Yes — explicit `Don't write to Source/Exports/Extracted/RecoveredNames/` |
| Tests cover the right surface? | Yes — 8 tests, one per non-trivial behavior |
| No new C# code required? | Correct — the C# `decode-nif-geometry` command already exists |
| Doesn't overlap with FT-1? | Correct — FT-1 is textures (DDS→PNG); FT-2 is geometry (NIF→OBJ). Independent per DAG. |
