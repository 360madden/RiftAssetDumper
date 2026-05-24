# Ghidra review-rank probe batch handoff — 2026-05-24

## Stage completed

Added a durable workflow command for regenerating focused Ghidra review-rank mesh probes without a manual PowerShell loop.

## Command

```powershell
python scripts/rift_workflow.py ghidra-review-rank-probes --limit 14 --skip-build
```

Default behavior:

- reads `Exports/ghidra-pairing-review-report.json`
- rebuilds it from `Exports/nif-mesh-binding-inventory.json` if needed
- filters `ReviewKind == ghidra-only`
- writes focused probe JSON under ignored `Exports/ghidra-review-rank-probes/rankNN/`
- writes ignored per-kind `manifest-*.json` / `manifest-*.md` files under `Exports/ghidra-review-rank-probes/`

Use `--review-kind all` to include non-`ghidra-only` review rows.

Use this for the remaining shared semantic-change review rows:

```powershell
python scripts/rift_workflow.py ghidra-review-rank-probes --review-kind vertex-semantic-change --limit 11 --skip-build
```

## Files changed

- `scripts/rift_workflow.py`
- `scripts/Invoke-RiftWorkflow.ps1`
- `scripts/test_rift_workflow_review_rank.py`
- `scripts/test_rift_workflow_command_wiring.py`
- `README.md`
- `docs/ai-driven-workflow.md`

## Safety boundary

- The command only refreshes ignored focused probe outputs.
- It does not feed Ghidra pairings into decode/export paths.
- `ghidra-pairing-non-export-guard` remains the promotion brake for parser/export behavior.

## Validation

Run after this stage:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_rift_workflow_review_rank.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_rift_workflow_review_rank.py
python scripts/test_rift_workflow_command_wiring.py
ruff check scripts/rift_workflow.py scripts/test_rift_workflow_review_rank.py scripts/test_rift_workflow_command_wiring.py
mypy scripts/rift_workflow.py scripts/test_rift_workflow_review_rank.py scripts/test_rift_workflow_command_wiring.py --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Remaining

- Re-run `ghidra-review-rank-probes --limit 14 --skip-build` after any pairing-review scoring change before refreshing `ghidra-attribute-candidate-report`.
