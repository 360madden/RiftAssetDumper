# Ghidra normal/UV probe review fields handoff — 2026-05-24

## Status

Added focused candidate-only review evidence for Ghidra sidecar normal and UV mesh-probe pairings.

No parser/export/OBJ behavior was promoted.

## What changed

`probe-nif-mesh` Ghidra sidecar pairings now include:

- `VertexNormalVectorReview`
  - finite ratio
  - plausible ratio
  - nonzero ratio
  - near-unit-vector ratio
  - prefix vector samples
- `VertexUvRangeReview`
  - finite ratio
  - UV-range ratio
  - nonzero ratio
  - max extent
  - prefix vector samples

Console and Python report summaries now display compact review flags:

```text
normalReview=True nearUnit=1 finite=1
uvReview=True uvRange=1 finite=1 extent=...
```

## Refreshed Ghidra-only rank evidence

After regenerating the 25-row review report and refreshing ignored rank probes under `Exports/ghidra-review-rank-probes/`, the 14 Ghidra-only groups still cover all 64 Ghidra-only pairings.

| Semantic group | Review ranks | Pairing count | Current result |
|---|---|---:|---|
| Position | 2, 5, 9, 13 | 20 | 4/4 groups pass basic position bounds review |
| Normal | 1, 8, 10 | 17 | 3/3 groups pass basic normal-vector review |
| UV | 4, 6, 7, 11, 12 | 12 | 3/5 groups pass basic UV-range review; ranks 7 and 12 fail UV-range/extent checks |
| Repeated-pattern/noise | 3, 14 | 15 | Still low-confidence repeated-pattern candidates; keep rejected |

UV failures are useful negative evidence:

- Rank 7: `uvRange=0.875`, huge extent; keep candidate-only.
- Rank 12: `uvRange=0.8704`, huge extent; keep candidate-only.

## Validation evidence

```powershell
dotnet build RiftAssetDumper.slnx --no-restore
dotnet test RiftAssetDumper.slnx --no-restore
python -m py_compile scripts/rift_workflow_reports.py scripts/test_rift_workflow_reports.py
python scripts/test_rift_workflow_reports.py
python scripts/rift_workflow.py ghidra-pairing-review-report --quick --limit 25
python scripts/rift_workflow.py mesh-probe --review-rank 1 --skip-build
python scripts/rift_workflow.py mesh-probe --review-rank 4 --skip-build
python scripts/rift_workflow.py mesh-probe --review-rank 1..14 --skip-build --out Exports/ghidra-review-rank-probes/rankNN
```

Known warnings remain unchanged: SharpCompress `NU1902` and existing nullable `CS8602` warnings.

## Remaining before promotion

- Add a grouped position/normal/UV coherence report.
- Add a proof guard that can reject incomplete or contradictory Ghidra candidate attribute groups.
- Keep `ghidra-pairing-non-export-guard` passing.
- Do not route `GhidraPairings` into `DecodeNifGeometry`, `FindNifMeshAttributeSets`, or OBJ export.
