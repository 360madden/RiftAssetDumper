# Phase 1 M1.3 Prep Note — Sibling Source-Binding + Variant Attribute Layout Guards

**Date**: 2026-06
**Prepared by**: Forward-planning subagent (read-only exploration + draft in place; this task)
**Context**: Post-M1.2 finalize. M1.2 complete per `docs/roadmap/phase1-m1.2-coordination.md`, `docs/handoffs/draft-2026-06-m1.2-@304-extra-stream-classification.md`, `docs/roadmap/current-phase.md`, and new M1.2 artifacts (analysis-initial, magic, final-classification-summary). Per `docs/roadmap/project-roadmap.md` Phase 1 (M1.2 → M1.3: "Develop or extend proof guard(s) for 'sibling source-binding + variant attribute layout'"). Builds directly on M1.2 @304 classification (payload anomalies, low plaus 10/10 despite c=75 role, non-attr-extra path on #34, magic prefixes, ~0.4x ratios, distinct bodies) + M1.1 matrix (12/12 attr delta + shared @212 primary pos).
**Anti-drift**: Strictly meshSize=329 family only (no new discovery; light 305 comparison only in M1.4 per roadmap). **Candidate-only**; no parser/export promotion. Automation via **Python-only** (existing `scripts/rift_workflow.py` + narrow extensions in `rift_workflow_guards.py`; no new .ps1/.cmd per AGENTS.md hard rule). Do not commit `Exports/` content. Reference this prep + matrix + M1.2 handoff + roadmap in all M1.3 work. High-reasoning lane per `docs/task-routing-safety-policy.md`.
**References**: `docs/roadmap/project-roadmap.md` (Phase 1 M1.3 + M1.2), `docs/roadmap/phase1-m1.2-prep.md`, `docs/roadmap/current-phase.md`, `docs/task-routing-safety-policy.md` (high-reasoning for proof guards/asset truth), M1.2 handoff + analysis artifacts, `scripts/rift_workflow_guards.py` (pilot already present).

## Objective
Per explicit definition in `docs/roadmap/project-roadmap.md`:
> 3. **M1.3**: Develop or extend proof guard(s) for "sibling source-binding + variant attribute layout".

Turn M1.2 @304 classification evidence (and M1.1 matrix) into **repeatable, machine-checkable proof guards** that assert, per matrix sibling pairs (and full family):
1. **Sibling source-binding**: consistent primary position source (@212/#28, `position-float3-ror1-lead` c=75) shared between #7 and #34 variants; paired mesh-block relationship in 329 family.
2. **Variant attribute layout**: mesh#7 `attributeSets=1` (often with UV@304) vs mesh#34 `attributeSets=0` + extra pos@304 (`position-float3-ror1-lead` c=75); M1.2 finding that @304 on #34 is **not** parsed via attribute-extra stream path (attrSets=0).

## Entry Criteria (M1.2 Complete)
- M1.2 finalized (batch 8/8 informative "no attribute extra @304 on #34", analysis quant 8+ext, magic cross-ID, final summary 10/10+12/12 patterns, handoff updated with tables/blockers).
- Primary artifacts from M1.2 + M1.1: matrix (exact target list), M1.2 analysis/magic/final JSON+MD, probes for matrix IDs, sibling extra-pos reports.
- Guard pilot already prototyped in `scripts/rift_workflow_guards.py` (phase1_m13_329_variant_layout_guard + constants + matrix/probe helpers; wired in rift_workflow.py as `phase1-m1.3-329-variant-layout-guard`; refs this prep in docstring).
- All candidate-only, 329+matrix, Python, guards/safety, Phase 1 refs per verification (see `Exports/phase1-m1.2-safety-drift-verification.md`).

## Exact Target List
Reference the current matrix as the **exact target list**: `Exports/mesh329-family-attribute-role-matrix.json` (and .md/.csv). 
- IDsCovered (12 total): 0364ea142bc00ce7, 04de901531a091ab, 066fa520a8ce62e3, 07c733b4eee3ed2e, 4eb7745610adf8c7, 69da9507d49c42ff, 7f3e71246752afb2, 83df87e22bff4a94, 91ead5caf689a8a5, b57694c1f202ec07, c5a1982e92e15b7b, f2c347fe81a5e3b2.
- All have #34 data showing the extra @304 position-like stream (attrSets=0, role=position-float3-ror1-lead c=75 on @304/#57, shared @212 primary, @296 u32 body).
- 3+ paired for contrast (UV@304 on #7 vs. extra pos@304 on #34): 0364ea142bc00ce7, 04de901531a091ab, 066fa520a8ce62e3 (pilot per guard code); expand to more from M1.2 analysis (e.g. 0364/04de/07c7/69da etc.).
- New M1.2 artifacts for cross-check: `Exports/phase1-m1.2-@304-analysis-initial.json` + .md (PerID ratios/plaus/endian/bodyclass/magic), `Exports/phase1-m1.2-@304-magic-analysis.json` + .md (BodyFirst16 12/12, 022bc2 2/12, c2 11/12), `Exports/phase1-m1.2-final-classification-summary.json` (CorePatternsConfirmed 10/10+12/12).
- See M1.2 prep/coordination/handoff + curated queue for rationale/overlap.

## Top Pilot + Representative IDs (from Matrix + M1.2 Analysis)
Focus M1.3 guard pilot + expansion here first (3 anchors in existing guard code + prioritized by M1.2 coverage):
1. 0364ea142bc00ce7 (paired anchor)
2. 04de901531a091ab (paired)
3. 066fa520a8ce62e3 (paired low-v)
4. 69da9507d49c42ff (highest v; rich M1.2 data)
5. f2c347fe81a5e3b2
6. 07c733b4eee3ed2e
7. 83df87e22bff4a94
8. 4eb7745610adf8c7 / c5a1982e92e15b7b / 91ead5caf689a8a5 (M1.2 sampled)
(Expand to remaining: 7f3e71246752afb2, b57694c1f202ec07.)

## Focused Approach for M1.3
- **Probes/commands** (existing + narrow; run with --skip-build):
  - `mesh-probe --id <ID> --mesh-block 7|34` (refresh layout/attrSets/roles if needed).
  - `mesh329-attribute-role-matrix` (re-synth if probes added).
  - `position-source-sibling-extra-position-report` + `post50-mesh329-source-binding-compare` + `post50-mesh329-family-proof` (refresh sibling-binding evidence for 329 family using matrix).
  - `post50-validation-suite` + `post50-promotion-readiness-status` (hygiene/gate; expect still blocked).
  - Guard command: `phase1-m1.3-329-variant-layout-guard` (Python; consumes matrix + optional probes; already wired/prototyped).
  - Supporting: `phase1-m1.2-@304-magic-analysis` (if BodyFirst16 cross-check needed for guard).
  - Python post-processing on Exports/ matrix + phase1-m1.2-* analysis JSONs for scoring (e.g. extend guard or small postproc script).
- **Approach options** (per task + existing code): Extend `rift_workflow` with narrow guard mode (already done via phase1-m1.3-... command) **or** python guard prototype that consumes matrix/analysis json to score sibling-binding + attr delta. Pilot already in `rift_workflow_guards.py` (uses matrix PairComparisons/MatrixRows + optional probe JSONs for @212/@304 roles/attrSets/conf; asserts exactly the layout split + shared primary). Prefer reuse/extend existing rather than one-off; add matrix ID list param if expanding beyond pilot.
- **What to quantify/produce** (guard pass/fail on family, negative fixtures, machine checklist):
  - Per-ID + aggregate: pass/fail counts (pilot 3, then 10 scoped, then 12 matrix); attrSets delta (#7=1 vs #34=0); @304 role=pos c=75 on #34 only; shared @212 pos on both; probe cross-check success (when JSONs present).
  - Negative fixtures: synthetic or real cases that should fail (e.g. ID with attrSets mismatch, wrong @304 role/conf, no shared 212, non-329); record in guard report or separate fixture JSON/MD.
  - Machine checklist: "AllMatrixValidated", "AllProbeValidated", "ProbeCrossCheckCount", per-ID MatrixValidated/ProbeValidated bools, Aggregate.PilotCount etc. (already in pilot impl).
  - Output: Guard JSON+MD (phase1-m1.3-329-variant-layout-guard.json/.md per schema in code); refreshed post50 compare/family-proof; optional extended classification tying M1.2 quant (low plaus, magic) to guard (e.g. flag "requires-extra-proof" if low-plaus + attr delta).
  - Handoff contribution: pass/fail tables, fixture examples, updated blockers (e.g. "sibling-source-binding + variant-attr-layout-not-fully-guarded" resolved for 329 pilot).
- **Candidate guard sketch** (pseudocode / small py logic; matches existing pilot in rift_workflow_guards.py; "if mesh34 attrSets==0 and has @304 pos-c75 and shared @212 then flag as sibling-variant-requires-extra-proof"):
```python
# Sketch for M1.3 guard (Python; consumes matrix JSON + optional probes)
def check_sibling_variant_layout(matrix_row_7, matrix_row_34, probe7=None, probe34=None):
    # From matrix PairComparisons / MatrixRows for ID
    if matrix_row_7['attrSets'] != 1 or matrix_row_34['attrSets'] != 0:
        flag_as_requires_extra_proof("attr delta mismatch")
    if matrix_row_34['@304_role'] != "position-float3-ror1-lead" or matrix_row_34['@304_conf'] != 75:
        flag_as_requires_extra_proof("@304 pos-c75 missing on #34")
    if matrix_row_7['@212_role'] != "position-float3-ror1-lead" or matrix_row_34['@212_role'] != "position-float3-ror1-lead":
        flag_as_requires_extra_proof("shared @212 primary pos not both")
    # Optional probe cross-check (if JSON present)
    if probe34 and probe34['attrSets'] != 0: ...
    # M1.2 tie-in example: if low_plaus or magic_anomaly: still pass layout but note "variant-requires-extra-proof for semantic"
    return "PASS" if all checks else "FAIL (requires-extra-proof)"

# Run on all matrix IDsCovered; produce pass/fail + negative fixtures (e.g. alter one row attrSets=1 on #34 -> expect FAIL)
# See rift_workflow_guards.py:phase1_m13_329_variant_layout_guard for full impl (pilot 3 IDs, matrix-driven, probe optional, writes JSON+MD with PerID + Aggregate)
```
- **Handoff structure**:
  - Artifacts: Guard report (JSON+MD), refreshed post50-*.json/md for 329, any extended py postproc outputs, pass/fail tables + fixtures.
  - Dedicated M1.3 handoff in `docs/handoffs/` (short, like M1.2: objective, IDs from matrix, guard results/tables, updated blockers, artifacts list, validation, refs to matrix/M1.2 handoff/roadmap/Phase 1 M1.3 + M1.2 parents).
  - Update `docs/roadmap/current-phase.md` (M1.3 complete pointer to M1.4 or note).
  - Minor: `docs/roadmap/phase1-m1.3-coordination.md` if swarm used.
  - Validation: GeneratedOutputGuard, schema (guard has v1), candidate-only review, explicit "Phase 1 M1.3 per roadmap" + matrix ref, no promotion. Run verification grep post-run.
- **Validation gates** (repeat per run): GeneratedOutputGuard, candidate-only language, drift check (329 + matrix targets only), Phase 1 M1.2/M1.3 refs, schema if new, python-only.

## First Steps
1. Review M1.2 blockers (from finalized handoff: `mesh34-complete-geometry-binding-not-proven`, `mesh329-variant-attribute-layout-not-classified`, `position-vs-extra-stream-role-ambiguity-in-siblings`, `mesh329-extra-position-like-stream-candidate-only`, `parser-export-promotion-not-allowed`) + M1.2 analysis aggregates (low plaus, magic, ratios) + matrix patterns (12/12).
2. Sketch guard in py (see above; or review/extend existing `phase1_m13_329_variant_layout_guard` in `rift_workflow_guards.py` which already implements pilot on 3 + matrix).
3. Run on matrix IDs: `python scripts/rift_workflow.py phase1-m1.3-329-variant-layout-guard --out Exports/` (pilot defaults to 3; extend via param or edit for full 12); capture JSON+MD; run on negative fixtures; cross with M1.2 magic JSON if desired.
4. Draft M1.3 handoff (per structure; feed guard results + M1.2 evidence); update coordination/pointers; main reviews before M1.3 exit.

**Status**: Prep complete (draft in place + enhanced per task). Guard pilot pre-implemented in code. Ready for M1.3 execution per `docs/roadmap/current-phase.md`. Reference Phase 1 M1.2 (for entry evidence) + M1.3.

### Optional: Practical Next Steps / Improvement Ideas (Post-Prep / During M1.3)
- After pilot 3 pass, auto-expand guard to full matrix IDsCovered via list param (reuse M1.2 matrix synthesizer patterns).
- Tie M1.2 "low_plaus_despite_pos_role" + magic candidates into guard as "extra-proof required" annotations (not hard fail).
- Add guard to rift_workflow_reports.py or post50 suite for machine checklist export.
- Validate samples in MD (side-by-side #7/#34 attr + @304 role per ID).
- Feed M1.3 guard outputs directly into M1.4 (light 305) + M1.5 (comprehensive) prep.

#### Top 10 Suggested Next Best Recommended Actions 🚀 (Prioritized for M1.3 + Safety; ref Phase 1 M1.2/M1.3 + matrix + safety policy)
1. 🚀 **Main + swarm**: Run `phase1-m1.3-329-variant-layout-guard` on pilot 3 + full 12; produce pass/fail + fixtures in Exports/.
2. 📋 Enhance guard to consume phase1-m1.2-@304-analysis-initial.json (plaus/magic deltas as soft signals).
3. 📊 Refresh post50-mesh329-source-binding-compare + family-proof with matrix 12 + guard results.
4. 🔍 Quick Python: script to generate negative fixtures from matrix copy + assert FAILs.
5. ✅ Drift + safety review: Re-grep "329" + "M1.3" + matrix + "candidate-only" + "Phase 1 M1.3" in all new guard outputs.
6. 🧪 Optional: Run guard with --matrix-override (synthetic bad row) to test fixture path.
7. 📝 Populate m1.3 handoff draft with actual guard tables + pass counts (per its first-steps).
8. 📈 Add M1.3 guard schema + checklist to docs/schemas/ + post50-promotion-readiness-status.
9. 🔄 If 12/12 pass on layout: note "sibling-binding + variant-attr-layout guard stable for 329 pilot" in blockers.
10. 🗂️ Post-M1.3: Update promotion checklists with new guard evidence; prep light M1.4 (305) per roadmap; keep high-reasoning.

This keeps momentum on the roadmap (Phase 1 M1.3 next after M1.2) while preserving all safety boundaries. Matrix is the durable reference for targets. (All per AGENTS.md + task-routing-safety-policy.md + project-roadmap Phase 1 M1.2/M1.3.)

**Human-readable summary of this prep (per AGENTS.md for major milestones)**: Reviewed M1.2 finalize state (handoff, coordination, current-phase, analysis/magic/final artifacts, 10/10+12/12 patterns from matrix + @304 quant) + existing pilot guard code in rift_workflow_guards.py (already asserts exact layout: attrSets delta 1/0, @304 pos c=75 on #34, shared @212 pos; pilot 3 IDs; matrix-driven + probe optional; writes phase1-m1.3-*-guard.*; refs this prep). Drafted/enhanced this prep.md in place modeled exactly on phase1-m1.2-prep.md (structure, sections, emojis/tables, first-steps 1-4 per task, candidate guard sketch pseudocode + note on pre-impl, quantify pass/fail/neg-fixtures/checklist, handoff struct, AGENTS close with summary/Top10/next, refs Phase 1 M1.2/M1.3 + matrix + safety policy). Validated: overlap with M1.2 artifacts, candidate-only, 329-scope only, python-only, no promotion, explicit roadmap refs, guard pre-exists so prep focuses run/validate/extend. Uncertain: exact 12/12 guard results (pilot code not yet executed per searches; will vary if matrix/probes drift); full negative fixture coverage. Next lane: execute first steps (review M1.2 blockers, run guard on matrix, draft M1.3 handoff), integrate per current-phase swarm notes. (All findings derived directly from reviewed files + code; no speculation.)

**M1.3 prep enhancement note (autonomous, per task)**: Existing prep was good skeleton but incomplete vs m1.2-prep style + explicit task reqs (no sketch, no full AGENTS human/Top10, first-steps not exactly 1-4). Overwrote in place with full modeled content + integrated prior text + guard reality + new M1.2 artifacts list. No core m1.2 handoff/pointer touched. Verification report cross-refs this. Ready for clean transition.

**Light update with guard results (post-proc candidate prototype, per current task)**: After initial prep, executed the specified candidate-only Python guard prototype (post-proc; used -c + temp script for self-contained run per "no new permanent .py beyond output"; strictly 329+matrix; run on all 12 IDs). Produced supporting `Exports/phase1-m1.3-sibling-binding-guard-candidate.json` (schema/v1 CandidateOnly Phase1 M1.3, PerID table with scores/reasons/signals/matrix34, Aggregates 12/12, GuardLogicPython snippet, Validation scope/candidate/python/high-reasoning, PrepStatus note, refs to matrix + M1.2 handoff + post50) + `.md` (full tables, pseudocode, AGENTS human-readable summary sections with what/why/validated/uncertain + emojis/tables/Top10/next, refs Phase1 M1.3 + M1.2 finalized handoff + matrix). Results: 12/12 pass `candidate_sibling_variant=True` (scores 9-11/11, threshold 8); 0 false positives in scope; edges noted (f2c347fe81a5e3b2 no-c2 but low-plaus/ratio qualifies; 066fa/91ea low-v/low-plaus still pass). PrepStatus in artifact notes this prep was absent at start of run (swarm timing). No drift, all pre-write validated. See also swarm's companion `Exports/phase1-m1.3-329-variant-layout-guard.*` (pilot in scripts/). This light note added to prep for traceability (supporting only; no main pointer/handoff edits).

<subagent_meta>id=phase1-m1.2-verifier-m1.3-prep-drafter, type=explore+general, tool_calls=~40, turns=1</subagent_meta>

**End of M1.3 prep.** (All per AGENTS.md rules: refs, emojis/tables, human summary, Top10, next, Phase 1 M1.2/M1.3, matrix, safety policy, candidate-only, python, redaction, supporting only.)