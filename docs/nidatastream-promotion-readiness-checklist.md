# NiDataStream promotion-readiness checklist

Status date: 2026-05-25

## Current decision

`NiDataStream` Ghidra evidence is useful and increasingly machine-readable, but it is **not parser/export truth** yet.

Current v1 contracts intentionally lock promotion off:

- `docs/schemas/nidatastream-promotion-status-v1.schema.json` requires `ParserExportPromotionAllowed: false`.
- `docs/schemas/nidatastream-descriptor-proof-status-v1.schema.json` requires `FieldOrderPromoted: false`.
- `nidatastream-parser-field-proof-guard` passes only while promotion remains blocked.

## Required commands before any future parser/export patch

```powershell
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-promotion-dashboard
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
python scripts/rift_workflow.py ghidra-attribute-candidate-report
python scripts/rift_workflow.py ghidra-attribute-candidate-guard
python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build
python scripts/rift_workflow.py generated-output-guard
```

## Future promotion gates

| Gate | Required future proof | Current v1 status |
|---|---|---|
| Descriptor field order | Exact byte-level descriptor field map, including count/order/format/component semantics, backed by Ghidra report status and sample bytes | Candidate-only; `FieldOrderPromoted=false` |
| Sample-byte agreement | Copied/extracted samples agree across all selected `NiDataStream` blocks and a documented sample corpus | Candidate-only; ignored local report may show agreement but remains sidecar evidence |
| Pairing impact | A parser interpretation change improves complete position+normal+UV evidence without promoting noise/sentinel groups | Candidate-only; zero complete Ghidra-only groups is a brake, not promotion proof |
| Narrow parser patch | Smallest parser field-read change, covered by regression tests before exporter use | Not started |
| Export isolation | Ghidra evidence remains out of decode/export paths until promotion gates are all green | Guarded |
| Generated-output safety | No copied RIFT assets or generated reports are staged/committed | Guarded |

## Allowed next work

- Add more status/guard/report surfaces.
- Refresh ignored local reports.
- Add schemas and tests.
- Document exact evidence requirements.

## Not allowed in v1

- Do not set `ParserExportPromotionAllowed` to true.
- Do not set `FieldOrderPromoted` to true.
- Do not feed Ghidra evidence directly into decode/export behavior.
- Do not weaken schemas, guards, or generated-output checks to make a candidate pass.
