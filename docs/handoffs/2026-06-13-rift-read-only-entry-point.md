# Handoff: `rift_read_only` entry-point split

**Date:** 2026-06-13
**Branch:** main
**Scope:** split the 41 read-only commands out of `scripts/rift_workflow.py` into a new
peer entry point so the orphan-process guard bypass set can be reduced to zero.

## Why

`scripts/rift_workflow.py` grew to **9,622 lines / 73 commands**. The orphan-process guard
fires for every command unless the command is in `_ORPHAN_GUARD_BYPASS_COMMANDS`. The
bypass set grew to **42 members** — a sign that the entry point is doing too much. Mixing
spawner commands (which must trigger the guard) with read-only commands (which never need
it) bloats the bypass list and obscures the actual safety boundary.

## Audit finding

| Metric | Value |
|---|---:|
| Bypass set size before | 42 |
| Bypass set size after | **0** |
| Commands moved to `rift_read_only.py` | **41** |
| Commands that share dispatch with spawners | 0 |
| Borderline cases (needed a code read) | 1 (`ghidra-dry-run`, confirmed pure-Python — no `subprocess.run`) |
| CLI meta that never reach dispatch | 2 (`--help`, `-h` — handled by argparse) |

## Refactor

- **NEW `scripts/rift_read_only.py`** — peer entry point. Owns the 41 read-only commands.
  No orphan guard (read-only by construction). Thin wrapper that re-uses
  `rift_workflow._run_command` for dispatch (no handler logic duplicated).
- **SLIM `scripts/rift_workflow.py`** — `_ORPHAN_GUARD_BYPASS_COMMANDS` emptied (42 → 0).
  Keeps all 73 commands for backward compat. The guard now fires for every command on this
  entry point (harmless overhead — the guard is a fast `tasklist` check that returns
  immediately when no orphan is detected).
- **NEW `tests/test_rift_read_only_no_spawn.py`** — 6 test suites + module startup
  assertion: structural check that each of 41 read-only commands has `COMMAND_MAP[X]["dotnet"] == ""`
  (design-level proof of no-spawn), dispatch block existence, runtime smoke tests,
  cross-module invariants.
- **REWRITE `tests/test_rift_workflow_orphan_guard_bypass.py`** — startup assertion now
  asserts the bypass set is **empty** (not the original 4 members). Removed the 124
  parametrized tests (nothing to test anymore). Kept the `--help`/`-h` test.
- **UPDATE `.github/workflows/ci.yml`** — `orphan-guard` job now runs the new
  `test_rift_read_only_no_spawn.py` file alongside the existing 3 test files.

## Architecture after the split

```
scripts/
├── rift_workflow.py          # SPAWNERS (33 commands) + read-only dispatch (41 commands, backward compat)
│                             # ORPHAN GUARD: required, bypass set empty
├── rift_read_only.py         # READ-ONLY (41 commands), no dotnet, no subprocess.run
│                             # NO ORPHAN GUARD: read-only by construction
├── rift_orphan_guard.py      # shared guard helper, used by rift_workflow.py + bulk_export
├── rift_workflow_guards.py   # unchanged
├── rift_workflow_reports.py  # unchanged
└── rift_workflow_utils.py    # unchanged
```

## Migration

| Old | New |
|---|---|
| `python scripts/rift_workflow.py tools-status` | `python scripts/rift_read_only.py tools-status` |
| `python scripts/rift_workflow.py ghidra-summarize` | `python scripts/rift_read_only.py ghidra-summarize` |
| `python scripts/rift_workflow.py discovery-workbench` | `python scripts/rift_read_only.py discovery-workbench` |
| ... 38 more | ... |
| `python scripts/rift_workflow.py mesh-bindings` | unchanged (spawner) |
| `python scripts/rift_workflow.py mesh-probe --id X` | unchanged (spawner) |
| `python scripts/rift_workflow.py decode-geometry ...` | unchanged (spawner) |

**Note:** The old commands on `rift_workflow.py` still work for backward compat, but the
orphan-process guard now fires for them (harmless overhead). Users should migrate to
`rift_read_only.py` for a guard-free experience.

## The 41 moved commands

**Tooling inspection (2):** `tools-status`, `ghidra-dry-run`
**Ghidra read-only guards/reports (8):** `ghidra-pairing-non-export-guard`,
`ghidra-attribute-candidate-report`, `ghidra-attribute-candidate-guard`,
`ghidra-workflow-guard-suite`, `ghidra-function-site-target-guard`,
`ghidra-function-site-status`, `ghidra-summarize`, `ghidra-review-rank-probes-summary`
**Plan / post-50 read-only status (12):** `fifty-step-plan-status`,
`post50-position-source-status`, `post50-mesh34-negative-binding-status`,
`post50-mesh34-complete-binding-negative-proof`, `post50-mesh329-family-proof`,
`post50-mesh329-source-binding-compare`, `mesh329-attribute-role-matrix`,
`phase1-m1.2-304-magic-analysis`, `phase1-m1.3-329-variant-layout-guard`,
`post50-promotion-readiness-status`, `post50-validation-suite`,
`post50-residual-strict-threshold-delta`
**Python-only analysis reports (5):** `position-gap-report`, `triage-fallback-candidates`,
`semantic-hint-crosstab`, `discovery-workbench`, `generated-output-guard`
**NiDataStream read-only status/evidence (14):** `nidatastream-descriptor-table-sample`,
`nidatastream-descriptor-table-sample-status`, `nidatastream-descriptor-table-sample-compare`,
`nidatastream-descriptor-neighborhood-scan`, `nidatastream-descriptor-reference-classify`,
`nidatastream-descriptor-base-model-review`, `nidatastream-descriptor-proof-status`,
`nidatastream-descriptor-sample-compare`, `nidatastream-evidence-status`,
`nidatastream-promotion-status`, `nidatastream-promotion-dashboard`,
`nidatastream-parser-field-proof-guard`, `nidatastream-parser-export-non-consumption-guard`,
`nidatastream-layout`

(41 total — 2 CLI meta `--help`/`-h` are handled by argparse and not counted as commands.)

## Validation

- 206 tests pass (160 existing + 46 new in `test_rift_read_only_no_spawn.py`)
- mypy clean
- ruff clean
- Code reviewer: thumbs up
- Pre-commit hooks (ruff, gitleaks, generated-output guard): all pass
