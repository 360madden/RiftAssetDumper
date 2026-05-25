# NiDataStream parser/export promotion decision template

Status: template

Use this file as a copy/paste checklist for any future pull request or commit series that changes `NiDataStream` parser/export behavior. Do not fill this template by editing it in place; copy it into a dated handoff or decision record.

## Decision summary

- Date:
- Proposed parser/export change:
- Scope:
- Files changed:
- Promotion owner/reviewer:
- Decision: `blocked` / `candidate-only` / `approved for parser test` / `approved for export use`

## Required current-truth commands

Paste command output summaries, not raw generated reports:

```powershell
python scripts/rift_workflow.py nidatastream-promotion-preflight
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
python scripts/rift_workflow.py ghidra-attribute-candidate-report
python scripts/rift_workflow.py ghidra-attribute-candidate-guard
python scripts/rift_workflow.py generated-output-guard
```

## Evidence gates

| Gate | Required answer | Evidence summary | Pass? |
|---|---|---|---|
| FunctionSite targets | Are required Ghidra reports/summaries present and target registry paths safe? |  |  |
| Descriptor field order | Which exact bytes/fields prove descriptor order/count/format/component semantics? |  |  |
| Sample-byte agreement | Which copied/extracted sample corpus proves the parser interpretation? |  |  |
| Pairing impact | Does the change improve useful position/normal/UV evidence without promoting noise? |  |  |
| Parser isolation | Is the parser patch narrow and covered by targeted tests? |  |  |
| Export isolation | Is export still blocked until parser truth is validated? |  |  |
| Generated-output safety | Are copied/generated assets and reports ignored/not staged? |  |  |

## Required negative checks

- `ParserExportPromotionAllowed` is not changed to true until all gates pass.
- `FieldOrderPromoted` is not changed to true until descriptor proof is explicit.
- Existing negative fixtures still fail closed.
- `nidatastream-parser-export-non-consumption-guard` is updated only alongside deliberate parser/export promotion tests.
- No generated reports, copied RIFT assets, or extraction output are staged.

## Parser/export test plan

- Targeted parser tests:
- Targeted export tests:
- Regression tests for legacy behavior:
- Expected generated-output locations:
- Commands run:

## Rollback plan

- Revert commit(s):
- Restore schema locks:
- Re-run preflight:
- Re-run generated-output guard:

## Final decision

- Approved scope:
- Remaining blockers:
- Next action:
