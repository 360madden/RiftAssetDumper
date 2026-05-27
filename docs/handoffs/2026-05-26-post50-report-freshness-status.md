# Handoff — Post-50 Report Freshness Visibility

Date: 2026-05-26

## Goal

Make post-50 status output show whether ignored report inputs are fresh relative to each other, without promoting any candidate evidence into parser/export truth.

## What changed

- Added `ReportFreshness` to `post50-position-source-status`.
- Threaded the same `ReportFreshness` object into `post50-promotion-readiness-status`.
- The freshness object reports existing/missing/unreadable counts, oldest/newest report mtimes, mtime range, oldest/newest keys, older-than-newest keys, and missing/unreadable keys.
- Updated the relevant JSON schemas and targeted tests.

## Evidence and validation

- `python -m py_compile scripts/rift_workflow.py scripts/test_post50_position_source_status.py scripts/test_post50_promotion_readiness_status.py`
- `python scripts/test_post50_position_source_status.py`
- `python scripts/test_post50_promotion_readiness_status.py`
- `python scripts/test_schema_registry.py`
- `ruff check scripts/rift_workflow.py scripts/test_post50_position_source_status.py scripts/test_post50_promotion_readiness_status.py`
- `mypy scripts/rift_workflow.py scripts/test_post50_position_source_status.py scripts/test_post50_promotion_readiness_status.py --no-error-summary`
- `python scripts/rift_workflow.py post50-position-source-status --list-json`
- `python scripts/rift_workflow.py post50-promotion-readiness-status --list-json`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

All checks passed in this slice.

## Current truth

- Current local ignored post-50 report inputs exist and are schema-backed candidate evidence.
- The current local report mtime range is visible in the status payload, so future runs can identify stale/older proof inputs before using them for decision-making.
- Parser/export promotion remains locked false.

## Known blockers

- The freshness status is relative to local ignored report files; it does not prove the reports were regenerated from the newest source assets.
- mesh#34 `@304/#57` still lacks complete geometry binding and remains candidate-only.

## Generated outputs

No copied RIFT assets or generated extraction output were staged. `Exports/` remains local/generated.

## Next recommended actions

1. Add a compact `post50-validation-suite` command for the core status/schema/guard checks.
2. Add a mesh#34 complete-binding search/negative-proof report for current sibling examples.
3. Add a residual strict-threshold delta report for the meshSize 305 payload 288 lane.
4. Add docs links for the post-50 status commands.
5. Keep parser/export behavior unchanged until promotion gates pass.
