# 2026-05-26 Post-50 remaining report schemas handoff

## Goal

Schema-lock the remaining post-50 position-source input reports and make status
distinguish schema-backed candidate evidence from raw/missing candidate reports.

## What changed

- Added schemas:
  - `docs/schemas/position-source-gap-report-v1.schema.json`
  - `docs/schemas/residual-position-classifier-report-v1.schema.json`
  - `docs/schemas/residual-position-cluster-probe-report-v1.schema.json`
- Added `scripts/test_post50_remaining_report_schemas.py`.
- Extended `post50-position-source-status` report statuses with
  `EvidenceLevel`:
  - `schema-backed-candidate`
  - `raw-candidate`
  - `missing-or-unreadable`
- Updated the post-50 status schema/test to require `EvidenceLevel`.

## Current evidence

The current ignored local post-50 status now reports all 8 post-50 inputs as
`schema-backed-candidate` when present and parseable:

1. `PositionSourceGap`
2. `PositionSourceSiblingFamily`
3. `PositionSourceSiblingProbe`
4. `PositionSourceSiblingExtraPosition`
5. `Post50Mesh329FamilyProof`
6. `Post50Mesh329SourceBindingCompare`
7. `ResidualPositionClassifier`
8. `ResidualPositionClusterProbe`

## Validation

- `python -m py_compile scripts/rift_workflow.py scripts/test_post50_position_source_status.py scripts/test_post50_remaining_report_schemas.py`
- `python scripts/test_post50_remaining_report_schemas.py`
- `python scripts/test_post50_position_source_status.py`
- `python scripts/test_schema_registry.py`
- `ruff check scripts/rift_workflow.py scripts/test_post50_remaining_report_schemas.py scripts/test_post50_position_source_status.py`
- `mypy scripts/rift_workflow.py scripts/test_post50_remaining_report_schemas.py scripts/test_post50_position_source_status.py --no-error-summary`
- `python scripts/rift_workflow.py post50-position-source-status --list-json`

## Known blockers

- Schemas lock report shape and promotion brakes; they do not make residual or
  mesh#34 evidence export-ready.
- Parser/export promotion remains blocked by current status.

## Generated-output status

No generated output was staged. Tests optionally validate ignored `Exports/`
reports when present.

## Next recommended actions

1. Add the mesh#34 complete-binding negative proof packet/checklist.
2. Add a compact promotion-readiness checklist that consumes all schema-backed
   post-50 reports while keeping parser/export locked.
3. Re-run the post-50 status command after each proof refresh and keep lane
   ordering evidence-current.
