# Phase 2 M2.4 Prep Note — Promotion Gate Evaluation

**Date**: 2026-06
**Type**: Milestone Prep — Phase 2 M2.4
**Status**: **ACTIVE**
**Parent(s)**: `docs/roadmap/project-roadmap.md` (Phase 2 M2.4), `docs/roadmap/current-phase.md` (Phase 2 M2.3 IN PROGRESS)
**Entry**: M2.3 unified role↔descriptor↔binding integration handoff created (4 confirmed mappings, 4 priority gaps)

**Roadmap Reference**: This prep supports **M2.4** — the final milestone of Phase 2. Per the roadmap: "Pass key NiDataStream promotion gates (or document exactly why they remain blocked)."

**Anti-drift**: M2.4 evaluates promotion readiness against existing evidence; it does NOT set promotion flags or modify parser/export code. Candidate-only throughout. All work references Phase 2 M2.1-M2.3 evidence.

## Objective

Evaluate the NiDataStream promotion gate landscape against Phase 2 accumulated evidence (M2.1-M2.3). For each gate, determine:

- **Advanceable**: Evidence from M2.1-M2.3 moves the gate closer to pass
- **Still blocked**: Evidence is insufficient; document exactly why
- **Partially addressed**: Evidence narrows the gap but doesn't close it

Produce a clear, per-gate status table with rationale grounded in M2.1-M2.3 findings.

## Current Gate Status (Pre-M2.4)

From live `nidatastream-promotion-status` and `nidatastream-descriptor-proof-status`:

| Gate | Status | Blocks |
|---|---|---|
| `descriptor-field-order-proof` | candidate | ✅ yes |
| `descriptor-semantic-map` | blocked | ✅ yes |
| `descriptor-table-sample-proof` | candidate | ✅ yes |
| `sample-byte-agreement` | candidate | ✅ yes |
| `pairing-impact-proof` | candidate | ✅ yes |
| `narrow-parser-patch` | blocked | ✅ yes |

> **Note**: The current proof-status output labels byte-0 as "static table index." M2.1's per-block-embedded finding challenges this interpretation — byte-0 is more accurately described as an **inline descriptor field** (stream-type enumerator), not a table lookup index. The per-gate evaluation below addresses this reclassification.

**Flags**: `ParserExportPromotionAllowed = false`, `FieldOrderPromoted = false`

**Descriptor bytes**: Byte-0 = "static table index" (mapped), Bytes 1-3 = unmapped (1 core blocker: `descriptor-record-bytes-1-3-unmapped`)

## Phase 2 Evidence Inventory (M2.1-M2.3)

### M2.1: Descriptor Mapping

| Finding | Relevance to promotion |
|---|---|
| Descriptors are **per-block embedded** (4 bytes at offset 24), not a static table | Challenges the "static table index" interpretation for byte-0. Byte-0 is an **inline descriptor field** — possibly a stream-type enumerator, not a table lookup index. |
| `37 04 03 00` = 90/184 (49%) — generic ror1-float-stream descriptor | Confirms one descriptor pattern has a clear semantic: "ror1-float data." Role differentiation is NOT in the descriptor — it comes from Usage/Access. |
| Byte-3 always 0x00 across 184 sampled blocks | Confirms byte-3 is padding/reserved/sign-guard — universal invariant. |
| 5 distinct descriptor patterns; 4 remain role-unverified | Semantic mapping for patterns `36 04 02 00`, `15 02 01 00`, `10 01 04 00`, `3c 01 04 00` remains incomplete. |
| Descriptor-sample-compare: 10 blocking items remain | Structured gap list exists; none resolved in M2.1-M2.3. |

### M2.2: Binding Proofs

| Finding | Relevance to promotion |
|---|---|
| 329: 12/12 IDs × 6 bindings — source-binding reuse confirmed | Binding architecture is proven at scale for one family. Parser could use binding data to route streams to mesh attributes. |
| 305: 4 bindings — same reuse pattern | Cross-family validation of binding semantics. |
| All ror1-float streams → `37 04 03 00` regardless of role | Descriptor is not role-specific — semantic mapping must account for this. |
| Cross-family: siblings diverge on secondary streams | Parser must handle sibling-specific stream routing. |

### M2.3: Integrated Mapping

| Finding | Relevance to promotion |
|---|---|
| 3-way mapping (role↔descriptor↔block↔mesh attr) confirmed for 4 bindings | Core structural evidence ready for consumption. |
| 4 priority gaps: `36 04 02 00` (27% of sample), blocks #55/#57, `15 02 01 00`, `10`/`3c` patterns | Remaining descriptor semantics unmapped. |
| `37 04 03 00` ↔ position/normal/UV across two families | Strong positive evidence for one pattern. |

## Per-Gate Evaluation

### 1. descriptor-field-order-proof (currently: candidate)

**M2.1-M2.3 contribution**: Significant. M2.1 established that the descriptor is 4 bytes embedded at offset 24, not a static table. Byte-0 is an inline field. Byte-3 is universal zero. Bytes 1-2 vary but their semantics are not yet decoded.

**Advanceable?** **Partially**. The per-block-embedded finding is a solid structural fact. But 4 of 5 descriptor patterns have no verified role, and bytes 1-2 remain unmapped for parser semantics. The field order is structurally known (4 bytes at offset 24), but the field semantics are incomplete.

**Gap**: What do bytes 1-2 encode? (Component count? Stride? Element size? Encoding flags?) Without this, the field order is known but not semantically proven.

**Recommendation**: Document field-order structural facts; keep gate at candidate. Byte-0 reinterpretation (inline descriptor field vs table index) should be noted.

### 2. descriptor-semantic-map (currently: blocked)

**M2.1-M2.3 contribution**: Moderate. One pattern (`37 04 03 00`) has a clear semantic: "ror1-float data stream." The pattern spans position/normal/UV — it means float-data, not a specific role. The other 4 patterns have no verified semantics.

**Advanceable?** **Still blocked**. Semantic mapping requires: "what does each byte/field mean for the parser?" Only byte-3 has a clear, universal meaning (zero/padding). Byte-0 may differentiate stream data types (float vs uint vs index). Bytes 1-2 are completely opaque.

**Gap**: 4/5 patterns semantically unmapped; byte-1, byte-2 semantics unknown; no formal semantic mapping document or schema.

**Recommendation**: Keep blocked. Document the one semantic fact (byte-3=0x00 universal) and the `37 04 03 00` = ror1-float correlation. Note that even if byte-0 is reclassified as a stream-type field, its exact enumeration values are not mapped.

### 3. descriptor-table-sample-proof (currently: candidate)

**M2.1-M2.3 contribution**: Transformative. M2.1's base-model review found ALL static bytes zero at Ghidra addresses. Combined with the per-block-embedded finding, this gate's premise shifts: the "table sample" is maybe the wrong model. There IS no static descriptor table — descriptors are inline per-block.

**Advanceable?** **Gate premise challenged**. If descriptors are per-block embedded, the "descriptor-table" concept may be a Ghidra artifact (a static allocation that's normally zero-initialized, with per-block records written at runtime). The gate as currently defined (table sample proof) may need to be redefined or replaced.

**Recommendation**: Document the per-block-embedded evidence. Note that the static-table model is falsified by M2.1 (all-zero at static addresses). Reclassify this gate as needing redefinition in a future proof cycle.

### 4. sample-byte-agreement (currently: candidate)

**M2.1-M2.3 contribution**: Moderate. The 184-block ShiftedSamples corpus shows internal consistency (5 patterns, byte-3 always 0x00). But the sample corpus is only 0.6% of the full copied set (184/31,777). No cross-corpus validation against a larger sample.

**Advanceable?** **Partially**. Internal consistency is shown for the 8-file sample. Scale validation is missing. Semantic mapping is not ready.

**Recommendation**: Keep at candidate. Note the 184-block internal consistency. Flag the low sample coverage (0.6%). The `inventory-nif-mesh-bindings --full` command could provide scale validation.

### 5. pairing-impact-proof (currently: candidate)

**M2.1-M2.3 contribution**: Strong. M2.2 binding proofs show that siblings (#7/#34 in 329, #7/#27 in 305) share position blocks. The binding reuse pattern is confirmed across families. M2.3 unified mapping shows that the same descriptor serves multiple roles depending on which mesh attribute binds to it.

**Advanceable?** **Partially**. The binding reuse architecture is proven. But "complete groups" (position + normal + UV + index for one mesh) are still missing because attrSets=0 on sibling meshes blocks normal/UV binding. Parser pairing would need to handle incomplete bindings.

**Recommendation**: Document the binding reuse proof. Keep gate at candidate. Note that the positive impact (proven binding architecture) is offset by the negative impact (no complete groups exist due to attrSets=0).

### 6. narrow-parser-patch (currently: blocked)

**M2.1-M2.3 contribution**: None. No parser/export code changes have been made or proposed. This gate tracks whether parser behavior has been modified to consume NiDataStream evidence.

**Advanceable?** **Still blocked**. No parser changes. No targeted tests. No decision record.

**Recommendation**: Keep blocked. This is the intentional safety brake. It should only be addressed in Phase 3+ after all other gates advance significantly.

## Summary: Which Gates Could Advance?

| Gate | Pre-M2.4 status | Post-M2.4 assessment | Evidence from Phase 2 |
|---|---|---|---|
| `descriptor-field-order-proof` | candidate | **candidate (enhanced)** | 4-byte structure at offset 24 confirmed; byte-3=0x00 universal; byte-0 reinterpreted as inline field |
| `descriptor-semantic-map` | blocked | **blocked** | One partial semantic (ror1-float); 4 patterns unmapped; bytes 1-2 opaque |
| `descriptor-table-sample-proof` | candidate | **candidate (reclassified)** | Per-block-embedded evidence challenges static-table model; gate premise needs redefinition |
| `sample-byte-agreement` | candidate | **candidate (scoped)** | 184-block internal consistency; 0.6% sample coverage; scale validation pending |
| `pairing-impact-proof` | candidate | **candidate (strengthened)** | Binding reuse proven; no complete groups exist (attrSets=0 limitation) |
| `narrow-parser-patch` | blocked | **blocked (unchanged)** | No parser changes; safety brake intentionally held |

**Bottom line**: Phase 2 evidence strengthens 3 gates (field-order, sample-byte, pairing-impact), reclassifies 1 gate (table-sample), and leaves 2 unchanged (semantic-map, narrow-parser-patch). 0 gates can be cleared to pass. The core blockers are:

1. Bytes 1-2 descriptor semantics unknown (blocks semantic-map)
2. 4/5 descriptor patterns have no verified role (blocks field-order-proof)
3. No parser implementation exists (blocks narrow-parser-patch by design)
4. `FieldOrderPromoted` and `ParserExportPromotionAllowed` must remain false

## Commands

```bash
# Refresh promotion status for M2.4 handoff
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
# CI
ruff check scripts/ && mypy scripts/ --no-error-summary
```

## Deliverables

- [ ] `docs/roadmap/phase2-m2.4-prep.md` (this file)
- [ ] `docs/handoffs/draft-2026-06-m2.4-promotion-gate-evaluation.md`
- [ ] Per-gate evaluation table (6 gates assessed against M2.1-M2.3 evidence)
- [ ] Updated current-phase.md (M2.4 IN PROGRESS)
- [ ] Updated `docs/post50-parser-export-promotion-readiness-checklist.md` with Phase 2 evidence summary

## Validation Gates

- [ ] All 6 promotion gates evaluated against M2.1-M2.3 evidence
- [ ] No gate advanced to "pass" without clear evidence
- [ ] `FieldOrderPromoted` explicitly confirmed still false
- [ ] `ParserExportPromotionAllowed` explicitly confirmed still false
- [ ] Per-block-embedded finding correctly reflected in gate reclassification
- [ ] Gaps documented for each blocked/partially-advanced gate
- [ ] Candidate-only language throughout
- [ ] CI green

---

See `docs/roadmap/project-roadmap.md` (Phase 2), `docs/handoffs/draft-2026-06-m2.3-role-descriptor-integration.md`, `docs/nidatastream-promotion-readiness-checklist.md`, `docs/post50-parser-export-promotion-readiness-checklist.md`.
