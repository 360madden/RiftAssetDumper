# Handoff: NiDataStream descriptor record pattern matrix

Date: 2026-05-25

## Goal

Add a candidate-only per-record matrix that makes observed descriptor record patterns reviewable without changing parser/export behavior.

## What changed

- Added `DescriptorRecordPatternMatrix` to `nidatastream-descriptor-sample-compare`.
- Joined each observed descriptor record pattern with:
  - byte-0 candidate static-table index value,
  - bytes 1-2 candidate helper-lookup ignored values,
  - byte 3 sign-guard/padding candidate value,
  - bytes that remain unmapped for parser/export semantics.
- Surfaced matrix row count in `nidatastream-promotion-status` and the dashboard.
- Extended schemas/tests so the matrix remains candidate-only and promotion-locked.

## Current local evidence

Current ignored sample evidence shows 5 descriptor record pattern rows:

- `37 04 03 00` count 90
- `36 04 02 00` count 49
- `15 02 01 00` count 23
- `3c 01 04 00` count 14
- `10 01 04 00` count 8

The matrix makes bytes 1-2 visible per pattern, but they remain parser/export-unmapped blockers.

## Evidence/validation

Run during implementation:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py
python scripts/test_nidatastream_descriptor_sample_compare.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-promotion-preflight
```

## Known blockers

- Pattern rows are candidate-only sample evidence.
- Bytes 1-2 remain unmapped for parser/export semantics.
- `SemanticMappingReady`, `FieldOrderPromoted`, and `ParserExportPromotionAllowed` remain false.
- No parser/export behavior was changed.

## Next recommended actions

1. Add candidate-only correlation fields that compare bytes 1-2 against nearby pair-record values and semantic usage/access labels.
2. Add negative fixtures for malformed descriptor records in the pattern matrix.
3. Keep all pattern evidence report-only until parser/export semantics are independently proven.

## Generated outputs

`nidatastream-descriptor-sample-compare` refreshed ignored local outputs under `Exports/`. No copied RIFT assets or generated reports should be staged.
