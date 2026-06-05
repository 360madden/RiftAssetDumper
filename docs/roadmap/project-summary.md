# RiftAssetDumper Project Summary

**Last Updated**: 2026-06 (Phase 38)

**Purpose**: Comprehensive overview of all 40 completed phases, current state, key discoveries, and remaining work.

---

## 1. Project Overview

Reverse-engineering workspace for RIFT game asset archives. Focuses on decoding Gamebryo NIF geometry (NiMesh → NiDataStream bindings) for OBJ export.

### Core Architecture

| Component | Technology | Lines |
|---|---|---|
| CLI dumper | C# (.NET 9) | ~15K (single Program.cs) |
| Workflow orchestration | Python | 30+ commands in rift_workflow.py |
| Proof guards | Python | 8 guards in rift_workflow_guards.py |
| Reports | Python | 10+ report functions |
| Tests | xUnit + pytest | 50 C# + 50 Python |

### Key Tools

| Tool | Purpose | Status |
|---|---|---|
| Ghidra | Static analysis of RIFT DLLs | ✅ Configured |
| x64dbg | Runtime archive read behavior | ✅ Installed |
| NifSkope | NIF block tree inspection | ✅ Installed |
| ImHex | Binary stream analysis | ✅ Installed |
| Blender | OBJ visual verification | ✅ Installed |

---

## 2. Phase Summary (40 Phases)

### Phase Group 1: Foundation (Phases 1-10)
Descriptor subsystem, gate clearance, promotion, proof guards.

**Key achievements:**
- 7 gates cleared (100% promotion readiness)
- 6 descriptor byte patterns proven (4/4 bytes identified)
- Stride→usage rule: uint16×scalar→index, everything else→vertex
- 58 C# code lines, 49 tests, 0 regressions, no Ghidra required
- `FieldOrderPromoted=true`, `ParserExportPromotionAllowed=true`

### Phase Group 2: Discovery & Classification (Phases 11-20)
Population-scale inventory, sibling pairing maps, cross-type verification.

**Key achievements:**
- 142 sibling pairs identified across 10 MeshSize families
- 9 cross-type NIF files confirmed (f2+f3 co-resident in same entry)
- 22 DIST=0 (same-entry) pairs confirmed
- Float2 Z-source mechanism resolved: **sibling position pairing**
- 72% of OBJ positions use float2 encoding (8 bytes/vertex = XY)

### Phase Group 3: Export Pipeline (Phases 21-34)
Batch export scripts, manifest, index stream family map, coverage audit.

**Key achievements:**
- 4 batch export scripts created: `batch_export_sibling.py`, `batch_export_float3.py`, `batch_export_mb6.py`, `infer_meshsizes_from_clusters.py`
- Export manifest system (`build_export_manifest.py`, schema v2)
- Index stream family map (19 MeshSize families, per-MB breakdown)
- 100% coverage of pairing-map reachable assets
- Full project health sweep (all checks passing)

### Phase Group 4: Cluster Probe Analysis (Phases 35-38)
Targeted probes to resolve unknown MeshSizes from face-count clusters.

**Key achievements:**
- **Phase 35**: Probe cluster analysis — 3 probes confirmed MS=321 (414f) and MS=325 (318f), 37 cluster IDs identified
- **Phase 35.5**: 13 cluster-inferred IDs added to probe lookup; unknowns 101→83
- **Phase 36**: `infer_meshsizes_from_clusters.py` created; MS=276 and MS=354 discovered via probes; unknowns 83→79
- **Phase 37**: 12 probes resolved 3 new families (MS=267, MS=297, MS=330); unknowns 79→66
- **Phase 38**: **Regex bug fix in `build_export_manifest.py`** recovered **33 hidden IDs** that were always in Exports/ but couldn't be extracted (wrong regex pattern `-mesh\d+$` didn't account for `.obj` extension). 15 probes resolved 3 new families: MS=280, MS=367, MS=405 + 2 known matches. Unknowns 81→66.

---

## 3. Current State

### Export Totals

| Metric | Value |
|---|---|
| Total OBJ files | 268 |
| Unique asset IDs | 180 |
| **Faced** | **184** (68.7%) |
| **Position-only** | **84** (31.3%) |
| Total vertices | ~19,800 |
| Total faces | ~20,350 |
| Total bytes | ~2,200 KB |
| Structural issues | 0 |
| Probe lookup entries | 52 |
| Resolved MeshSize IDs | 52 |

### Per-MeshSize Breakdown

| MeshSize | Faced | PosOnly | Total | % Faced |
|---|---|---|---|---|
| 240 | 2 | 0 | 2 | 100% |
| 276 | 7 | 0 | 7 | 100% |
| 280 | 4 | 0 | 4 | 100% |
| 297 | 9 | 0 | 9 | 100% |
| 301 | 19 | 0 | 19 | 100% |
| 305 | 17 | 31 | 48 | 35% |
| 309 | 19 | 0 | 19 | 100% |
| 321 | 10 | 1 | 11 | 91% |
| 325 | 53 | 0 | 53 | 100% |
| 329 | 0 | 2 | 2 | 0% |
| 345 | 1 | 0 | 1 | 100% |
| 367 | 3 | 0 | 3 | 100% |
| 389 | 0 | 2 | 2 | 0% |
| 405 | 3 | 0 | 3 | 100% |
| 465 | 1 | 18 | 19 | 5% |
| unknown | 36 | 30 | 66 | 55% |
| **(total)** | **184** | **84** | **268** | **69%** |

### Probe Lookup Distribution (52 entries)

| MeshSize | IDs | Source |
|---|---|---|
| 240 | 1 | Phase 27 probe |
| 267 | 1 | Phase 37 probe |
| 276 | 4 | Phase 36-38 probes |
| 280 | 4 | Phase 38 regex recovery |
| 297 | 2 | Phase 37 probes |
| 301 | 8 | Phase 37-38 probes |
| 321 | 13 | Phase 35.5-38 probes + inference |
| 325 | 7 | Phase 35-37 probes + inference |
| 330 | 1 | Phase 37 probe |
| 354 | 1 | Phase 36 probe |
| 361 | 1 | Phase 27 probe |
| 365 | 1 | Phase 27 probe |
| 367 | 3 | Phase 38 regex recovery |
| 370 | 1 | Phase 27 probe |
| 405 | 3 | Phase 38 regex recovery |
| 465 | 1 | Phase 27 probe |

### Quality Metrics

| Check | Status |
|---|---|
| `ruff check scripts/` | ALL CLEAN |
| `mypy scripts/` | ALL OK |
| `dotnet build` | 0 errors |
| `dotnet test` | 50/50 pass |
| `dotnet format` | PASS |
| OBJ integrity | 0 structural issues |

---

## 4. Key Discoveries

### Sibling Position Pairing (Phase 15.5-17)
Z is sourced through sibling position pairing. Float2 meshes store XY-only (8 bytes/vertex). A paired float3 sibling in the same archive entry provides full XYZ data. The `NifPositionSourceSiblingAccumulator` handles cross-mesh pairing in the C# exporter.

### Index Stream Family Map (Phase 28-29)
Faced vs position-only is determined by **which mesh block you export**, not by asset. MB=6 is the canonical faced geometry block for MeshSizes 240-405. MB=7 and MB=27 are sister blocks for sibling pairing (position-only).

### 19 MeshSize Families Identified (Phases 27-38)
Through systematic probes and cluster analysis:
- **Canonical faced families**: 240, 267, 276, 280, 297, 301, 309, 321, 325, 330, 345, 354, 361, 365, 367, 405, 465 (MB=7)
- **Position-only families**: 329, 370, 389
- **Mixed family**: 305 (faced at MB=6,45,46; pos-only at MB=7,27)

### Regex Bug Discovery (Phase 38)
The `extract_asset_id()` function in `build_export_manifest.py` had a regex bug: `r"-mesh\d+$"` was supposed to strip `-mesh{N}` from OBJ filenames, but since filenames end with `.obj`, the regex never matched. This caused **33 IDs** to remain permanently unresolved. Fixed by changing the regex to `r"-mesh\d+\..*$"` (accounts for `.obj` extension).

### Batch Export Scripts
- **batch_export_sibling.py**: 142 sibling pairs exported (127 unique OBJs)
- **batch_export_float3.py**: 9 float3 IDs exported, 6 faced + 3 pos-only
- **batch_export_mb6.py**: 36 float2 IDs confirmed position-only
- **infer_meshsizes_from_clusters.py**: Automates cluster inference from probe lookup

### Float3 Batch Export (Phase 30)
34 float3 IDs in the pairing map. 8 produce faced OBJs (have index streams), 26 are position-only. All 34 have been exported (100% coverage).

---

## 5. Remaining Work

### Open Questions

1. **66 unknown MeshSize entries**: 36 faced + 30 position-only. 17 of these are IDs recovered by the Phase 38 regex fix that haven't been probed yet (these are position-only). The remaining 49 lack asset IDs entirely (from batch-264, fallback exports). Prior probes have resolved all IDs in Exports/ that have probe-accessible identifiers.

2. **Auto-face reconstruction**: 84 position-only OBJs have valid vertex data but no index streams. Could faces be generated algorithmically from vertex adjacency or strip topology?

3. **@264 mesh variants**: 5 batch-264-* OBJs exist (v128, v64, v80, v95) but only 1 faced (v128). The other variants are position-only — likely different vertex-count encoding attempts.

### Known Limitations

- **No faces for float2-paired meshes**: Meshes that require sibling pairing for Z-sourcing will never have index streams. This is a fundamental encoding decision in the game engine.
- **MeshSize not in OBJ headers**: OBJ files don't include MeshSize in their comments. MeshSize must be determined via probe or cross-reference with the pairing map.
- **Inventory file too large (219MB)**: Full cross-referencing with the population inventory requires the streaming parser from Phase 15.5.
- **No asset ID in OBJ files**: Asset ID is only in the OBJ filename path, not in the file contents. This makes ID recovery fragile — dependent on directory structure.

---

## 6. Script & Document Reference

### Batch Export Scripts

| Script | Purpose | Output Dir |
|---|---|---|
| `scripts/batch_export_sibling.py` | Export float2 meshes with --include-close | `Exports/obj-exports/` |
| `scripts/batch_export_float3.py` | Export unexported float3 meshes | `Exports/float3-exports/` |
| `scripts/batch_export_mb6.py` | Export MB=6 for float2 IDs | `Exports/mb6-exports/` |

### Utility & Analysis Scripts

| Script | Purpose |
|---|---|
| `scripts/build_export_manifest.py` | Generate comprehensive OBJ catalog |
| `scripts/infer_meshsizes_from_clusters.py` | Automate MeshSize inference from face-count clusters |
| `scripts/analyze_z_source.py` | Streaming JSON parser for inventory analysis |
| `scripts/build_sibling_pairing_v2.py` | Build comprehensive pairing database |
| `scripts/verify_cross_type_nifs.py` | Verify cross-type NIF files |
| `scripts/batch_sweep.py` | 4-phase OBJ integrity + candidate discovery |

### Reference Documents

| Document | Contents |
|---|---|
| `docs/roadmap/project-roadmap.md` | Original phase roadmap (Phases 0-17) |
| `docs/roadmap/current-phase.md` | Living phase pointer + full history (40 phases) |
| `docs/roadmap/index-stream-family-map.md` | Per-MeshSize per-MB index stream reference (19 families) |
| `docs/roadmap/project-summary.md` | This document — comprehensive overview |

---

## 7. Key Numbers

| Metric | Value |
|---|---|
| Total phases | 40 |
| Gates cleared | 7 |
| Descriptor patterns proven | 6 |
| Proof guards | 8 |
| C# tests | 50 |
| Python tests | ~49 |
| Batch/utility scripts | 8 |
| MeshSize families mapped | 19 (16 faced, 3 pos-only) |
| Float3 IDs tracked | 34 |
| Sibling pairs | 142 |
| Probe lookup entries | 52 |
| Faced OBJs | 184 |
| Position-only OBJs | 84 |
| Total vertices exported | ~19,800 |
| Total faces exported | ~20,350 |
| Unknown MeshSize | 66 (36 faced, 30 pos-only) |
| Structural issues | 0 |
