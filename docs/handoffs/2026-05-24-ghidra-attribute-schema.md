# Ghidra attribute candidate schema handoff — 2026-05-24

## Stage completed

Documented the generated `ghidra-attribute-candidate-report/v1` contract.

## Files changed

- `docs/schemas/ghidra-attribute-candidate-v1.schema.json`
- `scripts/test_rift_workflow_reports.py`
- `README.md`
- `docs/ai-driven-workflow.md`
- `docs/ghidra-pairing-promotion-checklist.md`

## Why this matters

`ghidra-attribute-candidate-report` is now a first-class workflow artifact with a committed schema, matching the already-documented `ghidra-pairing-review` report. This keeps the grouped position/normal/UV triage surface reviewable without making it an exporter input.

## Safety boundary

- The schema documents generated report shape only.
- It does not promote Ghidra pairings into decode/export behavior.
- Generated reports remain under ignored `Exports/` paths.

## Validation

Run after this stage:

```powershell
python -m py_compile scripts/rift_workflow_reports.py scripts/test_rift_workflow_reports.py
python scripts/test_rift_workflow_reports.py
ruff check scripts/test_rift_workflow_reports.py
mypy scripts/test_rift_workflow_reports.py --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Follow-up completed

- `scripts/test_rift_workflow_reports.py` now validates generated Ghidra pairing and attribute-candidate reports against their committed schemas.
- CI installs `jsonschema` and runs the offline workflow smoke-test set through `scripts/test_*.py`.

## Remaining

- Keep `ghidra-attribute-candidate-guard` as the promotion brake while the report still has zero complete position+normal+UV groups.
