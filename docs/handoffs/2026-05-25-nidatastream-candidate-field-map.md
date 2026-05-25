# Handoff — NiDataStream candidate descriptor field map

Date: 2026-05-25

## Goal

Make the descriptor-helper semantic leads easier to review by surfacing the candidate static descriptor field map beside descriptor/sample byte-order evidence.

## What changed

- `CandidateFieldMap` entries now carry explicit candidate-only metadata:
  - `PromotionStatus: candidate-only`,
  - `StaticTableStrideBytes: 12`,
  - `StaticTableOffsetBytes` for the static table fields at offsets `0`, `4`, and `8`,
  - `StreamDescriptorRecordStatus: not-mapped-to-parser-field`.
- `nidatastream-descriptor-sample-compare` Markdown now includes a candidate descriptor field-map table.
- Descriptor proof and descriptor/sample comparison schemas validate the new optional field-map metadata without permitting promoted entries.
- Descriptor proof and descriptor/sample tests assert the static-table metadata and schema rejection of promoted field-map entries.
- Parser-field comparison docs now distinguish static table offsets from unmapped stream descriptor record semantics.

## Evidence / validation

Validation for this slice should include:

- `python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_proof_status.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_schema_registry.py`
- `python scripts/test_nidatastream_descriptor_proof_status.py`
- `python scripts/test_nidatastream_descriptor_sample_compare.py`
- `python scripts/test_schema_registry.py`
- `ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_proof_status.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py nidatastream-descriptor-sample-compare`
- `python scripts/rift_workflow.py nidatastream-promotion-preflight`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

## Known blockers / guardrails

- This maps static descriptor helper table offsets only; it does not map stream descriptor record bytes into parser/export fields.
- `FieldOrderPromoted=false` and `ParserExportPromotionAllowed=false` remain locked.
- Generated comparison reports under `Exports/` remain ignored and must not be staged.

## Next recommended actions

1. Add a dedicated semantic decision record only if stream descriptor record byte meanings can be proven from Ghidra plus sample bytes.
2. Add narrow parser-patch fixtures only after the semantic decision record is complete.
3. Keep dashboard/preflight as the required brake before parser/export work.
