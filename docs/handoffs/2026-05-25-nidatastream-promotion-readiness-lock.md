# 2026-05-25 NiDataStream promotion-readiness lock handoff

## Goal

Document and test the fail-closed v1 promotion boundary for NiDataStream parser/export work.

## What changed

- Added `docs/nidatastream-promotion-readiness-checklist.md` with the exact future gates required before any parser/export patch.
- Added `scripts/test_nidatastream_promotion_locks.py` to assert v1 schemas keep `ParserExportPromotionAllowed=false`, `FieldOrderPromoted=false`, and `CandidateOnly=true`.
- Linked the checklist from README and AI workflow docs.

## Why it matters

The repo now has an explicit durable boundary between useful candidate Ghidra evidence and promoted parser/export truth. Future autonomous agents should add proof surfaces and tests, not flip v1 promotion booleans or weaken guards.

## Evidence / validation

Commands to run for this slice:

```powershell
python -m py_compile scripts/test_nidatastream_promotion_locks.py
python scripts/test_nidatastream_promotion_locks.py
python scripts/test_schema_registry.py
ruff check scripts/test_nidatastream_promotion_locks.py scripts/test_schema_registry.py
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Known blockers / limits

- This is a documentation/test guardrail, not a parser/export implementation.
- Future promotion should require a new schema/version or deliberately reviewed schema change, not a silent v1 edit.

## Generated-output handling

No generated files are required for this slice. `generated-output-guard` should report zero tracked/staged generated paths.

## Next recommended actions

1. Add an executable report comparing descriptor status, layout status, and pairing status in one compact Markdown summary.
2. Add CI documentation for the exact offline-safe Ghidra workflow commands.
3. Keep parser/export behavior unchanged until all promotion gates have reviewed positive proof.
