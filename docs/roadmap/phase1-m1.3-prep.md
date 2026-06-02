# Phase 1 M1.3 Prep Note — Sibling Source-Binding + Variant Attribute Layout Guards

**Date**: 2026-06
**Context**: Post-M1.2 transition. M1.2 complete per `docs/roadmap/phase1-m1.2-coordination.md`, `docs/handoffs/draft-2026-06-m1.2-@304-extra-stream-classification.md`, and `docs/roadmap/current-phase.md`. Per `docs/roadmap/project-roadmap.md` Phase 1 **M1.3**: develop or extend proof guard(s) for sibling source-binding + variant attribute layout.

**Anti-drift**: meshSize=329 family only (no new discovery). **Candidate-only**; no parser/export promotion. Automation via **Python-only** extensions in existing `scripts/rift_workflow.py` / `rift_workflow_guards.py` (no PowerShell). Do not commit `Exports/` content. Reference this prep + matrix + roadmap in all M1.3 work.

## Objective

Turn M1.2 @304 classification evidence into **repeatable proof guards** that assert, per matrix sibling pairs:

1. **Sibling source-binding**: consistent primary position source (@212/#28, `position-float3-ror1-lead`) and paired mesh-block relationship between #7 and #34 variants in the 329 family.
2. **Variant attribute layout**: mesh#7 `attributeSets=1` with UV@304 vs mesh#34 `attributeSets=0` with extra pos@304 (`position-float3-ror1-lead`, c=75) — including the M1.2 finding that @304 on #34 is **not** an attribute-extra stream on the attr-probe path.

## Entry Artifacts (from M1.2)

| Artifact | Role |
|---|---|
| `docs/handoffs/draft-2026-06-m1.2-@304-extra-stream-classification.md` | Finalized M1.2 findings, scoped 10 IDs, paired anchors |
| `Exports/phase1-m1.2-@304-analysis-initial.json` + `.md` | Per-ID quant (ratios, plaus, endian/body class, magic patterns) |
| `Exports/mesh329-family-attribute-role-matrix.json` (+ .md/.csv) | Authoritative target list (`IDsCovered`, 12/12 patterns) |
| `Exports/probe-nif-mesh-*-mesh34.json` / `*-mesh7.json` | Raw probe inputs for guard assertions |
| `docs/roadmap/phase1-m1.2-coordination.md` | Batch log + supporting probe refs |

**Scoped guard pilot IDs** (3 paired anchors): `0364ea142bc00ce7`, `04de901531a091ab`, `066fa520a8ce62e3`.  
**Expand to**: full matrix `IDsCovered` (12) after pilot passes.

## Target Commands (existing `rift_workflow.py`)

Run with `--skip-build` where applicable; outputs stay under `Exports/` (not committed).

| Command | Purpose |
|---|---|
| `position-source-sibling-extra-position-report` | Refresh extra @304 sibling rows for compare input |
| `post50-mesh329-source-binding-compare` | Schema-lock @212/#28 vs mesh#34 @304/#57 binding evidence |
| `post50-mesh329-family-proof` | Family-level proof report from inventory |
| `post50-validation-suite` | Post-50 hygiene before guard edits |
| `post50-promotion-readiness-status` | Gate check (expect promotion still blocked) |
| `mesh-probe --id <ID> --mesh-block 7\|34` | Refresh per-ID layout fields if probes stale |
| `mesh329-attribute-role-matrix` | Re-synthesize matrix if new probes added |
| Guard commands (extend/assert in Python): `position-source-sibling-lead-guard`, `attribute-extra-proof-guard` — **do not** reuse hardcoded non-329 sibling IDs from `attribute-extra-sibling-proof-guard` without 329-specific parameters |

New guard logic should live in `rift_workflow_guards.py` and be wired through an existing or narrowly added workflow command (Python-only policy).

## Deliverables

- Extended or new **329-family** proof guard(s) + tests asserting sibling binding + variant attr layout on matrix IDs.
- Refreshed post50 compare/family proof JSON+MD under `Exports/` (local only).
- `docs/roadmap/phase1-m1.3-coordination.md` (when execution starts; optional follow-up).
- M1.3 handoff draft in `docs/handoffs/` (separate agent lane; not part of this prep edit).
- Updated `docs/roadmap/current-phase.md` on M1.3 exit.

## Anti-Drift Rules (M1.3)

- Targets must come from `mesh329-family-attribute-role-matrix.json` `IDsCovered` unless explicitly adding a matrix refresh probe.
- Guards document **candidate-only** pass/fail; no promotion language.
- Do not reinterpret @304 as promotion-ready position binding (M1.2 low plaus + non-attr-extra path).
- No new mesh sizes, no Ghidra export paths, no asset copies into repo.

## First Steps (concrete)

1. Re-read M1.2 handoff § findings + `phase1-m1.2-@304-analysis-initial.md` aggregates (avg ratio ~0.405, 8/8 low plaus).
2. Refresh `position-source-sibling-extra-position-report`, then `post50-mesh329-source-binding-compare` + `post50-validation-suite`.
3. Draft guard assertion table: per paired ID → expected `attributeSets` (#7=1, #34=0), @304 roles (#7 UV vs #34 pos c=75), primary @212 pos on both.
4. Implement pilot guard function (Python) against probe JSON paths for the 3 anchors; run via `rift_workflow.py`.
5. Expand pilot to scoped 10, then matrix 12; record pass counts in coordination note.
6. Run `post50-mesh329-family-proof` and attach summary to M1.3 handoff draft (other lane).
7. Main agent: update `current-phase.md` to M1.3 COMPLETE only when guards stable on full `IDsCovered`.
8. Optional: `phase1-m1.2-304-magic-analysis` refresh if guard needs BodyFirst16 cross-check (existing command).

**References**: `docs/roadmap/project-roadmap.md` (Phase 1 M1.3), `docs/roadmap/phase1-m1.2-prep.md`, `scripts/rift_workflow.py`, `docs/task-routing-safety-policy.md`.

**Status**: Prep complete. Ready for M1.3 execution per `docs/roadmap/current-phase.md`. **Guard pilot implemented** — `phase1-m1.3-329-variant-layout-guard` (Python-only; `scripts/rift_workflow_guards.py`).