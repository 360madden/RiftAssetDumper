# Ghidra review-rank probe summary handoff — 2026-05-24

## Stage completed

Added a workflow command that summarizes ignored per-kind `ghidra-review-rank-probes` manifests so the Ghidra evidence queue can be reviewed without manually opening every rank folder.

## Command

```powershell
python scripts/rift_workflow.py ghidra-review-rank-probes-summary --review-kind all
```

Outputs stay ignored under:

```text
Exports/ghidra-review-rank-probes/
```

The command writes `summary-*.json` and `summary-*.md` files plus latest-run `summary.json` / `summary.md` aliases.

## Files changed

- `scripts/rift_workflow.py`
- `scripts/Invoke-RiftWorkflow.ps1`
- `scripts/test_rift_workflow_command_wiring.py`
- `scripts/test_rift_workflow_review_rank.py`
- `README.md`
- `docs/ai-driven-workflow.md`
- `docs/ghidra-pairing-promotion-checklist.md`
- `docs/handoffs/2026-05-24-ghidra-review-rank-probes-summary.md`

## Safety boundary

- This is report-only workflow glue.
- It reads ignored manifest evidence and writes ignored summaries under `Exports/`.
- It does not feed parser, decoder, OBJ, or exporter behavior.

## Validation

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_rift_workflow_review_rank.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_rift_workflow_review_rank.py
python scripts/test_rift_workflow_command_wiring.py
ruff check scripts/rift_workflow.py scripts/test_rift_workflow_review_rank.py scripts/test_rift_workflow_command_wiring.py
mypy scripts/rift_workflow.py scripts/test_rift_workflow_review_rank.py scripts/test_rift_workflow_command_wiring.py --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Follow-up local evidence:

```powershell
python scripts/rift_workflow.py ghidra-review-rank-probes --limit 14 --skip-build
python scripts/rift_workflow.py ghidra-review-rank-probes-summary --review-kind all
```

Result: passed, summarized 2 per-kind manifests covering 25 selected rows (`ghidra-only=14`, `vertex-semantic-change=11`). Existing SharpCompress `NU1902` and nullable `CS8602` warnings were unchanged during probe refresh.

## Remaining

- If summary output becomes a durable contract, add a JSON schema and schema validation test in the same style as the manifest schema.
