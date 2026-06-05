# Phase 1 M1.4 — Light 305-Family Comparison Prep

**Date**: 2026-06
**Type**: Milestone Prep — Phase 1 M1.4
**Status**: **ACTIVE**
**Parent(s)**: `docs/roadmap/project-roadmap.md` (Phase 1 M1.4), `docs/roadmap/current-phase.md` (M1.4 ACTIVE)
**Entry**: M1.3 COMPLETE (guards 12/12 PASS; validation suite 9/9 PASS; handoff finalized)
**Roadmap Reference**: This prep supports **M1.4** within **Phase 1: Position Source Family Proof & Role Classification** — light treatment of the #2 family (meshSize=305) for comparison against 329-family M1.1-M1.3 baseline.

**Anti-drift**: Strictly meshSize=305 comparison only; no new discovery, no 329 expansion, no other families. **Candidate-only** throughout; no parser/export promotion. Automation via **Python-only** (existing `scripts/rift_workflow.py` commands). Do NOT commit `Exports/` content. Reference this prep + roadmap + M1.3 handoff in all M1.4 work. High-reasoning lane per `docs/task-routing-safety-policy.md`.

## Objective

Per `docs/roadmap/project-roadmap.md` Phase 1:

> **M1.4**: Apply similar (lighter) treatment to the #2 family (meshSize=305) for comparison.

This milestone compares the 305-family sibling structure against the 329-family M1.1-M1.3 baseline. The 305 family was already heavily investigated in the post50 cycle (residual classifier, strict threshold delta, magic-43606 probe) — this milestone does NOT reopen that work. It produces a structural comparison handoff only.

## Scope

| Layer | Count | Description |
|---|---:|---|
| **Target family** | **1** | meshSize=305: 15 groups, 30 links, 15 distinct IDs |
| **Representative IDs** | **3** | 04297730afc68f38, 0d9a25c9a6af7b18, 75d5a06d7c0de1dd (anchors from sibling report) |
| **Comparison baseline** | **329 family** | M1.1 matrix (12 IDs), M1.2 @304 classification (10 scoped), M1.3 guards (12/12 PASS) |

## Entry Artifacts (M1.3 deliverables)

- `docs/handoffs/2026-06-m1.3-sibling-source-binding-guard.md` (finalized; 12/12 guards PASS)
- `Exports/position-source-sibling-family-report.json` + `.md` (lists both 329 and 305 families)
- `Exports/residual-position-classifier-report.json` + `.md` (305 stream@188 confirmed negative)
- `Exports/post50-mesh329-source-binding-compare.json` + `.md` (329 family anchor compare)
- `Exports/probe-nif-mesh-04297730afc68f38-mesh7.json` (305 mesh#7 probe)
- `Exports/probe-nif-mesh-04297730afc68f38-mesh27.json` (305 mesh#27 probe)

## 305 Family Structural Summary

From `Exports/position-source-sibling-family-report.json`:

| Field | Value |
|---|---|
| MeshSize | 305 |
| MeshBlocks | mesh#7, mesh#27 |
| MeshPayloadOffsets | stream@188 |
| EvidenceGroups | 15 |
| TotalStreamLinks | 30 |
| DistinctIds | 15 |
| TargetBlocks | block#21 |
| PayloadBytes | 168, 192, 264, 336, 408, 456, 840 |
| RepresentativeIds | 8 IDs |
| UsageAccess | 1/19 |
| Roles | position-float3-ror1-lead |
| Decision | repeated meshSize=305 source-binding family; candidate-only probe queue |

### Per-ID probe data (representative: 04297730afc68f38)

**mesh#7** (attrSets=1):

- Stream@188 — POSITION, block#21, 192 bytes, 16 float3 (ror1), plausible 0.958, extent 28.97
- Stream@196 — NORMAL, block#22, 192 bytes, 16 float3 (ror1), plausible 0.958, 100% unit vectors
- Has texture bindings (diffuseTexture, normalTexture)
- `RotatedFloat3`: [-12..17] X, [-0.1..0.33] Y, [16.5..24] Z

**mesh#27** (attrSets=0):

- Stream@188 — POSITION, block#21, 192 bytes — **identical to mesh#7** (same BodyFirst16)
- Stream@196 — UV-like, block#40, 216 bytes, 18 float2 (ror1), plausible 0.407, UV range
- `RotatedFloat3` (stream@196): 100% unit vectors, near-unit float3 normals — appears to be UV + padding

## Structural Comparison: 305 vs 329 Family

| Feature | 329 Family | 305 Family |
|---------|-----------|-----------|
| **Sibling pair** | mesh#7 ↔ mesh#34 | mesh#7 ↔ mesh#27 |
| **Primary position** | @212 (shared between #7 and #34) | @188 (shared between #7 and #27) |
| **#7 attrSets** | 1 | 1 |
| **Sibling attrSets** | 0 (#34) | 0 (#27) |
| **Sibling secondary stream** | @304 on #34 (position-like, c=75, low plaus) | @196 on #27 (UV-like, c=80, uv-float2-ror1-lead) |
| **Position data quality** | @212: good (ror1 float3, plausible); @304: anomalous (0.4× size, low plaus, distinct bodies, mixed endian) | @188: good (ror1 float3, plausible 0.958, shared between siblings) |
| **Sibling secondary role** | Anomalous position-like data — CANDIDATE-ONLY; no attr-extra path | Genuine UV data — confirmed unit vectors, UV range |
| **Known resolution** | @304: candidate-only; blocker: attrSets=0 on #34 blocks attr-extra path | @188 residual: CONFIRMED NEGATIVE (float32 decode = denormal garbage; magic 43606, plausible 0.9444 < 0.95) |
| **Evidence groups** | 23 groups, 46 links, 23 IDs | 15 groups, 30 links, 15 IDs |
| **Payload variety** | @304: 96-396 bytes (variable) | @188: 168-840 bytes (variable) |

## Key Differences & Parallels

### Parallels (shared patterns)

1. **Both families have attrSets=1/#7 vs attrSets=0/sibling split** — consistent pattern across families
2. **Both share primary position source** between #7 and sibling (#34 or #27)
3. **Both have a secondary stream on the sibling** that differs from #7's secondary stream (#7 has UV@304 on 329, NORMAL@196 on 305; sibling has pos-like@304 on 329, UV-like@196 on 305)
4. **Both siblings have attrSets=0** meaning no attribute-extra path for geometry export

### Differences (family-specific)

1. **Sibling secondary stream role**: 329's #34 has a low-plaus anomaly (@304 position-like with c=75 but <0.5 plausible); 305's #27 has genuine UV data (@196 uv-float2-ror1-lead with c=80)
2. **Stream payload** for secondary: 329's @304 is small (~0.4× primary) with anomalous bodies; 305's @196 is `position-float3-ror1-lead` that actually gives plausible ror1 float3 values
3. **Resolution status**: 329's @304 is candidate-only with detailed quant (M1.2); 305's @188 was probed deeper and confirmed negative (residual classifier: all targets < 0.95, magic-43606 = denormal garbage)
4. **Position data**: 305 has verified ror1 float3 positions at @188 on both siblings; 329 has verified ror1 float3 at @212 on both siblings

## Light Treatment Plan (M1.4 Steps)

1. **Structural comparison** (done — this prep doc): extract 305 family data from existing sibling report + probe JSONs; compare against 329 M1.1-M1.3 baseline
2. **Re-extract from existing sibling family report**: The `position-source-sibling-family-report` already contains the 305 entry; no new runs needed — re-extract from `Exports/position-source-sibling-family-report.json`
3. **Compare sibling layouts**: Contrast mesh#7/#27 (305) vs mesh#7/#34 (329) — block offsets, stream roles, attrSets patterns
4. **Record differences**: Document parallels and divergences in M1.4 handoff
5. **Validation**: Drift check (305-only, no new discovery, candidate-only); CI green (ruff + mypy + tests)
6. **Exit**: Produce M1.4 handoff; update current-phase.md to M1.4 COMPLETE → M1.5 ACTIVE

## Commands

```bash
# Structural comparison (existing data — no new runs needed)
python scripts/rift_workflow.py position-source-sibling-family-report --full

# Optional: re-probe 305 anchors for fresh data (skip if probe JSONs exist)
python scripts/rift_workflow.py mesh-probe --id 04297730afc68f38 --mesh-block 7
python scripts/rift_workflow.py mesh-probe --id 04297730afc68f38 --mesh-block 27

# CI
ruff check scripts/
mypy scripts/ --no-error-summary
python -m pytest scripts/ -v --tb=short
```

## Deliverables

- [ ] `docs/roadmap/phase1-m1.4-prep.md` (this file)
- [ ] `docs/handoffs/draft-2026-06-m1.4-305-family-comparison.md` (M1.4 handoff)
- [ ] `docs/roadmap/phase1-m1.4-coordination.md` (coordination log)
- [ ] Updated `docs/roadmap/current-phase.md` (M1.4 COMPLETE → M1.5 ACTIVE)

## Validation Gates

- [ ] Structural comparison table complete with parallels and differences
- [ ] Drift check: strictly meshSize=305 comparison only; no new families
- [ ] Candidate-only language throughout
- [ ] All refs to Phase 1 M1.4 + roadmap + M1.3 handoff + matrix
- [ ] Python-only; no new .ps1/.cmd
- [ ] CI green: ruff 0, mypy 0, Python tests passing
- [ ] No `Exports/` committed

## Blockers (inherited; not addressed by M1.4)

| Blocker | Status |
|---|---|
| `mesh34-complete-geometry-binding-not-proven` | Unchanged (329 family) |
| `parser-export-promotion-not-allowed` | Unchanged (candidate-only) |
| `meshSize-305-residual-dead-end` | Confirmed; float32 decode = denormal; magic-43606 not position data |
| `attrSets=0 on sibling variant` | Both families; blocks attr-extra path |

---

See `docs/roadmap/project-roadmap.md` Phase 1 M1.4, `docs/roadmap/current-phase.md`, `docs/handoffs/2026-06-m1.3-sibling-source-binding-guard.md`.
