# Handoff — NiDataStream descriptor record byte summary

Date: 2026-05-25

## Goal

Move the stream descriptor-record byte evidence from raw counter rows into a machine-readable and Markdown-visible distribution, while keeping it explicitly unmapped to parser/export semantics.

## What changed

- `nidatastream-descriptor-sample-compare` now emits `DescriptorRecordByteSummary`.
- The summary records:
  - source counter key,
  - descriptor record pattern count,
  - observed record count,
  - malformed record count,
  - record width,
  - per-byte offset value distributions.
- Descriptor/sample Markdown now includes a `Descriptor record byte distribution` table.
- Descriptor/sample tests validate the summary and schema rejection of promoted record-byte evidence.
- Parser-field comparison and promotion-readiness docs now list descriptor record byte distributions as distribution-only evidence.

## Evidence / validation

Validation for this slice should include:

- `python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_schema_registry.py`
- `python scripts/test_nidatastream_descriptor_sample_compare.py`
- `python scripts/test_schema_registry.py`
- `ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py nidatastream-descriptor-sample-compare`
- `python scripts/rift_workflow.py nidatastream-promotion-preflight`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

## Known blockers / guardrails

- This is distribution evidence only; byte offsets are not mapped to parser/export semantics.
- `FieldOrderPromoted=false` and `ParserExportPromotionAllowed=false` remain locked.
- Refreshed reports under `Exports/` remain ignored and must not be staged.

## Next recommended actions

1. Add a candidate-only semantic feasibility report that compares descriptor-record byte distributions against static descriptor field-map offsets without promoting either side.
2. If the feasibility report cannot prove semantics, document the stream-record mapping blocker explicitly.
3. Keep parser/export behavior unchanged until the semantic mapping has a decision record and negative fixtures.
