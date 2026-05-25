# Handoff: NiDataStream descriptor byte-role candidates

Date: 2026-05-25

## Goal

Classify observed descriptor-record bytes into candidate roles without changing parser/export behavior.

## What changed

- Added `DescriptorRecordByteRoleCandidates` to `nidatastream-descriptor-sample-compare`.
- Classified descriptor record byte 0 as a candidate static descriptor-table index when Ghidra record-index proof is present.
- Classified uniform-zero descriptor bytes as padding/reserved candidates.
- Kept variable unmapped descriptor bytes as semantic blockers.
- Surfaced byte-role counts in `nidatastream-promotion-status` and dashboard output.
- Extended schemas/tests to keep byte-role candidates candidate-only and promotion-locked.

## Current local evidence

Current ignored sample evidence shows:

- Byte 0: candidate static descriptor-table index.
- Byte 1: variable/unmapped.
- Byte 2: variable/unmapped.
- Byte 3: uniform-zero padding/reserved candidate.

`SemanticMappingReady`, `FieldOrderPromoted`, and `ParserExportPromotionAllowed` remain false.

## Evidence/validation

Run after implementation:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py
python scripts/test_nidatastream_descriptor_sample_compare.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
python scripts/rift_workflow.py nidatastream-promotion-preflight
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Known blockers

- Descriptor bytes 1 and 2 are still variable and unmapped.
- Byte 3 is only a padding/reserved candidate, not parser/export truth.
- Parser/export behavior remains unchanged and must stay guarded by non-consumption checks.

## Next recommended actions

1. Add focused sample fixtures that vary descriptor bytes 1 and 2 independently.
2. Add candidate-only Ghidra checks for whether bytes 1 and 2 encode component count/class or format-related metadata.
3. Keep promotion locked until all byte roles are proof-backed and pairing impact remains safe.

## Generated outputs

No copied RIFT assets are tracked. Local reports under `Exports/` remain ignored/generated.
