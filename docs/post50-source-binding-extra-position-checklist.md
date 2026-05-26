# Post-50 source-binding extra-position checklist

Status: **candidate-only**. The meshSize `329` mesh `#34` `@304/#57`
position-like stream is a useful discovery lead, but it must not drive parser,
geometry, or OBJ/export behavior until this checklist passes.

## Current workflow commands

```powershell
python scripts/rift_workflow.py position-source-sibling-family-report --skip-build
python scripts/rift_workflow.py position-source-sibling-probe-report --skip-build
python scripts/rift_workflow.py post50-position-source-status --list-json
python scripts/rift_workflow.py generated-output-guard
python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build
```

The current machine-readable contracts are:

```text
docs/schemas/post50-position-source-status-v1.schema.json
docs/schemas/position-source-sibling-probe-report-v1.schema.json
docs/schemas/position-source-sibling-extra-position-report-v1.schema.json
```

## Current evidence snapshot

`post50-position-source-status` currently ranks:

| Rank | Lane | Mesh size | Stream | Evidence | Export ready |
|---:|---|---:|---|---:|---|
| 1 | `source-binding-family` | 329 | `stream@212` | 23 groups / 46 links | false |
| 2 | `source-binding-extra-position` | 329 | `mesh#34 @304/#57` | 3 groups / 3 links | false |
| 3 | `residual-packed-position` | 305 | `stream@188` payload 288 | plausible 0.9444 | false |
| 4 | `residual-cluster-structure` | 305 | `stream@21` payload 288 | candidate cluster | false |

Current hard blockers:

- `mesh329-extra-position-like-stream-candidate-only`
- `residual-position-strict-threshold-not-met`
- `residual-cluster-no-complete-geometry-binding`
- `mesh325-position-source-sparse-no-residuals`
- `parser-export-promotion-not-allowed`

## Hard promotion gates for `mesh#34 @304/#57`

| Gate | Requirement |
|---|---|
| Candidate-only status | `post50-position-source-status` keeps the lane `ExportReady=false` until all gates pass. |
| Schema guard | The extra-position report validates against `position-source-sibling-extra-position-report/v1`. |
| Family coverage | At least three independent meshSize `329` sibling IDs reproduce the `mesh#34 @304/#57` position-like stream. |
| Stream role proof | The `@304/#57` bytes pass finite/plausible position-vector checks, not just role-name heuristics. |
| Attribute-binding proof | Explain why mesh `#34` lacks a complete position+normal+UV attribute set while still containing two position-like streams. |
| Topology proof | Identify which stream, if any, pairs with a valid index/topology source without borrowing unproven sibling-local normal/UV streams. |
| Negative proof | Show the `@304/#57` stream is not UV, sentinel, repeated-pattern, padding, duplicated transform data, or unrelated sidecar data. |
| Ghidra isolation | `ghidra-workflow-guard-suite --skip-build` passes and Ghidra evidence remains report-only. |
| Generated-output safety | `generated-output-guard` passes before commit; ignored `Exports/` reports are not staged. |
| Promotion patch discipline | Parser/export behavior changes, if ever justified, must be a separate guarded patch after this checklist is satisfied. |

## Explicit non-goals until promotion

- Do not feed `@304/#57` into `DecodeNifGeometry`.
- Do not reinterpret mesh `#34` UV or normal sources based only on sibling mesh `#7`.
- Do not merge residual payload `288` evidence with source-binding family evidence without a separate report boundary.
- Do not weaken existing Ghidra, generated-output, schema, or parser/export guards to make this candidate pass.

## Next safe action

Build a focused, ignored comparison report for the three meshSize `329`
`@304/#57` examples that records byte-level position plausibility, negative
semantic checks, and whether any valid topology/index binding exists. Keep the
result candidate-only until a separate proof guard exists.
