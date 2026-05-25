# 2026-05-25 Ghidra FunctionSiteSurvey summary refresh handoff

## Goal

Refresh local Markdown summaries for existing FunctionSiteSurvey reports so the Ghidra target status surface is fully evidence-ready without launching a new Ghidra run.

## What changed

Generated ignored Markdown summaries for existing local JSON reports:

- `Exports/ghidra-reports/twad_site_survey.md`
- `Exports/ghidra-reports/nidatastream_loadbinary_141186980.md`
- `Exports/ghidra-reports/nidatastream_semantic_adapter_14111e910.md`
- `Exports/ghidra-reports/nimesh_material_binding_caller_14111f570.md`

Existing descriptor summaries were already present locally.

## Why it matters

The target registry/status command now showed which targets had reports but no Markdown summaries. Refreshing summaries makes all currently registered local FunctionSiteSurvey targets reviewable through small Markdown files while keeping raw/generated output ignored.

## Evidence / validation

Commands run:

```powershell
python scripts/rift_workflow.py ghidra-summarize --ghidra-report Exports/ghidra-reports/twad_site_survey.json --ghidra-summary-out Exports/ghidra-reports/twad_site_survey.md --ghidra-summary-term TWAD --ghidra-summary-term MapViewOfFile --ghidra-summary-term 0x44415754
python scripts/rift_workflow.py ghidra-summarize --ghidra-report Exports/ghidra-reports/nidatastream_loadbinary_141186980.json --ghidra-summary-out Exports/ghidra-reports/nidatastream_loadbinary_141186980.md --ghidra-summary-term NiDataStream::LoadBinary --ghidra-summary-term alignment --ghidra-summary-term lock
python scripts/rift_workflow.py ghidra-summarize --ghidra-report Exports/ghidra-reports/nidatastream_semantic_adapter_14111e910.json --ghidra-summary-out Exports/ghidra-reports/nidatastream_semantic_adapter_14111e910.md --ghidra-summary-term "semantic adapter" --ghidra-summary-term NiDataStream --ghidra-summary-term "renderer semantic"
python scripts/rift_workflow.py ghidra-summarize --ghidra-report Exports/ghidra-reports/nimesh_material_binding_caller_14111f570.json --ghidra-summary-out Exports/ghidra-reports/nimesh_material_binding_caller_14111f570.md --ghidra-summary-term NiDX9MeshMaterialBinding::Create --ghidra-summary-term "semantic adapter" --ghidra-summary-term NiDataStream
python scripts/rift_workflow.py ghidra-function-site-status --list-json
python scripts/rift_workflow.py generated-output-guard
```

Local status after refresh: `EvidenceReadyCount=7`, `TargetCount=7`.

## Known blockers / limits

- This refreshed summaries from already-existing ignored JSON reports; it did not run Ghidra headless or refresh decompile evidence.
- The generated Markdown and JSON reports remain local/ignored and should not be staged.
- Parser/export behavior remains unchanged.

## Generated-output handling

Generated outputs stayed under ignored `Exports/ghidra-reports/`. `generated-output-guard` passed after refresh.

## Next recommended actions

1. If Ghidra evidence needs freshness beyond existing reports, run one serialized retained-project target at a time.
2. Prefer `ghidra-function-site-status --list-json` before choosing a target so agents do not rerun already-ready evidence unnecessarily.
3. Keep field promotion blocked until the parser-field checklist has green proof gates.
