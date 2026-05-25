# 2026-05-25 Ghidra FunctionSiteSurvey target guard/status handoff

## Goal

Make the integrated Ghidra FunctionSiteSurvey workflow safer and more agent-readable before additional retained-project runs.

## What changed

- Added `ghidra-function-site-target-guard` as a first-class workflow command and PowerShell alias.
- Added the target guard to `ghidra-workflow-guard-suite` so the suite now checks FunctionSiteSurvey target path safety before promotion brakes.
- Added `ghidra-function-site-survey --list-json` for machine-readable target inventory.
- Added `ghidra-function-site-status --list-json` / human status output to show whether ignored report and summary files currently exist for each target.
- Extended Ghidra runner/wiring tests for target guard, unsafe parent traversal rejection, list JSON, and status JSON.
- Updated README and `docs/ai-driven-workflow.md` with the new safe workflow commands.

## Why it matters

The previous registry had a schema and dry-run survey command, but no executable workflow guard to fail closed if a future edit pointed Ghidra outputs outside ignored `Exports/ghidra-reports/` or duplicated target keys/outputs. The new guard makes the Ghidra lane safer for autonomous execution and lets agents inspect target/status state without hand-parsing docs.

## Evidence / validation

Commands run:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_rift_workflow_command_wiring.py
python scripts/test_ghidra_runner.py
python scripts/rift_workflow.py ghidra-function-site-target-guard
python scripts/rift_workflow.py ghidra-function-site-status --list-json
python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build
```

Observed local status from ignored `Exports/ghidra-reports/`: 7 registered targets, 3 with both report and summary currently present. This is local generated-output state only, not tracked truth.

## Known blockers / limits

- Ghidra evidence remains candidate-only/report-only.
- `--list-json` mode still runs the generated-output guard, but suppresses success banners so stdout remains parseable JSON.
- No new retained-project Ghidra run was launched in this slice.

## Generated-output handling

No generated reports were staged or committed. The status command only inspected ignored files under `Exports/ghidra-reports/`.

## Next recommended actions

1. Add a parser-field proof checklist that consumes the current NiDataStream comparison doc without changing decoder/export behavior.
2. Add an aggregate schema validation test for tracked Ghidra JSON docs and schema files.
3. Run one serialized `ghidra-function-site-survey --ghidra-target nidatastream-descriptor-helper --ghidra-execute` only when the retained project is available and not locked.
4. Add status/list docs for how agents should parse JSON after workflow guard banners.
5. Keep parser/export promotion blocked until proof guards cover the exact field interpretation.
