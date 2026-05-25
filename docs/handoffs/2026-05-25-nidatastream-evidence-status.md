# NiDataStream evidence status command

Date: 2026-05-25

## Goal

Add a machine-readable way to inspect local ignored NiDataStream/Ghidra evidence artifact existence and timestamps before relying on reports during discovery or parser/export promotion planning.

## What changed

- Added `nidatastream-evidence-status` to `scripts/rift_workflow.py`.
- Added `--list-json` support and PowerShell alias `NiDataStreamEvidenceStatus`.
- Added schema `docs/schemas/nidatastream-evidence-status-v1.schema.json`.
- The command reports candidate-only status for:
  - promotion dashboard JSON/Markdown,
  - NiDataStream layout report JSON/Markdown,
  - Ghidra attribute candidate report JSON/Markdown,
  - Ghidra pairing review report JSON/Markdown,
  - FunctionSiteSurvey target reports and summaries from the tracked registry.
- Added tests for schema validation, repo-relative/redacted paths, timestamps, command wiring, and schema registry coverage.
- Updated workflow docs, quickstart, and promotion-readiness checklist.

## Evidence / validation

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_rift_workflow_command_wiring.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py scripts/test_rift_workflow_command_wiring.py scripts/test_schema_registry.py
python scripts/rift_workflow.py nidatastream-evidence-status --list-json
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Result: all commands passed.

## Current local evidence snapshot

`nidatastream-evidence-status --list-json` reported 22/22 configured artifacts present locally. These are ignored local evidence files under `Exports/`; they were not staged or committed.

## Generated outputs

No copied RIFT assets or generated reports were staged. The command is read-only.

## Known blockers

- Artifact presence/timestamps do not prove parser/export truth.
- Promotion remains blocked until descriptor/sample/pairing gates have positive proof.

## Next recommended actions

1. Consider adding optional stale-age thresholds only if evidence age starts causing practical confusion.
2. Use `nidatastream-evidence-status --list-json` before relying on ignored evidence in handoffs.
3. Keep parser/export behavior unchanged until promotion preflight and decision-record gates are satisfied.
