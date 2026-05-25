# NiDataStream promotion preflight command

Date: 2026-05-25

## Goal

Reduce manual sequencing risk before any future NiDataStream parser/export work by adding one practical preflight command that runs the current dashboard and promotion brakes together.

## What changed

- Added `nidatastream-promotion-preflight` to `scripts/rift_workflow.py`.
- Added PowerShell alias `NiDataStreamPromotionPreflight`.
- The preflight command now:
  - prints current `NiDataStreamPromotionStatus`,
  - writes ignored `Exports/nidatastream-promotion-dashboard.json` and `.md`,
  - runs `ghidra-workflow-guard-suite`, which includes target registry safety, parser-field proof guard, pairing non-export guard, parser/export non-consumption guard, and grouped attribute candidate guard,
  - reruns `generated-output-guard` at the end.
- Added routing/behavior tests.
- Updated workflow docs and the offline quickstart/readiness checklist to prefer the preflight command before future parser/export work.

## Evidence / validation

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_rift_workflow_command_wiring.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py scripts/test_rift_workflow_command_wiring.py
python scripts/rift_workflow.py nidatastream-promotion-preflight
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Result: all commands passed.

## Generated outputs

`nidatastream-promotion-preflight` refreshed ignored local dashboard files under `Exports/`. They were not staged or committed. Generated-output guard passed after the refresh.

## Known blockers

- `ParserExportPromotionAllowed` remains intentionally false.
- `FieldOrderPromoted` remains intentionally false.
- `narrow-parser-patch` remains blocked until positive descriptor/sample/pairing proof exists.

## Next recommended actions

1. Add a promotion decision-record template for any future parser/export change.
2. Add a compact status command that reports stale/old ignored evidence timestamps if that becomes useful.
3. Keep parser/export behavior unchanged until the preflight is green and promotion gates have positive proof.
