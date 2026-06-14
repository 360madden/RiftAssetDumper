# Phase 3 Prep Note — Parser/Export Implementation Scoping

**Date**: 2026-06
**Type**: Phase Prep — Phase 3 Entry
**Status**: **ACTIVE**
**Parent(s)**: `docs/roadmap/project-roadmap.md` (Phase 3), `docs/roadmap/current-phase.md` (Phase 3 ACTIVE)
**Entry**: Phase 2 EXITED (M2.5 consolidation handoff created; all 4 milestones documented; 0 promotion gates cleared; 7 core blockers characterized)

**Roadmap Reference**: This prep supports **Phase 3: Parser/Export Implementation**. Per the roadmap: "Implement narrow, tested parser changes that consume NiDataStream descriptor & binding evidence."

**Anti-drift**: Phase 3 must begin with the smallest possible parser change, guarded by proof-gate checks, with a decision record per `docs/nidatastream-parser-export-promotion-decision-template.md`. No export until parser truth is validated. Both `FieldOrderPromoted` and `ParserExportPromotionAllowed` must remain false until explicit gate clearance.

## Objective

Scope the Phase 3 parser/export implementation using Phase 2 NiDataStream evidence as the entry foundation. Identify the narrowest, best-proven parser change to start with; define pre-work requirements; specify decision record, test, and guard requirements.

## Phase 2 Evidence Foundation

### What's proven (candidate-only level, ready for parser consumption)

| Finding | Parser implication |
|---|---|
| Descriptor is 4 bytes at offset 24 in every NiDataStream block header | Parser can read 4 bytes at block header offset 24 |
| Byte-3 = 0x00 universal (184/184 confirmed) | Parser can assert byte-3 is zero; use as integrity check |
| `37 04 03 00` = ror1-float data (position, normal, UV) | Parser can use this pattern to classify float streams |
| 5 descriptor patterns exist; roles partially mapped | Parser needs pattern-to-role lookup table |
| Binding reuse: siblings share position blocks | Parser can reuse stream assignments across sibling meshes |
| 329: 12/12 IDs × 6 bindings (4 confirmed, 2 candidate) | Parser has scale-validated target data |
| Descriptor is role-agnostic | Parser must NOT use descriptor alone for role assignment; must consult Usage/Access |

### What's NOT proven (blocks parser consumption)

| Gap | Parser constraint |
|---|---|
| Bytes 1-2 semantics unknown | Parser cannot interpret bytes 1-2 |
| 4/5 patterns have no verified role | Parser can only use `37 04 03 00` classification |
| 0.58% sample coverage | Parser must degrade gracefully on unrecognized patterns |
| No complete geometry groups (attrSets=0) | Parser must handle partial bindings |
| Blocks #55/#57 descriptors unknown | Parser cannot validate these blocks |
| No parser code exists | All parser code is net-new |

## Proposed Parser Change: Narrowest First Step

### Candidate: Descriptor field read + classification

**What**: Read 4 bytes at NiDataStream block header offset 24, classify against known patterns.

**Scope**:

- Add `DescriptorBytes` field to NiDataStream record in `Program.cs`
- Implement `ClassifyDescriptor(byte[] bytes)` → pattern enum
- Known patterns: `37_04_03_00` (ror1-float), `36_04_02_00` (unknown), `15_02_01_00` (unknown), `10_01_04_00` (unknown), `3c_01_04_00` (unknown)
- Log warning when byte-3 ≠ 0x00 (classify as unknown pattern; do not crash)
- Log classification for probed streams

**NOT in scope**:

- No role assignment from descriptor (role comes from Usage/Access)
- No change to decode/export behavior
- No change to promotion flags
- No parser behavioral change — classification is informational only

**Why this is the right first step**:

1. Smallest possible code change (~50 lines in Program.cs)
2. Uses best-proven evidence (4-byte structure, byte-3=0x00, 5 patterns)
3. Doesn't change any existing behavior
4. Can be tested with targeted probe commands
5. Provides a foundation for future parser work (descriptor classification)

## Pre-Work Required Before Any Parser Patch

| # | Action | Priority | Blocks |
|---|---|---|---|
| 1 | Resolve `36 04 02 00` role (27% of sample) | **Critical** | Pattern classification completeness |
| 2 | Probe blocks #55/#57 descriptor bytes | **High** | 329 unified table completeness |
| 3 | Scale validate bindings beyond 12 matrix IDs | **High** | Pattern distribution confidence |
| 4 | Create decision record (per template) | **Required** | Any parser change |
| 5 | Review existing C# code for descriptor-adjacent logic | **Required** | Safe code integration |

## Commands

```bash
# Pre-work
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json

# CI
dotnet build RiftAssetDumper.slnx --nologo
dotnet test RiftAssetDumper.slnx --nologo
dotnet format RiftAssetDumper.slnx --verify-no-changes

# Python CI
ruff check scripts/ && mypy scripts/ --no-error-summary
```

## Decision Record Requirements

Per `docs/nidatastream-parser-export-promotion-decision-template.md`, before ANY parser change:

1. Exact `nidatastream-promotion-status --list-json` summary
2. Exact `nidatastream-descriptor-proof-status --list-json` summary
3. Before/after explanation of parser behavior
4. Generated-output safety statement
5. Targeted tests proving new behavior
6. Non-consumption guard update plan
7. Rollback plan

**Both `FieldOrderPromoted` and `ParserExportPromotionAllowed` must remain false throughout.**

## Deliverables (Phase 3 M3.1)

- [x] `docs/roadmap/phase3-prep.md` (this file)
- [ ] Pre-work: resolve `36 04 02 00` role
- [ ] Pre-work: probe blocks #55/#57
- [ ] Decision record (per template)
- [ ] Targeted parser patch (descriptor field read + classification)
- [ ] Targeted tests (xUnit)
- [ ] M3.1 handoff documenting results
- [ ] Updated current-phase.md

## Validation Gates

- [ ] All pre-work completed or explicitly deferred
- [ ] Decision record completed and reviewed
- [ ] Parser patch is minimal (descriptor read + classification only, no behavioral change)
- [ ] `FieldOrderPromoted` still false
- [ ] `ParserExportPromotionAllowed` still false
- [ ] Existing tests still pass (all xUnit tests)
- [ ] New targeted tests pass
- [x] `dotnet format --verify-no-changes` clean
- [x] CI green (both .NET and Python)
- [x] Generated-output guard clean

---

See `docs/roadmap/project-roadmap.md` (Phase 3), `docs/handoffs/2026-06-m2.5-phase2-exit-consolidation.md`, `docs/nidatastream-parser-export-promotion-decision-template.md`.
