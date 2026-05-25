# NiDataStream preflight evidence-status integration

Date: 2026-05-25

## Goal

Make the promotion preflight self-contained by printing ignored evidence artifact timestamp/status after refreshing the dashboard and before running promotion guard suites.

## What changed

- `nidatastream-promotion-preflight` now prints `NiDataStreamEvidenceStatus` after writing the dashboard.
- Updated preflight tests to assert evidence status is included.
- Updated workflow docs and offline quickstart to describe preflight evidence-status output.

## Evidence / validation

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py
python scripts/test_nidatastream_promotion_status.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_promotion_status.py
python scripts/rift_workflow.py nidatastream-promotion-preflight
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Result: all commands passed.

## Generated outputs

`nidatastream-promotion-preflight` refreshed ignored dashboard files under `Exports/`. They were not staged or committed. Generated-output guard passed.

## Known blockers

- Evidence artifact timestamps are observability only; they do not promote parser/export truth.
- Parser/export promotion remains blocked.

## Next recommended actions

1. Use preflight as the default before any NiDataStream parser/export proposal.
2. Add stale-age thresholds only if artifact freshness becomes ambiguous in practice.
3. Continue keeping ignored evidence out of commits.
