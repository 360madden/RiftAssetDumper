# 2026-05-25 schema registry validation handoff

## Goal

Add a single offline smoke test that catches drift in tracked JSON schemas and durable tracked JSON docs.

## What changed

- Added `scripts/test_schema_registry.py`.
- The test checks every `docs/schemas/*.schema.json` file has `$schema`, `$id`, and `title` fields.
- The test runs `jsonschema.Draft202012Validator.check_schema` for every tracked schema.
- The test validates `docs/ghidra-function-site-targets.json` against `docs/schemas/ghidra-function-site-targets-v1.schema.json` and asserts the registry remains candidate-only.
- Linked this handoff from `docs/ai-driven-workflow.md` current Ghidra lane state.

## Why it matters

The repo already had focused schema checks in individual workflow tests. This adds one aggregate guard that future agents and CI can run automatically with the existing `scripts/test_*.py` sweep, reducing the chance that tracked schema/docs drift silently while the Ghidra workflow grows.

## Evidence / validation

Commands run:

```powershell
python -m py_compile scripts/test_schema_registry.py
python scripts/test_schema_registry.py
ruff check scripts/test_schema_registry.py
mypy scripts/test_schema_registry.py --no-error-summary
```

## Known blockers / limits

- This validates tracked JSON docs only. It does not validate ignored runtime outputs under `Exports/` because those are local/generated and may be absent.
- Only `docs/ghidra-function-site-targets.json` is currently a durable tracked JSON doc outside `docs/schemas/`.

## Generated-output handling

No generated reports were created, staged, or committed.

## Next recommended actions

1. Add status/list schema files only if those JSON payloads become persisted durable artifacts.
2. Keep runtime `Exports/` output validation in focused command tests, not tracked-doc schema tests.
3. Continue toward a proof guard for NiDataStream parser-field promotion before any decoder/export change.
