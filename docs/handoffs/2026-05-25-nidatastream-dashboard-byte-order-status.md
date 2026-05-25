# Handoff — NiDataStream dashboard byte-order status

Date: 2026-05-25

## Goal

Surface descriptor/sample byte-order readiness directly in the promotion status/dashboard so agents do not have to open the sidecar comparison report to see whether the current sample-byte proof is complete.

## What changed

- `nidatastream-promotion-status --list-json` now includes `DescriptorSampleCompareStatus` with:
  - sample corpus scan/parse counts,
  - sample-byte check pass counts,
  - descriptor byte-order check pass counts,
  - aggregate descriptor/sample evidence readiness.
- `nidatastream-promotion-status` human output prints descriptor/sample sample-check and byte-order-check counts.
- `nidatastream-promotion-dashboard` Markdown now includes sample corpus, descriptor/sample byte checks, byte-order checks, and readiness rows.
- `sample-byte-agreement` gate evidence now reflects layout validity plus sample-byte and byte-order check counts.
- `docs/schemas/nidatastream-promotion-status-v1.schema.json` now validates the new dashboard/status object.
- Targeted smoke tests now verify the new status and dashboard fields.

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

- This is still candidate-only and report-only.
- `ParserExportPromotionAllowed=false` remains locked in the promotion status schema.
- `FieldOrderPromoted=false` remains locked in the descriptor proof schema.
- Ignored refreshed reports under `Exports/` must remain unstaged.

## Next recommended actions

1. Add fail-closed schema/tests for descriptor/sample status edge cases such as missing layout, parse errors, and partial check failures.
2. Use the dashboard readiness counts to focus the next semantic descriptor mapping proof.
3. Keep parser/export behavior unchanged until descriptor semantics, pairing impact, and negative fixtures pass together.
