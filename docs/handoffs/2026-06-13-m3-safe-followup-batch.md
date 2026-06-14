# 2026-06-13 — M3-Safe Followup Batch (4 commits)

**Date**: 2026-06-13
**Type**: Session Handoff — Durability Hardening
**Scope**: Three changes designed M3-safe (reversible, bounded, testable, single-file) plus one doc handoff
**Status**: All 4 commits landed on `origin/main`; CI run `27470486155` green on all 5 jobs

## Summary

A 4-commit M3-safe followup batch hardened the project against the "registry grew, test fixtures didn't" CI failure mode and added manual re-run capability. The batch was selected from a 10-item followup list using an explicit M3-safety filter (reversible / bounded / testable / single-file). Deferred items (tag v1.x release, DRY refactor across 3 test files, pre-commit hook additions) require higher-reasoning lanes and were left for a follow-on session.

The 4 commits:

- `45fac63` — `docs: update knowledge.md with CI-green sequence + Phase 1 milestones`
- `2d7b9c7` — `ci: add workflow_dispatch trigger for manual re-runs`
- `54e5f43` — `test: add POST50 registry/fixture invariant test for future-proofing`
- `cb2fe93` — `docs: 2026-06-13 CI-green 4-commit sequence handoff`

## Commits

### `45fac63` — docs: update knowledge.md with CI-green sequence + Phase 1 milestones

`knowledge.md` (+3 sections):

- **CI pipeline section** — corrected "Two parallel jobs" to "Four parallel jobs (3 windows + 1 ubuntu) + final summary"; added Orphan Guard Regression + Docs Lint job descriptions; added `workflow_dispatch` trigger note (2026-06-13).
- **Current project state section** — added "CI green sequence (2026-06-13, 4 commits)" bullet with commit SHAs and root-cause.
- **New "Recent Phase 1 milestones" section** — M1.1 (✅ complete), M1.2 (⏳ in progress), M1.3 (⏳ draft) with handoff doc references. Emoji aligned to file's existing ✅/⏭️ vocabulary.

### `2d7b9c7` — ci: add workflow_dispatch trigger for manual re-runs

`.github/workflows/ci.yml` (+1 line):

- Added `workflow_dispatch:` under `on:`. No other changes. No job changes.
- Enables `gh workflow run ci.yml --ref main` to manually re-trigger the same 5-job CI matrix (dotnet, python, lint-docs, orphan-guard, final).

### `54e5f43` — test: add POST50 registry/fixture invariant test for future-proofing

`scripts/test_post50_registry_invariant.py` (new, ~100 lines):

- Imports `POST50_POSITION_SOURCE_REPORTS` from `rift_workflow` via `sys.path` manipulation.
- `get_report_filenames()` def helper returns a fresh snapshot of the registry's filenames (encapsulated so callers see live state, not a frozen module-level snapshot).
- `_collect_fixture_writes(test_file, report_filenames)` uses AST (not regex) to parse each `scripts/test_post50_*.py` and collect string literals matching known report filenames.
- `test_all_reports_have_fixtures()` asserts every report in the registry has a matching fixture writer.
- `test_no_orphan_fixtures()` asserts no test file references a fixture for a report not in the registry.
- `if __name__ == "__main__":` block prints PASS results for the CI direct-invocation pattern.
- **Pre-commit note**: `ruff format` reformatted the file on first commit attempt (mechanical, line length / quotes only, no logic change). Re-staged and committed cleanly on retry; no `--no-verify` used.

### `cb2fe93` — docs: 2026-06-13 CI-green 4-commit sequence handoff

`docs/handoffs/2026-06-13-ci-green-4-commit-sequence.md` (new, ~70 lines):

- Documents the prior 4-commit CI repair sequence (910b168 + 88af1a9 + ac7db4c + 4187892).
- Sections: Summary, Commits (per commit), Root Cause, Validation, Durability/Prevention, Non-Blocker note.
- Cross-references this M3-safe followup batch as the durability layer for the fix.

## Why These Changes (M3-Safety Rationale)

The 4-commit batch was selected from the 10-item M3-safety matrix with these criteria:

- **Reversible** — every change can be undone via `git revert` (or `git tag -d` / `gh secret delete` for tag-style changes).
- **Bounded** — single-file or single-config-block changes; no cross-cutting refactors.
- **Testable** — each change has a clear validation gate (markdownlint for docs, ruff + mypy + test run for Python, yaml.safe_load for ci.yml).
- **Single-file** — knowledge.md is one file; ci.yml is one config; invariant test is one new file; handoff is one new file.

Deferred (not M3-safe for the M3 lane):

- Tag v1.x release — version selection is a judgment call M3 might get wrong (deferred to higher-reasoning lane).
- DRY refactor of the 25-line matrix fixture across 3 test files — **resolved 2026-06-14** by `d5a0a07` (`test: share POST50 mesh329 matrix fixture`).
- Pre-commit hook addition — affects local dev workflow, M3 might pick a bad trigger event (deferred).
- Deprecation notice investigation — **resolved 2026-06-14** by `7097c12` (`ci: update GitHub Actions to Node 24 majors`); remote CI stayed green in `27514610185`, `27514690400`, and `27514768077`.
- Parser UX: hint at missing process identifier when --scan-region-base is set — see `docs/handoffs/2026-06-14-parser-ux-region-pin-hint.md` (non-blocking UX follow-up, deferred to single-purpose docs commit after the §8.4 Step 49 status decision lands; live-read tooling must not be in flux during the decision window).

## Validation

- **ruff clean** on `scripts/test_post50_registry_invariant.py`
- **mypy clean** on `scripts/test_post50_registry_invariant.py` (Python 3.14 strict)
- **Test run**: `python scripts/test_post50_registry_invariant.py` → "PASS: all 11 reports in POST50_POSITION_SOURCE_REPORTS have fixture writers" + "PASS: no orphan fixture references in test_post50_*.py files"
- **markdownlint clean** on `knowledge.md` and `docs/handoffs/2026-06-13-ci-green-4-commit-sequence.md`
- **YAML valid** for `.github/workflows/ci.yml` (triggers: `[push, pull_request, workflow_dispatch]`; jobs: `[dotnet, python, lint-docs, orphan-guard, final]`)
- **CI run `27470486155`** (pushed commit `cb2fe93`):
  - .NET Build & Test: success
  - Python Lint & Test: success (new `test_post50_registry_invariant.py` ran in the job; "All tests passed!")
  - Docs Lint: success
  - Orphan Guard Regression: success
  - Summary: success
- **Pre-commit hooks** (ruff, gitleaks, generated-output guard, dotnet format) passed on each commit. 3 of 4 commits passed first try; commit 3 was aborted once by `ruff format` (reformatted the file, no logic change), re-staged and passed on retry — no `--no-verify` used.

## Durability / Future Prevention

Three changes from this batch add durable protections:

1. **`scripts/test_post50_registry_invariant.py`** (commit `54e5f43`) — machine-checkable invariant that fails CI if a 12th report is added to `POST50_POSITION_SOURCE_REPORTS` without updating test fixtures. AST-based, robust to cosmetic changes.
2. **`.github/workflows/ci.yml` `workflow_dispatch` trigger** (commit `2d7b9c7`) — manual re-runs are now possible via `gh workflow run ci.yml --ref main`. Useful for testing CI changes without waiting for a push or PR.
3. **`knowledge.md` updates** (commit `45fac63`) — durable project knowledge now records the CI pipeline structure, the CI green sequence, and Phase 1 milestone status. Future agents see current state.

Follow-on resolution:

- **CI action deprecation path** (commit `7097c12`) — GitHub Actions were upgraded to Node 24-compatible majors (`actions/checkout@v6`, `actions/setup-dotnet@v5`, `actions/setup-python@v6`, `DavidAnson/markdownlint-cli2-action@v23`). This resolves the deferred "Deprecation notice investigation" without changing build/test commands.
- **POST50 matrix fixture DRY refactor** (commit `d5a0a07`) — the repeated mesh329 attribute-role matrix payload was extracted to `scripts/post50_test_fixtures.py` and reused by the three POST50 status tests. Report filenames and assertions stayed in the tests, preserving registry-invariant coverage.

## Related

- Prior handoff: `docs/handoffs/2026-06-13-ci-green-4-commit-sequence.md` (this batch's commit 4 reproduces that handoff's content)
- Prior M3-safety analysis: see conversation context for the 10-item M3-safety matrix and the 6-item M3-safe subset selection
- AGENTS.md: durable project rule "Always include optional top 10 suggestions for next best recommended action. Default to 10 followups (not 3) when invoking the `suggest_followups` tool; sort them by priority with the best followups for the current workflow first." (set 2026-06-13)
