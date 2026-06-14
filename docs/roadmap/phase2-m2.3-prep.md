# Phase 2 M2.3 Prep Note — Role↔Descriptor↔Binding Integration

**Date**: 2026-06
**Type**: Milestone Prep — Phase 2 M2.3
**Status**: **ACTIVE**
**Parent(s)**: `docs/roadmap/project-roadmap.md` (Phase 2 M2.3), `docs/roadmap/current-phase.md` (Phase 2 M2.2 IN PROGRESS)
**Entry**: M2.2 binding proofs drafted (329: 12/12 IDs × 6 bindings; 305: 4 bindings; source-binding reuse confirmed; all ror1-float → `37 04 03 00`)

**Roadmap Reference**: This prep supports **M2.3** — the third milestone of Phase 2. Per the roadmap: "Integrate role assignment (position/normal/UV/index) with descriptor data."

**Anti-drift**: All integration work ties back to Phase 1+2 evidence. No new families. No parser/export promotion. Candidate-only. Python + .NET only.

## Objective

Per the roadmap: **M2.3**: Integrate role assignment (position/normal/UV/index) with descriptor data.

This milestone builds a unified three-way mapping:

```
Stream Role ←→ Descriptor Bytes ←→ NiDataStream Block ←→ NiMesh Attribute
```

Where each link is independently validated, and the integrated mapping reveals gaps, contradictions, and confirmation points.

## Entry Criteria

| Criterion | Status |
|---|---|
| M2.1: 5 descriptor patterns documented | ✅ `37 04 03 00` = generic ror1-float; boty-3=0x00; per-block embedded |
| M2.2: Binding proofs drafted | ✅ 329: 6 bindings × 12 IDs; 305: 4 bindings; cross-family comparison |
| Phase 1: Stream roles classified | ✅ position/normal/UV/index/anomalous at known offsets with confidence scores |

## Target Scope

### Three-way mapping (329 family)

| Role (c) | Descriptor | Block | Mesh Attr | Validated? |
|---|---|---|---|---|
| position-float3-ror1-lead (75) | `37 04 03 00` | #28 | #7/Pos, #34/Pos | 12/12 matrix + ShiftedSamples |
| normal-float3-ror1-lead (85) | `37 04 03 00` | #29 | #7/Norm | 12/12 matrix + ShiftedSamples |
| uv-float2-ror1-lead (80) | `37 04 03 00` | #36 | #7/UV | 12/12 matrix + ShiftedSamples |
| position-float3-ror1-lead (75) | `?` | #57 | #34/Extra | 12/12 candidate; descriptor unverified |
| u32-repeated-pattern-body (25) | `?` | #55 | #34/u32 | 12/12 low-c; descriptor unverified |

### Integration goals

1. **Unified table**: One machine-readable table joining role, descriptor, block, mesh attribute
2. **Gap identification**: Which roles have no verified descriptor? Which descriptors have no verified role?
3. **Cross-family**: Does 305's position→`37 04 03 00`→#21 repeat the 329 pattern?
4. **Index streams**: Where do index streams (u16be-strip-lead, u16be-list-lead) fit in the descriptor landscape?
5. **Anomalous classification**: What descriptor pattern (if any) maps to the anomalous @304 on #34?

## Approach

### Step 1: Build unified role↔descriptor↔block mapping

From M2.1 + M2.2 evidence: join per-stream roles with descriptor bytes and binding targets

### Step 2: Identify gaps

- Blocks #55, #57: roles known, descriptors unknown
- `15 02 01 00`, `36 04 02 00`, `10 01 04 00`, `3c 01 04 00`: descriptors known, roles hypothesized
- Index streams: not yet probed for descriptor bytes

### Step 3: Cross-family validation

- 305 position @188 → block #21 → `37 04 03 00` (inferred)
- 305 normal @196 → block #22 → descriptor unknown
- 305 UV @196 → block #40 → descriptor unknown

### Step 4: Produce M2.3 handoff

Unified role↔descriptor↔binding table with confidence levels and gap annotations

## Commands

```bash
# Refresh descriptor proof status
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
# Refresh layout report
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
# CI
ruff check scripts/ && mypy scripts/ --no-error-summary
```

## Deliverables

- [ ] `docs/roadmap/phase2-m2.3-prep.md` (this file)
- [x] `docs/handoffs/2026-06-m2.3-role-descriptor-integration.md`
- [ ] Unified role↔descriptor↔block table
- [ ] Gap analysis
- [ ] Updated current-phase.md

## Validation Gates

- [ ] All 5 descriptor patterns mapped to at least one known role
- [ ] All 12/12 matrix bindings cross-referenced with descriptor patterns
- [ ] Gaps explicitly documented (blocks #55, #57; index streams; `3c 01 04 00`)
- [ ] Candidate-only throughout; no promotion claims
- [ ] CI green

---

See `docs/roadmap/project-roadmap.md` (Phase 2), `docs/handoffs/2026-06-m2.2-binding-proofs.md`, `docs/handoffs/2026-06-m2.1-nidatastream-descriptor-mapping.md`.
