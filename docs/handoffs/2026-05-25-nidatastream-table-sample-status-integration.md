# Handoff — NiDataStream descriptor-table sample status integration

Date: 2026-05-25

## Goal

Make the new Ghidra descriptor-table sampler evidence visible in the existing NiDataStream descriptor/sample and promotion-status workflow without promoting parser/export behavior.

## What changed

- Added `DescriptorTableSampleStatus` to `nidatastream-descriptor-sample-compare` output.
- Added schema coverage for descriptor-table sample status in `docs/schemas/nidatastream-descriptor-sample-compare-v1.schema.json`.
- Surfaced descriptor-table sample readiness, row counts, all-zero status, and semantic-promotion lock in `nidatastream-promotion-status` and promotion dashboard output.
- Added promotion-status schema fields for descriptor-table sample status in `docs/schemas/nidatastream-promotion-status-v1.schema.json`.
- Added test fixtures and negative schema checks for descriptor-table sample status.

## Evidence observed

Local current repo state:

```powershell
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare --list-json
```

Observed descriptor-table sample status from ignored local Ghidra evidence:

| Field | Value |
|---|---:|
| Report exists | true |
| Rows | 15 |
| Nonzero rows | 0 |
| All rows zero | true |
| Stream semantics explained | false |

## Interpretation

The workflow now treats the descriptor-table sampler as durable candidate-only evidence. The current all-zero indexed sample result is visible as blocker/status data instead of living only in an ignored report. Parser/export promotion remains locked because table samples do not explain descriptor semantics.

## Validation / safety

Validated during this stage:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py
python scripts/test_nidatastream_descriptor_sample_compare.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare --list-json
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Generated descriptor-table sample reports remain ignored under `Exports/ghidra-reports/`.

## Known blockers

- Descriptor-table sample report exists and is readable, but all current sampled rows are zero.
- `DescriptorTableSampleStatus.StreamSemanticsExplained` is intentionally schema-locked to false.
- Descriptor record bytes 1-2 remain unmapped for parser/export semantics.

## Next recommended actions

1. Add a compact descriptor-table sample field/index status row to any remaining human docs that reference descriptor/sample comparison.
2. Investigate alternate static table base/address interpretations only through candidate-only ignored reports.
3. Keep parser/export promotion blocked until nonzero table evidence plus sample bytes are semantically mapped and guarded.
