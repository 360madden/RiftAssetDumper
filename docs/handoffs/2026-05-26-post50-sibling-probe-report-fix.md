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

## Post-50 status integration follow-up

Updated `post50-position-source-status` so it now reads the repaired sibling
probe report and the extra-position sibling report alongside the four earlier
post-50 reports. The status payload now surfaces a ranked
`source-binding-extra-position` lane for meshSize `329` mesh `#34`
`@304/#57`, keeping it explicitly candidate-only and blocked from parser/export
promotion.

Added `docs/schemas/position-source-sibling-extra-position-report-v1.schema.json`
with fixture validation so the extra-position report consumed by post-50 status
has a tracked shape guard.

Documented `docs/post50-source-binding-extra-position-checklist.md` so the
meshSize `329` mesh `#34` `@304/#57` lane has explicit candidate-only
promotion gates and non-goals before any parser/export work.

## Known blockers / uncertainty

- The report remains candidate-only. Shared position-stream evidence is a
  source-binding search clue, not geometry truth or OBJ/export readiness.
- The underlying `.NET` probe commands still emit the pre-existing
  `SharpCompress` NU1902 moderate advisory warning.
- Generated outputs remain local/ignored and should not be staged.

## Next recommended actions

1. Use the repaired/schema-validated report to keep the post-50 source-binding lane focused on
   meshSize `329` stream `@212`.
2. Build the focused, ignored byte-level comparison report requested by
   `docs/post50-source-binding-extra-position-checklist.md`.
3. Keep residual payload `288` evidence separate from sibling source-binding
   reports until a strict parser/export promotion gate exists.
