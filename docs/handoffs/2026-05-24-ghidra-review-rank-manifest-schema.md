# Ghidra review-rank manifest schema handoff — 2026-05-24

## Stage completed

Locked the `ghidra-review-rank-probes` manifest contract with a tracked JSON schema and test validation for both default `ghidra-only` and non-default `vertex-semantic-change` batch runs.

## Schema

```text
docs/schemas/ghidra-review-rank-probes-manifest-v1.schema.json
```

The schema requires:

- `SchemaVersion = ghidra-review-rank-probes-manifest/v1`
- `CandidateOnly = true`
- source report/root metadata
- selected review-kind filter and count
- per-rank result rows with rank, review kind, sample id prefix, mesh block, roles, and output JSON path

## Safety boundary

- This is contract/schema coverage only.
- Manifest files remain ignored `Exports/` evidence.
- No parser, decoder, or exporter path consumes these manifests.

## Validation

```powershell
python -m py_compile scripts/test_rift_workflow_review_rank.py
python scripts/test_rift_workflow_review_rank.py
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Remaining

- If future manifest fields are added, update this schema and the review-rank workflow tests in the same patch.
