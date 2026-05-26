# 2026-05-26 Position-source sibling-family schema handoff

## Goal

Schema-lock the candidate-only sibling-family report that drives the current
top post-50 discovery lane: meshSize `329`, stream `@212`, `23` evidence groups,
and `46` stream links.

## What changed

- Added `docs/schemas/position-source-sibling-family-report-v1.schema.json`.
- Added `scripts/test_position_source_sibling_family_report_schema.py`.
- The new test validates:
  - a focused fixture for the top meshSize `329` source-binding family,
  - guarded family threshold fields,
  - the current ignored local report when it exists.

## Evidence / validation

- `python -m py_compile scripts/test_position_source_sibling_family_report_schema.py`
- `python scripts/test_position_source_sibling_family_report_schema.py`
- `python scripts/test_schema_registry.py`
- `ruff check scripts/test_position_source_sibling_family_report_schema.py`
- `mypy scripts/test_position_source_sibling_family_report_schema.py --no-error-summary`
- `git diff --check`
- `python scripts/rift_workflow.py generated-output-guard`

## Known blockers

- This schema only locks report shape. It does not prove mesh#34 has complete
  geometry binding.
- Parser/export promotion remains blocked by the current post-50 status gates.

## Generated-output status

No new generated outputs are required for this slice. The optional actual-report
validation reads ignored `Exports/position-source-sibling-family-report.json`
when present but does not stage it.

## Next recommended actions

1. Add a compact family-summary compare packet for the top meshSize `329`
   `stream@212` lane if more than report-shape validation is needed.
2. Keep mesh#34 `@304/#57` evidence candidate-only until a complete geometry
   binding proof exists.
3. Re-run `post50-position-source-status --list-json` after any proof report
   refresh to avoid stale lane ordering.
