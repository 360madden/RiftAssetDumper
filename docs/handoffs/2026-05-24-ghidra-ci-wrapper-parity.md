# Ghidra CI/wrapper parity handoff — 2026-05-24

## Stage completed

Wired the current Ghidra report/guard commands through the thin PowerShell wrapper and made CI run the offline workflow smoke-test set instead of only one Python utility test. CI now installs `jsonschema`, and the report smoke test validates both committed Ghidra report schemas.

## Files changed

- `scripts/Invoke-RiftWorkflow.ps1`
- `scripts/test_rift_workflow_command_wiring.py`
- `scripts/test_rift_workflow_reports.py`
- `.github/workflows/ci.yml`
- `docs/ai-driven-workflow.md`
- `README.md`
- `docs/handoffs/2026-05-24-ghidra-attribute-schema.md`

## Why this matters

The durable Ghidra workflow now has three aligned entry surfaces:

1. direct Python commands in `scripts/rift_workflow.py`
2. legacy-friendly thin wrapper aliases in `scripts/Invoke-RiftWorkflow.ps1`
3. CI coverage for offline Ghidra/report/guard command wiring and schema-validation tests

This reduces drift without reviving the larger retired legacy PowerShell workflow.

## Safety boundary

- No generated `Exports/`, `Source/`, or `Extracted/` files are staged.
- No decode/export behavior changes are made.
- `Invoke-RiftAssetWorkflow.ps1` remains untouched; the supported wrapper path for this lane is the thin Python-delegating wrapper.

## Validation

Run after this stage:

```powershell
python -c "import pathlib, py_compile; [py_compile.compile(str(path), doraise=True) for path in pathlib.Path('scripts').glob('*.py')]"
Get-ChildItem scripts/test_*.py | Sort-Object Name | ForEach-Object { python $_.FullName; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
ruff check scripts/
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Remaining

- Keep future Ghidra command aliases covered by `scripts/test_rift_workflow_command_wiring.py`.
- Keep generated report schema validation in tests only; do not make generated reports runtime inputs until a separate promotion proof exists.
