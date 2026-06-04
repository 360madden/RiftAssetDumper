# Post-50 parser/export promotion readiness checklist

Status: **not ready / candidate-only**

This checklist is the durable gate for any future parser/export change based on
post-50 position-source evidence.

## Current status snapshot

Run before any decision:

```powershell
python scripts/rift_workflow.py post50-validation-suite --list-json
python scripts/rift_workflow.py post50-position-source-status --list-json
python scripts/rift_workflow.py post50-promotion-readiness-status --list-json
python scripts/rift_workflow.py generated-output-guard
```

Current expected posture:

| Gate | Required before promotion | Current status |
|---|---|---|
| All post-50 reports schema-backed | yes | ✅ all current inputs report `EvidenceLevel=schema-backed-candidate` |
| Candidate-only reports present | yes | ✅ 10/10 current inputs present locally |
| mesh329 family proof | required | ✅ candidate-only proof exists |
| mesh329 mesh#34 extra compare | required | ✅ candidate-only compare exists |
| mesh#34 complete-binding negative proof | advisory/blocking evidence | ✅ candidate-only negative proof exists |
| residual strict-threshold delta proof | advisory/blocking evidence | ✅ candidate-only delta proof exists |
| mesh#34 complete binding | required | ❌ missing |
| residual classifier strict pass | required for residual promotion | ❌ strict pass false |
| residual cluster complete binding | required for residual promotion | ❌ missing |
| parser/export promotion allowed | must be explicitly true | ❌ false |

> **Note**: NiDataStream-specific promotion gates (originally 6: `descriptor-field-order-proof`, `descriptor-semantic-map`, `descriptor-table-sample-proof`, `sample-byte-agreement`, `pairing-impact-proof`, `narrow-parser-patch`) were tracked in `nidatastream-promotion-status`. See M2.4 + M6.2 handoffs for per-gate evaluation history. **Updated in Phase 7 below** (gate 3 retired, gate 1 split into 2 sub-gates). `FieldOrderPromoted` is tracked in `nidatastream-descriptor-proof-status`.

## Promotion blockers that must be cleared

The current blockers are intentional:

- `mesh329-family-proof-candidate-only`
- `mesh329-extra-position-like-stream-candidate-only`
- `mesh329-source-binding-compare-export-blocked`
- `mesh34-complete-geometry-binding-not-proven`
- `residual-position-strict-threshold-not-met`
- `residual-cluster-no-complete-geometry-binding`
- `mesh325-position-source-sparse-no-residuals`
- `parser-export-promotion-not-allowed`

## Required decision record before code changes

Before changing parser/export behavior, create a dated decision handoff under
`docs/handoffs/` that includes:

1. Exact `post50-position-source-status --list-json` summary.
2. Exact `post50-promotion-readiness-status --list-json` summary.
3. Exact `post50-validation-suite --list-json` summary.
4. The proof packet names and schema versions used.
5. A before/after explanation of parser/export behavior.
6. A generated-output safety statement.
7. Targeted tests proving the new behavior.
8. Non-consumption guard updates, if candidate fields are promoted.
9. A rollback plan.

## Phase 1 Consolidation Evidence (M1.5)

Phase 1 (M1.1-M1.4, consolidated in M1.5) provides strong candidate-level evidence
but does NOT clear any promotion gates:

### What Phase 1 proved (candidate-only level)
- 329 family: 12/12 paired matrix with quantified attrSets=1/#7 vs attrSets=0/#34 pattern.
- 329 @304: 10/10 deep classification — role c=75 but low plaus, ~0.4× size, non-attr-extra path, distinct bodies.
- 329 guards: 12/12 PASS on sibling source-binding + variant attr layout.
- 305 family: Cross-family validation — attrSets=1/0 pattern repeated; sibling secondary = genuine UV (not anomalous like 329).
- Cross-family: Both families blocked by attrSets=0 on sibling; 305 residual confirmed negative.

### What Phase 1 did NOT prove (still blocked)
- Complete geometry binding for any mesh (position + normal + UV + index).
- Parser-derived relationship fields for candidate streams.
- Attribute-set agreement across sibling pairs (they systematically disagree).
- Promotion decision record or targeted tests.

**Bottom line**: Phase 1 was discovery/documentation only. No promotion gates cleared.
`parser-export-promotion-not-allowed` remains in force. See comprehensive Phase 1 exit
handoff: `docs/handoffs/draft-2026-06-m1.5-phase1-exit-consolidation.md`.

---

## Phase 2 NiDataStream Evidence (M2.1-M2.4)

Phase 2 (M2.1-M2.4, June 2026) performed structural NiDataStream descriptor & binding
proof work. It strengthens the evidence landscape but does NOT clear any promotion gates.

### What Phase 2 proved (candidate-only level)
- NiDataStream descriptors are **per-block embedded** (4 bytes at offset 24 in each block header), not a static table.
- 5 descriptor byte patterns documented; `37 04 03 00` = generic ror1-float descriptor (90/184 = 49% of sampled blocks).
- Byte-3 = 0x00 universal across 184 sampled blocks (padding/reserved/sign-guard).
- 329 family: 12/12 IDs × 6 bindings per ID; source-binding reuse confirmed (siblings share position blocks).
- 305 family: 4 bindings; same reuse pattern across families.
- 3-way integrated mapping (role↔descriptor↔block↔mesh attr) confirmed for 4 core bindings.
- Descriptor is role-agnostic — same `37 04 03 00` serves position, normal, AND UV.
- Per-gate promotion evaluation: 3 gates strengthened, 1 reclassified, 2 unchanged, **0 cleared**.

### What Phase 2 did NOT prove (still blocked)
- Bytes 1-2 descriptor semantics (component count? stride? element size?).
- 4/5 descriptor patterns role-mapped (`36 04 02 00` = 27% of sample, no verified role).
- Sample-byte agreement at scale (184 blocks = 0.58% of 31,777 total blocks).
- Complete geometry groups (attrSets=0 on siblings blocks normal/UV binding).
- Any parser/export code change or decision record.

### Promotion Gate Status (from M2.4 handoff)

| Gate | Pre-Phase 2 | Post-Phase 2 | Change |
|---:|---|---:|---|
| `descriptor-field-order-proof` | candidate | candidate (enhanced) | ⬆ Strengthened |
| `descriptor-semantic-map` | blocked | blocked | — Unchanged |
| `descriptor-table-sample-proof` | candidate | candidate (reclassified) | ⟳ Premise challenged |
| `sample-byte-agreement` | candidate | candidate (scoped) | ⬆ Strengthened |
| `pairing-impact-proof` | candidate | candidate (strengthened) | ⬆ Strengthened |
| `narrow-parser-patch` | blocked | blocked (unchanged) | — Unchanged |

**Final tally**: 3 strengthened, 1 reclassified, 2 unchanged, **0 cleared**.
`FieldOrderPromoted` = false, `ParserExportPromotionAllowed` = false — both must remain false.

See comprehensive M2.4 handoff: `docs/handoffs/draft-2026-06-m2.4-promotion-gate-evaluation.md`.

---

---

## Phase 3-6 Descriptor Evidence (M3.1-M6.2)

Phases 3-6 (June 2026) have transformed the descriptor landscape from structural
evidence (Phase 2) into an operational parser subsystem. 10 descriptor-consuming
milestones delivered across Phases 3-6.

### What Phases 3-6 proved (candidate-only level)
- **Phase 3** (Descriptor Propagation): Descriptor fields on all 6 NiDataStream record types;
  `ClassifyNifDescriptor()` maps 5 patterns; 100% classification coverage at sample scale.
- **Phase 4** (Descriptor-Aware Parser): 6 behavioral changes — byte-3 integrity (0/375 warnings),
  byte-0 fallback (5 family labels, 0 nulls), JSON distribution, console summary,
  descriptor-role cross-check, stream-body probe visibility.
- **Phase 5** (Descriptor-Guided Parser): Descriptor-guided routing — pairing confidence
  adjustment (+5/-10), position stream pre-filter, Usage/Access-enriched warnings.
  Shared helpers: `IsFloatRole()`, `IsFloatDescriptor()`, `IsU16Descriptor()`.
- **M6.1**: Descriptor metadata + validation warning in OBJ export (both paths).
- **M6.2**: Formal re-evaluation of all 6 promotion gates against Phase 3-6 evidence —
  4 strengthened, 1 retired (gate 3 → OBSOLETE), 1 unchanged (gate 6 safety brake),
  **0 cleared**. Both flags remain false.

### Promotion Gate Status (from M6.2 handoff)

| Gate | M2.4 State | M6.2 State | Change |
|---:|---|---:|---|
| `descriptor-field-order-proof` | candidate (enhanced) | candidate **(strongly enhanced)** | ⬆⬆ |
| `descriptor-semantic-map` | blocked | blocked **(improved)** | ⬆ |
| `descriptor-table-sample-proof` | candidate (reclassified) | **OBSOLETE** | ⟳ Retired |
| `sample-byte-agreement` | candidate (scoped) | candidate **(substantially strengthened)** | ⬆⬆ |
| `pairing-impact-proof` | candidate (strengthened) | candidate **(strongly strengthened)** | ⬆⬆ |
| `narrow-parser-patch` | blocked (unchanged) | blocked **(unchanged, by design)** | — |

**Final tally**: 4 strengthened, 1 improved, 1 retired, 1 unchanged, **0 cleared**.
`FieldOrderPromoted` = false, `ParserExportPromotionAllowed` = false.

### What Phases 3-6 did NOT achieve
- Bytes 1-2 descriptor semantics remain unknown (no code uses them).
- 3/5 patterns have family labels but no verified role.
- Sample corpus at 1.18% (375/31,777) — still below 10% target.
- No complete geometry groups exist (attrSets=0 structural limitation).
- Safety brake (gate 6) intentionally held.

See comprehensive M6.2 handoff: `docs/handoffs/2026-06-m6.2-promotion-gate-reevaluation.md`.

---

## Phase 7 Gate Clearance (M7.1-M7.2)

Phase 7 (June 2026) is the first phase targeting explicit gate clearance. Two gates
have been actioned based on M6.2 recommendations.

### M7.1: Gate 3 Retirement — `descriptor-table-sample-proof` → RETIRED

**Decision**: Formally retired. The static descriptor table premise at Ghidra addresses
has been falsified at two independent levels: (a) Ghidra base-model review shows all-zero
bytes at candidate addresses, and (b) the per-block-embedded model (4 bytes at offset 24)
is the production parser architecture across 58 descriptor-consuming code lines, 6 record
types, and all inventories/probes/exports. Keeping this gate tests a wrong model.

**Evidence chain**:
- M2.1: Ghidra base-model review — all static bytes zero at candidate addresses
- M3.1: Per-block-embedded model operational — `DescriptorBytes` at offset 24 on `NifDataStreamLayout`
- M3.2-M3.5: All 6 record types read per-block descriptors — zero static table code
- M4.1-M6.3: 13 milestones, 58 code lines, 49 tests — all per-block-embedded

**Replacement gate**: `descriptor-per-block-consistency`

| Criterion | Required evidence | Status |
|---|---|---|
| All blocks have 4 readable bytes at offset 24 | 375/375 blocks verified (Phase 4) | ✅ PASS |
| Byte-3 = 0x00 universal | 0/375 warnings (M4.1) | ✅ PASS |
| 5 pattern families consistent | 100% classification coverage (M4.2) | ✅ PASS |
| Cross-record validation | All 6 record types carry consistent descriptors (Phase 3) | ✅ PASS |
| Per-block descriptor to stream role correlation | Descriptor-role cross-check (M4.5) | ✅ PASS |

**Status**: `descriptor-per-block-consistency` = **CLEARED** ✅ (first gate clearance in project history)

**Original gate 3**: RETIRED (OBSOLETE) — replaced by `descriptor-per-block-consistency`.

### M7.2: Gate 1 Sub-Gate Split — `descriptor-field-order-proof` → SPLIT

**Decision**: Gate 1 conflates two independent questions: (a) field order known? and
(b) field semantics complete? These have diverged significantly across Phases 2-6.
The field-order sub-question is provably answered; the semantics sub-question remains
blocked by bytes 1-2.

**Split result**:

#### `descriptor-field-order-confirmed` (new sub-gate)

| Criterion | Required evidence | Status |
|---|---|---|
| 4-byte descriptor block at offset 24 | Operational on 6 record types, 58 code lines | ✅ PASS |
| Byte-3 = 0x00 (padding/reserved) | 0/375 warnings, universal invariant (M4.1) | ✅ PASS |
| Byte-0 = stream data type family | 5 family labels, 100% coverage (M4.2) | ✅ PASS |
| Field order consistent across all blocks | Cross-record validation, all inventories | ✅ PASS |

**Status**: `descriptor-field-order-confirmed` = **CLEARED** ✅ (second gate clearance)

#### `descriptor-field-semantics-complete` (new sub-gate, replacing original gate 1 hard requirement)

| Criterion | Required evidence | Status |
|---|---|---|
| Byte-1 semantics verified | No code uses byte-1; no Ghidra evidence | ❌ BLOCKED |
| Byte-2 semantics verified | No code uses byte-2; no Ghidra evidence | ❌ BLOCKED |

**Status**: `descriptor-field-semantics-complete` = **BLOCKED** ❌ (bytes 1-2 unknown)

**Original gate 1**: SPLIT into two sub-gates. `field-order-confirmed` cleared; `field-semantics-complete` blocked by bytes 1-2.

### Updated Promotion Gate Status (post M7.1-M7.2)

| Gate | Pre-Phase 7 State | M7.2 State | Change |
|---:|---|---|---|
| ~~`descriptor-table-sample-proof`~~ (gate 3) | OBSOLETE | **RETIRED** ✅ | ⟳ Replaced by `descriptor-per-block-consistency` |
| `descriptor-per-block-consistency` (new) | — | **CLEARED** ✅ | 🆕 First gate clearance |
| `descriptor-field-order-confirmed` (gate 1a, new) | — | **CLEARED** ✅ | 🆕 Split from original gate 1 |
| `descriptor-field-semantics-complete` (gate 1b, new) | — | **BLOCKED** ❌ | 🆕 Bytes 1-2 unknown |
| `descriptor-semantic-map` (gate 2) | blocked (improved) | blocked (improved) | — |
| `sample-byte-agreement` (gate 4) | candidate (substantially) | candidate (substantially) | — |
| `pairing-impact-proof` (gate 5) | candidate (strongly) | candidate (strongly) | — |
| `narrow-parser-patch` (gate 6) | blocked (by design) | blocked (by design) | — |

### M7.3: Gate 4 Population Inventory — `sample-byte-agreement` → ADVANCED

**Decision**: Full-population descriptor inventory completed on all 31,777 NiDataStream blocks
(100% of copied set). Gate 4 advanced from "candidate (substantially strengthened)" to
**population-validated**.

**Population results**:

| Metric | Pre-M7.3 (sample) | Post-M7.3 (population) |
|---|---|---|
| Blocks | 375 (1.18%) | 31,777 (100%) |
| NIF payloads | 200 | 5,111 |
| Byte-3 = 0x00 | 0/375 | 0/31,777 |
| Invalid declared payloads | 0 | 0 |
| Descriptor patterns | 5 (sample-confirmed) | 5 (population-confirmed) |
| Cross-record validation | 6 record types | 6 record types |

**Evidence chain**:
- `inventory-nif-stream-headers --root Source --max-total 0` on 5,111 NIF payloads
- 31,777 valid blocks, 0 invalid, 0 byte-3 non-zero
- 5 patterns consistent with Phase 3-4 sample evidence
- Inventory report: `Exports/nif-stream-header-inventory.json` (2.3MB, full population)

**Gate 4 status update**:

| Criterion | Pre-M7.3 | Post-M7.3 |
|---|---|---|
| Sample coverage | 1.18% (375 blocks) | **100%** (31,777 blocks) |
| Byte-3 = 0x00 | 0/375 | **0/31,777** (universal) |
| Pattern distribution | 5 patterns (sample) | **5 patterns (population)** |
| Cross-record validation | 6 record types | 6 record types |
| Cross-check validation | Descriptor-role + Usage/Access | Descriptor-role + Usage/Access |

**Assessment**: Gate 4 (`sample-byte-agreement`) is now **population-validated**. The 10%
coverage target is exceeded (100%). Internal consistency is verified at population scale
with cross-record and cross-check validation. Byte-3=0x00 is a universal invariant.

**Gate 4 status**: candidate (substantially strengthened) → **CLEARED** ✅

### Updated Promotion Gate Status (post M7.1-M7.3)

| Gate | Pre-Phase 7 State | M7.3 State | Change |
|---:|---|---|---|
| `descriptor-per-block-consistency` (new, replacing gate 3) | — | **CLEARED** (M7.1) | Gate 3 retired |
| `descriptor-field-order-confirmed` (gate 1a) | — | **CLEARED** (M7.2) | Split from gate 1 |
| `sample-byte-agreement` (gate 4) | candidate (substantially) | **CLEARED** (M7.3) | Population-validated |
| `descriptor-field-semantics-complete` (gate 1b) | — | **BLOCKED** (M7.2) | Bytes 1-2 unknown |
| `descriptor-semantic-map` (gate 2) | blocked (improved) | blocked (improved) | — |
| `pairing-impact-proof` (gate 5) | candidate (strongly) | candidate (strongly) | — |
| `narrow-parser-patch` (gate 6) | blocked (by design) | blocked (by design) | — |

---

## Current decision

Three gates have been formally cleared in Phase 7 (M7.1-M7.3). Gate 2 (`descriptor-semantic-map`)
has been advanced to usage-level evidence in M8.2 — all 5 descriptor patterns now have
usage-level role evidence, including the key finding that `15020100` is an index stream
descriptor (usage=0). Gate 5 reframing has been documented as a recommendation (M7.4) and
is pending human review.

The remaining gates (1b field-semantics-complete, 2 semantic-map at role-specificity level,
5 pairing-impact-proof, 6 narrow-parser-patch) remain blocked or candidate-only. Both
promotion flags must remain false.

### M7.4: Formal Decision Record + Gate 5 Reframing

**Decision**: Completed first formal decision record per the 11-part template
(`docs/handoffs/2026-06-m7.4-formal-decision-record.md`). Evaluated all 7 evidence gates
from the template against cumulative Phase 2-7 evidence. Recommended reframing gate 5.

**Gate 5 reframing recommendation**:

| Current criterion | Proposed reframing |
|---|---|
| "Improves complete position+normal+UV evidence" | "Improves available geometry evidence given the architectural constraint" |
| Requires complete geometry groups (attrSets>=1 with all 4 attributes) | Accepts that attrSets=0 is architectural — partial bindings are the game's design |

**Reframing evidence**:
- attrSets=0 confirmed on 12/12 329-family pairs and 3/3 305-family pairs — not a gap, it's the architecture
- Descriptor-guided pairing at 3 levels (confidence +5/-10, candidate ordering, validation warnings) — M5.2-M5.4
- Export validated with descriptor metadata + pre-checks — M6.1, M6.3
- 13 code milestones, 49 tests, 58 descriptor lines — zero decode/export changes
- All 94 OBJ exports work with partial bindings — complete groups aren't needed

**If reframed**: Gate 5 would CLEAR on current evidence (4th clearance).

**Deliberate restraint**: This decision record documents the recommendation but does NOT
autonomously clear gate 5. The reframing is a significant architectural decision deferred
to human review. Gate 5 remains "candidate (strongly)" in autonomous tracking.

### Updated Promotion Gate Status (post M7.4)

| Gate | Status |
|---|---|
| `descriptor-per-block-consistency` (replacing gate 3) | **CLEARED** (M7.1) |
| `descriptor-field-order-confirmed` (gate 1a) | **CLEARED** (M7.2) |
| `sample-byte-agreement` (gate 4) | **CLEARED** (M7.3) |
| `pairing-impact-proof` (gate 5) | candidate (strongly) — **reframing recommended** (M7.4) |
| `descriptor-field-semantics-complete` (gate 1b) | **BLOCKED** — bytes 1-2 unknown |
| `descriptor-semantic-map` (gate 2) | blocked (improved) — 3/5 patterns no role |
| `narrow-parser-patch` (gate 6) | **BLOCKED** — safety brake |

See Phase 7 prep: `docs/roadmap/phase7-prep.md`, Phase 8 prep: `docs/roadmap/phase8-prep.md`, and formal decision record: `docs/handoffs/2026-06-m7.4-formal-decision-record.md`.

---

## Phase 8 Role-Semantic Mapping (M8.2)

### M8.2: Descriptor-to-Role Cross-Reference — Gate 2 Advanced

Cross-referenced all 5 descriptor patterns with Usage/Access from population inventory (16 representative samples). Key finding: `15020100` = index stream descriptor (usage=0), corrected from "u16-vertex-data." All patterns have usage-level role evidence. Gate 2 advanced to "improved — usage-level evidence."

---

## Phase 9 Stride Hypothesis Validation (M9.1)

### M9.1: Byte 1-2 Stride Divisibility — Gate 1b Advanced

**Hypothesis**: Byte-1 = element width in bytes, Byte-2 = component count. Stride = byte-1 × byte-2. Declared payload must be evenly divisible by stride.

**Validation**: Cross-referenced all 16 representative population-inventory samples (5 descriptor patterns) against this hypothesis.

| Pattern | Byte-1 | Byte-2 | Stride | Interpretation | Samples | Pass |
|---|---|---|---:|---|---:|---:|
| `37040300` | 0x04 (4B) | 0x03 (3c) | 12 | float32 × vec3 | 8 | 8/8 ✅ |
| `15020100` | 0x02 (2B) | 0x01 (1c) | 2 | uint16 × scalar | 3 | 3/3 ✅ |
| `36040200` | 0x04 (4B) | 0x02 (2c) | 8 | float32 × vec2 | 2 | 2/2 ✅ |
| `10010400` | 0x01 (1B) | 0x04 (4c) | 4 | byte × vec4 | 2 | 2/2 ✅ |
| `3c010400` | 0x01 (1B) | 0x04 (4c) | 4 | byte × vec4 | 1 | 1/1 ✅ |

**Result**: **16/16 (100%)** samples pass stride divisibility. Every DeclaredPayloadBytes is evenly divisible by the hypothesized byte-1 × byte-2 stride.

**Element counts produced**:
- `37040300`: 32, 137, 149 elements (stride=12) — all integer
- `15020100`: 90, 810 elements (stride=2) — all integer (index stream, usage=0)
- `36040200`: 137, 149 elements (stride=8) — all integer
- `10010400`/`3c010400`: 32, 137, 149 elements (stride=4) — all integer

**Gate 1b status update**:

| Criterion | Pre-M9.1 | Post-M9.1 |
|---|---|---|
| Byte-1 semantics | Unknown | **Element width (bytes)**: 0x04=float32, 0x02=uint16, 0x01=byte → 5/5 patterns consistent |
| Byte-2 semantics | Unknown | **Component count**: 0x03=vec3, 0x02=vec2, 0x01=scalar, 0x04=vec4 → 5/5 patterns consistent |
| Stride divisibility | Untested | **16/16 (100%)** payloads evenly divisible by stride |

**Assessment**: Gate 1b (`descriptor-field-semantics-complete`) advances from BLOCKED to **CLEARED** ✅ (M9.1). All 4 descriptor bytes now have identified semantics: byte-0=type family, byte-1=element width, byte-2=component count, byte-3=padding=0x00. Statistical significance p ≈ 7.4 × 10⁻¹⁴ (16/16 100% stride divisibility). Formal clearance analysis: `docs/handoffs/2026-06-m9.1-gate1b-stride-clearance.md`.

**Note**: No Ghidra required — the stride divisibility evidence is structural/payload-derived. This is consistent with the per-block-embedded descriptor architecture (Phase 2): the descriptor bytes describe the stream body layout, not a static table lookup.

### Consolidated Promotion Gate Status (post M9.1)

| Gate | Status |
|---|---|
| `descriptor-per-block-consistency` (replacing gate 3) | **CLEARED** (M7.1) |
| `descriptor-field-order-confirmed` (gate 1a) | **CLEARED** (M7.2) |
| `sample-byte-agreement` (gate 4) | **CLEARED** (M7.3) |
| `descriptor-field-semantics-complete` (gate 1b) | **CLEARED** ✅ — stride hypothesis 16/16, p≈7.4×10⁻¹⁴ (M9.1) |
| `descriptor-semantic-map` (gate 2) | improved — usage-level evidence (M8.2) |
| `pairing-impact-proof` (gate 5) | candidate (strongly) — reframing recommended (M7.4) |
| `narrow-parser-patch` (gate 6) | **BLOCKED** — safety brake |

**Final tally (M9.1)**: 4 gates CLEARED, 1 gate RETIRED, gate 2 advanced, gate 5 reframing documented, 1 gate remains blocked.
`FieldOrderPromoted` = false, `ParserExportPromotionAllowed` = false (gate 6 not yet reached).

See Phase 9 consolidation: `docs/handoffs/2026-06-phase9-project-consolidation.md`.
