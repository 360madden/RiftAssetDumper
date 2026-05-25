# Handoff — NiDataStream promotion field-map status

Date: 2026-05-25

## Goal

Expose the remaining descriptor semantic gap in the top-level promotion status/dashboard, not only in the descriptor/sample comparison sidecar.

## What changed

- `nidatastream-promotion-status --list-json` now includes `DescriptorFieldMapStatus` with:
  - total candidate field-map entries,
  - candidate-only entry count,
  - static table offset count,
  - static table stride when uniform,
  - stream descriptor record mapped count/status.
- Human promotion status now prints descriptor field-map counts and whether stream descriptor records are mapped.
- Promotion dashboard Markdown now includes descriptor field-map and stream descriptor record mapped rows.
- Promotion status schema and smoke tests validate the new status object and fail closed on non-boolean mapped status.
- Workflow docs/checklists now call out that static descriptor table offsets are visible, while stream record semantics remain unmapped.

## Evidence / validation

Validation for this slice should include:

- `python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py`
- `python scripts/test_nidatastream_promotion_status.py`
- `python scripts/test_schema_registry.py`
- `ruff check scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py nidatastream-promotion-status --list-json`
- `python scripts/rift_workflow.py nidatastream-promotion-dashboard`
- `python scripts/rift_workflow.py nidatastream-promotion-preflight`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

## Known blockers / guardrails

- Stream descriptor record semantics are still not mapped to parser/export fields.
- `FieldOrderPromoted=false` and `ParserExportPromotionAllowed=false` remain locked.
- Ignored dashboard/comparison reports under `Exports/` must remain unstaged.

## Next recommended actions

1. Decide whether stream descriptor record bytes can be proven from current Ghidra reports; if not, document that blocker explicitly.
2. If proof exists, add a candidate-only semantic decision record before touching parser/export code.
3. Keep the promotion dashboard as the quick preflight surface for future autonomous agents.
