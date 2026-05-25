# Handoff: NiDataStream descriptor record index proof

Date: 2026-05-25

## Goal

Capture the first concrete Ghidra-backed stream descriptor-record semantic as candidate-only workflow evidence: descriptor record byte 0 is the static descriptor-table index.

## What changed

- Added `DescriptorRecordIndexProof` to `nidatastream-descriptor-proof-status` and `nidatastream-descriptor-sample-compare`.
- The proof checks retained FunctionSiteSurvey decompile terms showing `LoadBinary` passes the read descriptor record value into descriptor helpers and that helpers mask `param_1 & 0xff` before indexing the 12-byte static table.
- Updated semantic feasibility to mark record byte 0 as candidate-mapped while keeping bytes 1-3, full semantic mapping, field-order promotion, and parser/export promotion blocked.
- Surfaced record byte-0 index status in promotion status/dashboard output.
- Extended schemas and tests so record-index proof remains candidate-only and promotion-locked.

## Evidence/validation

Run after implementation:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_proof_status.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py
python scripts/test_nidatastream_descriptor_proof_status.py
python scripts/test_nidatastream_descriptor_sample_compare.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_proof_status.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
python scripts/rift_workflow.py nidatastream-promotion-preflight
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Known blockers

- Descriptor record bytes 1-3 remain unmapped.
- The candidate byte-0 index proof is not parser/export truth and does not change decode/export behavior.
- `SemanticMappingReady`, `FieldOrderPromoted`, and `ParserExportPromotionAllowed` remain false.

## Next recommended actions

1. Add focused sample fixtures that vary bytes 1-3 independently of byte 0.
2. Add candidate-only checks for whether bytes 1-3 are always zero/padding in the current sample corpus.
3. Only after byte roles are proven, draft a parser/export promotion decision record.

## Generated outputs

No copied RIFT assets are tracked. Local reports under `Exports/` remain ignored/generated.
