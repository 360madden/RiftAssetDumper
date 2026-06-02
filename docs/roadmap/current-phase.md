# Current Active Phase & Milestone

**Last Updated**: 2026-06 (M1.2 complete; M1.3 active)

## Current Phase
**Phase 1: Position Source Family Proof & Role Classification**

## Milestone Status (Phase 1)

| Milestone | Status | Primary artifacts |
|---|---|---|
| **M1.1** | **COMPLETE** | `docs/handoffs/draft-2026-06-m1.1-329-matrix.md`; `Exports/mesh329-family-attribute-role-matrix.*` (12 IDs, 12/12 paired patterns) |
| **M1.2** | **COMPLETE** | `docs/handoffs/draft-2026-06-m1.2-@304-extra-stream-classification.md`; `Exports/phase1-m1.2-@304-analysis-initial.json` + `.md` |
| **M1.3** | **ACTIVE** | Prep: `docs/roadmap/phase1-m1.3-prep.md`; initial handoff: `docs/handoffs/draft-2026-06-m1.3-sibling-source-binding-guard.md`; guard swarm active (prototype + updater); prior coord: `docs/roadmap/phase1-m1.2-coordination.md` |

## Current Milestone (within Phase 1)
**M1.3** — Develop or extend proof guard(s) for **sibling source-binding + variant attribute layout** (per `docs/roadmap/project-roadmap.md` Phase 1 M1.3).

**Entry from M1.2**: mesh#34 `attributeSets=0` + @304 scored as `position-float3-ror1-lead` (c=75) but **not** an attribute-extra stream on the attr-probe path; mesh#7 siblings keep `attributeSets=1` with UV@304. Scoped **10/10** (matrix **12/12**) repeat the layout split. See M1.2 handoff + analysis-initial for ratios, magic (`022bc2` / `c2`), body class (uint16 vs strided), and low plausibility notes.

**M1.3 Handoff (initial draft created)**: `docs/handoffs/draft-2026-06-m1.3-sibling-source-binding-guard.md` (modeled on M1.2; incorporates prep, M1.2 evidence, existing sibling-lead-guard baseline, candidate guard sketch, pilot plan on 3 anchors + expand to 12, blockers, validation, AGENTS summary + top10). Swarm active for guard prototype (task 019e86ec-b6b8-7d90-bffd-b51939dffba0) + related.

## Next Concrete Actions (M1.3)
1. Read `docs/roadmap/phase1-m1.3-prep.md` + M1.2 handoff findings; use matrix `IDsCovered` as guard target list (329-family only).
2. Refresh `position-source-sibling-extra-position-report` then run `post50-mesh329-source-binding-compare` (schema-lock @212/#28 vs mesh#34 @304/#57 sibling evidence).
3. Run `post50-mesh329-family-proof` + `post50-validation-suite` for hygiene before guard changes.
4. Extend or add **Python-only** proof guard assertions (in `scripts/rift_workflow_guards.py` via existing `rift_workflow.py` guard commands) encoding: (a) sibling binding consistency across mesh blocks, (b) variant attribute layout (`attributeSets` 1 on #7 vs 0 on #34, @304 role inversion UV vs pos).
5. Pilot guards on 3 paired anchors (0364, 04de, 066fa) then expand to scoped 10 / matrix 12.
6. Produce M1.3 coordination note (phase1-m1.3-coordination.md) + integrate swarm guard results; handoff draft created (draft-2026-06-m1.3-sibling-source-binding-guard.md).
7. Update living pointers when M1.3 exit criteria met (do not edit handoff files in parallel agent lane; reference created handoff).

## Active Focus Rules (from roadmap)
- Stay strictly within meshSize=329 (and light 305 comparison only in later M1.4). Do not open new unrelated leads.
- Every probe/guard run must contribute JSON + markdown + handoff material; use existing `python scripts/rift_workflow.py` commands.
- Reference `docs/roadmap/project-roadmap.md` in all major handoffs.
- **Candidate-only** throughout; no parser/export promotion; no Exports content committed to git.

## Entry Criteria Met
- Phase 0 complete.
- M1.1 exit: 12/12 matrix + handoff.
- M1.2 exit: @304 classification batch + analysis-initial + finalized M1.2 handoff.

## Progress Snapshot (Autonomous)
- M1.1: ID Curator queue, Block 34 + Block 7 probes, matrix synthesizer, finalized handoff — see `docs/roadmap/phase1-m1.1-coordination.md`.
- M1.2: attribute-extra batch (8/8 informative negatives), analysis-initial quant, supporting sibling/stream probes — see `docs/roadmap/phase1-m1.2-coordination.md`.

See `docs/roadmap/project-roadmap.md` for full phase details and anti-drift rules.