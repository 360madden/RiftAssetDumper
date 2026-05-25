# 2026-05-25 NiDataStream descriptor proof status handoff

## Goal

Make descriptor-helper evidence machine-readable without promoting it into parser/export behavior.

## What changed

- Added `nidatastream-descriptor-proof-status` to `scripts/rift_workflow.py`.
- Wired `NiDataStreamDescriptorProofStatus` through `scripts/Invoke-RiftWorkflow.ps1` and command-wiring tests.
- Added `docs/schemas/nidatastream-descriptor-proof-status-v1.schema.json`.
- Added `scripts/test_nidatastream_descriptor_proof_status.py` with synthetic FunctionSiteSurvey reports for descriptor helper/builders.
- Extended `nidatastream-promotion-status --list-json` with a `DescriptorReportStatus` summary.
- Updated README and Ghidra/NiDataStream docs to point agents at the descriptor status command.

## Why it matters

Ghidra now contributes a concrete, repeatable descriptor evidence surface: the local FunctionSiteSurvey reports are checked for expected call edges, data-reference anchors, and decompile terms across `LoadBinary` plus three descriptor helper/builders. Current local evidence is 4/4 ready, but `FieldOrderPromoted` remains false and parser/export behavior remains unchanged.

## Evidence / validation

Commands run for this slice:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_proof_status.py scripts/test_nidatastream_promotion_status.py scripts/test_rift_workflow_command_wiring.py scripts/test_schema_registry.py
python scripts/test_nidatastream_descriptor_proof_status.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_rift_workflow_command_wiring.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_proof_status.py scripts/test_nidatastream_promotion_status.py scripts/test_rift_workflow_command_wiring.py scripts/test_schema_registry.py
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json | python -c "import json,sys; data=json.load(sys.stdin); print(data['SchemaVersion'], data['EvidenceReadyCount'], data['RequiredTargetCount'], data['AllRequiredEvidenceReady'])"
python scripts/rift_workflow.py nidatastream-promotion-status --list-json | python -c "import json,sys; data=json.load(sys.stdin); print(data['DescriptorReportStatus']['EvidenceReadyCount'], data['DescriptorReportStatus']['RequiredTargetCount'], data['Gates'][2]['State'])"
python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Observed key results: `nidatastream-descriptor-proof-status/v1 4 4 True`; promotion status reports descriptor gate state `candidate`; guard suite and generated-output guard passed.

## Known blockers / limits

- The descriptor command proves only local FunctionSiteSurvey report evidence shape: expected calls, data refs, and decompile terms.
- It does not yet prove a final byte-level field order, component semantics, or safe parser/export behavior.
- `FieldOrderPromoted` is schema-locked to false in v1.
- Parser/export promotion still requires sample-byte, pairing-impact, and narrow-parser-patch proof gates.

## Generated-output handling

No copied RIFT assets or generated report files were staged. Existing ignored Ghidra reports and `Exports/nidatastream-layout-report.json` remain local/generated evidence only.

## Next recommended actions

1. Add a promotion-readiness checklist for changing `FieldOrderPromoted`/`ParserExportPromotionAllowed` in a future schema version.
2. Add an executable pairing-impact bridge that ties descriptor/sample evidence to grouped candidate rows without promoting complete noisy groups.
3. Keep descriptor evidence in `ghidra-workflow-guard-suite` indirectly through `nidatastream-parser-field-proof-guard`/promotion status.
4. Re-run descriptor status after any refreshed FunctionSiteSurvey target before citing new Ghidra evidence.
5. Avoid parser/export patches until descriptor, sample-byte, pairing-impact, and narrow-patch tests all pass together.
