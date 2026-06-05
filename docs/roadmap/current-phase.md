# Current Active Phase & Milestone

**Last Updated**: 2026-06 (Phase 35 ✅; targeted probe cluster analysis — MS=321 and MS=325 confirmed via 3 probes; unknowns reduced 101→98)

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
| **Phase 16** | **Sibling Pairing Map** | **Pairing map** | **0** | **✅ COMPLETE** |
| **Phase 17** | **Sibling Pair Verification** | **Probe confirmation** | **0** | **✅ COMPLETE** |
| **Phase 18** | **Comprehensive Sibling Pairing Database** | **Full-inventory scan** | **0** | **✅ COMPLETE** |
| **Phase 19** | **Sibling Pairing Improvements** | **DIST=0 tracking + JSON output** | **0** | **✅ COMPLETE** |
| **Phase 20** | **Cross-Type NIF Verification** | **9 cross-type NIFs analyzed** | **0** | **✅ COMPLETE** |
| **Phase 21** | **Sibling-Aware Batch OBJ Export** | **22 DIST=0 pairs exportable via batch-export-sibling** | **0** | **✅ COMPLETE** |
| **Phase 22** | **Sibling Export Validation** | **22/22 exports ✅ 1,020 vertices, 0 structural issues** | **0** | **✅ COMPLETE** |
| **Phase 23** | **Extended Sibling Export** | **--include-close flag; 142 pairs total; 0-face root cause documented** | **0** | **✅ COMPLETE** |
| **Phase 24** | **Full Sibling Export Run** | **142/142 exports ✅ 127 unique OBJs, 0 structural issues** | **0** | **✅ COMPLETE** |
| **Phase 25** | **Export Manifest** | **scripts/build_export_manifest.py — 142 OBJs catalogued: 94 faced, 48 position-only, 5,360 vertices, 6,682 faces** | **0** | **✅ COMPLETE** |
| **Phase 26** | **Comprehensive Export Manifest** | **259 OBJs across all Exports/, per-MeshSize breakdown, export batch classification** | **0** | **✅ COMPLETE** |
| **Phase 27** | **Bidirectional MeshSize Resolution** | **float3 + probe lookup; 8 IDs resolved; 4 new MeshSizes discovered** | **0** | **✅ COMPLETE** |
| **Phase 28** | **MeshSize 305 Mixed-Family Investigation** | **Root cause: split by mesh block (MB=6,45,46→faced; MB=7,27→pos-only)** | **0** | **✅ COMPLETE** |
| **Phase 29** | **Index Stream Family Map** | **docs/roadmap/index-stream-family-map.md — 11 MeshSize families, per-MB breakdown, key findings** | **0** | **✅ COMPLETE** |
| **Phase 30** | **Float3 Batch Export** | **scripts/batch_export_float3.py — 9/9 exported (6 faced + 3 pos-only), MS=465 MB=7 discovered as faced** | **0** | **✅ COMPLETE** |
| **Phase 31** | **MB=6 Batch Export** | **scripts/batch_export_mb6.py — 36 float2 IDs confirmed position-only; no MB=6/MB=7 blocks exist** | **0** | **✅ COMPLETE** |
| **Phase 32** | **Final Coverage Audit** | **34/34 float3 IDs exported (8 faced + 26 pos-only); pairing map coverage 100% complete** | **0** | **✅ COMPLETE** |
| **Phase 33** | **Full Project Health Sweep** | **ruff ✅ mypy ✅ build 0 errors tests 50/50 ✅ manifest 268 OBJs clean** | **0** | **✅ COMPLETE** |
| **Phase 34** | **Project Summary Document** | **docs/roadmap/project-summary.md — comprehensive overview of all 34 phases** | **0** | **✅ COMPLETE** |
| **Phase 35** | **Targeted Probe Cluster Analysis** | **3 probes resolved MS=321 (414f), MS=325 (318f + 18f); 37 cluster IDs identified** | **0** | **✅ COMPLETE** |
| **Phase 35.5** | **Cluster Inference Resolution** | **13 inferred IDs added to probe lookup; unknowns 101→83 (53 faced, 30 pos-only)** | **0** | **✅ COMPLETE** |

**Project totals**: 37 phases complete, 7 gates cleared, 6 descriptor patterns proven, 8 proof guards.

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

### Phase 16: Concrete Sibling Pairing Map

**Finding: Concrete float2→float3 sibling pairs confirmed across 9 MeshSize families.**

Key sibling pairs (by archive proximity, distance = entry index difference):

| MeshSize | Archive | Float2 Entry | Float3 Entry | Dist | Strength |
|---|---|---|---|---|---|
| 305 | assets.037 | 544 | 544 | **0** | 🟢 Same entry |
| 309 | assets.040 | 1412 | 1412 | **0** | 🟢 Same entry |
| 465 | assets.050 | 861-864 | 864 | **0** | 🟢 Same entry |
| 301 | assets.037 | 819 | 818 | 1 | 🟡 Adjacent |
| 345 | assets.032 | 213 | 211 | 2 | 🟡 Near |
| 325 | — | Unpaired | — | — | ⚪ Cross-archive |
| 329 | — | Unpaired | — | — | ⚪ Cross-archive |

**Key insight**: 3 MeshSizes (305, 309, 465) have DIST=0 pairs — float2 and float3 data
live in the SAME archive entry. The OBJ exporter pairs them directly within the same
TWAD entry. Other MeshSizes (325, 329) require cross-archive pairing via the
NIF block reference system.

See: `scripts/build_sibling_pairing_map.py` for the pairing map builder.

### Phase 18: Comprehensive Sibling Pairing Database

**Finding: Full-inventory analysis reveals 142 sibling pairs across 10 shared MeshSize families.**

Extended the Phase 16 archive-proximity approach from 88 OBJ-only IDs to the full inventory:

| Metric | Phase 16 (OBJ-only) | Phase 18 (Full) |
|---|---|---|
| Float2 position meshes | 36 | **230** |
| Float3 position meshes | 20 | **176** |
| Shared MeshSizes | 9 | **10** |
| Archive-close sibling pairs | ~25 | **142** |
| NIF files with cross-type (f2+f3) | — | **9** |

**Newly discovered shared MeshSize: 389** (previously missed in OBJ-only scan).

**9 NIF files contain BOTH float2 and float3 position streams** in different mesh blocks within the same NIF — this is the NIF-level sibling group that the C# `NifPositionSourceSiblingAccumulator` was designed to detect.

**59 NIF files** have multiple position-stream mesh blocks requiring sibling resolution.

The heuristic uses greedy nearest-entry matching (distance < 100 entries within same archive),
so some float3 meshes may be 1:N paired with multiple float2 meshes.

See: `scripts/build_sibling_pairing_v2.py` for the comprehensive database builder.

### Phase 20: Cross-Type NIF Verification

**Finding: All 9 cross-type NIF files confirmed — float2+float3 co-reside in same archive entry.**

Analyzed using Phase 19 pairing map data:

| Group | NIF IDs | Structure |
|---|---|---|
| 1 (6 NIFs) | d703, c36e, 75d5, ec36, 1d7d, a6b2 | MB=7: **f2+f3** (shared); MB=27: f3 only |
| 2 (1 NIF) | 45ef | MB=7: f2 only; MB=27: f3 only |
| 3 (2 NIFs) | 0d9a, 3feb | MB=27: **f2+f3** (shared); MB=7: f3 only |

**Key insight**: All 9 are MeshSize 305 — this family has the most complex
sibling pairing infrastructure. MB=7 is the canonical float2 position block,
paired with MB=7 or MB=27 for float3 Z-source.

**3 NIF groups** (shared MBs = same mesh block has both f2+f3 roles):
- Group 1 (6 NIFs): MB=7 has both float2 (descriptor-float2-uv) and float3 (descriptor-float3-generic)
- Group 3 (2 NIFs): MB=27 has both
- Group 2 (1 NIF): separate MBs for f2 vs f3

This validates the C# `NifPositionSourceSiblingAccumulator` which handles
in-NIF sibling discovery across different mesh blocks.

See: `scripts/verify_cross_type_nifs.py`

### Phase 19: Sibling Pairing Improvements

**Finding: 22 DIST=0 (same-entry) pairs confirmed across 3 MeshSizes — 7x expansion from Phase 17.**

| Metric | Phase 18 | Phase 19 |
|---|---|---|
| Total archive-close pairs | 142 | **142** (same) |
| DIST=0 (same entry) pairs | not tracked | **22** |
| MeshSizes with DIST=0 pairs | 3 (305, 309, 465) | **3** (expanded: 305=9, 329=2, 465=11) |
| JSON output | none | **Exports/phase19-sibling-pairing-map.json** |

**New finding**: MeshSize 329 now has 2 DIST=0 pairs (was 0 in Phase 16 analysis). This means
sibling pairing within the same archive entry extends to the meshSize=329 family.

**Improvements**:
- DIST=0 pairs tracked and annotated with `(SAME ENTRY)` in output
- Structured JSON output written to `Exports/phase19-sibling-pairing-map.json`
- Per-MeshSize DIST=0 counts in summary
- `int()` casts now use `or "0"` fallback to prevent ValueError

### Phase 17: Concrete Sibling Pair Verification

**Finding: Sibling pairing CONFIRMED — DIST=0 pair at MeshSize 305 entry 544.**

Probed ID `42024b768fcd2e2b` (assets.037, entry 544, MeshSize 305):

| Mesh Block | Position Descriptor | Payload | Elements | Bytes/El | Content |
|---|---|---|---|---|---|
| **MB=6** | `descriptor-float2-uv` | 192 bytes | **24** | 8 | XY pairs only |
| **MB=34** | `descriptor-float3-generic` | 768 bytes | **64** | 12 | Full XYZ |

**This confirms the Z-source mechanism end-to-end:**
1. Mesh Block 6 stores XY position data (8 bytes/vertex, float2 encoding)
2. Mesh Block 34 stores full XYZ position data (12 bytes/vertex, float3 encoding)
3. Both exist in the **same archive entry** (544 in assets.037)
4. The OBJ exporter pairs them via `NifPositionSourceSiblingAccumulator`
5. The float3 mesh provides Z values that complete the float2 mesh
6. The pairing maps 24 float2 vertices → 64 float3 vertices (consistent with earlier OBJ analysis showing 9/36 unique Z on a different mesh — sibling vertex mapping pattern holds)

**This is the first direct evidence of the sibling pairing mechanism in action.**
The same TWAD entry physically contains both the XY-only and full XYZ data,
confirming that the encoding is intentional: positions are split across sibling
mesh blocks within the same archive entry.

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