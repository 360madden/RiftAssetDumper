# 2026-05-25 Ghidra FunctionSiteSurvey list/status schemas handoff

## Goal

Make the machine-readable FunctionSiteSurvey list/status outputs durable enough for agent workflow automation.

## What changed

- Added `docs/schemas/ghidra-function-site-target-list-v1.schema.json` for `ghidra-function-site-survey --list-json` stdout payloads.
- Added `docs/schemas/ghidra-function-site-status-v1.schema.json` for `ghidra-function-site-status --list-json` stdout payloads.
- Extended `scripts/test_ghidra_runner.py` to validate both payloads against their schemas.
- Updated README and `docs/ai-driven-workflow.md` with the new schema references.

## Why it matters

The target list/status commands are now safe for automation and have schema-backed contracts. Future agents can parse target inventory and local evidence-readiness without relying on markdown tables or brittle console text.

## Evidence / validation

Commands to run for this slice:

```powershell
python -m py_compile scripts/test_ghidra_runner.py
python scripts/test_ghidra_runner.py
python scripts/test_schema_registry.py
ruff check scripts/test_ghidra_runner.py
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Known blockers / limits

- These schemas cover stdout payload contracts; they do not make ignored `Exports/` reports tracked artifacts.
- `TargetCount` and `EvidenceReadyCount` are not cross-field-count validated by JSON Schema; tests assert the current payload validates structurally.

## Generated-output handling

No generated reports were staged or committed. The schemas and tests are tracked; `Exports/` remains ignored/local.

## Next recommended actions

1. Add a proof guard for any future NiDataStream parser-field promotion.
2. Keep using status JSON before deciding whether a Ghidra target needs rerun or only summarization.
3. Avoid promoting status/list payloads into tracked generated outputs unless there is a clear durable reporting need.
