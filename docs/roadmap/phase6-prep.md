# Phase 6 Prep Note — Descriptor-Validated Export

**Date**: 2026-06
**Type**: Phase Prep — Phase 6 Entry
**Status**: **ACTIVE** — M6.1 COMPLETE, M6.2 COMPLETE, M6.3 planning
**Parent(s)**: `docs/roadmap/project-roadmap.md`, `docs/handoffs/2026-06-m5.5-phase5-exit-consolidation.md`
**Entry**: Phase 5 EXITED — descriptor-guided parser complete (M5.1-M5.4); descriptor data now influences pairing confidence, candidate ordering, and Usage/Access-enriched warnings

**Roadmap Reference**: This prep supports **Phase 6: Descriptor-Validated Export**. Per the Phase 5 exit handoff: "Use accumulated descriptor evidence to strengthen existing export paths — metadata enrichment, validation checks, and promotion gate evaluation."

**Anti-drift**: Phase 6 adds descriptor validation to export without clearing promotion gates. Both promotion flags remain false. All changes are enrichment or warning-only.

## Objective

Use Phase 3-5 descriptor evidence to validate and enrich OBJ export — metadata comments, descriptor-based warnings, and pre-export validation checks — without changing decode/export behavior.

## Phase 5 Foundation (ready for Phase 6)

| Finding | Phase 6 implication |
|---|---|
| Float-family descriptors correlate with position/normal/UV data | Can validate position stream before export |
| Descriptor-aware confidence scoring (M5.2) | Pairing confidence reflects descriptor alignment |
| Pre-filter prefers float-family candidates (M5.3) | Export path already guided by descriptor |
| Shared helpers: IsFloatRole/IsFloatDescriptor/IsU16Descriptor | Available for export validation |
| All changes behind gates or candidate-only | Safety pattern proven |

## Proposed Milestones

### M6.1 — Descriptor Metadata in OBJ Export
- [x] positionDescriptor variable captures descriptor in both experimental and attribute-set paths
- [x] OBJ header comment: # Position descriptor: ...
- [x] Console warning when descriptor is not float-family
- [x] 41/41 tests pass

### M6.2 — Promotion Gate Re-Evaluation
- [x] Formal re-evaluation of all 6 gates against 10 Phase 3-6 milestones
- [x] 4 gates strengthened, gate 3 recommended for retirement (OBSOLETE), 0 cleared
- [x] Both flags confirmed false; promotion readiness checklist updated
- [x] Handoff: `docs/handoffs/2026-06-m6.2-promotion-gate-reevaluation.md`

### M6.3 — Descriptor-Aware Export Pre-Checks (PLANNING)
- Validate vertex count against descriptor stride hints
- Warn on structural anomalies before export

### M6.4 — Phase 6 Exit Consolidation (PLANNING)
- Comprehensive handoff documenting M6.1-M6.3
- Phase 7 entry assessment

## Commands

```bash
dotnet build RiftAssetDumper.slnx --nologo
dotnet test RiftAssetDumper.slnx --nologo
dotnet format RiftAssetDumper.slnx --verify-no-changes
```

## Validation Gates

- [x] Build: 0 errors
- [x] Tests: 41/41 pass
- [x] `dotnet format --verify-no-changes` clean
- [ ] `FieldOrderPromoted` still false
- [ ] `ParserExportPromotionAllowed` still false
- [ ] Generated-output guard clean

---

See `docs/roadmap/project-roadmap.md` (Phase 6), `docs/handoffs/2026-06-m5.5-phase5-exit-consolidation.md`.
