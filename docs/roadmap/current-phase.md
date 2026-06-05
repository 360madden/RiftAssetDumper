# Current Active Phase & Milestone

**Last Updated**: 2026-06 (Phase 15.5 ✅; Z-source confirmed as mesh transform, not separate stream)

---

## Current State

**Phase 10: Human Review Gates + Final Promotion** — **COMPLETE** ✅  
**Phase 13: Descriptor Consistency Proof Guard** — **COMPLETE** ✅

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
| 3 | **M11.3**: Disambiguate float3-generic sub-roles + discover new position sources | ✅ Complete | **546 descriptor→role mismatches found** (458 float2→position, 88 float2→normal). M11.4 reframes: float2 positions are valid encoding, not errors. |
| 4 | **M11.4**: Validate descriptor roles against existing OBJ exports | ✅ Complete | **82 OBJ IDs matched**. 63% of OBJ positions use `descriptor-float2-uv` (float2 encoding). 37% use `descriptor-float3-generic`. Descriptor correctly identifies stream element format; role disambiguation requires data inspection. |
| 5 | **M11.5**: Exit handoff | ✅ Complete | `docs/handoffs/2026-06-phase11-exit-descriptor-guided-role-classification.md` |

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
| **Phase 11** | **Descriptor-Guided Role Classification** | **M11.1-M11.5** | **0** | **✅ COMPLETE** |
| **Phase 12** | **Unknown Descriptor Discovery** | **M12.1-M12.3** | **0** | **✅ COMPLETE** |

| **Phase 13** | **Descriptor Consistency Proof Guard** | **M13.1-M13.3** | **0** | **✅ COMPLETE** |
| **Phase 14** | **Inventory Refresh + Baseline Update** | **M14.1-M14.2** | **0** | **✅ COMPLETE** |
| **Phase 15** | **Float2 Position Encoding Investigation** | **M15.1-M15.4** | **0** | **✅ COMPLETE** |
| **Phase 15.5** | **Float2 Z-Source Resolution** | **Z-source analysis** | **0** | **✅ COMPLETE** |

**Project totals**: 16 phases complete, 7 gates cleared, 6 descriptor patterns proven, 8 proof guards.

### Phase 15 Key Finding

**Float2 position encoding confirmed.** 51/71 (72%) OBJ-exported position streams use `descriptor-float2-uv`
(8 bytes/vertex = XY pairs). 20/71 (28%) use `descriptor-float3-generic` (12 bytes/vertex = XYZ).
Float2 positions produce valid 3D OBJ vertices with real Z values — Z is sourced from a separate
stream, mesh transform, or computed. Raw data requires endian-aware decoding (big-endian prevalent).

### Phase 15.5 Z-Source Resolution

**CORRECTED Finding: Z is sourced from sibling position pairing, not mesh transform.**

Full stream inventory analysis of 36 float2-position meshes (156 streams):
- **48 position streams, ALL float2** — zero float3 position streams co-resident
- **No companion Z-stream exists** in any of the 36 meshes
- **Stream composition**: 48 pos + 42 index + 33 normal + 7 UV + 26 other

**Probe verification** (mesh `4768bc6e3cfaabd0` MB=6):
- Probe reveals only **3 streams**: normal (float3 @216), index (uint16 @292), UV (float2 @300)
- **No position stream exists in this mesh's direct data**
- Position is resolved through **legacy pairing** (2 pairings, 95% confidence)
- The `--experimental-position-source` code uses `NifPositionSourceSiblingAccumulator`
  to find a sibling mesh with full XYZ data and pair it with this mesh's XY data

**OBJ Z-value verification** (36 vertices):
- Z range: [-0.9260, 0.9351] (range = 1.8612, significant variation)
- Only **9 unique Z values** out of 36 — consistent with sibling-pair mapping
  (sibling has different vertex count; pairing maps vertices across meshes)

**Mechanism**:
1. Float2-position meshes store XY data only (8 bytes/vertex, descriptor-float2-uv)
2. These meshes lack attribute sets — they have NO direct position stream
3. The OBJ exporter (`--experimental-position-source`) uses sibling pairing:
   - `NifPositionSourceSiblingAccumulator` groups related meshes
   - `NifPositionSourceSiblingGroup` pairs meshes that share source bindings
   - The sibling provides full XYZ data that fills in the Z values
4. The heuristic classifier's `position-float3-lead` label reflects the PAIRED result, not raw data
5. The descriptor's `descriptor-float2-uv` correctly identifies the raw stream format

This is a **sophisticated encoding**: position data is split across sibling meshes
as XY + Z, with Z sourced from a different mesh's full float3 stream. The pairing
system reconstructs 3D positions by cross-referencing mesh siblings.

See: `scripts/analyze_z_source.py` (reusable analysis script).
See: `Exports/phase15.5-z-source-analysis.txt` for per-mesh breakdown (local/ignored).

### Phase 14 Refresh Results

| Metric | Before (Phase 11) | After (Phase 14) | Delta |
|---|---|---|---|
| DescriptorGuidedRole count | 4,045 | **4,076** | +31 (08010400) |
| Hard errors | 530 | 530 | 0 |
| Warnings | 107 | 107 | 0 |
| Ambiguous | 3,407 | **7,515** | +4,108 (improved counting) |
| Total described streams | 4,044 | **8,152** | +4,108 |

Note: The Phase 11 baseline only counted streams with BOTH DescriptorGuidedRole AND PrimaryRole. 
The Phase 14 baseline counts ALL PrimaryRole entries, including those without descriptors. 
The 08010400 addition correctly captures all 31 previously unknown streams.

See individual exit handoffs under `docs/handoffs/2026-06-m*.*-phase*-exit-consolidation.md`.