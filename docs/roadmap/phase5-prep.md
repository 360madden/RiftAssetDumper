# Phase 5 Prep Note — Descriptor-Guided Parser

**Date**: 2026-06
**Type**: Phase Prep — Phase 5 Entry
**Status**: **ACTIVE** — M5.4 COMPLETE, M5.5 planning
**Parent(s)**: `docs/roadmap/project-roadmap.md` (Phase 5), `docs/handoffs/2026-06-m4.6-phase4-exit-consolidation.md` (Phase 4 exit)
**Entry**: Phase 4 EXITED — descriptor-aware parser foundation complete (M4.1-M4.6); 6 narrow changes delivered; descriptor data now drives warnings and console/JSON output

**Roadmap Reference**: This prep supports **Phase 5: Descriptor-Guided Parser**. Per the Phase 4 exit handoff: "Consume descriptor data for routing hints, role validation, and stream selection — while maintaining the candidate-only safety boundary and promotion gate discipline."

**Anti-drift**: Phase 5 extends Phase 4's observational consumption into guided routing. No promotion flags change until explicit gate clearance. Both `FieldOrderPromoted` and `ParserExportPromotionAllowed` must remain false.

## Objective

Use Phase 4's proven descriptor data layer (integrity checks, classification, visibility, cross-checks) to guide parser decisions — stream selection hints, role validation, and pairing confidence — without changing decode/export behavior.

## Phase 4 Foundation (ready for Phase 5)

| Finding | Phase 5 implication |
|---|---|
| Byte-3 = 0x00 universal (0/375 warnings) | Integrity check can be extended to other invariant bytes |
| Byte-0 classification achieves 100% coverage | Family labels available for every stream |
| Descriptor-role cross-check working (M4.5) | Pattern for descriptor-driven validation |
| All probe/inventory commands show descriptor data | Visibility confirmed across all commands |
| Descriptor fields on all 6 record types | Data available at every pipeline stage |
| Pairing records now carry descriptor fields (M5.1) | Pairing-level descriptor visibility established |

## Proposed Milestones

### M5.1 — Descriptor Classification on Pairing Records ✅

- Add `VertexDescriptorClassification` and `IndexDescriptorClassification` to `NifMeshProbePairing` and `NifMeshBindingPairingSample` records
- Propagate during pairing construction
- Show in probe-nif-mesh pairing console output

### M5.2 — Descriptor-Guided Pairing Confidence Adjustment

- [x] AdjustConfidenceByDescriptor() helper (+5 boost for float match, -10 dampen for mismatch)
- [x] Called in FindNifMeshProbePairings after compatibleVertexCount boost
- [x] 10 xUnit tests (39/39 pass); refactored with shared IsFloatRole/IsFloatDescriptor/IsU16Descriptor helpers
- [x] Candidate-only — does not change export behavior

### M5.3 — Descriptor-Based Stream Pre-Filter

- [x] DescriptorClassification on NifLinkedStreamPositionCandidate record
- [x] Propagated from stream summaries in both float32 and uint16 branches
- [x] IsFloatDescriptor() boost sorting before lead candidate selection
- [x] Console output shows descriptor on candidate listing
- [x] Behind `--experimental-position-source` gate; candidate-only

### M5.4 — Usage/Access × Descriptor Correlation (PLANNING)

- Extend M4.5 cross-check to validate descriptor against Usage/Access fields
- Add to CheckDescriptorRoleConsistency or create parallel checker

### M5.5 — Phase 5 Exit Consolidation (PLANNING)

- Comprehensive handoff documenting all M5.x milestones
- Phase 5 exit criteria assessment
- Phase 6 entry planning

## Commands

```bash
dotnet build RiftAssetDumper.slnx --nologo
dotnet test RiftAssetDumper.slnx --nologo
dotnet format RiftAssetDumper.slnx --verify-no-changes
ruff check scripts/ && mypy scripts/ --no-error-summary
```

## Deliverables (Phase 5 M5.1)

- [x] `docs/roadmap/phase5-prep.md` (this file)
- [x] `NifMeshProbePairing` record: `IndexDescriptorClassification` + `VertexDescriptorClassification` fields
- [x] `NifMeshBindingPairingSample` record: `IndexDescriptorClassification` + `VertexDescriptorClassification` fields
- [x] Pairing construction: descriptor propagation from stream summaries
- [x] Console output: descriptor on pairing detail line
- [x] Build, test, format, code-review (M5.1)
- [x] Build, test, format, code-review (M5.2)
- [ ] Updated current-phase.md

## Validation Gates

- [x] Build: 0 errors
- [x] Tests: 29/29 pass
- [x] `dotnet format --verify-no-changes` clean
- [x] ruff 0, mypy 0
- [x] `FieldOrderPromoted` still false
- [x] `ParserExportPromotionAllowed` still false
- [x] Generated-output guard clean

---

See `docs/roadmap/project-roadmap.md` (Phase 5), `docs/handoffs/2026-06-m4.6-phase4-exit-consolidation.md`.
