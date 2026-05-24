# Ghidra NiDataStream parser-field comparison handoff — 2026-05-24

## Stage completed

Added a tracked comparison note connecting the current C# `NiDataStream` layout/report fields to the Ghidra `LoadBinary` / descriptor / semantic-adapter target evidence.

## Document

```text
docs/ghidra-nidatastream-parser-field-comparison.md
```

## Safety boundary

- Documentation-only.
- Does not promote Ghidra-aligned slicing into parser/export behavior.
- Keeps descriptor helper evidence labeled as candidate-only/report-only.

## Validation

```powershell
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-descriptor-helper
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Remaining

- Convert a specific field-order mismatch into a guardable parser patch only after descriptor-helper evidence is reviewed with copied-sample byte checks.
