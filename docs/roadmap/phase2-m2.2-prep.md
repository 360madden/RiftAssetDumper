# Phase 2 M2.2 Prep Note — NiMesh → NiDataStream Binding Proofs at Scale

**Date**: 2026-06
**Type**: Milestone Prep — Phase 2 M2.2
**Status**: **ACTIVE**
**Parent(s)**: `docs/roadmap/project-roadmap.md` (Phase 2 M2.2), `docs/roadmap/current-phase.md` (Phase 2 ACTIVE), `docs/handoffs/draft-2026-06-m2.1-nidatastream-descriptor-mapping.md` (M2.1 evidence gathered)
**Entry**: M2.1 evidence gathered — descriptor is per-block embedded (4 bytes at offset 24, not static table); 5 consistent patterns; `37 04 03 00` spans position/normal/UV; all promotion brakes intact

**Roadmap Reference**: This prep supports **M2.2** — the second milestone of **Phase 2: NiDataStream Descriptor & Binding Proof System**. Per the roadmap: "Build/validate 'NiMesh offset → NiDataStream block' binding proofs at scale."

**Anti-drift**: All binding proof work must tie back to Phase 1 mesh/stream families (329: matrix IDsCovered, 305: representative anchors). No new Ghidra targets without explicit geometry proof linkage. **Candidate-only** throughout; no parser/export promotion. Use existing `scripts/rift_workflow.py` + `.NET` inventory commands. Do NOT commit `Exports/` content. High-reasoning lane per `docs/task-routing-safety-policy.md`.

## Objective

Per `docs/roadmap/project-roadmap.md` Phase 2:

> **M2.2**: Build/validate "NiMesh offset → NiDataStream block" binding proofs at scale.

This milestone uses Phase 1's family proof data (23 sibling groups, 46 stream links for 329; 15 groups, 30 links for 305) and M2.1's descriptor findings to build machine-readable binding proofs. A binding proof connects a specific NiMesh block (the mesh consumer) to a specific NiDataStream block (the data provider), establishing which stream payload feeds which mesh attribute.

## Entry Criteria (M2.1 Evidence Gathered)

| Criterion | Status |
|---|---|
| M2.1 descriptor field-order evidence gathered | ✅ 5 consistent descriptor patterns; per-block embedded; byte-3 universally 0x00 |
| Phase 1 family proof data available | ✅ Post50: 329 family (23 groups, 46 links); 305 family (15 groups, 30 links) |
| Phase 1 matrix with per-block assignments | ✅ 12 IDs with mesh#7/#34 block indices per stream |
| M2.1 structural insight: descriptor is per-block | ✅ Static table hypothesis falsified; descriptors travel with streams |

## Target Scope

### Binding proof sources (Phase 1 + M2.1)

| Source | Data Available | Binding Relevance |
|---|---|---|
| Post50 family proof | 23 groups, 46 links showing shared stream offsets | **Direct**: sibling pairs share position sources at known block indices |
| M1.1 matrix | 12 IDs, per-stream block assignments (#28=pos, #29=normal, #36=UV, #57=anomalous) | **Direct**: known block→role mapping for each anchor |
| M1.2 analysis | @304 body classification, low plaus, non-attr-extra path | **Binding constraint**: @304 on #34 is NOT an attribute-extra stream |
| M2.1 layout report | 184 blocks, 5 descriptor patterns, per-block offset 24 | **Descriptor context**: confirms block structure validity |
| M1.4 comparison | 305 family: #7↔#27, @188 shared, @196 UV vs NORMAL divergence | **Cross-family**: binding pattern validation |

### Binding proof architecture

A binding proof asserts:

```
NiMesh(block=X, attribute=N) → NiDataStream(block=Y, offset=Z)
```

Where:
- **X** = NiMesh block index within the NIF
- **N** = mesh attribute index (0=position, 1=normal, 2=UV, etc.)
- **Y** = NiDataStream block index (the data provider)
- **Z** = mesh payload offset within the stream

### Known bindings from Phase 1 (329 family)

From the M1.1 matrix (all 12 IDs consistent):

| Mesh Attribute | Mesh Block | Stream Block | Offset | Role | Confirmed? |
|---|---|---|---|---|---|
| Position (#7) | #7 | #28 | @212 | position-float3-ror1-lead (75) | 12/12 |
| Normal (#7) | #7 | #29 | @220 | normal-float3-ror1-lead (85) | 12/12 |
| UV (#7) | #7 | #36 | @304 | uv-float2-ror1-lead (80) | 12/12 |
| Position (#34) | #34 | #28 | @212 | position-float3-ror1-lead (75) | 12/12 |
| Extra (#34) | #34 | #57 | @304 | position-float3-ror1-lead (75) | 12/12 (candidate-only) |
| u32 pattern (#34) | #34 | #55 | @296 | u32-repeated-pattern-body (25) | 12/12 (low-confidence, c=25, not deeply probed) |

## Focused Approach for M2.2

### Step 1: Formalize binding proof schema

Create a machine-readable binding proof format:
- Per-NIF, per-mesh-block: list of (attribute, stream_block, offset, role, confidence)
- Cross-reference with descriptor bytes at stream block offset 24
- Validate: do all position bindings target blocks with descriptor `37 04 03 00`?

### Step 2: Validate bindings against Phase 1 evidence

For the 12 matrix IDs:
- Assert: mesh#7 attribute 0 → block #28 (12/12)
- Assert: mesh#7 attribute 1 → block #29 (12/12)
- Assert: mesh#7 attribute 2 → block #36 (12/12)
- Assert: mesh#34 shares block #28 for position (12/12)
- Assert: mesh#34 has additional binding to block #57 (12/12, candidate-only)

### Step 3: Cross-validate with descriptor evidence

For each binding pair (mesh_block, stream_block):
- Read the NiDataStream descriptor at stream block offset 24
- Assert descriptor byte 3 = 0x00 (confirmed 184/184)
- Hypothesis: all position/normal/UV bindings target blocks with `37 04 03 00`
- Hypothesis: anomalous @304 bindings target blocks with `15 02 01 00`

### Step 4: Cross-family validation (329 vs 305)

**305 family known binding** (from Phase 1 M1.4 + sibling family report):

| Mesh Attribute | Mesh Block | Stream Block | Offset | Role | Confirmed? |
|---|---|---|---|---|---|
| Position (#7) | #7 | #21 | @188 | position-float3-ror1-lead (75) | Representative (04297730afc68f38) |
| Normal (#7) | #7 | #22 | @196 | normal-float3-ror1-lead (85) | Representative |
| Position (#27) | #27 | #21 | @188 | position-float3-ror1-lead (75) | Representative (shared body with #7) |
| UV-like (#27) | #27 | #40 | @196 | uv-float2-ror1-lead (80) | Representative (candidate-only) |

Cross-family validation:
- 329: mesh#7 ↔ mesh#34 share block #28 for position
- 305: mesh#7 ↔ mesh#27 share block #21 for position
- Validate: in both families, the sibling shares the SAME NiDataStream block for position
- Validate: the sibling's differing secondary stream targets a DIFFERENT NiDataStream block (#57 in 329, #40 in 305)

### Step 5: Produce M2.2 handoff with binding tables

Document per-family, per-ID binding proofs with:
- Binding pair table (mesh attribute → stream block → role)
- Cross-family comparison
- Descriptor byte cross-reference
- Remaining gaps (attrSets=0 sibling bindings, anomalous @304)

## Commands

```bash
# 1. Refresh family proof (binding data)
python scripts/rift_workflow.py post50-mesh329-family-proof --out Exports/
python scripts/rift_workflow.py post50-mesh329-source-binding-compare --out Exports/

# 2. Run mesh-bindings inventory (full binding data)
python scripts/rift_workflow.py inventory-nif-mesh-bindings --full

# 3. Cross-reference with layout report
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full

# 4. Verify promotion brakes
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json

# CI
ruff check scripts/
mypy scripts/ --no-error-summary
python -m pytest scripts/ -v --tb=short
```

## Deliverables

- [ ] `docs/roadmap/phase2-m2.2-prep.md` (this file)
- [ ] `docs/handoffs/draft-2026-06-m2.2-binding-proofs.md` (M2.2 handoff)
- [ ] Binding proof table: 329 family (12 IDs × per-mesh attribute → stream block)
- [ ] Cross-family binding comparison (329 vs 305)
- [ ] Descriptor byte cross-reference (binding → descriptor pattern)
- [ ] Updated `docs/roadmap/current-phase.md` (M2.2 IN PROGRESS)

## Validation Gates

- [ ] All Phase 1 matrix IDs covered in binding proofs
- [ ] Binding assertions validated against post50 family proof data
- [ ] Descriptor byte cross-reference confirmed (byte 3 = 0x00 for all bound streams)
- [ ] Cross-family binding pattern validated (sibling shares primary position block)
- [ ] Candidate-only language; no promotion claims
- [ ] Drift check: strictly M2.2 scope — no parser changes, no new families
- [ ] All refs to Phase 2 M2.2 + roadmap + M2.1 handoff + Phase 1 exit handoff
- [ ] CI green: ruff 0, mypy 0, Python tests passing
- [ ] No `Exports/` committed

## Blockers (M2.2 context)

| Blocker | Status | M2.2 Impact |
|---|---|---|
| `DescriptorTableAllZero` | Not relevant (descriptors are per-block) | M2.1 resolved: no static table to sample |
| `FieldOrderPromoted=false` | **Holds** | M2.2 does not promote; binding proofs are structural |
| `ParserExportPromotionAllowed=false` | **Holds** | Binding proofs are candidate-only evidence |
| `attrSets=0 on sibling` | **Holds** — blocks complete geometry binding | M2.2 documents the sibling binding constraint |

---

See `docs/roadmap/project-roadmap.md` (Phase 2), `docs/handoffs/draft-2026-06-m2.1-nidatastream-descriptor-mapping.md` (M2.1 evidence), `docs/handoffs/2026-06-m1.5-phase1-exit-consolidation.md` (Phase 1 exit).

**End of M2.2 prep.**
