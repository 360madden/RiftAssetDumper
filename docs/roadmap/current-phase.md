# Current Active Phase & Milestone

**Last Updated**: 2026-06 (post Block 7 batch completion for M1.1; 12/12 pairs)

## Current Phase
**Phase 1: Position Source Family Proof & Role Classification**

## Current Milestone (within Phase 1)
M1.1 — Expand sample of 329-family mesh pairs (target 10+ groups). Systematically run mesh-probe on mesh#7 and #34 variants. Produce machine-readable attribute/role matrix.

**Status**: **COMPLETE** (finalized; Block 7 batch completed 2026-06). 
- ID Curator subagent (task 019e8655-c7c1-7851-b421-d23747fb4827): ranked 12-ID queue (see phase1-m1.1-curated-probe-queue.md).
- Block 34 Prober subagent (task 019e8655-c7c6-7d10-9735-aed099b85052): 8-ID #34 batch + structured table + all *-mesh34.json .
- Block 7 execution (focused subagent): exact `python scripts/rift_workflow.py mesh-probe --id <ID> --mesh-block 7 --skip-build` (7 priority + 0364 anchor); raw plain + *-mesh7.json naming ensured in Exports/ for all; key fields (attrSets=1, streams @212/220/296/304 roles/payloads/vecs/confs + extras) extracted + logged in coordination.md.
- Matrix Synthesizer subagent (task 019e8655-d929-7bc3-a10a-680221f8bbba) + refresh: schema + command + final artifacts (12 IDs covered, 12 paired comparisons, 24 rows; 12/12 confirmation of mesh#34 attrSets=0 + @304 position-float3-ror1-lead c=75; 12/12 #7 attrSets=1 + UV@304).
- Official M1.1 handoff: `docs/handoffs/draft-2026-06-m1.1-329-matrix.md` (full tables from latest matrix, subagent refs, artifacts, validation, candidate-only).
- Coordination + this file updated with accurate M1.1 complete + M1.2 pointer + batch details.
- Primary matrix: `Exports/mesh329-family-attribute-role-matrix.json` + .md + .csv (final refresh post #7 batch; see table for all priority vecs 77..38 etc.).

M1.1 exit criteria met per `docs/roadmap/project-roadmap.md` (10+ examples classified + matrix + handoff). All candidate-only. See handoff for quantified patterns, table, and traceability. Reference Phase 1 M1.1.

## Transition to M1.2
M1.2 prep complete (`docs/roadmap/phase1-m1.2-prep.md`). Target list = M1.1 matrix IDsCovered. Swarm of 3 new subagents launched for: attribute-extra-probe batch on top 8 #34, analysis/quant tables, initial M1.2 handoff draft. Reference matrix + this prep in all M1.2 work. Phase 1 M1.2 active.

**M1.1 Status**: COMPLETE (12/12 pairs in matrix, 12 IDs, handoff finalized, 12/12 pattern confirmation). See `docs/handoffs/draft-2026-06-m1.1-329-matrix.md` (finalized content) + `Exports/mesh329-family-attribute-role-matrix.*`.

**M1.2 Status**: Prep complete. Swarm of 3 new subagents launched for: attribute-extra-probe batch on top 8 #34 (completed: all errored "no attribute extra stream found at @304 on #34" — informative; no JSONs for extra304 on #34 as expected), analysis/quant tables (complete: produced `Exports/phase1-m1.2-@304-analysis-initial.json` + .md with per-ID tables for 8, aggregates avg vec ratio 0.405, all plaus low 8/8, common 022bc2 prefix 2/8, 7/8 c2 patterns, classif uint16=2/strided=6, candidate patterns low plaus despite pos role/mixed-endian/stride 12 viable/sharp diffs/no simple transform), initial M1.2 handoff draft (completed: created `docs/handoffs/draft-2026-06-m1.2-@304-extra-stream-classification.md`). Refreshed sibling-extra-pos, compare, stream-bodies (69da #34: 14 valid, top 456 etc.; f2c3 #34 similar; 07c7 #34 top 384/672), stream-endianness (69da #34: mixed-u16=12, big-u16-lead=2) run. Reference matrix + prep in all M1.2 work. Phase 1 M1.2 active. Swarm driving M1.2.

## Active Focus Rules (from roadmap)
- Stay strictly within meshSize=329 (and light 305 comparison). Do not open new unrelated leads.
- Every probe must produce JSON + markdown + handoff contribution.
- Use existing `rift_workflow.py` commands.
- Reference `docs/roadmap/project-roadmap.md` in all major handoffs.

## Entry Criteria Met
- Phase 0 complete (roadmap + baseline artifacts created and referenced).

## Progress (Autonomous)
- ID Curator completed: ranked 12-ID queue (see `docs/roadmap/phase1-m1.1-curated-probe-queue.md`).
- Probes: full 8-ID #34 batch (Block 34 Prober) + Block 7 batch completion for all top priority (69da... b576 + 0364 anchor) via exact rift_workflow mesh-probe --mesh-block 7 --skip-build + suffixed naming (see coordination.md + block7-batch1.md for extracts: consistent attrSets=1, specific roles/confs/payloads/vecs per ID).
- Matrix Synthesizer completed (task 019e8655-d929-7bc3-a10a-680221f8bbba) + post-batch refresh: schema + `mesh329-attribute-role-matrix` command + final artifacts (12 IDs, 12 pairs, patterns 12/12 quantified).
- Handoff finalized: `docs/handoffs/draft-2026-06-m1.1-329-matrix.md` (real data/tables from latest matrix MD/JSON, refs to subagents incl. this Block7 execution, ID Curator, Block34 Prober, updated blockers/artifacts/validation).
- Coordination.md , block7-batch1.md and this file updated with M1.1 complete status + accurate 12/12. M1.1 exit criteria satisfied. Pattern 12/12 confirmed. Ready for M1.2.

## Next Concrete Actions (Main Agent + Swarm)
- M1.1 complete (see finalized handoff `docs/handoffs/draft-2026-06-m1.1-329-matrix.md` and updated coordination.md + current numbers 12/12).
- Transition focus to M1.2 per `docs/roadmap/project-roadmap.md`: deep @304 classification using M1.1 matrix as target list.
- Update living pointer and coordination when M1.2 active.
- Optional (low priority): probe remaining lower queue #7 (e.g. c5a1982e92e15b7b) then re-matrix if more pairs desired before M1.2.

See `docs/roadmap/project-roadmap.md` for full phase details and anti-drift rules. Reference Phase 1 M1.1 handoff for current evidence baseline.