# Current Active Phase & Milestone

**Last Updated**: 2026-06 (Phase 11 ACTIVE — M11.1 ✅ M11.2 ✅ M11.3 ✅; 546 clear mismatches found; 458 float2→position classification errors)

---

## Current State

**Phase 10: Human Review Gates + Final Promotion** — **COMPLETE** ✅  
**Phase 11: Descriptor-Guided Stream Role Classification** — **ACTIVE** 🔄

### Gate Landscape (ALL 7 CLEARED — from Phase 10)

| Gate | Status | Cleared By |
|---|---|---|
| `descriptor-per-block-consistency` | **CLEARED** ✅ | M7.1 |
| `descriptor-field-order-confirmed` (1a) | **CLEARED** ✅ | M7.2 |
| `sample-byte-agreement` (4) | **CLEARED** ✅ | M7.3 |
| `descriptor-field-semantics-complete` (1b) | **CLEARED** ✅ | M9.1 |
| `descriptor-semantic-map` (2) | **CLEARED** ✅ | M9.3 |
| `pairing-impact-proof` (5) | **CLEARED** ✅ | M10.1 |
| `narrow-parser-patch` (6) | **CLEARED** ✅ | M10.2 |
| ~`descriptor-table-sample-proof`~ (3) | RETIRED | M7.1 |

**Both flags**: `FieldOrderPromoted=true`, `ParserExportPromotionAllowed=true`

### Descriptor Subsystem (Proven Complete)

- 4/4 descriptor bytes identified (family, element width, component count, padding)
- 5/5 patterns mapped to roles (3 specific + 2 family-level, 0 unmapped)
- Stride→usage rule proven: uint16×scalar → index, everything else → vertex
- 58 code lines, 49 tests, 0 regressions, no Ghidra required

---

## Next Actions (Phase 11)

| # | Action | Status | Reference |
|---|---|---|---|
| 1 | **M11.1**: Extend inventory to emit descriptor-classified roles | ✅ Complete | Commit `2b848c9` + `291ffe4` (tests) — `ClassifyNifDescriptorRole` + `DescriptorGuidedRole` wired |
| 2 | **M11.2**: Run population-scale inventory + cross-reference analysis | ✅ Complete | 4,045/8,152 streams (49.6%) classified; cross-ref: only 134 float3-generic→position |
| 3 | **M11.3**: Disambiguate float3-generic sub-roles + discover new position sources | ✅ Complete | **546 clear mismatches**: 458 float2→position (cannot be positions), 88 float2→normal (cannot be normals). 1,180 float3→normal + 614 float3→uv ambiguous (need data inspection). Descriptor as consistency check on heuristic. |
| 4 | **M11.4**: Validate descriptor roles against existing OBJ exports | ⏳ Pending | 94 OBJs, 65 faced |
| 5 | **M11.5**: Exit handoff | ⏳ Pending | `docs/handoffs/` |

---

## Active Focus Rules

- Stay within stream role classification — no new export formats or archive format changes
- Every C# change must be additive (new fields/reports, not behavioral changes to existing decode paths)
- Heuristic classifier remains as fallback — descriptor-guided is supplementary
- Both promotion flags remain true (already cleared)
- One lead at a time per Aggressive Evidence Workflow

---

## Phase History

| Phase | Name | Milestones | Gates Cleared | Status |
|---|---|---|---|---|
| Phase 1 | Position Source Family Proof | M1.1-M1.5 | N/A | ✅ |
| Phase 2 | Descriptor & Binding Proof | M2.1-M2.5 | 0 | ✅ |
| Phase 3 | Descriptor Propagation | M3.1-M3.5 | 0 | ✅ |
| Phase 4 | Descriptor-Aware Parser | M4.1-M4.6 | 0 | ✅ |
| Phase 5 | Descriptor-Guided Parser | M5.1-M5.5 | 0 | ✅ |
| Phase 6 | Descriptor-Validated Export | M6.1-M6.4 | 0 | ✅ |
| Phase 7 | Promotion Gate Clearance | M7.1-M7.5 | **3** | ✅ |
| Phase 8 | Semantic Gate Clearance | M8.2, M8.4 | 0 | ✅ |
| Phase 9 | Final Clearance + Consolidation | M9.0-M9.4 | **2** | ✅ EXITED |
| Phase 10 | Human Review + Final Promotion | M10.1-M10.2 | **2** | ✅ COMPLETE |
| **Phase 11** | **Descriptor-Guided Role Classification** | **M11.1-M11.5** | **0** | **🔄 ACTIVE** |

**Project totals**: 10 phases complete, 7 gates cleared. Phase 11 in progress.

See individual exit handoffs under `docs/handoffs/2026-06-m*.*-phase*-exit-consolidation.md`.