# 2026-06-13 — CI Green 4-Commit Sequence

**Date**: 2026-06-13
**Type**: Session Handoff — CI Repair
**Scope**: Resolve pre-existing CI failures masked by the Docs Lint failure
**Status**: All 4 commits landed on `origin/main`; full CI green

## Summary

A 4-commit sequence (`910b168` → `88af1a9` → `ac7db4c` → `4187892`) resolved pre-existing CI failures that had been hidden behind the Docs Lint failure's CI Summary gate. The root cause was a test fixture gap: the `POST50_POSITION_SOURCE_REPORTS` registry in `scripts/rift_workflow.py:6235` grew from 10 to 11 reports when the Phase 1 M1.1 work added `mesh329-family-attribute-role-matrix.json`, but three test files were not updated to write the new fixture.

## Commits

### `910b168` — docs: fix MD032 in 2026-06-11-live-family-scanner.md

1-line blank-line insertion in `docs/handoffs/2026-06-11-live-family-scanner.md` to fix the MD032 (blanks-around-lists) lint error. This commit exposed the pre-existing Python test failures (which had been masked by the CI Summary gate).

### `88af1a9` — test: add missing Mesh329AttributeRoleMatrix fixture to post50 status test

`scripts/test_post50_position_source_status.py` (+36, -3):

- Added a minimal valid fixture for `mesh329-family-attribute-role-matrix.json` (conforms to `docs/schemas/329-family-attribute-role-matrix-v1.schema.json`)
- Added `jsonschema.validate()` against the matrix schema with a PASS print
- Updated 3 count expectations: 10→11 (ReportStatuses count, ExistingReportCount, MissingReportCount in missing-fixture branch)
- 6 pre-existing CI failures resolved (report status count, freshness missing reports, freshness missing keys, schema-backed report statuses, next action, missing freshness missing reports)

### `ac7db4c` — test: add missing Mesh329AttributeRoleMatrix fixture to promotion-readiness test

`scripts/test_post50_promotion_readiness_status.py` (+28, -2):

- Added the same matrix fixture
- Updated 2 count expectations: 10→11 (SchemaBackedReportCount, ExistingReportCount)
- 2 pre-existing CI failures resolved (freshness missing reports, all-post50-reports-schema-backed gate)

### `4187892` — test: add missing Mesh329AttributeRoleMatrix fixture to validation-suite test

`scripts/test_post50_validation_suite_status.py` (+27, -1):

- Added the same matrix fixture
- Updated 1 count expectation: 10→11 (ExistingReportCount)
- CI exit-code-1 failure resolved (the "post50-validation-suite moved to rift_read_only.py" deprecation notice in the log is noise from the rift_read_only split in commit `e8749e9`, not the actual failure)

## Root Cause

Phase 1 M1.1 work added `mesh329-family-attribute-role-matrix.json` as the 11th report in `POST50_POSITION_SOURCE_REPORTS` (see `rift_workflow.py:6242`), but three test fixtures were not updated to write the new fixture. The Docs Lint failure was masking these Python test failures from the CI Summary gate, so the failures went undetected until the MD032 fix was applied.

## Validation

- **27/27 checks pass** on `test_post50_position_source_status.py`
- **7/7 checks pass** on `test_post50_promotion_readiness_status.py`
- **All checks pass** on `test_post50_validation_suite_status.py`
- **ruff clean** on all 3 test files
- **mypy clean** on all 3 test files
- **markdownlint clean** on the docs handoff file
- **Full CI green** on commit `4187892` (re-run: `27468397203`):
  - .NET Build & Test: success
  - Orphan Guard Regression: success
  - Python Lint & Test: success
  - Docs Lint: success

## Durability / Future Prevention

Three follow-on changes were made on 2026-06-13 to harden against the same failure mode:

1. **`scripts/test_post50_registry_invariant.py`** (new) — loops over `POST50_POSITION_SOURCE_REPORTS` and asserts every report has a matching fixture writer in at least one `test_post50_*.py` file (AST-based, robust to cosmetic changes). Catches the next occurrence of this failure mode at the unit-test level.
2. **`AGENTS.md` followup default** (updated) — list 10 followups (not 3) when using the `suggest_followups` tool, sorted by priority for the current workflow.
3. **`.github/workflows/ci.yml` `workflow_dispatch` trigger** (added) — `gh workflow run ci.yml --ref main` now works for manual re-runs.

## Non-Blocker (for future cleanup)

The 25-line `mesh329-family-attribute-role-matrix.json` fixture is duplicated verbatim across `test_post50_position_source_status.py`, `test_post50_promotion_readiness_status.py`, and `test_post50_validation_suite_status.py`. If a 4th test file ever needs it, extract a shared `write_minimal_mesh329_attribute_role_matrix_report(out_dir)` helper into a new `scripts/test_post50_fixtures.py` module. Not worth doing now — the duplication is contained to 3 files and matches the surrounding inline-JSON style.
