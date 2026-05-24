# Ghidra FunctionSiteSurvey target registry handoff — 2026-05-24

## Stage completed

Added a tracked registry of reusable `FunctionSiteSurvey.java` targets and a workflow command that prints or executes one serialized target at a time.

## Commands

List registered targets:

```powershell
python scripts/rift_workflow.py ghidra-function-site-survey
```

Print the rerun/summarize plan for one target:

```powershell
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-loadbinary
```

Execute one serialized target intentionally:

```powershell
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-loadbinary --ghidra-execute
```

## Registry

```text
docs/ghidra-function-site-targets.json
```

Initial target keys:

- `twad-header-magic`
- `nidatastream-loadbinary`
- `nidatastream-semantic-adapter`
- `nimesh-material-binding-caller`
- `nidatastream-descriptor-helper`
- `nidatastream-descriptor-builder-1770`
- `nidatastream-descriptor-builder-17c0`

## Safety boundary

- Dry-run/plan output is the default.
- `--ghidra-execute` is required before launching Ghidra.
- Generated reports and summaries stay under ignored `Exports/ghidra-reports/`.
- Retained-project Ghidra runs should remain serialized; do not run several targets in parallel against the same project.
- This does not change parser, decoder, or exporter behavior.

## Validation

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_ghidra_runner.py
python scripts/test_rift_workflow_command_wiring.py
ruff check scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py
mypy scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Follow-up local evidence:

```powershell
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-loadbinary
python scripts/rift_workflow.py generated-output-guard
```

Result: passed as a dry-run plan and printed the retained-project `ghidra-run` plus `ghidra-summarize` commands for `nidatastream-loadbinary`; no generated output was staged or tracked.

## Remaining

- Target registry schema is now tracked by `docs/schemas/ghidra-function-site-targets-v1.schema.json`; update it with any future target field changes.
