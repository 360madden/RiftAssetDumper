# NiDataStream parser/export non-consumption guard

Date: 2026-05-25

## Goal

Keep the post-Stage-18 Ghidra/NiDataStream proof lane safe by adding an explicit guard that prevents candidate NiDataStream/Ghidra layout evidence from becoming parser/export behavior without a deliberate promotion patch.

## What changed

- Added `nidatastream_parser_export_non_consumption_guard()` in `scripts/rift_workflow_guards.py`.
- Added workflow command and PowerShell alias:
  - `python scripts/rift_workflow.py nidatastream-parser-export-non-consumption-guard`
  - `NiDataStreamParserExportNonConsumptionGuard`
- Wired the new guard into `nidatastream-parser-field-proof-guard`, so `ghidra-workflow-guard-suite` runs it automatically.
- Added tests for:
  - safe candidate-only fixture,
  - decode/export Ghidra-body consumption failure,
  - pairing-helper `GhidraRoleStats` consumption failure,
  - actual `Program.cs` guard pass,
  - workflow-suite invocation,
  - command/PowerShell alias wiring.
- Updated workflow docs and the NiDataStream promotion-readiness checklist.

## Evidence / validation

```powershell
python -m py_compile scripts/rift_workflow.py scripts/rift_workflow_guards.py scripts/test_rift_workflow_guards.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_rift_workflow_guards.py
python scripts/test_rift_workflow_command_wiring.py
ruff check scripts/rift_workflow.py scripts/rift_workflow_guards.py scripts/test_rift_workflow_guards.py scripts/test_rift_workflow_command_wiring.py
python scripts/rift_workflow.py nidatastream-parser-export-non-consumption-guard
python scripts/rift_workflow.py nidatastream-parser-field-proof-guard
python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Result: all commands passed.

## Current guard meaning

`BuildNifMeshBoundStreamSummaries` may continue to carry report-only sidecar fields such as `GhidraRoleStats`, but decode/export-sensitive consumers must remain legacy `RoleStats` based. The guard allows report metadata propagation where already present, but fails closed if parser/export consumers start reading candidate layout fields such as `GhidraStyleLayoutValid`, `SliceNifDataStreamGhidraBody`, or `GhidraRoleStats`.

## Generated outputs

No copied RIFT assets or generated reports were staged. Python bytecode/cache output may have been produced locally by validation and remains ignored.

## Known blockers

- `ParserExportPromotionAllowed` remains intentionally false.
- `FieldOrderPromoted` remains intentionally false.
- Pairing impact still has zero complete Ghidra-only position+normal+UV groups; Ghidra evidence remains candidate-only.

## Next recommended actions

1. Add a JSON schema/contract test for `nidatastream-promotion-dashboard` output.
2. Add a negative dashboard fixture to fail closed if promotion fields drift.
3. Add an offline Ghidra/NiDataStream quickstart that names the exact guard sequence.
4. Refresh ignored NiDataStream layout and Ghidra candidate reports only when useful for new evidence.
5. Keep parser/export behavior unchanged until all promotion gates have positive proof.
