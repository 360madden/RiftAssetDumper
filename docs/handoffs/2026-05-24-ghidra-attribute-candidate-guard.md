# Ghidra attribute candidate guard handoff — 2026-05-24

## Status

Added a fail-closed guard for the grouped Ghidra attribute candidate report.

This guard preserves the current safe baseline: the Ghidra-only queue has useful partial evidence, but **zero complete position+normal+UV candidate groups**.

## Command

```powershell
python scripts/rift_workflow.py ghidra-attribute-candidate-guard
```

The command reads or builds:

- `Exports/ghidra-attribute-candidate-report.json`

and asserts:

| Summary field | Expected |
|---|---:|
| `GhidraOnlyGroups` | 14 |
| `GhidraOnlyPairingsCovered` | 64 |
| `GroupedSampleMeshes` | 8 |
| `CompletePositionNormalUvCandidateGroups` | 0 |
| `ProbeBackedRanks` | 14 |
| `PositionReviewPassGroups` | 4 |
| `NormalReviewPassGroups` | 3 |
| `UvReviewPassGroups` | 3 |
| `UvReviewFailGroups` | 2 |
| `RejectedNoiseGroups` | 2 |

It also verifies:

- `SchemaVersion == ghidra-attribute-candidate-report/v1`
- `CandidateOnly == true`
- no group has `CompletePositionNormalUvCandidate == true`

## Validation evidence

```powershell
python -m py_compile scripts/rift_workflow.py scripts/rift_workflow_guards.py scripts/test_rift_workflow_guards.py
python scripts/test_rift_workflow_guards.py
ruff check scripts/rift_workflow.py scripts/rift_workflow_guards.py scripts/test_rift_workflow_guards.py
mypy scripts/rift_workflow.py scripts/rift_workflow_guards.py scripts/test_rift_workflow_guards.py --no-error-summary
python scripts/rift_workflow.py ghidra-attribute-candidate-guard
```

## Meaning

If a future run discovers a complete position+normal+UV Ghidra-only group, this guard will intentionally fail. That future failure should trigger a deliberate review and a new proof/promotion patch, not silent exporter wiring.

## Remaining

- Add schema for `ghidra-attribute-candidate-report/v1`.
- Add a batch probe/report command that can regenerate rank-probe JSON without manual loops.
- Keep exporter promotion blocked until a complete group and promotion proof guard exist.
