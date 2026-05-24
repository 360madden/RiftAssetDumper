# Ghidra NiDataStream descriptor target handoff — 2026-05-24

## Stage completed

Registered the next three NiDataStream descriptor/helper FunctionSiteSurvey targets from the prior static proof lane.

## Added target keys

```text
nidatastream-descriptor-helper
nidatastream-descriptor-builder-1770
nidatastream-descriptor-builder-17c0
```

These point at existing ignored report/summary paths under `Exports/ghidra-reports/` and are intended for serialized reruns through:

```powershell
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-descriptor-helper
```

## Safety boundary

- Registry-only workflow expansion.
- Report paths remain ignored.
- No parser/decode/export behavior changes.
- Target names remain static-analysis handles, not durable source symbols.

## Validation

```powershell
python -m py_compile scripts/test_ghidra_runner.py
python scripts/test_ghidra_runner.py
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-descriptor-helper
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Remaining

- Use these targets to write a parser-field comparison note before considering any `NiDataStream` parser change.
