# 2026-05-25 NiDataStream promotion status guard handoff

## Goal

Make the active post-Stage-18 Ghidra/NiDataStream discovery lane machine-readable, fail-closed, and explicit about why parser/export promotion remains blocked.

## What changed

- Added `nidatastream-promotion-status` to `scripts/rift_workflow.py` with JSON/human-readable promotion gate status.
- Added `nidatastream-parser-field-proof-guard` to fail closed if Ghidra-backed NiDataStream parser/export promotion is ever marked allowed before proof gates exist.
- Integrated that proof guard into `ghidra-workflow-guard-suite` so the suite checks target safety, parser/export promotion blocking, export isolation, and grouped candidate baselines together.
- Wired both commands through `scripts/Invoke-RiftWorkflow.ps1` aliases and command-wiring tests.
- Added `docs/schemas/nidatastream-promotion-status-v1.schema.json` and schema validation coverage.
- Added `docs/post-stage18-ghidra-proof-status.md` to fix canonical wording: historical geometry/export pipeline is Stage 18 complete; current work is the post-Stage-18 Ghidra/NiDataStream proof-guard lane.
- Updated README, AI workflow docs, and the parser-field comparison checklist with the new commands and current candidate-only gate status.

## Why it matters

The workflow now has a single parseable gate surface for agent decisions. It prevents an autonomous agent from treating Ghidra evidence as parser/export truth just because local FunctionSiteSurvey evidence exists. Ghidra remains useful as candidate evidence, but promotion requires additional descriptor-field, sample-byte, pairing-impact, and narrow-parser-patch proof.

## Evidence / validation

Validated after the code/doc/schema changes:

```powershell
python -c "import pathlib, py_compile; [py_compile.compile(str(path), doraise=True) for path in pathlib.Path('scripts').glob('*.py')]"
Get-ChildItem scripts/test_*.py | Sort-Object Name | ForEach-Object { python $_.FullName; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
ruff check scripts/
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py nidatastream-promotion-status --list-json | python -c "import json,sys; data=json.load(sys.stdin); print(data['SchemaVersion'], data['HistoricalStage'], data['BlockerCount'])"
python scripts/rift_workflow.py nidatastream-parser-field-proof-guard
python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Observed key result: `nidatastream-promotion-status/v1 Stage 18 complete 4`; `nidatastream-parser-field-proof-guard` passed while keeping parser/export promotion blocked by four gate(s).

## Known blockers / limits

- The command is intentionally candidate-only and does not alter decoder/export behavior.
- FunctionSiteSurvey evidence is locally available, but descriptor field order and sample-byte agreement are not yet executable promotion proof.
- Pairing-impact proof remains blocked until candidate rows can be shown not to promote noise/sentinels or incorrect complete groups.
- `ParserExportPromotionAllowed` is schema-locked to `false` in v1 by design.

## Generated-output handling

No copied RIFT assets or generated extraction/export reports were staged. `generated-output-guard` reported zero tracked/staged generated paths. `Source/`, `Extracted/`, `Exports/`, `bin/`, `obj/`, caches, and `.pyc` remain local/generated boundaries.

## Next recommended actions

1. Add an executable descriptor-field-order proof artifact for the NiDataStream helper targets.
2. Add sample-byte agreement checks that compare current `nidatastream-layout` output against concrete ignored sample reports.
3. Add a schema-backed JSON output for the descriptor/sample proof once it exists.
4. Keep `nidatastream-parser-field-proof-guard` in the Ghidra guard suite before any parser/export patch.
5. Add promotion-readiness docs that explain the exact evidence needed to change `ParserExportPromotionAllowed` in a future schema version.
