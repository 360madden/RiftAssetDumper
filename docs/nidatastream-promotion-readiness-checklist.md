# NiDataStream promotion-readiness checklist

Status date: 2026-05-25

## Current decision

`NiDataStream` Ghidra evidence is useful and increasingly machine-readable, but it is **not parser/export truth** yet.

Current v1 contracts intentionally lock promotion off:

- `docs/schemas/nidatastream-promotion-status-v1.schema.json` requires `ParserExportPromotionAllowed: false`.
- `docs/schemas/nidatastream-descriptor-proof-status-v1.schema.json` requires `FieldOrderPromoted: false`.
- `nidatastream-parser-field-proof-guard` passes only while promotion remains blocked.
- `nidatastream-parser-export-non-consumption-guard` verifies decode/export-sensitive C# consumers do not read candidate NiDataStream/Ghidra body-layout fields.

Before changing any promotion-critical schema, follow `docs/nidatastream-ghidra-schema-policy.md`.

Before proposing any parser/export behavior change, copy and fill `docs/nidatastream-parser-export-promotion-decision-template.md` into a dated decision record or handoff.

## Required commands before any future parser/export patch

```powershell
python scripts/rift_workflow.py nidatastream-evidence-status --list-json
python scripts/rift_workflow.py nidatastream-promotion-preflight
```

Expanded equivalent command sequence:

```powershell
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-promotion-dashboard
python scripts/rift_workflow.py nidatastream-parser-export-non-consumption-guard
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
python scripts/rift_workflow.py nidatastream-descriptor-table-sample
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
python scripts/rift_workflow.py ghidra-attribute-candidate-report
python scripts/rift_workflow.py ghidra-attribute-candidate-guard
python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build
python scripts/rift_workflow.py generated-output-guard
```

## Future promotion gates

| Gate | Required future proof | Current v1 status |
|---|---|---|
| Descriptor field order | Exact byte-level descriptor field map, including count/order/format/component semantics, backed by Ghidra report status and sample bytes | Candidate-only; static table offsets are machine-readable and summarized by promotion status/dashboard, but stream record semantics remain unmapped and `FieldOrderPromoted=false` |
| Sample-byte agreement | Copied/extracted samples agree across all selected `NiDataStream` blocks and a documented sample corpus | Candidate-only; ignored local report may show agreement but remains sidecar evidence |
| Descriptor/sample comparison | One machine-readable report joins descriptor-helper readiness, sample corpus metadata, copied-sample byte-counter uniformity, candidate byte-order offsets, first descriptor-record byte distributions, record byte-0 index proof, helper argument-use proof, byte-role candidates, per-pattern matrix rows, copied-sample context correlation/review queue, indexed descriptor-table sample status, and static-vs-stream semantic feasibility before any parser patch | Guarded/report-only by `nidatastream-descriptor-sample-compare` plus `nidatastream-descriptor-table-sample`; summarized by `nidatastream-promotion-status` and `nidatastream-promotion-dashboard`; byte 0 is candidate-mapped as the static-table index, tracked helpers do not use bytes 1-2 for helper table lookup, byte 3 is a uniform-zero padding/reserved/sign-guard candidate, current indexed table sample status prefers the all-index report and shows readable but all-zero rows for all 256 byte indices, descriptor records are grouped/ranked with copied-sample first pair record plus usage/access/type context, variable bytes 1-2 remain unmapped for parser/export semantics, semantic mapping remains false, and promotion still blocks |
| Descriptor static-data neighborhood | Candidate data references and nearby memory are checked for nonzero table-like bytes before relying on static table semantics | `nidatastream-descriptor-neighborhood-scan`; schema `docs/schemas/ghidra-descriptor-table-neighborhood-scan-v1.schema.json` | Report-only; current retained-project scan found 0 nonzero hits in 6915 memory-backed rows around the candidate references, so it reinforces the promotion block |
| Pairing impact | A parser interpretation change improves complete position+normal+UV evidence without promoting noise/sentinel groups | Candidate-only; zero complete Ghidra-only groups is a brake, not promotion proof |
| Narrow parser patch | Smallest parser field-read change, covered by regression tests before exporter use | Not started |
| Export isolation | Ghidra evidence and candidate NiDataStream body-layout fields remain out of decode/export paths until promotion gates are all green | Guarded |
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
