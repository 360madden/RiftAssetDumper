# Handoff: NiDataStream descriptor semantic feasibility

Date: 2026-05-25

## Goal

Make the descriptor/sample comparison explicitly compare candidate static descriptor-table offsets against observed stream descriptor-record byte distributions without promoting either side to parser/export truth.

## What changed

- Added `DescriptorSemanticFeasibility` to `nidatastream-descriptor-sample-compare` output.
- Added a blocked `descriptor-semantic-map` promotion gate to `nidatastream-promotion-status`/dashboard surfaces.
- Extended schemas/tests so semantic mapping and parser/export promotion remain locked false in v1.
- Updated the NiDataStream parser-field comparison and readiness docs to call out the static-vs-stream semantic gap.

## Evidence/validation

Run after implementation:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py
python scripts/test_nidatastream_descriptor_sample_compare.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-promotion-preflight
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Known blockers

- Stream descriptor-record byte positions remain unmapped to parser/export semantics.
- `ParserExportPromotionAllowed` and `FieldOrderPromoted` intentionally remain false.
- Any future parser/export change still needs a decision record, focused fixtures, pairing-impact proof, and non-consumption guard updates.

## Next recommended actions

1. Add a focused fixture that varies descriptor-record bytes so semantic mapping proof can distinguish count/class/format hypotheses.
2. If Ghidra helper/control-flow evidence identifies a concrete byte role, add it as candidate-only first with schema guards.
3. Keep parser/export behavior unchanged until semantic mapping, pairing impact, and narrow parser-patch gates are green together.

## Generated outputs

No copied RIFT assets are tracked. Local reports under `Exports/` remain ignored/generated.
