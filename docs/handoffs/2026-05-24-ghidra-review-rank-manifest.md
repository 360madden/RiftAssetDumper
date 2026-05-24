# Ghidra review-rank probe manifest handoff — 2026-05-24

## Stage completed

Extended `ghidra-review-rank-probes` so batch probe runs produce compact ignored per-kind manifests and have durable coverage for non-default review kinds such as `vertex-semantic-change`.

## Commands

Current Ghidra-only batch:

```powershell
python scripts/rift_workflow.py ghidra-review-rank-probes --limit 14 --skip-build
```

Shared semantic-change batch:

```powershell
python scripts/rift_workflow.py ghidra-review-rank-probes --review-kind vertex-semantic-change --limit 11 --skip-build
```

Both write ignored output under:

```text
Exports/ghidra-review-rank-probes/
```

## Files changed

- `scripts/rift_workflow.py`
- `scripts/test_rift_workflow_review_rank.py`
- `README.md`
- `docs/ai-driven-workflow.md`
- `docs/ghidra-pairing-promotion-checklist.md`
- `docs/handoffs/2026-05-24-ghidra-review-rank-probes.md`
- `docs/handoffs/2026-05-24-ghidra-review-rank-manifest.md`

## Safety boundary

- Probe manifests are generated evidence only.
- Per-kind manifests use names such as `manifest-ghidra-only.json` and `manifest-vertex-semantic-change.json`; `manifest.json` remains the latest run pointer.
- They are ignored local output and must not be staged.
- This does not change parser, decode, or export behavior.

## Validation

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_rift_workflow_review_rank.py
python scripts/test_rift_workflow_review_rank.py
ruff check scripts/rift_workflow.py scripts/test_rift_workflow_review_rank.py
mypy scripts/rift_workflow.py scripts/test_rift_workflow_review_rank.py --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Follow-up local evidence:

```powershell
python scripts/rift_workflow.py ghidra-review-rank-probes --review-kind vertex-semantic-change --limit 11 --skip-build
```

Result: passed, selected ranks `15..25`, selected 11 shared semantic-change rows, and wrote ignored `manifest-vertex-semantic-change.*` files under `Exports/ghidra-review-rank-probes/`. Existing SharpCompress `NU1902` and nullable `CS8602` warnings were unchanged.

## Remaining

- Re-run the shared semantic-change batch after review scoring changes.
- Keep manifest files ignored; summarize findings in tracked docs only when they change durable workflow decisions.
