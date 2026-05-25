# NiDataStream parser-field comparison — Ghidra sidecar status

Status: **candidate-only / report-only**. This note compares current repo parser/report fields with the retained-project Ghidra `NiDataStream` static evidence. It is not a parser promotion plan.

## Evidence inputs

| Evidence | Current source |
|---|---|
| Load routine anchor | `ghidra-function-site-survey --ghidra-target nidatastream-loadbinary` |
| Descriptor/helper anchors | `nidatastream-descriptor-helper`, `nidatastream-descriptor-builder-1770`, `nidatastream-descriptor-builder-17c0` |
| Semantic adapter anchor | `ghidra-function-site-survey --ghidra-target nidatastream-semantic-adapter` |
| Parser-side comparison reports | `nidatastream-layout`, `inventory-nif-stream-bodies`, `inventory-nif-mesh-bindings` |

All Ghidra reports/summaries are ignored local evidence under `Exports/ghidra-reports/`.

## Current field alignment

| Concept | Ghidra static read | Current repo surface | Promotion state |
|---|---|---|---|
| Declared payload byte count | Load path reads stream binary fields/counts before payload data | `DeclaredPayloadBytes` from the first 4 payload bytes | Reported and used for bounds checks |
| Payload prefix | Load path evidence supports payload beginning before the old legacy body offset | `PayloadPrefixBytes`, `GhidraStyleLayoutValid` | Sidecar/report-only |
| Legacy payload offset | Historical parser consumed the body after the older offset | `LegacyPayloadOffset`, `LegacyOffsetMinusPayloadPrefixBytes` | Still preserved for backward compatibility |
| Trailing flag | Ghidra-aligned layout leaves a 1-byte trailer after declared payload | `PayloadTrailerBytes`, `TrailingFlag` | Sidecar/report-only |
| Descriptor static lookup table | Descriptor helper/builders use a candidate 12-byte static table stride with offsets 0/4/8 for special flag, component/class, and format-size lookup evidence | `CandidateFieldMap` in `nidatastream-descriptor-proof-status` and `nidatastream-descriptor-sample-compare` | Candidate-only; stream descriptor record bytes are not mapped to parser/export fields |
| Stream descriptor record bytes | Copied/extracted samples expose first descriptor record byte distributions and a per-pattern matrix; Ghidra LoadBinary/helper evidence maps byte 0 as the candidate static-table index while current byte-role classification keeps variable bytes 1-2 unmapped and treats byte 3 as a uniform-zero padding/reserved candidate | `DescriptorRecordByteSummary`, `DescriptorRecordIndexProof`, `DescriptorRecordByteRoleCandidates`, and `DescriptorRecordPatternMatrix` in `nidatastream-descriptor-sample-compare` | Candidate-only; partial index/padding/pattern proof only |
| Helper argument byte usage | Tracked descriptor helper/builders gate negative signed descriptor values, then mask the helper argument with `param_1 & 0xff`; current proof reports bytes 1-2 as not affecting tracked helper table lookup and byte 3 as sign-guard-only | `DescriptorHelperArgumentUseProof` in `nidatastream-descriptor-proof-status` and `nidatastream-descriptor-sample-compare` | Candidate-only; bytes 1-2 still unmapped for parser/export semantics |
| Descriptor semantic feasibility | Static descriptor-table offsets are compared against observed stream descriptor-record byte offsets, the byte-0 index proof, and byte-role candidates, but remaining variable bytes and parser/export semantics stay blocked | `DescriptorSemanticFeasibility` in `nidatastream-descriptor-sample-compare` | Candidate-only; semantic mapping remains false and parser/export promotion remains locked |
| Usage/access metadata | Gamebryo block names encode usage/access variants | `DataStreamUsage`, `DataStreamAccess` | Reported and used for ranking/grouping |
| Semantic adapter ordering | Ghidra semantic adapter path checks stream-element/semantic ordering | Role/grouping reports preserve stream order and semantic grouping | Reported only |

## Parser-field promotion checklist

Do not change decoder/export behavior until every required gate for the target field is green. A yellow or red row keeps the field report-only.

| Gate | Required proof | Current command/source | Current status |
|---|---|---|---|
| Target registry safety | FunctionSiteSurvey targets are candidate-only, unique, and write only repo-relative ignored `Exports/ghidra-reports/` files | `ghidra-function-site-target-guard`; included in `ghidra-workflow-guard-suite` | ✅ Guarded |
| Ghidra evidence availability | The target has both a local ignored JSON report and Markdown summary before being cited as fresh evidence | `ghidra-function-site-status --list-json` | ✅ Local 7/7 evidence-ready as of the 2026-05-25 summary refresh; still ignored/generated and candidate-only |
| Descriptor field order | Descriptor helper/builders prove count/order/format/component fields strongly enough to map bytes, not just names | `nidatastream-descriptor-proof-status --list-json`; descriptor builder targets | 🟨 Candidate-only; local status checks 4 descriptor helper/builders and exposes static table offsets, but stream record semantics remain unmapped |
| Sample-byte agreement | Copied/extracted NIF samples agree with the proposed Ghidra-aligned prefix/payload/trailer interpretation | `nidatastream-layout --root Extracted --full`; schema `docs/schemas/nidatastream-layout-report-v1.schema.json` | 🟨 Local ignored report currently shows 184/184 Ghidra-style-valid blocks; still report-only |
| Descriptor/sample compare | Descriptor-helper readiness, sample corpus metadata, copied-sample byte counters, candidate descriptor byte-order offsets, first descriptor-record byte distributions, record byte-0 index proof, helper argument-use proof, byte-role candidates, per-pattern matrix rows, and static-vs-stream semantic feasibility are joined in one machine-readable report | `nidatastream-descriptor-sample-compare`; schema `docs/schemas/nidatastream-descriptor-sample-compare-v1.schema.json` | 🟨 Report-only; local compare currently shows descriptor/sample ready with 6/6 byte-counter checks and 7/7 byte-order checks, 5 descriptor pattern rows, and tracked helpers not using bytes 1-2 for helper lookup, but variable descriptor bytes 1-2 remain unmapped for parser/export semantics, semantic mapping remains false, `FieldOrderPromoted=false`, and parser/export promotion locked |
| Pairing impact | A field interpretation change creates complete position+normal+UV evidence without promoting noise/sentinels | `ghidra-attribute-candidate-report`; `ghidra-attribute-candidate-guard`; summarized by `nidatastream-promotion-status --list-json` | 🟨 Local ignored report has 0 complete position+normal+UV Ghidra-only groups across 14 groups; still candidate-only |
| Export isolation | Ghidra evidence is not consumed by decode/export paths | `ghidra-workflow-guard-suite`; `ghidra-pairing-non-export-guard` | ✅ Guarded |
| Narrow parser patch | Any future parser change is isolated to the smallest field-read surface and has regression tests before exporter use | Future C#/Python tests | 🟥 Not started |

Executable status/guard surface:

```powershell
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-parser-field-proof-guard
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
```

## Current decision

- Keep `NiDataStream` Ghidra evidence as a sidecar until a narrow parser patch has a proof guard.
- Do not switch geometry decode/export consumers from legacy body slicing to Ghidra-aligned slicing in this stage.
- Continue using `nidatastream-layout`, `nidatastream-descriptor-sample-compare`, `ghidra-function-site-status --list-json`, and Ghidra target summaries to identify a minimal, guardable parser-field promotion if one becomes necessary.

## Next safe proof questions

1. Do descriptor-helper targets prove a field count/order that the C# parser is currently missing?
2. Can the byte-order proof be expanded from structural offsets/record bytes into exact descriptor semantics before any exporter uses it?
3. Does any current Ghidra-only mesh candidate become a complete position/normal/UV group after a field interpretation change?

Until those are answered with tests and guards, parser/export behavior remains unchanged.
