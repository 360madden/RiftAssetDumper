# 2026-05-25 NiDataStream pairing-impact status handoff

## Goal

Make the pairing-impact gate visible in the machine-readable NiDataStream promotion status without promoting Ghidra evidence.

## What changed

- Extended `nidatastream-promotion-status --list-json` with `PairingImpactStatus` from the ignored local `ghidra-attribute-candidate-report.json` when present.
- Updated the `pairing-impact-proof` gate evidence to report complete position+normal+UV group counts instead of a static sentence.
- Extended `docs/schemas/nidatastream-promotion-status-v1.schema.json` and promotion-status tests for the pairing-impact summary.
- Updated Ghidra/NiDataStream docs with the current local pairing-impact status.

## Why it matters

The promotion status now reports all three active evidence lanes together: descriptor helper reports, sample-byte layout reports, and grouped pairing-impact reports. Current local evidence still has zero complete Ghidra-only position+normal+UV groups, which is exactly why parser/export promotion remains blocked.

## Evidence / validation

Validated as part of the descriptor/pairing status slice:

```powershell
python -c "import pathlib, py_compile; [py_compile.compile(str(path), doraise=True) for path in pathlib.Path('scripts').glob('*.py')]"
Get-ChildItem scripts/test_*.py | Sort-Object Name | ForEach-Object { python $_.FullName; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
ruff check scripts/
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py nidatastream-promotion-status --list-json | python -c "import json,sys; data=json.load(sys.stdin); print(data['PairingImpactStatus']['CompletePositionNormalUvCandidateGroups'], data['PairingImpactStatus']['GhidraOnlyGroups'], data['Gates'][4]['State'])"
python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Expected local result: `0 14 candidate`; parser/export promotion remains false.

## Known blockers / limits

- `PairingImpactStatus` is a summary of ignored local report state; fresh clones may show no report until `ghidra-attribute-candidate-report` is run locally.
- Zero complete groups is a guard baseline, not promotion proof. It prevents premature promotion; it does not prove new parser/export behavior.
- Parser/export promotion remains blocked by the combined promotion guard.

## Generated-output handling

No generated report files were staged. Ignored `Exports/` reports remain local evidence only.

## Next recommended actions

1. Add a promotion-readiness checklist documenting exact future conditions for `ParserExportPromotionAllowed` to change.
2. Add a small guard/test that fails if a future v1 schema allows `FieldOrderPromoted` or `ParserExportPromotionAllowed` to become true.
3. Keep refreshing ignored pairing reports locally when descriptor/sample evidence changes.
4. Only consider a narrow parser patch after descriptor, sample-byte, and pairing-impact status are all green and reviewed.
5. Keep generated-output guard in every commit gate.
