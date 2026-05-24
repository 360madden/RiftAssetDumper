# Ghidra workflow guard suite handoff — 2026-05-24

## Stage completed

Added a single workflow command that runs the current Ghidra promotion brakes together.

## Command

```powershell
python scripts/rift_workflow.py ghidra-workflow-guard-suite
```

It runs:

1. `ghidra-pairing-non-export-guard`
2. `ghidra-attribute-candidate-guard`

If the grouped attribute candidate report is missing, the suite rebuilds it from the existing review report or mesh-binding inventory.

## Files changed

- `scripts/rift_workflow.py`
- `scripts/Invoke-RiftWorkflow.ps1`
- `scripts/test_rift_workflow_command_wiring.py`
- `scripts/test_rift_workflow_guards.py`
- `README.md`
- `docs/ai-driven-workflow.md`
- `docs/ghidra-pairing-promotion-checklist.md`

## Safety boundary

- This is guard orchestration only.
- It does not promote Ghidra sidecar evidence into decode/export paths.
- Generated reports, if rebuilt, remain under ignored `Exports/`.

## Validation

```powershell
python -m py_compile scripts/rift_workflow.py scripts/rift_workflow_guards.py scripts/test_rift_workflow_guards.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_rift_workflow_guards.py
python scripts/test_rift_workflow_command_wiring.py
ruff check scripts/rift_workflow.py scripts/rift_workflow_guards.py scripts/test_rift_workflow_guards.py scripts/test_rift_workflow_command_wiring.py
mypy scripts/rift_workflow.py scripts/rift_workflow_guards.py scripts/test_rift_workflow_guards.py scripts/test_rift_workflow_command_wiring.py --no-error-summary
python scripts/rift_workflow.py ghidra-workflow-guard-suite
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Remaining

- Add future Ghidra promotion guards to this suite instead of relying on manual command lists.

## Follow-up note

- The shared review-report helper now reports the calling workflow in missing-input errors, so `ghidra-attribute-candidate-guard` and the guard suite no longer inherit the batch-probe command name in their error text.
