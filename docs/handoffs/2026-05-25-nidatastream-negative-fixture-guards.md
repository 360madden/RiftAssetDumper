# 2026-05-25 NiDataStream negative fixture guards handoff

## Goal

Add targeted negative fixtures for the highest-risk promotion status failure modes without expanding production code.

## What changed

- Extended `scripts/test_nidatastream_descriptor_proof_status.py` with a missing-call fixture for the descriptor helper.
- Extended `scripts/test_nidatastream_promotion_status.py` with a pairing-impact fixture where a complete Ghidra-only position+normal+UV group appears.
- Verified those fixtures fail closed: descriptor readiness becomes false, and the pairing-impact gate becomes `blocked`.

## Why it matters

The workflow now tests that the candidate evidence surfaces do not only pass happy paths. A missing descriptor call or a promoted complete Ghidra-only group now has direct coverage in the Python test suite.

## Evidence / validation

Commands run for this slice:

```powershell
python -m py_compile scripts/test_nidatastream_descriptor_proof_status.py scripts/test_nidatastream_promotion_status.py
python scripts/test_nidatastream_descriptor_proof_status.py
python scripts/test_nidatastream_promotion_status.py
ruff check scripts/test_nidatastream_descriptor_proof_status.py scripts/test_nidatastream_promotion_status.py
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Observed results: all targeted tests passed, and generated-output guard reported zero tracked/staged generated paths.

## Known blockers / limits

- These are synthetic fixture tests; they do not change parser/export behavior.
- They guard failure modes in the status layer, not full end-to-end Ghidra report generation.

## Generated-output handling

No generated files were staged. Temporary test outputs were created under temp directories only.

## Next recommended actions

1. Add a concise CI/workflow note for GitHub Actions Node 20 and Windows runner migration warnings.
2. Keep future promotion status changes covered by both positive and negative fixtures.
3. Add an explicit test that `nidatastream-promotion-dashboard --out <temp>` remains report-only and schema-compatible after future status fields are added.
