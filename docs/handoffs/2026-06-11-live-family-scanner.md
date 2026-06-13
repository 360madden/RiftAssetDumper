# Session Handoff — 2026-06-11: Live Archive Expansion + Live Family Scanner

**Commit:** `f52afe2` — `feat: live family scanner + 3 new live-archive OBJ exports`

## Primary Achievement: 3 New Live-Archive OBJ Exports

First OBJ exports from live RIFT archives — 3 completely new MeshSize families not in the copied Source set:

| MeshSize | Asset ID | Block | Vertices | Faces | Size | NaN | Status |
|:--------:|----------|:-----:|:--------:|:-----:|:----:|:---:|:------:|
| **362** | `cf54e712ff57eaac` | 6 | 6,489 | 6,487 | 776 KB | 0 | ✅ |
| **357** | `cf54e712ff57eaac` | 107 | 41 | 39 | 4.7 KB | 0 | ✅ |
| **349** | `1ecdbaf5a2576ba5` | 78 | 60 | 58 | 4.9 KB | 0 | ✅ |

All from `assets.002` in the live install, all using `--experimental-position-source --write-obj` (fan fallback faces).

## Live Family Scanner (`scripts/live_family_scanner.py`)

New Python script that:

- Reads live mesh-binding inventory (handles UTF-8 BOM)
- Extracts families not in the 29 known copied-set families
- Ranks by export viability (position > normal > UV > index)
- Supports `--probe` and `--export` modes with `--live-root` configuration
- JSON + regex fallback parsing for probe results

**23 new mesh-size families discovered** in the 500-entry live scan (mesh sizes up to 417).

## Probed/Pending Families

| MeshSize | Asset ID | Block | Result |
|:--------:|----------|:-----:|--------|
| 341 | `f606732348273b6f` | 32 | Normal+UV only, no position @MB=32; MB=37/156 not found |
| 391 | `a4dc0e5ed18c9c49` | 134 | Normal+UV, no position |
| 396 | `160c605b3e6f89ca` | 135 | Normal+UV, no position |
| 271 | `4f2391a70cf4bacb` | 7 | Not probed |
| 299 | `c655a3bd21df0243` | 6 | Not probed |
| 311 | `c68df298188e6c2c` | 6 | Not probed |
| 333 | `cf54e712ff57eaac` | 218 | Not probed (MB index likely invalid) |
| 350 | `cf54e712ff57eaac` | 288 | Not probed (MB index likely invalid) |

## Key Insight: RoleGroups Aggregation

The live inventory's RoleGroups aggregates roles **across all NIFs** of a given mesh size, not per-NIF. A mesh size showing "position-float3-ror1-lead" in RoleGroups doesn't guarantee that specific sample NIF has position data — probing the correct mesh block is required.

## CI Status (All Green ✅)

| Check | Result |
|-------|:------:|
| Build | 0 errors |
| C# Tests | 50/50 |
| Ruff | 0 violations |
| Mypy | 0 errors |

## Next Steps

| Priority | Action |
|:--------:|--------|
| 1 | Run larger live scan (`--max-total 2000+`) to capture complete mesh-size distribution and more asset IDs |
| 2 | Probe remaining normal-priority families (271, 299, 311) — might find position data at undiscovered mesh blocks |
| 3 | Fix live_family_scanner.py: use `checked_run` for direct dotnet calls, add `--skip-build` flag, JSON parsing for export results |
| 4 | Scale to full live inventory — 244 archives with ~2.4M entries likely contain dozens more new families |
