# Handoff — NiDataStream status edge fixtures

Date: 2026-05-25

## Goal

Make the promotion-status/dashboard lane fail closed for malformed or partial descriptor/sample evidence, not just the happy-path ignored local reports.

## What changed

- `nidatastream-promotion-status` now treats a non-object `nidatastream-layout-report.json` as an explicit layout-report error instead of assuming a JSON object.
- Added smoke-test coverage that verifies:
  - `DescriptorSampleCompareStatus` is required by the promotion status schema,
  - readiness flags must be booleans,
  - missing layout evidence reports zero passed sample/byte-order checks and `ready=false`,
  - corrupt layout JSON keeps the sample-byte gate blocked,
  - non-object layout JSON is reported as an error,
  - partial sample/byte-order counters fail closed and keep the sample-byte gate blocked.

## Evidence / validation

Validation for this slice should include:

- `python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py`
- `python scripts/test_nidatastream_promotion_status.py`
- `python scripts/test_schema_registry.py`
- `ruff check scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py nidatastream-promotion-preflight`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

## Known blockers / guardrails

- The edge fixtures validate the workflow brakes only; they do not promote descriptor semantics.
- `ParserExportPromotionAllowed=false` and `FieldOrderPromoted=false` remain locked.
- Generated local reports under `Exports/` remain ignored and must not be staged.

## Next recommended actions

1. Add a compact semantic descriptor-field mapping candidate table only after confirming the current Ghidra reports contain enough byte-level terms.
2. Keep using fail-closed fixtures before any parser/export-facing code change.
3. Consider a future dedicated schema edge-fixture test helper if promotion schemas keep growing.
