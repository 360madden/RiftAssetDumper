# Phase 1 M1.2 Prep Note — Deep Classification of @304 Extra Stream on mesh#34 Variants

**Date**: 2026-06
**Prepared by**: Forward-planning subagent (read-only exploration)
**Context**: Post-M1.1 transition prep. M1.1 substantially complete (matrix + handoff mature per `docs/roadmap/phase1-m1.1-coordination.md`, `current-phase.md`, and `draft-2026-06-m1.1-329-matrix.md` in handoffs/). Per `docs/roadmap/project-roadmap.md` Phase 1 (M1.1 → M1.2: "Deep classification of the @304 extra stream on mesh#34 variants (payload analysis, vector comparison, magic patterns, role scoring refinement)").
**Anti-drift**: Strictly meshSize=329 family only (light 305 comparison disallowed unless explicitly in later milestone). Everything **candidate-only**. No parser/export promotion. Use existing `python scripts/rift_workflow.py` commands. Every probe → JSON + MD + handoff contribution. Reference this prep + matrix + roadmap in all M1.2 work. High-reasoning lane per `docs/task-routing-safety-policy.md`.

## Exact Target List

Reference the current matrix as the **exact target list**: `Exports/mesh329-family-attribute-role-matrix.json` (and .md/.csv).

- IDsCovered (10 total): 0364ea142bc00ce7, 04de901531a091ab, 066fa520a8ce62e3, 07c733b4eee3ed2e, 4eb7745610adf8c7, 69da9507d49c42ff, 83df87e22bff4a94, 91ead5caf689a8a5, c5a1982e92e15b7b, f2c347fe81a5e3b2.
- All have #34 data showing the extra @304 position-like stream (attrSets=0, role=position-float3-ror1-lead c=75 on @304/#57, shared @212 primary, @296 u32 body).
- 3 paired for contrast (UV@304 on #7 vs. extra pos@304 on #34): 0364ea142bc00ce7, 04de901531a091ab, 066fa520a8ce62e3.
- See also curated queue (`docs/roadmap/phase1-m1.1-curated-probe-queue.md`) for overlap/rationale (top-8 wave executed on block 34; matrix is synthesized current view).

## Top 5-8 Representative IDs (from Matrix) Showing Extra @304 on #34

Focus M1.2 deep dives here first (prioritized by matrix vector coverage + paired examples + @304 vec diversity; all directly from matrix #34 rows):

1. 69da9507d49c42ff (#34 only in matrix; primary 77v / @304 38v pos; highest coverage, rich probe data)
2. f2c347fe81a5e3b2 (#34; 64v / 25v pos)
3. 07c733b4eee3ed2e (#34; 56v / 21v pos)
4. 83df87e22bff4a94 (#34; 52v / 18v pos)
5. 0364ea142bc00ce7 (paired anchor: #7: 48v UV@304 / #34: 48v/20v pos@304)
6. 4eb7745610adf8c7 (#34; 46v / 11v pos)
7. c5a1982e92e15b7b (#34; 45v / 16v pos)
8. 04de901531a091ab (paired: #7: 37v UV@304 / #34: 37v/23v pos@304)

(Expand to remaining matrix IDs like 066fa520a8ce62e3 (paired low-v) and 91ead5caf689a8a5 as time allows.)

## Focused Approach for M1.2

- **Probes/commands** (existing; run with --skip-build):
  - `mesh-probe --id <ID> --mesh-block 34` (baseline/refresh @304 details).
  - `attribute-extra-probe --id <ID> --mesh-block 34 --extra-offset 304` (core for deep dive on the extra stream; yields samples, histograms, index compat, position/normal vertex samples from *that* stream, body stats, role fit beyond mesh-probe).
  - Leverage/extend `position-source-sibling-extra-position-report` (and the orchestration in workflow) + `post50-mesh329-source-binding-compare` (expand hardcoded 3-pair logic to matrix IDs; feed matrix rows).
  - Supporting: `stream-bodies`, `stream-endianness` (on relevant streams/IDs), `decode-geometry` (with --experimental-position-source), post50-validation-suite/status for blocker hygiene.
  - Python post-processing on Exports/ probe JSONs for cross-ID analysis.
- **What to quantify** (extend existing report logic like extra-to-primary ratios, mod-12 remainders, attr deltas):
  - Vector ratios (extra@304 vecs / primary@212 vecs) + payload diffs (extra vs. primary/normal; %12 for float3 stride).
  - Endian (EndianStats: little/big prefixes, classification "mixed-u16-body", low-value ratios; compare to primary pos streams).
  - Float plausibility + body classification (PlausibleFloat32Count / Finite vs. UInt16Count, "uint16-compatible-body" vs. position role, stride candidates incl. 12 vs. others; conflicts in RoleStats evidence).
  - Magic/common patterns (shared first-N bytes/hex prefixes across @304 BodyFirst* from 5-8 IDs; repeated patterns, non-zero density).
  - Sample comparison (first 4-8 float3 vectors from extra vs. primary position samples; ranges, correlation, subset/transformed?, vs. #7 UV samples).
  - Consistency across targets (e.g., @304 always c=75 position despite body stats? @296 u32 always present? Normal block variance?).
  - Other: IndexStats on the "pos" stream (triangles/strips despite role?), AttrExtraStreamCount, full probe path cross-refs.
  - Output: New/expanded tables (e.g., extended pair summaries or 329-@304-classification matrix) with aggregates (like existing PatternQuantification).
- **Handoff structure**:
  - Artifacts: Expanded classification report (JSON+MD, e.g., refreshed extra-pos report or new mesh329-@304-*-classification.*), raw attribute-extra + probe outputs, quant tables.
  - Dedicated M1.2 handoff in `docs/handoffs/` (short, like M1.1 draft: objective, IDs from matrix, findings/quant tables, updated blockers, artifacts list, validation, refs to matrix/roadmap/Phase 1 M1.2 + M1.1 parents).
  - Update `docs/roadmap/current-phase.md` (advance from M1.1; point to M1.3 or note M1.2 complete).
  - Minor: Refresh matrix if new #7 probes added; contribute to post50 reports if applicable.
  - Validation: GeneratedOutputGuard, schema (extend if new report), candidate-only review, explicit "Phase 1 M1.2 per roadmap" + matrix ref, no promotion.

## First Steps

1. Review latest matrix + 1-2 rich probe JSONs (e.g., 69da #34 + a paired) for @304 body samples/stats.
2. Run attribute-extra-probe batch on the 8 #34 targets (parallel where possible; --skip-build).
3. Re-run/extend sibling-extra-pos + compare reports using matrix IDs (or Python post-process).
4. Quantify + pattern search (cross-ID first-bytes + ratios); produce classification artifact.
5. Draft M1.2 handoff + update pointers; main agent reviews before M1.1 exit.

**Validation gates** (repeat per run): GeneratedOutputGuard, candidate-only language, drift check (329 + matrix targets only), Phase 1 refs, schema if new reports.
**References**: `docs/roadmap/project-roadmap.md` (Phase 1 M1.2), `current-phase.md`, matrix artifacts, M1.1 coordination/handoffs (e.g., role-analysis, draft matrix), curated queue, `scripts/rift_workflow.py` + `rift_workflow_reports.py` (probe/report logic).
**Status**: Prep complete. Ready for main agent post-M1.1.

```

### Optional: Practical Next Steps / Improvement Ideas (Post-Prep / During M1.2)
- Keep pace aggressive but gate every output (matrix-ref + candidate-only + roadmap phase explicit).
- Table-driven: After first 3-4 attribute-extra runs, synthesize a mini cross-ID table before full batch (prevents drift).
- Reuse/extend existing report fns (e.g., add matrix ID list param) rather than new one-off scripts.
- For magic search: Start with simple Python set intersection on BodyFirst16 hex from the 8 probes (low effort, high signal).
- Validate samples visually in MD (e.g., side-by-side primary vs. extra float3 prefixes).
- After M1.2 quant, feed directly into M1.3 guard ideas (sibling source-binding + variant attr layout).

#### Top 10 Suggested Next Best Recommended Actions 🚀 (Prioritized for Smooth M1.1→M1.2 Transition + Safety)
1. 🚀 **Main agent**: Write the prep note content above to `docs/roadmap/phase1-m1.2-prep.md`; update `current-phase.md` with M1.2 pointer + "M1.1 complete, matrix delivered".
2. 📋 Run attribute-extra-probe batch on the exact 8 IDs above (#34, extra-offset 304) + capture in a temp MD summary.
3. 📊 Extend `position-source-sibling-extra-position-report` logic (or Python) to consume the full matrix IDsCovered + refresh compare report.
4. 🔍 Quick Python snippet (on existing probe JSONs) to tabulate @304 BodyFirst16 across the 8 + shared prefixes (magic candidate).
5. 📈 Produce first-pass quant table (ratios + plausible-float + endian class + sample diffs) in Exports/ as M1.2 seed artifact.
6. ✅ Drift + safety review: Re-grep for "329" + "M1.2" + matrix filename in all new outputs before handoff.
7. 🧪 Optional: Run decode-geometry --experimental on 1-2 high-v #34 (e.g., 69da) to observe @304-as-pos effects (candidate-only).
8. 📝 Draft skeleton M1.2 handoff (copy M1.1 draft structure) with placeholders for the 8 IDs + quant sections.
9. 🔄 If pairs can expand cheaply: Run missing #7 mesh-probes for 1-2 more matrix IDs (e.g., to grow paired beyond 3) before full M1.2.
10. 🗂️ Post-M1.2: Update promotion checklists / blockers with new @304 classification evidence; prepare M1.3 guard sketch.

This keeps momentum on the roadmap (Phase 1 M1.2 next) while preserving all safety boundaries. Matrix is the durable reference for targets. Ready for main lane handoff/execution. (All findings derived directly from reviewed files; no speculation.) 

**Human-readable summary of this prep (per AGENTS.md for major milestones)**: Reviewed M1.1 matrix (10 IDs/3 pairs from Exports/, exact target) + queue; confirmed repeatable @304 extra pos on all #34 (with body stats anomalies like uint16-compat despite c=75 role). Proposed M1.2 uses attribute-extra-probe + extended reports for payload/ratios/magic/endian/samples quant on top 8 reps. Prep note drafted in response for file creation. Validated: overlap, candidate-only, 329-scope, command reuse. Uncertain: exact new probe results (will vary slightly); whether @304 resolves to "true" secondary pos or packed/index data (that's M1.2's job). Next lane: main agent executes first steps.

**M1.2 batch execution update (autonomous, post-prep)**: Attribute-extra-probe batch on the exact 8 #34 targets from the prep/matrix completed via swarm (all errored "no attribute extra stream was found at mesh payload offset @304 on NiMesh #34. No attribute extra streams were found for this mesh." — with JSON outputs). This is key data: the @304 "position" on #34 is not structured as a recognized "attribute extra" (consistent with attrSets=0 on #34 from mesh-probe). Refreshed sibling-extra-pos and compare also run (shows extra on the 3 anchors). Analysis subagent ingesting for quant tables. Swarm driving M1.2. Additional supporting (stream-bodies for 69da #34 showing 14 valid bodies, top payloads incl. 456 (@304), signatures, etc.; stream-endianness for 69da #34: mixed-u16-body=12, big-endian-u16-lead=2; stream-bodies for f2c3 #34; for 07c7 #34). M1.2 handoff drafter running (66+ calls).

<subagent_meta>id=019e86d0-5664-7cc2-b3e5-4b4bd853863b, type=explore, tool_calls=47, turns=1, duration_ms=276708</subagent_meta>

<subagent_result>
subagent_id: 019e86d0-5664-7cc2-b3e5-4b4bd853863b
subagent_type: explore
To continue this subagent's conversation, use resume_from="019e86d0-5664-7cc2-b3e5-4b4bd853863b".
</subagent_result>
