# Ghidra review-rank summary schema handoff — 2026-05-24

## Stage completed

Locked the `ghidra-review-rank-probes-summary` output shape with a tracked JSON schema and test validation for both all-kind and filtered summary outputs.

## Schema

```text
docs/schemas/ghidra-review-rank-probes-summary-v1.schema.json
```

The schema requires:

- `SchemaVersion = ghidra-review-rank-probes-summary/v1`
- `CandidateOnly = true`
- ignored probe-root metadata
- manifest/selected-row counts
- per-review-kind rows with ranks, sample meshes, and Ghidra role counts

## Safety boundary

- This is contract/schema coverage only.
- Summary files remain ignored `Exports/` evidence.
- No parser, decoder, or exporter path consumes these summaries.

## Validation

```powershell
python -m py_compile scripts/test_rift_workflow_review_rank.py
python scripts/test_rift_workflow_review_rank.py
ruff check scripts/test_rift_workflow_review_rank.py
mypy scripts/test_rift_workflow_review_rank.py --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Remaining

- If future summary fields are added, update this schema and the review-rank workflow tests in the same patch.
