# Ghidra attribute candidate report handoff — 2026-05-24

## Status

Added a grouped, candidate-only Ghidra attribute triage report.

No parser/export/OBJ behavior was changed.

## Command

```powershell
python scripts/rift_workflow.py ghidra-attribute-candidate-report
```

Inputs:

- `Exports/ghidra-pairing-review-report.json`
- optional ignored rank probes under `Exports/ghidra-review-rank-probes/rankNN/`

Outputs:

- `Exports/ghidra-attribute-candidate-report.json`
- `Exports/ghidra-attribute-candidate-report.md`

## Current result

| Metric | Value |
|---|---:|
| Ghidra-only groups | 14 |
| Ghidra-only pairings covered | 64 |
| Grouped sample meshes | 8 |
| Complete position/normal/UV candidate groups | 0 |
| Probe-backed ranks | 14 |
| Position review pass groups | 4 |
| Normal review pass groups | 3 |
| UV review pass groups | 3 |
| UV review fail groups | 2 |
| Rejected/noise groups | 2 |

## Group interpretation

| Sample mesh | Ranks | Count | Semantics | Decision |
|---|---:|---:|---|---|
| `25f30ec90608eab7` mesh#7 | 1,2,3 | 42 | normal, other, position | position-normal partial; needs UV/group proof |
| `a5e25bb93626ea8c` mesh#7 | 8,9 | 4 | normal, position | position-normal partial; needs UV/group proof |
| `cabc6ebf8a7ede5b` mesh#45 | 4,5,7 | 11 | position, uv | position-UV partial; needs normal/group proof |
| `d6e7cb59dab746cf` mesh#6 | 13,14 | 2 | other, position | position-only candidate; needs companions |
| `c8dcc07010e2642b` mesh#6 | 10 | 1 | normal | normal-only candidate; needs companions |
| `18e0926347a7c51c` mesh#6 | 11 | 1 | uv | UV-only candidate; needs companions |
| `a5e25bb93626ea8c` mesh#34 | 12 | 1 | uv | UV-only candidate; needs companions |
| `e21df228cbc5851d` mesh#6 | 6 | 2 | uv | UV-only candidate; needs companions |

## Meaning

Ghidra-only evidence is useful and real, but the current queue has **no complete position+normal+UV candidate group**. That means exporter promotion remains blocked. The next safe step is a proof guard/report that keeps partial groups partial and rejects UV/noise failures.

## Validation evidence

```powershell
python -m py_compile scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_rift_workflow_reports.py
python scripts/test_rift_workflow_reports.py
ruff check scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_rift_workflow_reports.py
mypy scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_rift_workflow_reports.py --no-error-summary
python scripts/rift_workflow.py ghidra-attribute-candidate-report
```

## Remaining

- Add a fail-closed proof guard around `ghidra-attribute-candidate-report`.
- Keep `CompletePositionNormalUvCandidateGroups == 0` as the current safe baseline unless future evidence proves otherwise.
- Keep export/OBJ promotion blocked.
