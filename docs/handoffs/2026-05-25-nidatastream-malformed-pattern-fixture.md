# Handoff: NiDataStream descriptor malformed pattern fixture

Date: 2026-05-25

## Goal

Harden the descriptor record pattern matrix with a negative fixture for malformed descriptor records.

## What changed

- Extended the descriptor/sample test fixture helper to accept custom descriptor record rows.
- Added a malformed descriptor record fixture that keeps JSON schema validation passing while surfacing fail-closed blockers.
- Verified malformed rows add `descriptor-record-pattern-malformed` to both `DescriptorRecordPatternMatrix.Blockers` and top-level compare blockers.

## Evidence/validation

Run during implementation:

```powershell
python -m py_compile scripts/test_nidatastream_descriptor_sample_compare.py
python scripts/test_nidatastream_descriptor_sample_compare.py
```

## Known blockers

- This is test hardening only; parser/export behavior remains unchanged.
- Pattern matrix evidence remains candidate-only.

## Next recommended actions

1. Add candidate-only correlation-readiness reporting for bytes 1-2 vs pair-record/sample context.
2. Add sample diversity checks before any parser/export semantic claims.
3. Keep promotion locks unchanged.

## Generated outputs

No copied RIFT assets or generated reports were intentionally created by this test-only slice.
