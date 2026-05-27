# Handoff — Residual Strict-Threshold Delta Proof

Date: 2026-05-26

## Goal

Make the meshSize 305 residual payload 288 blocker explicit and auditable by adding a schema-backed candidate-only report that shows its delta to the strict plausible threshold.

## What changed

- Added `post50-residual-strict-threshold-delta` workflow command.
- Added `Post50ResidualStrictThresholdDelta` PowerShell wrapper alias.
- Added `post50-residual-strict-threshold-delta/v1` JSON schema.
- Added targeted tests for the residual delta report and schema.
- Integrated the new report into post-50 status tracking, promotion-readiness advisory gates, and the compact validation suite.
- Updated post-50 status fixtures from 9 to 10 schema-backed report inputs.

## Current evidence

The local generated report shows payload `288` is the strongest residual candidate for meshSize 305 `stream@188`, with plausible ratio `0.9444`. It misses the strict `0.95` threshold by `0.0056` and still lacks complete geometry binding, so it remains candidate-only and parser/export remains locked.

## Evidence and validation

- `python -m py_compile scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_post50_residual_strict_threshold_delta.py scripts/test_post50_position_source_status.py scripts/test_post50_promotion_readiness_status.py scripts/test_post50_validation_suite_status.py scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_post50_residual_strict_threshold_delta.py`
- `python scripts/test_post50_position_source_status.py`
- `python scripts/test_post50_promotion_readiness_status.py`
- `python scripts/test_post50_validation_suite_status.py`
- `python scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py post50-residual-strict-threshold-delta`
- `python scripts/rift_workflow.py post50-validation-suite --list-json`
- `ruff check scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_post50_residual_strict_threshold_delta.py scripts/test_post50_position_source_status.py scripts/test_post50_promotion_readiness_status.py scripts/test_post50_validation_suite_status.py scripts/test_rift_workflow_command_wiring.py`
- `mypy scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_post50_residual_strict_threshold_delta.py scripts/test_post50_position_source_status.py scripts/test_post50_promotion_readiness_status.py scripts/test_post50_validation_suite_status.py scripts/test_rift_workflow_command_wiring.py --no-error-summary`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

All checks passed in this slice.

## Known blockers

- The report is a candidate-only blocker explanation; it does not prove geometry truth.
- Payload 288 still lacks strict-threshold pass and complete binding proof.
- Relative report mtime drift remains advisory because local ignored reports were generated at different times.

## Generated outputs

The command generated ignored local `Exports/post50-residual-strict-threshold-delta.json` and `.md` outputs. They were not staged. `Exports/` remains local/generated.

## Next recommended actions

1. Link the post-50 proof and validation commands from workflow docs.
2. Add a compact post-50 report refresh/order checklist.
3. Add a freshness guard that distinguishes advisory mtime drift from required stale-source blockers.
4. Investigate the payload 288 miss cause without promoting parser/export behavior.
5. Keep parser/export behavior locked until positive complete-binding proof exists.
