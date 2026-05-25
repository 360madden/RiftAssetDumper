# 2026-05-25 NiDataStream promotion dashboard handoff

## Goal

Add the compact combined dashboard recommended by the current promotion-readiness lane without changing parser/export behavior.

## What changed

- Added `nidatastream-promotion-dashboard` to `scripts/rift_workflow.py`.
- The command writes ignored `Exports/nidatastream-promotion-dashboard.json` and `.md` snapshots by default.
- The dashboard combines FunctionSite evidence, descriptor proof status, sample-byte layout status, pairing-impact status, and gate rows.
- Wired `NiDataStreamPromotionDashboard` through `scripts/Invoke-RiftWorkflow.ps1` and command-wiring tests.
- Extended `scripts/test_nidatastream_promotion_status.py` to assert dashboard JSON/Markdown output.
- Updated README, AI workflow docs, and promotion-readiness checklist with the dashboard command.

## Why it matters

Agents now have one practical human-readable artifact for the active post-Stage-18 Ghidra/NiDataStream lane. The JSON remains schema-backed by the existing promotion-status schema, while the Markdown is compact enough for handoffs and review. The command is report-only and keeps Ghidra evidence candidate-only.

## Evidence / validation

Commands run for this slice:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_rift_workflow_command_wiring.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py scripts/test_rift_workflow_command_wiring.py
python scripts/rift_workflow.py nidatastream-promotion-dashboard --out Exports
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Observed result: dashboard command wrote ignored JSON/Markdown under `Exports/`; `generated-output-guard` reported zero tracked/staged generated paths.

## Known blockers / limits

- Dashboard content reflects local ignored report availability; fresh clones may show missing local reports until evidence commands are run.
- The dashboard does not promote parser/export truth. `ParserExportPromotionAllowed` remains false.
- It does not replace the guard suite; run `ghidra-workflow-guard-suite --skip-build` before promotion-sensitive commits.

## Generated-output handling

`Exports/nidatastream-promotion-dashboard.json` and `.md` were generated locally and remain ignored. They were not staged.

## Next recommended actions

1. Add a negative fixture for descriptor status missing required calls/data refs.
2. Add a negative fixture for pairing-impact status with complete Ghidra-only position+normal+UV groups.
3. Add a concise CI/workflow note for GitHub Actions Node 20 and Windows runner migration warnings.
