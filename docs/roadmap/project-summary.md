# RiftAssetDumper Project Summary

**Last Updated**: 2026-06 (Phase 41)

**Purpose**: Comprehensive overview of all 43 completed phases, current state, key discoveries, and remaining work.

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

## 2. Phase Summary (43 Phases)

### Phase Group 1: Foundation (Phases 1-10)
Descriptor subsystem, gate clearance, promotion, proof guards.
- 7 gates cleared, 6 descriptor patterns proven, 49 tests, 0 regressions

### Phase Group 2: Discovery & Classification (Phases 11-20)
Population-scale inventory, sibling pairing maps, cross-type verification.
- 142 sibling pairs across 10 MeshSize families, 9 cross-type NIFs, float2 Z-source resolved

### Phase Group 3: Export Pipeline (Phases 21-34)
Batch export scripts, manifest, index stream family map, coverage audit.
- 4 export scripts, export manifest (schema v2), 100% pairing-map coverage

### Phase Group 4: Cluster Probe Analysis (Phases 35-41)
Targeted probes, cluster analysis, regex bug fix, pattern matching.

**Key achievements:**
- **Phase 35**: 3 probes confirmed MS=321, 325; 37 cluster IDs identified
- **Phase 35.5**: 13 inferred IDs; unknowns 101→83
- **Phase 36**: `infer_meshsizes_from_clusters.py`; MS=276, 354 discovered; unknowns 83→79
- **Phase 37**: 12 probes; 3 new families (MS=267, 297, 330); unknowns 79→66
- **Phase 38**: Regex bug fix recovered **33 hidden IDs**; 15 probes; 3 new families (MS=280, 367, 405); unknowns 81→66
- **Phase 39**: Project summary updated; health sweep (all clean)
- **Phase 40**: 16 pos-only regex-recovered IDs probed; **8 new pos-only families** (MS=193, 197, 214, 272, 275, 307, 326, 337); unknowns 66→49
- **Phase 41**: **Pattern-matching logic** added to `build_export_manifest.py` — resolves no-ID entries by (faces, verts, MB) matching against known probes with 10% tolerance; **32 entries resolved without probes**; unknowns 49→22

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
| Probe lookup entries | 68 |
| Resolved MeshSize IDs | 68 |

### Per-MeshSize Breakdown

| MeshSize | Faced | PosOnly | Total | % Faced |
|---|---|---|---|---|
| 193 | 0 | 2 | 2 | 0% |
| 197 | 0 | 1 | 1 | 0% |
| 214 | 0 | 1 | 1 | 0% |
| 240 | 4 | 0 | 4 | 100% |
| 272 | 0 | 2 | 2 | 0% |
| 275 | 0 | 3 | 3 | 0% |
| 276 | 8 | 0 | 8 | 100% |
| 280 | 4 | 0 | 4 | 100% |
| 297 | 6 | 0 | 6 | 100% |
| 301 | 22 | 0 | 22 | 100% |
| 305 | 17 | 34 | 51 | 33% |
| 307 | 0 | 1 | 1 | 0% |
| 309 | 19 | 0 | 19 | 100% |
| 321 | 10 | 1 | 11 | 91% |
| 325 | 61 | 0 | 61 | 100% |
| 326 | 0 | 1 | 1 | 0% |
| 329 | 0 | 5 | 5 | 0% |
| 337 | 0 | 1 | 1 | 0% |
| 345 | 5 | 0 | 5 | 100% |
| 367 | 13 | 0 | 13 | 100% |
| 389 | 0 | 2 | 2 | 0% |
| 405 | 3 | 0 | 3 | 100% |
| 465 | 1 | 19 | 20 | 5% |
| unknown | 11 | 11 | 22 | 50% |
| **(total)** | **184** | **84** | **268** | **69%** |

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
Z is sourced through sibling position pairing. Float2 meshes store XY-only (8 bytes/vertex). A paired float3 sibling provides full XYZ data.

### Index Stream Family Map (Phase 28-29)
Faced vs position-only is determined by **which mesh block you export**. MB=6 is the canonical faced geometry block for MeshSizes 240-405. MB=7 and MB=27 are sister blocks for sibling pairing.

### 29 MeshSize Families Identified (Phases 27-41)
Through systematic probes, cluster analysis, and pattern matching:
- **17 faced-capable families**: 240, 267, 276, 280, 297, 301, 309, 321, 325, 330, 345, 354, 361, 365, 367, 405, 465 (MB=7)
- **1 mixed family**: 305 (faced at MB=6,45,46; pos-only at MB=7,27)
- **11 position-only families**: 193, 197, 214, 272, 275, 307, 326, 329, 337, 370, 389

### Regex Bug Discovery (Phase 38)
`extract_asset_id()` had a regex bug: `r"-mesh\d+$"` never matched `.obj` extension. Fixed to `r"-mesh\d+\..*$"`. Recovered **33 hidden IDs**.

### Pattern-Matching Resolution (Phase 41)
`build_export_manifest.py` now resolves no-ID entries by matching (faces, vertices, mesh_block, faced) patterns against known probe entries with 10% tolerance. **32 entries resolved without probes** in the first run.

### Batch Export Scripts
- **batch_export_sibling.py**: 142 sibling pairs exported
- **batch_export_float3.py**: 9 IDs, 6 faced + 3 pos-only
- **batch_export_mb6.py**: 36 float2 IDs confirmed position-only
- **infer_meshsizes_from_clusters.py**: Cluster inference automation

---

## 5. Remaining Work

### Open Questions

1. **22 unknown MeshSize entries**: 11 faced + 11 position-only. These are individual-export OBJs without asset IDs that didn't match any probe pattern. Likely edge cases (very small meshes, 0-face OBJs, one large NIF not in Source/).

2. **Auto-face reconstruction**: 84 position-only OBJs have valid vertex data but no index streams. Could faces be generated algorithmically from vertex adjacency or strip topology?

3. **No probe targets remain**: All IDs in Exports/ that have probe-accessible identifiers have been resolved. The remaining unknowns cannot be resolved via probes.

### Known Limitations

- **No faces for float2-paired meshes**: These fundamentally lack index streams.
- **MeshSize not in OBJ headers**: Must be determined via probe or cross-reference.
- **No asset ID in OBJ files**: ID recovery depends on directory structure.
- **Multiple MBs for same family**: Future probe work may need to target new MB variants.

---

## 6. Script & Document Reference

### Key Scripts

| Script | Purpose |
|---|---|
| `scripts/build_export_manifest.py` | Export manifest with ID extraction + pattern matching |
| `scripts/infer_meshsizes_from_clusters.py` | Cluster-based MeshSize inference |
| `scripts/analyze_z_source.py` | Streaming JSON parser |
| `scripts/build_sibling_pairing_v2.py` | Comprehensive pairing database |
| `scripts/batch_sweep.py` | 4-phase OBJ integrity + discovery |

### Reference Documents

| Document | Contents |
|---|---|
| `docs/roadmap/current-phase.md` | Living phase pointer + full history (43 phases) |
| `docs/roadmap/index-stream-family-map.md` | Per-MeshSize per-MB index stream reference |
| `docs/roadmap/project-summary.md` | This document |

---

## 7. Key Numbers

| Metric | Value |
|---|---|
| Total phases | 43 |
| Gates cleared | 7 |
| Proof guards | 8 |
| C# tests | 50 (all pass) |
| Python tests | ~49 (all pass) |
| MeshSize families mapped | 29 (17 faced + 1 mixed + 11 pos-only) |
| Sibling pairs | 142 |
| Probe lookup entries | 68 |
| Faced OBJs | 184 |
| Position-only OBJs | 84 |
| Unknown MeshSize | 22 (11 faced, 11 pos-only) |
| Structural issues | 0 |
