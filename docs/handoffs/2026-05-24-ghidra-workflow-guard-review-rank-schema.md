# Ghidra workflow guard/review-rank/schema handoff — 2026-05-24

## Status

Implemented the next Ghidra workflow hardening slice. Ghidra remains **candidate-only** and **non-export-consuming**.

## What changed

- Added candidate-only evidence to focused mesh probes:
  - `GhidraPairings` now carry `CandidateOnly=true`.
  - Ghidra position rows include a basic finite/plausible/nonzero/extent review and vector prefix samples.
- Added workflow guard:

```powershell
python scripts/rift_workflow.py ghidra-pairing-non-export-guard
```

The guard statically checks that Ghidra pairing evidence is not referenced by geometry/export-critical members such as `DecodeNifGeometry`, `FindNifMeshAttributeSets`, linked-position fallback, and attribute vertex sample builders.

- Added review-rank jump:

```powershell
python scripts/rift_workflow.py mesh-probe --review-rank 2 --skip-build
```

This resolves `--id` and `--mesh-block` from `Exports/ghidra-pairing-review-report.json`, or rebuilds the review report from an existing `nif-mesh-binding-inventory.json`.

- Added schema:

```text
docs/schemas/ghidra-pairing-review-v1.schema.json
```

- Added promotion checklist:

```text
docs/ghidra-pairing-promotion-checklist.md
```

## Current discovery interpretation

Ghidra is helping meaningfully as an offline sidecar:

| Evidence | Current value |
|---|---:|
| Shared legacy/Ghidra pairings | 4,195 |
| Legacy-only pairings | 4 |
| Ghidra-only pairings | 64 |
| Top review queue rows emitted | 10 |

The top Ghidra-only family is repeated and actionable, but still candidate-only:

```text
Rank 2: index-u16le-lead->position-float3-lead
sample: 25f30ec90608eab7 mesh#7
probe: python scripts/rift_workflow.py mesh-probe --review-rank 2 --skip-build
```

That probe currently shows a plausible candidate position stream with finite/plausible/nonzero ratios of `1` and max extent around `0.985711`. This is evidence for triage, not promotion.

## Validation evidence

Commands run across the slices:

```powershell
dotnet test RiftAssetDumper.slnx --no-restore
python -m py_compile scripts/rift_workflow.py scripts/rift_workflow_guards.py scripts/rift_workflow_reports.py scripts/test_rift_workflow_guards.py scripts/test_rift_workflow_review_rank.py scripts/test_rift_workflow_reports.py
python scripts/test_rift_workflow_guards.py
python scripts/test_rift_workflow_review_rank.py
python scripts/test_rift_workflow_reports.py
python scripts/rift_workflow.py ghidra-pairing-non-export-guard
python scripts/rift_workflow.py mesh-probe --review-rank 2 --skip-build
ruff check scripts/
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Known warnings are unchanged: SharpCompress `NU1902` and existing nullable `CS8602` warnings.

## Commits

```text
f3d9e29 feat: detail Ghidra mesh probe evidence
4abf969 test: guard Ghidra pairings from export paths
eddac2f feat: jump mesh probe from Ghidra review rank
```

The schema/checklist/docs slice follows this handoff.

## Remaining unwired pieces

- No Ghidra pairing drives `DecodeNifGeometry`, attribute-set construction, or OBJ/export.
- The 64 Ghidra-only pairings still need family-by-family review before promotion.
- A future parser patch must add a proof guard before changing durable role truth.
- Export promotion remains blocked until parser truth and export-specific guards pass.

## Recommended next safe milestone

Use `mesh-probe --review-rank N --skip-build` on ranks 1-10, starting with the repeated position families at ranks 2, 5, and 9. Record which families are valid geometry, normal/UV companion streams, or noise/repeated-pattern bodies before touching exporter behavior.
