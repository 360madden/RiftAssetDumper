# 2026-05-25 NiDataStream layout schema/status handoff

## Goal

Strengthen the sample-byte agreement gate without promoting parser/export behavior.

## What changed

- Added `docs/schemas/nidatastream-layout-report-v1.schema.json` for `nidatastream-layout` JSON output.
- Extended `scripts/test_nidatastream_layout_report.py` to validate direct and workflow-generated layout reports against the schema.
- Extended `nidatastream-promotion-status --list-json` with `LayoutReportStatus`, summarizing the ignored local `Exports/nidatastream-layout-report.json` when present.
- Updated the promotion-status schema/tests to cover `LayoutReportStatus`.
- Updated README and Ghidra/NiDataStream docs to point at the schema-backed sample-byte report.

## Why it matters

The workflow can now distinguish three states for the sample-byte gate: no local report, unreadable report, or candidate report with all blocks matching the Ghidra-style layout. On this machine, the current ignored report shows 184/184 `NiDataStream` blocks as Ghidra-style-valid, but the evidence remains candidate-only and blocked from parser/export promotion.

## Evidence / validation

Commands run for this slice:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_layout_report.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py
python scripts/test_nidatastream_layout_report.py
python scripts/test_nidatastream_promotion_status.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_nidatastream_layout_report.py scripts/test_nidatastream_promotion_status.py scripts/test_schema_registry.py
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py nidatastream-promotion-status --list-json | python -c "import json,sys; data=json.load(sys.stdin); print(data['LayoutReportStatus']['NiDataStreamBlocks'], data['LayoutReportStatus']['GhidraStyleLayoutValidBlocks'], data['Gates'][3]['State'])"
python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Observed key result: `184 184 candidate`; guard suite and generated-output guard passed.

## Known blockers / limits

- `LayoutReportStatus` reads an ignored local report if it exists; CI and fresh clones may report zero blocks until `nidatastream-layout` is run locally against copied/extracted samples.
- The schema validates report shape and sample-byte counters; it does not prove descriptor field order or authorize parser/export changes.
- Parser/export promotion remains blocked by the descriptor-field-order, sample-byte, pairing-impact, and narrow-parser-patch gates.

## Generated-output handling

`python scripts/rift_workflow.py nidatastream-layout --root Extracted --full` refreshed ignored files under `Exports/`. They were intentionally not staged. `generated-output-guard` reported zero tracked/staged generated paths.

## Next recommended actions

1. Add descriptor-field-order status that parses FunctionSiteSurvey reports for the three NiDataStream descriptor helper targets.
2. Add schema coverage for that descriptor status once its payload exists.
3. Keep `LayoutReportStatus` as candidate-only until descriptor and pairing gates also pass.
4. Add a promotion-readiness checklist row explaining what would be required to change `ParserExportPromotionAllowed` in a future schema version.
5. Re-run `nidatastream-layout --root Extracted --full` after any new sample corpus is copied locally, without staging the output.
