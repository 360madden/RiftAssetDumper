# 2026-05-26 Post-50 meshSize 329 source-binding compare handoff

## Goal

Build a schema-backed, candidate-only proof report that compares the shared
primary meshSize `329` source-binding stream `@212/#28` with mesh#34's extra
position-like stream `@304/#57` across the current sibling examples.

## What changed

- Added `post50-mesh329-source-binding-compare`, a Python workflow command that
  reads `Exports/position-source-sibling-extra-position-report.json` and writes:
  - `Exports/post50-mesh329-source-binding-compare.json`
  - `Exports/post50-mesh329-source-binding-compare.md`
- Added schema coverage at
  `docs/schemas/post50-mesh329-source-binding-compare-v1.schema.json`.
- Integrated the compare report into `post50-position-source-status` so status
  now lists the new ignored report and enriches the mesh#34 extra-position lane
  when the compare packet exists.
- Added Python and PowerShell wrapper wiring for
  `Post50Mesh329SourceBindingCompare`.
- Added targeted tests for the report schema, status integration, and command
  wiring.

## Current evidence

The retained local compare packet currently covers three sibling examples:

| ID | Primary `@212/#28` vectors | Extra `@304/#57` vectors | Extra payload remainder | mesh#34 normal vectors |
|---|---:|---:|---:|---:|
| `0364ea142bc00ce7` | 48 | 20 | 0 | 30 |
| `04de901531a091ab` | 37 | 23 | 4 | 35 |
| `066fa520a8ce62e3` | 22 | 8 | 0 | 12 |

Aggregate candidate-only findings:

- Shared primary `@212/#28`: `3/3`.
- Extra mesh#34 `@304/#57`: `3/3`.
- mesh#7 complete attribute sets: `3/3`.
- mesh#34 complete attribute sets: `0/3`.
- mesh#34 UV streams: `0`.
- Parser/export promotion: `false`.

## Validation

- `python -m py_compile scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_post50_mesh329_source_binding_compare.py scripts/test_post50_position_source_status.py scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_post50_mesh329_source_binding_compare.py`
- `python scripts/test_post50_position_source_status.py`
- `python scripts/test_rift_workflow_command_wiring.py`
- `python scripts/rift_workflow.py post50-mesh329-source-binding-compare`
- Actual ignored compare report validated against
  `docs/schemas/post50-mesh329-source-binding-compare-v1.schema.json`.
- `python scripts/rift_workflow.py post50-position-source-status --list-json`
- `python scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py generated-output-guard`
- `ruff check scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_post50_mesh329_source_binding_compare.py scripts/test_post50_position_source_status.py scripts/test_rift_workflow_command_wiring.py`
- `mypy scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_post50_mesh329_source_binding_compare.py scripts/test_post50_position_source_status.py scripts/test_rift_workflow_command_wiring.py --no-error-summary`

## Known blockers

- `mesh329-extra-position-like-stream-candidate-only`
- `mesh34-missing-complete-attribute-set`
- `mesh34-uv-stream-missing`
- `parser-export-promotion-not-allowed`

## Generated-output status

Generated compare output was created under ignored `Exports/` and remains local.
No copied RIFT assets or generated extraction/export output should be staged.

## Next recommended actions

1. Add a small status/schema validation for the actual ignored compare report
   when present, without requiring generated output in CI.
2. Convert the mesh#34 compare packet into a promotion-decision checklist input
   that explicitly blocks decode/export consumption until all geometry bindings
   pass.
3. Continue with the next source-binding family proof for meshSize `329`
   stream `@212` before revisiting residual meshSize `305` candidates.
