# Handoff — NiDataStream descriptor sample-context correlation

Date: 2026-05-25

## Goal

Surface copied-sample context for the remaining unmapped `NiDataStream` descriptor record bytes without changing parser/export behavior.

## What changed

- Added `DescriptorSampleContextCorrelation` to `nidatastream-descriptor-sample-compare`.
- The new section groups copied `ShiftedSamples` by `FirstDescriptorRecordBytes` and reports:
  - sample count per descriptor record,
  - top first pair-record byte patterns,
  - usage values,
  - access values,
  - type-name values.
- Added promotion-status/dashboard summary fields:
  - `DescriptorContextCorrelationReady`,
  - `DescriptorContextCorrelationSampleCount`,
  - `DescriptorContextCorrelationPatternCount`.
- Extended schemas and tests so the new evidence remains candidate-only and parser/export promotion remains locked.
- Refreshed workflow/checklist docs to mention descriptor/sample context correlation.

## Current evidence

Local ignored evidence currently reports:

- `DescriptorSampleContextCorrelation.SampleCount`: 50
- `SamplesWithDescriptorRecord`: 50
- `SamplesWithPairRecord`: 50
- `DescriptorPatternCount`: 5
- `CorrelationReady`: true
- `RemainingUnmappedByteOffsets`: `1,2`
- Blocker: `descriptor-context-correlation-parser-semantics-unmapped`

Top local descriptor context rows:

| Descriptor record | Samples | Pair patterns |
|---|---:|---:|
| `37 04 03 00` | 24 | 6 |
| `36 04 02 00` | 14 | 5 |
| `15 02 01 00` | 7 | 7 |
| `10 01 04 00` | 4 | 3 |
| `3c 01 04 00` | 1 | 1 |

## Validation

Passed:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py
python scripts/test_nidatastream_descriptor_sample_compare.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
python scripts/rift_workflow.py nidatastream-promotion-preflight
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Generated output safety

- Refreshed ignored local reports under `Exports/`.
- No copied RIFT assets or generated extraction/report outputs are intended to be staged.
- `generated-output-guard` reported 0 tracked and 0 staged generated/copy/build output paths.

## Known blockers

- Descriptor record bytes 1-2 remain unmapped for parser/export semantics.
- Context correlation is useful review evidence but does not prove exact parser field semantics by itself.
- `ParserExportPromotionAllowed=false` and `FieldOrderPromoted=false` remain intentionally locked by schemas/guards.

## Next recommended actions

1. Add a descriptor context-correlation review checklist that ranks which pair/usage/access/type clusters are worth manual static follow-up.
2. Compare the context rows against descriptor helper/builder decompile summaries to see if bytes 1-2 align with count/order/format/component concepts.
3. Add a focused negative fixture for missing pair records if context correlation becomes a promotion-adjacent gate.
4. Keep parser/export behavior unchanged until a narrow field-semantics decision record is filled and guards are green.
