# Handoff — NiDataStream promotion status table-sample comparison

Date: 2026-05-25

## Goal

Integrate descriptor-table multi-report comparison into the promotion-status gate so parser/export readiness uses the combined known table evidence, not only a single selected table-sample report.

## What changed

- `nidatastream-promotion-status --list-json` now includes descriptor-table sample comparison counters:
  - report count,
  - existing report count,
  - ready report count,
  - nonzero report count,
  - all-existing-reports-zero flag.
- The `descriptor-table-sample-proof` gate evidence now points to `nidatastream-descriptor-table-sample-compare --list-json`.
- Updated `docs/schemas/nidatastream-promotion-status-v1.schema.json`.
- Added promotion-status tests for the new comparison fields.
- Updated `docs/ai-driven-workflow.md`.

## Evidence / validation

Validation for this slice:

- `python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py`
- `python scripts/test_nidatastream_promotion_status.py`
- `python scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py nidatastream-promotion-status --list-json`

Current retained evidence still blocks promotion:

- Known descriptor-table reports are all zero.
- No known descriptor-table sample report has nonzero semantic evidence.
- `ParserExportPromotionAllowed` remains `false`.

## Generated outputs

No generated outputs were created by this slice. The status command reads ignored local evidence and writes nothing.

## Known blockers / remaining uncertainty

- Promotion status now sees multi-report table evidence, but it still does not include neighborhood-scan and reference-classification summaries directly in the same status packet.
- No parser/export behavior was changed.

## Next recommended actions

1. Add reference-classification operand summaries to the next descriptor dashboard/status packet.
2. Add neighborhood-scan nonzero-hit summary beside table-sample comparison.
3. Generate a bounded candidate-only query plan from operand scale/offset evidence before more Ghidra execution.
