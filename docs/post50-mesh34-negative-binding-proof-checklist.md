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

## M1.2 Data Refresh (candidate-only; extends for Phase 1 M1.3)

M1.2 (final handoff + analysis + matrix) adds quantified support to the negative facts:

- 10/10 scoped + 12/12 matrix: `attributeSets=0` on #34 (inversion vs #7=1 with UV@304).
- @304 on #34: position c=75 but **no attr-extra stream** on attr-probe path (8/8 informative ERROR from batch; path blocked by attrSets=0).
- Payload/magic/low-plaus/distinct body (M1.2): avg ratio ~0.405; 022bc2 (2/8) + c2 (7/8); 8/8 low plaus (PlausF32 << expected); distinct bodies (first16/samp diffs, no 1:1 to primary @212); mixed endian; stride12 viable.
- See dedicated `Exports/post50-mesh329-m1.2-evidence-update.json` + `.md` (light Python postproc scores + per-blocker tables + extended 10-row evidence with M12_* fields).

**Hard gates remain** (now strengthened): complete attr+UV binding + attr-extra path agreement + proof packet + reviewed promotion decision still required before any consumption of #34 @304.

**Refs**: M1.2 handoff `docs/handoffs/draft-2026-06-m1.2-@304-extra-stream-classification.md`; analysis `Exports/phase1-m1.2-@304-analysis-initial.*` + final-summary; matrix `Exports/mesh329-family-attribute-role-matrix.*`; roadmap `docs/roadmap/project-roadmap.md` Phase 1 M1.3/M1.2 + preps; `docs/roadmap/phase1-m1.3-prep.md`.

Candidate-only; 329 family only. Supports M1.3 guard work on sibling source-binding + variant attribute layout. (Appended post M1.2; redacted; no active phase or main M1.2 handoff edited.)

**Updated checklist status**: still **not ready / candidate-only / export-blocking**.

## Phase 1 Consolidation (M1.5 — Comprehensive Exit Handoff)

Phase 1 (M1.1-M1.4) consolidation adds cross-family evidence to the negative-binding facts:

### 329 Family (full evidence chain)

- M1.1: 12/12 paired matrix — attrSets=0 on #34 universal; @304 pos c=75 on #34; shared @212 primary.
- M1.2: @304 deep classification — 10/10 low plaus despite c=75 role; avg ratio ~0.4× primary; non-attr-extra path (8/8 informative ERROR); 022bc2 (2/10) + c2 (9/10) magic patterns; distinct bodies; mixed endian; no simple float3 transform to primary.
- M1.3: Sibling-binding + variant attr layout guards — 12/12 PASS (pilot 3/3 + prototype 12/12 scores 9-11/11); validation suite 9/9 PASS.

### 305 Family (cross-family validation)

- M1.4: Light structural comparison — 15 groups, 30 links, #7↔#27 sibling pair; attrSets=1/#7 vs attrSets=0/#27 confirmed (same pattern as 329); shared primary position @188 (same BodyFirst16 between siblings).
- 305 sibling #27: secondary stream @196 is **genuine UV data** (c=80, UV-range unit vectors) — different from 329 #34 @304 anomalous pos-like.
- 305 residual: CONFIRMED NEGATIVE (magic-43606, plausible 0.9444 < 0.95, float32 = denormal garbage) — closed.

### Cross-family blocker status

| Blocker | 329 (#34) | 305 (#27) |
|---|---|---|
| `attrSets=0 on sibling` | 12/12 confirmed | Confirmed (representative) |
| `non-attr-extra path` | 8/8 informative ERROR | By structural inference |
| `@304/@196 role anomaly` | Pos c=75 but 10/10 low plaus | Clean UV c=80 — but export blocked by attrSets=0 |
| `complete geometry binding` | NOT PROVEN | NOT PROVEN |
| `export-ready` | NO | NO |

**Hard gates remain** — strengthened by cross-family evidence. See comprehensive Phase 1 exit handoff: `docs/handoffs/2026-06-m1.5-phase1-exit-consolidation.md`.

**Refs**: M1.5 prep `docs/roadmap/phase1-m1.5-prep.md`; M1.5 handoff `docs/handoffs/2026-06-m1.5-phase1-exit-consolidation.md`; M1.1-M1.4 handoffs; matrix; roadmap Phase 1 + Phase 2.

Candidate-only; cross-family (329 + 305); Phase 1 consolidation. (Appended M1.5; no hard gate changes.)
