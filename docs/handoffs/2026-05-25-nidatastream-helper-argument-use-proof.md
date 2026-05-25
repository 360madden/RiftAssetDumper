# Handoff: NiDataStream descriptor helper argument-use proof

Date: 2026-05-25

## Goal

Surface candidate-only Ghidra proof for which descriptor-record bytes affect tracked descriptor helper table lookup.

## What changed

- Added `DescriptorHelperArgumentUseProof` to `nidatastream-descriptor-proof-status` and `nidatastream-descriptor-sample-compare`.
- Checked the descriptor helper and both tracked builder helpers for:
  - signed-negative guard evidence,
  - byte-0 table lookup masking via `param_1 & 0xff`,
  - absence of tracked high-byte lookup terms.
- Surfaced helper high-byte proof status in `nidatastream-promotion-status` and dashboard output.
- Extended schemas/tests so this evidence remains candidate-only and parser/export promotion remains locked.

## Current local evidence

Current ignored Ghidra reports show `3/3` helper argument-use checks pass:

- Byte 0: candidate static descriptor-table lookup index.
- Bytes 1-2: candidate ignored for tracked helper lookup, but still unmapped for parser/export semantics.
- Byte 3: sign-guard-related candidate only; observed descriptor record byte 3 remains uniform zero in current sample evidence.

`SemanticMappingReady`, `FieldOrderPromoted`, and `ParserExportPromotionAllowed` remain false.

## Evidence/validation

Run during implementation:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_proof_status.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py
python scripts/test_nidatastream_descriptor_proof_status.py
python scripts/test_nidatastream_descriptor_sample_compare.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_proof_status.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py
mypy scripts/ --no-error-summary
python -c "import pathlib, py_compile; [py_compile.compile(str(path), doraise=True) for path in pathlib.Path('scripts').glob('*.py')]"
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
python scripts/rift_workflow.py nidatastream-promotion-preflight
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Known blockers

- Bytes 1-2 are only proven unused for tracked helper table lookup; they remain unmapped for parser/export semantics.
- Helper argument-use proof is candidate-only and must not be consumed by decode/export code.
- No parser/export behavior was changed.

## Next recommended actions

1. Add a candidate-only per-record descriptor pattern matrix that joins byte0 index, bytes1-2 values, and sample block context.
2. Add focused fixtures that vary bytes 1 and 2 independently to make parser/export semantic blockers easier to review.
3. Keep promotion locked until descriptor semantics, pairing impact, and a narrow parser patch are proof-backed together.

## Generated outputs

`nidatastream-descriptor-sample-compare` refreshed ignored local outputs under `Exports/`. No copied RIFT assets or generated reports should be staged.
