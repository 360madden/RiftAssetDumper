# 2026-05-26 — Post-50 Sibling Probe Report Fix

## Goal

Restore the Python `position-source-sibling-probe-report` workflow after the
post-50 status lane exposed a report-generation failure.

## What changed

- Fixed `scripts/rift_workflow_reports.py` so
  `position_source_sibling_probe_report()` mirrors the existing PowerShell
  workflow semantics:
  - validates two focused sibling pairs,
  - checks shared position stream block/payload/usage/access/role evidence,
  - checks matching vertex-count and topology evidence,
  - records the shifted/same payload-offset pattern,
  - keeps the report candidate-only with no parser/export promotion.
- Added a targeted fixture-backed test in
  `scripts/test_rift_workflow_reports.py` covering the shifted 325/329 pair
  and repeated 329 pair.

## Evidence / validation

```powershell
python -m py_compile scripts/rift_workflow_reports.py scripts/test_rift_workflow_reports.py
python scripts/test_rift_workflow_reports.py
python scripts/rift_workflow.py position-source-sibling-probe-report --skip-build
```

`position-source-sibling-probe-report --skip-build` now exits `0` and writes
ignored candidate-only outputs under `Exports/`:

- `Exports/position-source-sibling-probe-report.json`
- `Exports/position-source-sibling-probe-report.md`
- representative, secondary, and extra-position sibling reports

## Schema follow-up

Added `docs/schemas/position-source-sibling-probe-report-v1.schema.json` and
validated the fixture-backed sibling probe report against it in
`scripts/test_rift_workflow_reports.py`. The schema keeps the report
candidate-only and fail-closed around the exact shared-position evidence fields
used by the workflow.

## Known blockers / uncertainty

- The report remains candidate-only. Shared position-stream evidence is a
  source-binding search clue, not geometry truth or OBJ/export readiness.
- The underlying `.NET` probe commands still emit the pre-existing
  `SharpCompress` NU1902 moderate advisory warning.
- Generated outputs remain local/ignored and should not be staged.

## Next recommended actions

1. Use the repaired/schema-validated report to keep the post-50 source-binding lane focused on
   meshSize `329` stream `@212`.
2. Classify the meshSize `329` mesh `#34` extra `@304/#57` position-like stream
   as candidate-only source-binding evidence.
3. Keep residual payload `288` evidence separate from sibling source-binding
   reports until a strict parser/export promotion gate exists.
