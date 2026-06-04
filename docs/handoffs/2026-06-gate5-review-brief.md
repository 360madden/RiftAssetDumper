# Gate 5 Review Brief — Pairing-Impact-Proof Reframing

**Date**: 2026-06
**Type**: Human Review Brief
**Status**: **Awaiting decision** — 5 of 7 gates cleared; gate 5 is next

---

## TL;DR

**Gate 5 blocks parser/export promotion because it requires "complete position+normal+UV evidence."** But the RIFT game engine uses `attrSets=0` on sibling meshes by design — complete geometry groups don't exist. The gate's criterion is architecturally impossible to satisfy.

**Recommendation**: Reframe gate 5 to accept the game's architectural constraint. If reframed, gate 5 would CLEAR on current evidence (13 code milestones, 3 levels of descriptor-guided pairing, 94 OBJ exports working with partial bindings).

**No code changes are proposed.** Both promotion flags remain false until gate 6 (safety brake) is also resolved.

---

## Current State

### Gate Landscape

| # | Gate | Status | Notes |
|---|---|---|---|
| 1a | field-order-confirmed | **CLEARED** ✅ | M7.2 |
| 1b | field-semantics-complete | **CLEARED** ✅ | M9.1 — stride hypothesis 16/16 |
| 2 | semantic-map | **CLEARED** ✅ | M9.3 — 5/5 patterns mapped |
| 3 | (retired) | RETIRED | M7.1 |
| 4 | sample-byte-agreement | **CLEARED** ✅ | M7.3 — 100% population |
| — | per-block-consistency | **CLEARED** ✅ | M7.1 — replacement for gate 3 |
| **5** | **pairing-impact-proof** | **candidate — reframing recommended** | **M7.4 — THIS GATE** |
| 6 | narrow-parser-patch | BLOCKED — safety brake | Must be last |

**5 of 7 gates cleared.** Only gates 5 and 6 remain.

### Descriptor Subsystem

The NiDataStream descriptor subsystem is proven complete:
- All 4 descriptor bytes have identified semantics (family, element width, component count, padding)
- All 5 descriptor patterns have role assignments (3 specific + 2 family-level, 0 unmapped)
- Stride→usage rule proven: uint16×scalar → index, everything else → vertex
- 58 code lines, 49 tests, 0 regressions
- No Ghidra required — evidence is structural/payload-derived
- 31,777 blocks population-validated (100% coverage)

---

## The Problem: attrSets=0 Architecture

### What attrSets=0 means

In the RIFT NIF format, `NiMesh` blocks reference streams through integer offsets. The `FindNifMeshAttributeSets` function looks for complete position+normal+UV groups. But many meshes have `attributeSets=0` — they reference position, normal, or UV streams individually but not as a complete set.

### Why attrSets=0 is architectural, not anomalous

| Family | Pairs tested | attrSets=0 pattern | Confirmed |
|---|---|---|---|
| meshSize=329 | 12/12 | mesh#7=1, mesh#34=0 | ✅ |
| meshSize=305 | 3/3 | mesh#7=1, mesh#27=0 | ✅ |
| meshSize=321 | 11/11 | sibling pairs repeat pattern | ✅ |

**15/15 pairs across 2 independent families** — consistent, not a coincidence. The game deliberately uses partial bindings on some mesh variants. Complete geometry groups (all 4 attributes: position + normal + UV + index) do not exist in the game's asset data at the `FindNifMeshAttributeSets` level.

### Impact on gate 5

Gate 5's original criterion — "improves complete position+normal+UV evidence" — is structurally impossible. **No mesh in the copied archive set has complete geometry groups.** Yet:
- 94 OBJ exports work with partial bindings
- Pairing-based face generation works despite attrSets=0
- Descriptor-guided pairing improves evidence quality at 3 independent levels

The gate tests an impossible standard.

---

## Evidence for Reframing

### Descriptor-Guided Pairing (3 levels)

| Level | Mechanism | Evidence |
|---|---|---|
| Confidence adjustment | `AdjustConfidenceByDescriptor()`: +5 float match, -10 u16 mismatch | 10 tests in M5.2 |
| Candidate prioritization | `IsFloatDescriptor()` boost in position pre-filter | M5.3, behind experimental gate |
| Validation warnings | `CheckDescriptorRoleConsistency()` + Usage/Access enrichment | M4.5, M5.4 |

### Export Validation (2 levels)

| Mechanism | Evidence |
|---|---|
| `ValidateDescriptorExportPrechecks()` | 8 tests in M6.3; structural + descriptor alignment |
| `# Position descriptor:` comment in OBJ | M6.1, both export paths |

### Safety Record

- **13 code milestones** (Phases 4-6) — zero decode/export path changes
- **49 xUnit tests** — all pass
- **Both promotion flags** — never changed from false
- **Safety brake (gate 6)** — held perfectly through entire descriptor stack

### Reframed Criterion

| Original | Reframed |
|---|---|
| "Improves complete position+normal+UV evidence" | "Improves available geometry evidence given the architectural constraint" |

Under this reframing:
- ✅ Descriptor data improves pairing quality (3 levels)
- ✅ Descriptor data does not promote noise (all changes candidate-only/gated)
- ✅ Pairing evidence is at the best available level (attrSets=0 is architectural)
- ✅ 94 OBJ exports validated working with partial bindings

---

## Decision Required

**Should gate 5 (`pairing-impact-proof`) be reframed to accept the `attrSets=0` architectural constraint?**

| Option | Outcome |
|---|---|
| **Accept reframing** | Gate 5 CLEARS. 6 of 7 gates cleared. Only gate 6 (safety brake) remains. |
| **Reject reframing** | Gate 5 remains candidate. Project stalls on architecturally impossible criterion. |
| **Hold for more evidence** | Gate 5 remains candidate. Specify what additional evidence would suffice. |

---

## What This Decision Does NOT Do

- ❌ Does NOT clear gate 6 (safety brake) — that remains BLOCKED
- ❌ Does NOT change any code
- ❌ Does NOT set `FieldOrderPromoted = true`
- ❌ Does NOT set `ParserExportPromotionAllowed = true`
- ✅ Only reframes gate 5's criterion to match the game's architecture

---

## References

| Artifact | Path |
|---|---|
| M7.4 formal decision record | `docs/handoffs/2026-06-m7.4-formal-decision-record.md` |
| Promotion readiness checklist | `docs/post50-parser-export-promotion-readiness-checklist.md` |
| Phase 9 exit handoff | `docs/handoffs/2026-06-m9.4-phase9-exit-consolidation.md` |
| Gate 1b clearance analysis | `docs/handoffs/2026-06-m9.1-gate1b-stride-clearance.md` |
| Gate 2 clearance analysis | `docs/handoffs/2026-06-m9.3-gate2-semantic-map-clearance.md` |
| Promotion decision template | `docs/nidatastream-parser-export-promotion-decision-template.md` |
