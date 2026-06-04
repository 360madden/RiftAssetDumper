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

> **Note**: NiDataStream-specific promotion gates (6 blockers: `descriptor-field-order-proof`, `descriptor-semantic-map`, `descriptor-table-sample-proof`, `sample-byte-agreement`, `pairing-impact-proof`, `narrow-parser-patch`) are tracked in `nidatastream-promotion-status`. See M2.4 handoff for per-gate evaluation. `FieldOrderPromoted` is tracked in `nidatastream-descriptor-proof-status`.

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

## Current decision

No parser/export promotion is allowed from the current evidence. Phases 1-6 are all
complete or active. 0 promotion gates have been cleared across two formal evaluations
(M2.4 and M6.2). Gate 3 (`descriptor-table-sample-proof`) is recommended for retirement
as obsolete (per-block-embedded is the production architecture). Both promotion flags
must remain false.
