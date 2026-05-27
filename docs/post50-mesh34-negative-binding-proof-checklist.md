# Post-50 mesh#34 negative-binding proof checklist

Status: **candidate-only / export-blocking**

This checklist captures why meshSize `329` mesh#34 extra stream `@304/#57`
cannot be consumed by parser/export code yet, even though it is repeatable
source-binding evidence.

## Required evidence sources

| Evidence source | Required status | Current status |
|---|---|---|
| `post50-mesh329-source-binding-compare` | schema-backed candidate report | ✅ present in `post50-position-source-status` |
| `position-source-sibling-extra-position-report` | schema-backed candidate report | ✅ present in `post50-position-source-status` |
| `post50-mesh329-family-proof` | schema-backed top-family proof | ✅ present in `post50-position-source-status` |
| `post50-mesh34-complete-binding-negative-proof` | schema-backed negative proof | ✅ present in `post50-position-source-status` |
| Parser/export promotion gate | locked false | ✅ `ParserExportPromotionAllowed=false` |

Refresh/check command sequence:

```powershell
python scripts/rift_workflow.py post50-mesh329-source-binding-compare
python scripts/rift_workflow.py post50-mesh34-complete-binding-negative-proof
python scripts/rift_workflow.py post50-mesh34-negative-binding-status --list-json
python scripts/rift_workflow.py post50-validation-suite --list-json
```

## Negative-binding facts to preserve

These facts are blockers, not promotions:

| ID | Shared primary `@212/#28` | Extra mesh#34 `@304/#57` | mesh#34 attribute sets | mesh#34 UV streams | Export-ready? |
|---|---:|---:|---:|---:|---|
| `0364ea142bc00ce7` | 48 vectors | 20 vectors | 0 | 0 | false |
| `04de901531a091ab` | 37 vectors | 23 vectors plus 4-byte remainder | 0 | 0 | false |
| `066fa520a8ce62e3` | 22 vectors | 8 vectors | 0 | 0 | false |

## Hard gates before parser/export consumption

Do **not** consume mesh#34 `@304/#57` in decode/export code unless a future
validated proof packet shows all of the following:

1. mesh#34 has a complete position/normal/UV binding group.
2. The binding group references the candidate stream through parser-derived
   relationship fields, not through report-only heuristics.
3. Attribute-set and UV evidence agree across at least the current three sibling
   examples.
4. The proof packet has a tracked schema and targeted tests.
5. `post50-position-source-status` changes from candidate-only blocker to an
   explicit reviewed promotion state.
6. Parser/export non-consumption guards are updated only after the promotion
   decision record is committed.
7. Generated output guard still proves no copied/generated game assets are
   staged.

## Current decision

`mesh#34 @304/#57` is useful evidence for source-binding discovery, but it is a
negative-binding proof for parser/export purposes:

- repeatable: yes
- schema-backed: yes
- complete geometry binding: no
- export-ready: no
- parser/export promotion allowed: no

Keep this lane as candidate-only until the hard gates above pass.
