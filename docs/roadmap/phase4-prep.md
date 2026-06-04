# Phase 4 Prep Note — Descriptor-Aware Parser Scoping

**Date**: 2026-06
**Type**: Phase Prep — Phase 4 Entry
**Status**: **ACTIVE** — M4.1-M4.6 COMPLETE, M4.7 planning
**Parent(s)**: `docs/roadmap/project-roadmap.md` (Phase 4), `docs/roadmap/current-phase.md` (Phase 4 PLANNING)
**Entry**: Phase 3 EXITED (`docs/handoffs/2026-06-m3.5-phase3-exit-consolidation.md`; all 6 NiDataStream record types carry `DescriptorBytes` + `DescriptorClassification`; descriptor data layer complete)

**Roadmap Reference**: This prep supports **Phase 4: Descriptor-Aware Parser**. Per the roadmap: "Consume descriptor fields for parser behavioral changes — integrity checks, routing hints, role validation — while maintaining the candidate-only safety boundary and promotion gate discipline."

**Anti-drift**: Phase 4 must begin with the smallest possible parser behavioral change, guarded by proof-gate checks. No promotion flags change until explicit gate clearance. Every behavioral change requires a decision record per `docs/nidatastream-parser-export-promotion-decision-template.md`. Both `FieldOrderPromoted` and `ParserExportPromotionAllowed` must remain false.

## Objective

Scope the Phase 4 descriptor-aware parser implementation using Phase 3 propagated descriptor data as the foundation. Identify the narrowest, best-proven behavioral change. Define pre-work, decision record, test, and guard requirements.

## Phase 3 Evidence Foundation

### What Phase 3 delivered (ready for consumption)

| Finding | Parser implication |
|---|---|
| `DescriptorBytes` available on all 6 NiDataStream record types | Any probe or inventory command now emits descriptor data |
| `ClassifyNifDescriptor()` maps 5 known patterns | Ready for integration into routing/role logic |
| Descriptor data flows through all JSON outputs | Inventory-scale analysis possible without code changes |
| Byte-3 = 0x00 universal (Phase 2, 184/184 sampled) | Structural invariant — can be used as integrity check |
| Pattern distribution verified at sample scale | `37 04 03 00` dominant (ror1-float), `15 02 01 00` (12.5%), `36 04 02 00` (27%) |

### What's still constrained

| Constraint | Impact on Phase 4 |
|---|---|
| Both promotion flags false | No parser/export promotion — behavioral changes are guarded, not promoted |
| Bytes 1-2 semantics unknown | Cannot interpret component count or stride from descriptor alone |
| 3/5 patterns role-unverified | Classification is informational; role decisions still need Usage/Access |
| 0.58% sample coverage | Population-scale validation pending |

## Proposed First Behavioral Change: Descriptor Byte-3 Integrity Check

### What
In `AnalyzeNifDataStreamLayout`, add a warning when byte-3 of the descriptor (at offset 27 of block payload) is not 0x00. This is the smallest possible behavioral change that consumes descriptor data.

### Scope (~5 lines in Program.cs)
- After extracting `rawDescriptorBytes`, check `blockPayload[27] != 0x00`
- If non-zero, add a warning to the layout return
- Warning text: `"descriptor-byte-3-nonzero"` (or append to existing warning)

### Why this is the right first step
1. **Smallest possible behavioral change** — single byte check, single warning
2. **Best-proven evidence** — byte-3 = 0x00 universal across 184/184 sampled blocks (Phase 2)
3. **Safety-first** — warns on unexpected data without blocking processing
4. **Testable** — construct a block with byte-3 ≠ 0x00, verify warning appears
5. **Foundation for future** — establishes pattern for descriptor-aware safety checks

### NOT in scope
- No blocking of processing (warning only, no error)
- No change to promotion flags
- No change to decode/export behavior
- No role assignment or routing changes

## Pre-Work

| # | Action | Status |
|---|---|---|
| 1 | Phase 3 descriptor data layer complete | ✅ |
| 2 | Byte-3 universal finding established (Phase 2) | ✅ |
| 3 | All 6 record types carry descriptor fields | ✅ |

## Commands

```bash
dotnet build RiftAssetDumper.slnx --nologo
dotnet test RiftAssetDumper.slnx --nologo
dotnet format RiftAssetDumper.slnx --verify-no-changes
ruff check scripts/ && mypy scripts/ --no-error-summary
```

## Decision Record Requirements

Per `docs/nidatastream-parser-export-promotion-decision-template.md`:
1. Exact `nidatastream-promotion-status --list-json` summary
2. Before/after explanation of behavior change
3. Generated-output safety statement
4. Targeted tests proving new behavior
5. Non-consumption guard update plan
6. Rollback plan

**Both promotion flags must remain false throughout.**

## Deliverables (Phase 4 M4.1)

- [x] `docs/roadmap/phase4-prep.md` (this file)
- [x] M4.1 decision record (per template)
- [x] Implementation: byte-3 ≠ 0x00 warning in `AnalyzeNifDataStreamLayout`
- [x] Targeted xUnit tests (2 new; 19/19 pass)
- [x] M4.1 handoff (inline in current-phase.md)
- [x] Updated current-phase.md

### M4.2 Deliverables
- [x] `ClassifyNifDescriptorByByte0()` method (5 family labels)
- [x] `_ => ClassifyNifDescriptorByByte0(descriptorBytes)` fallback in `ClassifyNifDescriptor`
- [x] 4 xUnit tests (23/23 pass)
- [x] Scale verification: 16/16 classified, 0 nulls

### M4.3 Deliverables
- [x] `DescriptorClassificationGroups` field on `NifStreamHeaderInventoryReport`
- [x] Aggregation loop in `InventoryNifStreamHeaders`
- [x] 23/23 tests pass

### M4.4 Deliverables
- [x] Console descriptor classification summary line in `inventory-nif-stream-headers` output (23/23 tests)

### M4.5 Deliverables
- [x] `CheckDescriptorRoleConsistency()` cross-check helper (internal static)
- [x] Warning loop in `ProbeNifMesh` after stream refs line
- [x] 6 xUnit tests (29/29 pass)

### M4.6 Deliverables
- [x] Descriptor classification in `probe-nif-stream-body` console output (one-line addition)
- [x] 29/29 tests pass

### M4.7 Deliverables (PLANNING)
- [ ] Next descriptor-aware parser behavioral change

## Validation Gates

- [x] Build: 0 errors (M4.1-M4.3)
- [x] Tests: 23/23 pass (M4.1-M4.3)
- [x] `dotnet format --verify-no-changes` clean
- [x] ruff 0, mypy 0
- [x] `FieldOrderPromoted` still false
- [x] `ParserExportPromotionAllowed` still false
- [x] Generated-output guard clean
- [x] Console descriptor summary visible (M4.4)

---

See `docs/roadmap/project-roadmap.md` (Phase 4), `docs/handoffs/2026-06-m3.5-phase3-exit-consolidation.md`.
