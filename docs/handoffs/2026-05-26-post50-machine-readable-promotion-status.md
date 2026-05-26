# Handoff — Post-50 Machine-Readable Promotion Status

Date: 2026-05-26

## Goal

Make the post-50 source-binding/promotion lane easier to audit by adding machine-readable status commands for mesh#34 negative-binding evidence and parser/export promotion readiness.

## What changed

- Added `post50-mesh34-negative-binding-status` to summarize the meshSize 329 / mesh#34 extra `@304/#57` lane as candidate-only negative-binding evidence.
- Added `post50-promotion-readiness-status` to summarize parser/export promotion gates from the existing post-50 report set.
- Added PowerShell wrapper aliases:
  - `Post50Mesh34NegativeBindingStatus`
  - `Post50PromotionReadinessStatus`
- Added Draft 2020-12 JSON schemas for both new status payloads.
- Added a targeted Python test that builds a temp report fixture, runs both commands with `--list-json`, validates schemas, and verifies promotion remains locked.
- Extended workflow command-wiring tests to cover the new aliases.

## Evidence and validation

- `python -m py_compile scripts/rift_workflow.py scripts/test_post50_promotion_readiness_status.py scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_post50_promotion_readiness_status.py`
- `python scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_schema_registry.py`
- `ruff check scripts/rift_workflow.py scripts/test_post50_promotion_readiness_status.py scripts/test_rift_workflow_command_wiring.py`
- `mypy scripts/rift_workflow.py scripts/test_post50_promotion_readiness_status.py scripts/test_rift_workflow_command_wiring.py --no-error-summary`
- `python scripts/rift_workflow.py post50-mesh34-negative-binding-status --list-json`
- `python scripts/rift_workflow.py post50-promotion-readiness-status --list-json`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

All checks passed in this slice.

## Current truth

- All tracked post-50 report statuses are schema-backed candidate evidence.
- mesh#34 `@304/#57` remains useful discovery evidence, but it is negative-binding evidence for parser/export because the current examples still lack complete attribute-set and UV binding.
- Parser/export promotion remains locked false.

## Known blockers

- `mesh34-complete-geometry-binding-not-proven`
- `mesh34-uv-stream-missing`
- `mesh329-extra-position-like-stream-candidate-only`
- `residual-position-strict-threshold-not-met`
- `residual-cluster-no-complete-geometry-binding`
- `parser-export-promotion-not-allowed`

## Generated outputs

No copied RIFT assets or generated extraction output were staged. The status commands were exercised with `--list-json`; ignored `Exports/` contents remain local/generated.

## Next recommended actions

1. Add report-freshness metadata to post-50 status output so stale ignored reports are visible.
2. Add a compact `post50-validation-suite` command that runs the core schema/status guards without a heavy validation loop.
3. Add a mesh#34 complete-binding search/negative-proof report that records the absence of position/normal/UV binding across current siblings.
4. Add a residual strict-threshold delta report to show exactly what keeps `0.9444` from promotion.
5. Add docs links for the two new machine-readable status commands.
