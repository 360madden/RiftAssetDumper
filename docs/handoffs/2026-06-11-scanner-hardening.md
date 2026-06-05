# Session Handoff — 2026-06-11: Live Family Scanner Hardening

**Commit:** `f246925` — `refactor: harden live_family_scanner.py`

## What Changed

Hardened `scripts/live_family_scanner.py` based on code review feedback:

| Fix | Before | After |
|-----|--------|-------|
| Process spawning | `sys.executable → rift_workflow.py → dotnet` (2 Python processes) | `dotnet run` directly via `subprocess.run` (0 Python intermediaries) |
| Probe output paths | `probe-nif-mesh-{aid}.json` (overwrites across mesh blocks) | `probe-nif-mesh-{aid}-mesh{mb}.json` (mesh-block-specific) |
| Export result parsing | Regex-only on stdout | Structured JSON parsing from decode report + OBJ file as fallback |
| `--skip-build` flag | Accepted but never wired through | Wired to `dotnet_args.insert(1, "--no-build")` |
| Default `skip_build` | `True` (would fail on fresh checkout) | `False` (builds on first run) |
| Progress feedback | Timeouts gave no context | Timeout errors include command prefix |

## Probe Results (All Normal-Priority Families Exhausted)

| MeshSize | Asset ID | Block | Result |
|:--------:|----------|:-----:|--------|
| 271 | `4f2391a70cf4bacb` | 7 | Normal only, no position ❌ |
| 299 | `c655a3bd21df0243` | 6 | Normal only, no position ❌ |
| 311 | `c68df298188e6c2c` | 6 | Normal only, no position ❌ |
| 341 | `f606732348273b6f` | 32 | Normal+UV, no position ❌ |
| 391 | `a4dc0e5ed18c9c49` | 134 | Normal+UV, no position ❌ |
| 396 | `160c605b3e6f89ca` | 135 | Normal+UV, no position ❌ |

**Key insight:** The live inventory's RoleGroups aggregates roles across ALL NIFs of a given mesh size. "position-float3-ror1-lead" in RoleGroups means SOME NIF of that mesh size has position data, not the specific sample. Finding export candidates requires probing the correct mesh block.

## Exported Live-Only OBJs This Session

| MeshSize | Asset ID | Vertices | Faces | Size |
|:--------:|----------|:--------:|:-----:|:----:|
| 362 | `cf54e712ff57eaac` | 6,489 | 6,487 | 776 KB |
| 357 | `cf54e712ff57eaac` | 41 | 39 | 4.7 KB |
| 349 | `1ecdbaf5a2576ba5` | 60 | 58 | 4.9 KB |

## CI (All Green ✅)

| Check | Result |
|-------|:------:|
| Build | 0 errors |
| C# Tests | 50/50 |
| Ruff | 0 violations |
| Mypy | 0 errors |

## Next Steps

| # | Action |
|---|--------|
| 1 | Run larger live scan (`--max-total 2000+`) to capture more mesh-size families with populated IDs |
| 2 | Use hardened scanner with `--probe` on larger inventory to automatically find position-enabled families |
| 3 | Investigate index-priority families (375, 383, 412, 417, 423) — may have faces even without position streams |
