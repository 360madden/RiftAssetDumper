# 50-step plan Step 47 scanner scaffold handoff

Date: 2026-05-26

## Goal

Complete Step 47 of the original 50-step plan by adding a safe, gated, read-only live-memory scanner scaffold without executing a live process read.

## What changed

- Added `scripts/live_memory_scanner.py` with:
  - `label=hex` pattern parsing and validation,
  - fixture-backed `ProcessReader` abstraction,
  - bounded exact-byte scan core,
  - Windows `ReadProcessMemory` live reader guarded behind explicit workflow flags,
  - generated-output report writer for the ignored live lane.
- Added `scan-live-memory` to `scripts/rift_workflow.py` and the PowerShell wrapper alias.
- Added `docs/schemas/live-memory-scan-plan-v1.schema.json` for dry-run/live-result packets.
- Added `scripts/test_live_memory_scanner.py` for schema, parser, fixture scanner, and no-live CLI dry-run coverage.
- Updated the 50-step plan tracker so the repo now reports **47/50 complete; Stage 5 Step 48 next**.

## Evidence / validation

Validated locally:

```powershell
python -m py_compile scripts/live_memory_scanner.py scripts/rift_workflow.py scripts/test_live_memory_scanner.py scripts/test_fifty_step_plan_status.py scripts/test_rift_workflow_command_wiring.py scripts/test_schema_registry.py
python scripts/test_live_memory_scanner.py
python scripts/test_fifty_step_plan_status.py
python scripts/test_rift_workflow_command_wiring.py
python scripts/test_schema_registry.py
python scripts/rift_workflow.py scan-live-memory --live-pattern strip_prefix=00010002000200010003000400050006 --list-json | Out-Null
python scripts/rift_workflow.py fifty-step-plan-status --list-json | Out-Null
ruff check scripts/live_memory_scanner.py scripts/test_live_memory_scanner.py scripts/rift_workflow.py scripts/test_fifty_step_plan_status.py scripts/test_rift_workflow_command_wiring.py scripts/test_schema_registry.py
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Dry-run proof:

```text
scan-live-memory dry-run passed: no process was opened and no live memory was read.
Completed steps: 47/50
Current step: Step 48 - Scan for @264/#15 index buffer pattern in live memory
Live process read executed: false
```

## Known blockers / guardrails

- No actual live process read was executed.
- Step 48 must begin with a dry-run plan and explicit review of PID, pattern, output paths, and limits.
- Actual live execution remains blocked unless all of these are present: `--execute-live-read --experimental-live --confirm-live-read --pid`.
- Parser/export promotion remains blocked; live evidence is candidate-only until later guard-backed promotion work.

## Generated output status

No generated live scan files, copied RIFT assets, or extraction outputs were created or staged. The scanner will only write execution reports under ignored `Exports/discovery-plan/stage5-live/`.

## Next recommended actions

1. Build a Step 48 dry-run plan for the @264/#15 big-endian strip prefix.
2. Add a pattern manifest/checklist for known live-memory scan targets.
3. Add a Step 48 result/status schema before any live evidence is trusted.
4. Keep actual live process execution as a separate safety event.
5. Continue non-live guard/docs work if live PID review is not appropriate in the current run.
