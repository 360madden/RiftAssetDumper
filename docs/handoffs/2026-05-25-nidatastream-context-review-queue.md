# Handoff — NiDataStream descriptor sample-context review queue

Date: 2026-05-25

## Goal

Make the descriptor/sample context correlation immediately actionable by ranking candidate-only static-review rows for remaining `NiDataStream` descriptor bytes 1-2.

## What changed

- Added `ReviewQueueRows` and `ReviewQueueCount` under `DescriptorSampleContextCorrelation` in `nidatastream-descriptor-sample-compare`.
- The queue ranks descriptor records by copied-sample coverage, pair-record variety, and descriptor-record bytes.
- Each queue row includes dominant copied-sample context:
  - first pair-record bytes/count,
  - usage value/count,
  - access value/count,
  - type name/count,
  - candidate-only review rationale.
- Extended the descriptor/sample compare schema and tests to reject malformed review queue ranks.
- Markdown output now includes a `Descriptor/sample context review queue` section.

## Current local review queue

Ignored local evidence currently reports 5 review rows:

| Rank | Descriptor record | Samples | Pair patterns | Dominant pair record | Dominant usage | Dominant access |
|---:|---|---:|---:|---|---|---|
| 1 | `37 04 03 00` | 24 | 6 | `00 00 00 00 0a 00 00 00` (8) | `1` (24) | `19` (24) |
| 2 | `36 04 02 00` | 14 | 5 | `00 00 00 00 0a 00 00 00` (6) | `1` (14) | `19` (14) |
| 3 | `15 02 01 00` | 7 | 7 | `00 00 00 00 06 00 00 00` (1) | `0` (7) | `19` (7) |
| 4 | `10 01 04 00` | 4 | 3 | `00 00 00 00 0a 00 00 00` (2) | `1` (4) | `19` (4) |
| 5 | `3c 01 04 00` | 1 | 1 | `00 00 00 00 28 01 00 00` (1) | `1` (1) | `19` (1) |

## Validation

Passed:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py
python scripts/test_nidatastream_descriptor_sample_compare.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
python scripts/rift_workflow.py nidatastream-promotion-preflight
```

## Generated output safety

- Refreshed ignored local reports under `Exports/`.
- No copied RIFT assets or generated extraction/report outputs are intended to be staged.
- `generated-output-guard` ran inside descriptor/sample compare and preflight and reported 0 tracked/staged generated output paths.

## Known blockers

- The review queue is a prioritization aid, not parser/export truth.
- Descriptor bytes 1-2 still need exact semantic proof from Ghidra/helper/builder evidence and parser fixtures.
- Parser/export promotion remains intentionally locked by schema and guards.

## Next recommended actions

1. Compare the rank-1 and rank-2 descriptor records against descriptor helper/builder decompile summaries.
2. Add a focused static-evidence report that maps review-queue records to helper/builder target terms when reliable.
3. Keep context rows candidate-only until exact byte semantics are proven and negative fixtures exist.
