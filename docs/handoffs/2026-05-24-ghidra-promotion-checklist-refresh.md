# Ghidra promotion checklist refresh handoff — 2026-05-24

## Stage completed

Updated `docs/ghidra-pairing-promotion-checklist.md` so the promotion gate matches the current Ghidra workflow.

## What changed

- Added `ghidra-review-rank-probes --limit 14 --skip-build` to the current command set.
- Added `ghidra-attribute-candidate-report` and `ghidra-attribute-candidate-guard` to the checklist workflow.
- Made grouped candidate proof an explicit hard promotion gate.
- Updated the promotion sequence to require grouped candidate review before parser/export changes.
- Linked the durable batch probe handoff.

## Safety boundary

- Documentation-only change.
- No generated `Exports/`, `Source/`, or `Extracted/` files are staged.
- No decode/export behavior is changed.

## Validation

```powershell
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Remaining

- Keep this checklist current if a future complete position+normal+UV group appears.
