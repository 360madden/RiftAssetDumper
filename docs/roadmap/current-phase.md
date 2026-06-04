# Current Active Phase & Milestone

**Last Updated**: 2026-06 (Phase 5 ACTIVE — M5.1 COMPLETE: descriptor on pairing records; M5.2 COMPLETE: confidence adjustment; M5.3 COMPLETE: pre-filter; M5.4 planning)

## Current Phase
**Phase 5: Descriptor-Guided Parser**

## Phase 2 Status: **COMPLETE** ✅ (June 2026)

Phase 2 (NiDataStream Descriptor & Binding Proof System) completed with all 4 milestones delivered:
- **M2.1**: NiDataStream descriptor mapping — per-block embedded (4 bytes at offset 24), 5 patterns, `37 04 03 00` = ror1-float
- **M2.2**: Binding proofs — 329: 12/12×6; 305: 4 bindings; source-binding reuse confirmed
- **M2.3**: Role↔descriptor↔binding integration — unified 3-way mapping, 4 confirmed, 4 priority gaps
- **M2.4**: Promotion gate evaluation — 6 gates assessed, 3 strengthened, 1 reclassified, 2 unchanged, 0 cleared

See `docs/handoffs/2026-06-m2.5-phase2-exit-consolidation.md` for the full capstone handoff.

## Phase 1 Status: **COMPLETE** ✅ (June 2026)

Phase 1 (Position Source Family Proof & Role Classification) completed with all 5 milestones delivered:
- **M1.1**: 329 family attribute & role matrix (12/12 paired, machine-readable)
- **M1.2**: @304 extra stream deep classification (10/10 quantified, 3 analysis waves)
- **M1.3**: Sibling source-binding + variant attribute layout guards (12/12 PASS)
- **M1.4**: 305-family light comparison (15-feature structural validation)
- **M1.5**: Comprehensive Phase 1 exit handoff consolidating M1.1-M1.4 into unified family proof documentation

See `docs/handoffs/2026-06-m1.5-phase1-exit-consolidation.md` for the full capstone handoff.

## Milestone Status (Phase 1)

| Milestone | Status | Primary artifacts |
|---|---|---|
| **M1.1** | **COMPLETE** | `docs/handoffs/draft-2026-06-m1.1-329-matrix.md`; `Exports/mesh329-family-attribute-role-matrix.*` (12 IDs, 12/12 paired patterns) |
| **M1.2** | **COMPLETE** | `docs/handoffs/draft-2026-06-m1.2-@304-extra-stream-classification.md`; `Exports/phase1-m1.2-@304-analysis-initial.json` + `.md`; full N=10 `phase1-m1.2-@304-analysis-full.*` (subagent completed) |
| **M1.3** | **COMPLETE** | `docs/handoffs/2026-06-m1.3-sibling-source-binding-guard.md`; `Exports/phase1-m1.3-329-variant-layout-guard.*` (3/3 PASS pilot); `Exports/phase1-m1.3-sibling-binding-guard-candidate.*` (12/12 PASS prototype); `Exports/post50-mesh329-*` refreshed; validation suite 9/9 PASS |
| **M1.4** | **COMPLETE** | `docs/handoffs/2026-06-m1.4-305-family-comparison.md`; `docs/roadmap/phase1-m1.4-prep.md`; 15-feature structural comparison table (parallels + divergences); reused existing sibling report + probe JSONs; CI green |
| **M1.5** | **COMPLETE** | Prep: `docs/roadmap/phase1-m1.5-prep.md`; handoff: `docs/handoffs/2026-06-m1.5-phase1-exit-consolidation.md` (6-part comprehensive consolidation: 329 evidence chain, 305 cross-validation, unified cross-family tables, blocker matrix, promotion readiness, Phase 2 assessment); post50 reports refreshed (validation suite 9/9 PASS, family-proof 23/46/23, source-binding compare 3/3); post50 checklists updated; CI green |

## Phase 4: Descriptor-Aware Parser (planning)

| Milestone | Status | Primary artifacts |
|---|---|---|
| **M4.1** | **COMPLETE** | Byte-3 ≠ 0x00 integrity check in `AnalyzeNifDataStreamLayout`; verified at scale (0/375 warnings); 19/19 tests |
| **M4.2** | **COMPLETE** | Byte-0 fallback classification (`ClassifyNifDescriptorByByte0`); 5 family labels; verified at scale (16/16 classified, 0 nulls); 23/23 tests |
| **M4.3** | **COMPLETE** | `DescriptorClassificationGroups` distribution in `NifStreamHeaderInventoryReport` JSON; aggregated across all header group samples; 23/23 tests |
| **M4.4** | **COMPLETE** | Console descriptor classification summary in `inventory-nif-stream-headers` output; 23/23 tests |
| **M4.5** | **COMPLETE** | Descriptor-role cross-check in `probe-nif-mesh`: warns on float/u16 descriptor-role mismatches; 29/29 tests |
| **M4.6** | **COMPLETE** | Descriptor classification in `probe-nif-stream-body` console output; 29/29 tests |
| **M5.3** | **COMPLETE** | Descriptor-based position stream pre-filter in decode-nif-geometry; 39/39 tests |
| **M5.2** | **COMPLETE** | Descriptor-guided pairing confidence adjustment (AdjustConfidenceByDescriptor); 39/39 tests |
| **M5.1** | **COMPLETE** | Descriptor fields on  and ; pairing console output; 29/29 tests |
| **M4.x** | **COMPLETE** | Exit handoff: `docs/handoffs/2026-06-m4.6-phase4-exit-consolidation.md` |

## Phase 3: Parser/Export Implementation (Descriptor Propagation)

| Milestone | Status | Primary artifacts |
|---|---|---|
| **M3.1** | **COMPLETE** | Decision record + core implementation: `NifDataStreamLayout.DescriptorBytes`, `ClassifyNifDescriptor()`, `NifMeshBoundStreamSummary` fields; 5 xUnit tests; live-verified on mesh#7/#34 |
| **M3.2** | **COMPLETE** | `NifStreamHeaderSample` + `inventory-nif-stream-headers` descriptor propagation; verified: 5 patterns across 16 samples |
| **M3.3** | **COVERED** | `NifMeshBindingStreamSample` wraps `NifMeshBoundStreamSummary` — auto-inherits descriptor fields from M3.1 |
| **M3.4** | **COMPLETE** | `NifStreamBodySample` + `inventory-nif-stream-bodies` descriptor propagation |
| **M3.5** | **COMPLETE** | `NifStreamBodyProbe` + `probe-nif-stream-body` descriptor propagation |
| **M3.x** | **COMPLETE** | Exit handoff: `docs/handoffs/2026-06-m3.x-phase3-descriptor-propagation.md` |

## Phase 2: NiDataStream Descriptor & Binding Proof System

| Milestone | Status | Primary artifacts |
|---|---|---|
| **M2.1** | **COMPLETE** | Prep: `docs/roadmap/phase2-m2.1-prep.md`; handoff: `docs/handoffs/draft-2026-06-m2.1-nidatastream-descriptor-mapping.md` |
| **M2.2** | **COMPLETE** | Prep: `docs/roadmap/phase2-m2.2-prep.md`; handoff: `docs/handoffs/draft-2026-06-m2.2-binding-proofs.md` |
| **M2.3** | **COMPLETE** | Prep: `docs/roadmap/phase2-m2.3-prep.md`; handoff: `docs/handoffs/draft-2026-06-m2.3-role-descriptor-integration.md` |
| **M2.4** | **COMPLETE** | Prep: `docs/roadmap/phase2-m2.4-prep.md`; handoff: `docs/handoffs/draft-2026-06-m2.4-promotion-gate-evaluation.md` |
| **M2.5** | **COMPLETE** | Consolidation: `docs/handoffs/2026-06-m2.5-phase2-exit-consolidation.md` (unified Phase 2 exit handoff; all M2.1-M2.4 evidence consolidated; Phase 3 entry assessment) |

## Active Focus Rules (from roadmap — Phase 4)
- Descriptor data layer is complete — Phase 4 should consume descriptor fields for parser behavioral changes.
- All parser behavioral changes must be narrow, tested, and guarded by proof-gate checks.
- No parser/export promotion without completed decision record (per `docs/nidatastream-parser-export-promotion-decision-template.md`).
- Both `FieldOrderPromoted` and `ParserExportPromotionAllowed` remain false until explicit gate clearance.
- Every parser behavioral change → decision record + targeted tests + CI green.
- Reference `docs/roadmap/project-roadmap.md` Phase 4 in all M4.x handoffs.

## Current Milestone (within Phase 3)
**M5.4** — Usage/Access x descriptor correlation (planning): add warning when byte-3 ≠ 0x00 in `AnalyzeNifDataStreamLayout`. Smallest possible behavioral change (~5 lines), uses best-proven Phase 2 evidence (byte-3=0x00 universal in 184/184 sampled blocks).

**Entry from Phase 2**: Phase 2 complete with mature descriptor & binding proof system: per-block-embedded (4 bytes at offset 24), 5 patterns, `37 04 03 00` = ror1-float, binding reuse proven cross-family, 3-way integrated mapping, 6 promotion gates evaluated (0 cleared), 7 core blockers characterized. Both promotion flags intentionally held false. See `docs/handoffs/2026-06-m2.5-phase2-exit-consolidation.md`.

**Phase 2 Exit Handoff**: `docs/handoffs/2026-06-m2.5-phase2-exit-consolidation.md` — comprehensive 7-part capstone; unified descriptor & binding tables; per-gate evaluation; blocker matrix; Phase 3 entry assessment.

**Phase 3 Entry**: Phase 2 complete with mature descriptor & binding proof system: per-block-embedded (4 bytes at offset 24), 5 patterns, `37 04 03 00` = ror1-float, binding reuse proven cross-family, 3-way integrated mapping, 6 promotion gates evaluated (0 cleared), 7 core blockers characterized. Both promotion flags intentionally held false.

**M2.1 Evidence Gathered**: NiDataStream layout report refreshed (184/184 blocks valid, 5 descriptor byte patterns, byte-3 always 0x00). Descriptor-sample-compare run (6/6 byte-counter, 7/7 byte-order, 10 blocking items documented). Base-model review reveals all static bytes zero at Ghidra addresses — the descriptor table is NOT statically allocated. Critical finding: descriptors are **per-block embedded** (4 bytes at offset 24 in each NiDataStream block header). `37 04 03 00` spans position (#28), normal (#29), AND UV (#36) blocks — a generic ror1-float-stream descriptor, not role-specific. Role differentiation comes from Usage/Access fields. M2.2 prep created for binding proofs at scale.

**M2.2 Progress**: Handoff created (`docs/handoffs/draft-2026-06-m2.2-binding-proofs.md`) and **COMPLETE**: 329 binding proofs (12/12 IDs, 6 bindings per ID, source-binding reuse pattern), 305 binding proofs (4 bindings, same reuse pattern), cross-family 11-feature comparison, blocker status. Key findings: source-binding reuse confirmed; all ror1-float streams carry descriptor `37 04 03 00`; secondary streams diverge between siblings.

**M2.3 Progress**: Prep + handoff created and **COMPLETE** (corrected per code review; updated June 2026 with `36 04 02 00` gap resolved). Unified 3-way mapping confirms `37 04 03 00` as role-agnostic (spans position/normal/UV). `36 04 02 00` resolved: Usage=1, Access=19 matches `37 04 03 00` → float-vertex-data category; appears in clustered groups of 3; byte-1=0x04 = float32 element width. Three remaining gaps: `15 02 01 00` (appears at blocks 23/26/35 — NOT at #57), `10`/`3c` patterns, blocks #55/#57 descriptors. Cross-family 305 confirms same pattern. Validation Performed section added per convention.

**M2.4 Progress**: Handoff created (`docs/handoffs/draft-2026-06-m2.4-promotion-gate-evaluation.md`) and **COMPLETE**. 7 parts: refreshed live promotion status (6 blockers, both flags false), Phase 2 evidence summary, per-gate evaluation for all 6 gates, evaluation summary table, 7 core blockers documented, Phase 2 exit criteria assessment. Key finding: 3 strengthened, 1 reclassified, 2 unchanged, 0 cleared. Per-block-embedded finding drives descriptor-table-sample gate reclassification. Both promotion flags must remain false.

**M2.5 Progress**: Consolidation handoff created (`docs/handoffs/2026-06-m2.5-phase2-exit-consolidation.md`). **Phase 2 EXITED.** All M2.1-M2.4 evidence unified into 7-part capstone document. Modeled on M1.5 structure. Phase 3 entry assessment complete.

## Next Concrete Actions (Phase 5 M5.4)
1. Extend cross-check infrastructure to validate descriptor against Usage/Access fields
2. Add targeted tests
3. Build, test, format, code-review

## Entry Criteria Met
- Phase 0 complete.
- M1.1 exit: 12/12 matrix + handoff.
- M1.2 exit: @304 classification batch + analysis-initial + full N=10; finalized M1.2 handoff; safety verification CLEAN/PASS.
- M1.3 exit: guard pilots 3/3 + prototype 12/12 PASS; all reports refreshed; validation suite 9/9 PASS; handoff finalized.
- M1.4 exit: light 305-family structural comparison handoff + prep created; 15-feature comparison table; cross-family attrSets=1/0 pattern confirmed; zero new probes; CI green.
- M1.5 exit: comprehensive Phase 1 exit handoff consolidated (6 parts: 329 chain, 305 cross-validation, unified cross-family tables, blocker matrix, promotion readiness, Phase 2 assessment); post50 reports refreshed; promotion checklists updated; handoff finalized; CI green.
- **Phase 1 COMPLETE**: All 5 milestones delivered; all exit criteria met (≥10 329 examples: 12/12, guards passing: 12/12, candidate-only vs promotion-blocking distinctions documented, comprehensive handoff committed).
- **Phase 2 EXITED**: M2.1-M2.5 all delivered. Per-block-embedded descriptors. 5 patterns. `37 04 03 00` = ror1-float. Binding reuse proven. 3-way integration done. 6 gates evaluated (0 cleared). Both flags false. See `docs/handoffs/2026-06-m2.5-phase2-exit-consolidation.md`.
- **Phase 3 entry**: Phase 2 exit complete; descriptor facts established (per-block embedded, 4-byte structure, byte-3=0x00, 5 patterns, 2 with category); binding architecture proven (329: 12/12×6; 305: 4 bindings); gate landscape mapped (6 gates evaluated, 0 cleared, 7 core blockers characterized); both promotion flags intentionally held false.
- Phase 3 M3.1 decision: candidate-only descriptor read + classification; no promotion flags changed.
- **Phase 3 entry criteria met**: Phase 2 exit complete ✅, descriptor structural facts established ✅, binding architecture proven ✅, promotion gate landscape mapped ✅, both promotion flags intentionally held ✅. See `docs/handoffs/2026-06-m2.5-phase2-exit-consolidation.md` Part 7.

## Progress Snapshot (Autonomous)
- **Phase 1 (COMPLETE)**: 5 milestones delivered — M1.1 (329 matrix 12/12), M1.2 (@304 classification 10/10), M1.3 (sibling-binding guards 12/12 PASS), M1.4 (305 comparison 15-feature), M1.5 (comprehensive Phase 1 exit handoff). All reports refreshed; validation suite 9/9; CI green throughout. See `docs/handoffs/2026-06-m1.5-phase1-exit-consolidation.md`.
- **Phase 2 (COMPLETE)**: All 5 milestones delivered — M2.1 (descriptor mapping: per-block-embedded, 5 patterns, `37 04 03 00`=ror1-float), M2.2 (binding proofs: 329: 12/12×6; 305: 4 bindings), M2.3 (unified 3-way integration, 4 confirmed, 4 gaps), M2.4 (promotion gate evaluation: 3 strengthened, 1 reclassified, 2 unchanged, 0 cleared), M2.5 (consolidation handoff). Both promotion flags false. Phase 2 EXITED. See `docs/handoffs/2026-06-m2.5-phase2-exit-consolidation.md`.
- **Phase 3 (EXITED)**: M3.1-M3.5 complete — descriptor propagation across all 6 NiDataStream record types. See `docs/handoffs/2026-06-m3.x-phase3-descriptor-propagation.md`.
- **Phase 4 (ACTIVE)**: M4.1 COMPLETE (byte-3 integrity), M4.2 COMPLETE (byte-0 fallback), M4.3 COMPLETE (JSON distribution), M4.4 COMPLETE (console summary), M4.5 COMPLETE (descriptor-role cross-check), M4.6 COMPLETE (stream-body probe visibility), M5.1 COMPLETE (descriptor on pairing records), M5.2 COMPLETE (confidence adjustment), M5.3 COMPLETE (pre-filter). 39/39 tests. M5.4 planning. — scope first parser behavioral change consuming descriptor fields. (`docs/handoffs/2026-06-m3.1-parser-descriptor-read-decision.md`). Formal per-template evaluation: 6 promotion gates still blocked; both flags false. Scope: descriptor read + classification only — no behavioral change. Decision: candidate-only. Live status refreshed. Test plan: 5 targeted xUnit cases. Next: implement the change in `Program.cs`.