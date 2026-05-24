# Ghidra FunctionSiteSurvey target schema handoff — 2026-05-24

## Stage completed

Locked the tracked `docs/ghidra-function-site-targets.json` registry with a JSON schema and test validation.

## Schema

```text
docs/schemas/ghidra-function-site-targets-v1.schema.json
```

The schema requires:

- `SchemaVersion = ghidra-function-site-targets/v1`
- `CandidateOnly = true`
- retained-project defaults
- target keys as stable kebab-case names
- hex target addresses
- ignored `Exports/ghidra-reports/` report and summary paths
- summary terms and descriptions

## Safety boundary

- This is registry contract coverage only.
- Target paths stay under ignored `Exports/ghidra-reports/`.
- The registry remains static-analysis evidence and does not promote parser/export behavior.

## Validation

```powershell
python -m py_compile scripts/test_ghidra_runner.py
python scripts/test_ghidra_runner.py
ruff check scripts/test_ghidra_runner.py
mypy scripts/test_ghidra_runner.py --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Remaining

- Add new Ghidra survey targets only when they have a clear handoff/proof reason and remain ignored-output/report-only.
