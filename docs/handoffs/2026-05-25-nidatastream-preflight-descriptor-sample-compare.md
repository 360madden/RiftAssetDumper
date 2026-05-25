# Handoff — NiDataStream preflight descriptor/sample compare integration

Date: 2026-05-25

## Goal

Make `nidatastream-promotion-preflight` refresh the descriptor/sample comparison automatically so the primary promotion brake produces the same candidate-only evidence snapshot an agent would otherwise have to run manually.

## What changed

- `nidatastream-promotion-preflight` now writes:
  - `Exports/nidatastream-descriptor-sample-compare.json`
  - `Exports/nidatastream-descriptor-sample-compare.md`
- Preflight console output now includes a compact descriptor/sample readiness and blocker line.
- Preflight evidence status now runs after the comparison write, so `nidatastream-evidence-status` can report those compare artifacts as present/missing in the same run.
- Added a mismatch fixture proving the comparison blocks readiness when sample-byte counters diverge from the expected Ghidra-aligned values.
- Updated offline quickstart and AI workflow docs to state that preflight writes the descriptor/sample compare report.

## Evidence / validation

- `python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py`
- `python scripts/test_nidatastream_descriptor_sample_compare.py`
- `python scripts/test_nidatastream_promotion_status.py`
- `ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py`
- `python scripts/rift_workflow.py nidatastream-promotion-preflight`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

Current local preflight evidence after this slice:

- Descriptor/sample compare: `descriptor+sample-ready=true`, blockers `2`
- Evidence artifacts listed by preflight: `24/24`
- Parser/export promotion: still locked

## Known blockers / guardrails

- Preflight still keeps parser/export promotion locked.
- Compare output is evidence only; it is not parser truth.
- Generated compare/dashboard files remain ignored under `Exports/`.

## Next recommended actions

1. Keep preflight as the default first command before any NiDataStream parser/export work.
2. Add an exact descriptor byte-order proof only after evidence can support it.
3. Keep mismatch/negative fixtures ahead of any future promotion schema change.
