# RiftAssetDumper Project Summary

**Last Updated**: 2026-06-18 (Cycle 2 COMPLETE; v0.2 delivery pipeline shipped; test counts reconciled: 56 C# + 475 Python = 531 total)

**Purpose**: Comprehensive overview of all 50 completed phases, current state, key discoveries, and remaining work.

---

## 1. Project Overview

Reverse-engineering workspace for RIFT game asset archives. Focuses on decoding Gamebryo NIF geometry (NiMesh → NiDataStream bindings) for OBJ export.

### Core Architecture

| Component | Technology | Lines |
|---|---|---|
| CLI dumper | C# (.NET 9) | ~15K (single Program.cs) |
| Workflow orchestration | Python | 30+ commands in rift_workflow.py |
| Proof guards | Python | 9 guards in rift_workflow_guards.py |
| Reports | Python | 10+ report functions |
| Tests | xUnit + pytest | 56 C# + 475 Python = 531 total |

### Key Tools

| Tool | Purpose | Status |
|---|---|---|
| Ghidra | Static analysis of RIFT DLLs | ✅ Configured |
| x64dbg | Runtime archive read behavior | ✅ Installed |
| NifSkope | NIF block tree inspection | ✅ Installed |
| ImHex | Binary stream analysis | ✅ Installed |
| Blender | OBJ visual verification | ✅ Installed |

---

## 2. Phase Summary (51 Phases)

### Phase Group 1: Foundation (Phases 1-10)

Descriptor subsystem, gate clearance, promotion, proof guards.

- 7 gates cleared, 6 descriptor patterns proven, 49 tests, 0 regressions

### Phase Group 2: Discovery & Classification (Phases 11-20) + Cycle 2 (C2-1..C2-7)

Population-scale inventory, sibling pairing maps, cross-type verification, scene manifest pipeline, NIF-confirmed material scan, RiftFlythrough delivery.

- 142 sibling pairs across 10 MeshSize families, 9 cross-type NIFs, float2 Z-source resolved
- **Cycle 2 SHIPPED**: 241 per-asset scene manifests (217 stage6 + 24 stage2), NIF-confirmed material properties (217/217), 153/217 consumer-ready, v0.2 delivery pipeline (404/404 texture URLs, path privacy)

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
- **Phase 42**: Project summary updated; health sweep (all clean); family counts fixed to 29 total
- **Phase 43**: **Probe lookup pattern matching** added — secondary lookup from `probe-meshsize-lookup.json` for IDs probed but never OBJ-exported; **18 more entries resolved**; unknowns 22→4
- **Phase 44**: Project summary updated through Phase 43; health sweep (all clean)
- **Phase 45**: **0 unknowns remaining!** 🎉 Two bug fixes (regex `-mesh\d+(\.*)?$` fix for nested directories + guard removal for unresolved asset IDs) and 3 final probes resolved last edge cases. All 268 OBJs now fully classified.
- **Phase 46**: Documentation update with 0 unknowns milestone; accurate stats from live manifest
- **Phase 47**: MS=280 MB=25 anomaly investigation — MB=25 has index stream but no position data; sibling-pairing behavior confirmed
- **Phase 48**: Pos-only cross-MB pairing audit — **0 recoverable faced candidates found** across all 84 pos-only OBJs
- **Phase 49**: **Triangle fan fallback** for pos-only OBJs — approximate fan faces from vertex 0 when no index-vertex pairings exist. **Batch export**: 76/77 pos-only OBJs exported with 2,847 fan faces across 15 families. All docs updated through Phase 49.

---

## 3. Current State

### Export Totals

| Metric | Value |
|---|---|
| Total OBJ files | 350 |
| Unique asset IDs | 217 |
| **Faced** | **270** (77.1%) |
| **Position-only** | **80** (22.9%) |
| Total vertices | 23,421 |
| Total faces | 30,864 |
| Total bytes | 2,797 KB |
| Structural issues | 0 |
| Provenance: copied | 345 |
| Provenance: live | 5 |
| Remaining unknowns | **0** 🎉 |

### Per-MeshSize Breakdown

> See `Exports/export-manifest.json` for the live 30-family breakdown (350 OBJs, 270 faced, 80 pos-only).
> The table below is a historical snapshot from Phase 45 (29 families, 268 OBJs) preserved for reference.

| MeshSize | Faced | PosOnly | Total | % Faced |
|---|---|---|---|---|
| 193 | 0 | 2 | 2 | 0% |
| 197 | 0 | 2 | 2 | 0% |
| 214 | 0 | 1 | 1 | 0% |
| 240 | 3 | 0 | 3 | 100% |
| 267 | 1 | 0 | 1 | 100% |
| 272 | 0 | 6 | 6 | 0% |
| 275 | 0 | 3 | 3 | 0% |
| 276 | 7 | 0 | 7 | 100% |
| 280 | 4 | 1 | 5 | 80% |
| 297 | 6 | 0 | 6 | 100% |
| 301 | 30 | 0 | 30 | 100% |
| 305 | 17 | 36 | 53 | 32% |
| 307 | 0 | 1 | 1 | 0% |
| 309 | 19 | 0 | 19 | 100% |
| 321 | 20 | 1 | 21 | 95% |
| 325 | 63 | 0 | 63 | 100% |
| 326 | 0 | 1 | 1 | 0% |
| 329 | 0 | 5 | 5 | 0% |
| 330 | 1 | 0 | 1 | 100% |
| 337 | 0 | 1 | 1 | 0% |
| 345 | 3 | 0 | 3 | 100% |
| 354 | 1 | 0 | 1 | 100% |
| 361 | 1 | 0 | 1 | 100% |
| 365 | 1 | 0 | 1 | 100% |
| 367 | 3 | 0 | 3 | 100% |
| 370 | 0 | 1 | 1 | 0% |
| 389 | 0 | 2 | 2 | 0% |
| 405 | 3 | 0 | 3 | 100% |
| 465 | 1 | 21 | 22 | 5% |
| **(total)** | **184** | **84** | **268** | **69%** |

### Quality Metrics

| Check | Status |
|---|---|
| `ruff check scripts/` | ALL CLEAN |
| `mypy scripts/` | ALL OK |
| `dotnet build` | 0 errors |
| `dotnet test` | 56/56 pass |
| `dotnet format` | PASS |
| `pytest` | 475/475 pass |
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

1. **0 unknown MeshSize entries** 🎉 — All 350 OBJs are now fully classified with no unknowns.

2. **Cross-MB recovery exhausted** (Phase 48): Audited all 80 pos-only OBJs — 5 have faced siblings in the same NIF (all MS=305, already paired), 0 have recoverable index streams at other MBs. No low-hanging fruit remains.

3. **Auto-face reconstruction** (Phase 49) ✅ — Triangle fan fallback implemented for both `--experimental-position-source` (0-attribute-set) and `--export-obj` (attribute-set) paths. Batch export: 76/77 pos-only OBJs, **2,847 fan faces** across 15 families.

4. **No probe targets remain**: All IDs in Exports/ with probe-accessible identifiers have been resolved. 71 entries in probe lookup, 29 MeshSize families mapped.

5. **Ghidra/NiDataStream proof-guard lane**: All 7 promotion gates CLEARED ✅. Both flags true (`FieldOrderPromoted=true`, `ParserExportPromotionAllowed=true`). Ghidra static analysis evidence remains candidate-only and does not drive parser/export behavior changes.

### Known Limitations

- **Triangle fan faces are approximate**: Vertex 0 as fan hub produces correct faces only for fan-like primitive shapes. For arbitrary game geometry, most faces will be self-intersecting. Useful as a visual hint but not renderable geometry.
- **No faces for float2-paired meshes**: These fundamentally lack index streams.
- **MeshSize not in OBJ headers**: Must be determined via probe or cross-reference.
- **No asset ID in OBJ files**: ID recovery depends on directory structure. Regex now handles all known directory structures (Phase 45).
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
| `docs/roadmap/current-phase.md` | Living phase pointer + full history (50 phases) |
| `docs/roadmap/index-stream-family-map.md` | Per-MeshSize per-MB index stream reference |
| `docs/roadmap/project-summary.md` | This document |

---

## 7. Key Numbers

| Metric | Value |
|---|---|
| Total phases | 51 |
| Gates cleared | 7 |
| Proof guards | 9 |
| C# tests | 56 (all pass) |
| Python tests | 475 (all pass) |
| MeshSize families mapped | 29 (17 faced + 1 mixed + 11 pos-only) |
| Sibling pairs | 142 |
| Probe lookup entries | 71 |
| Faced OBJs | 270 |
| Position-only OBJs | 80 |
| Unknown MeshSize | **0** 🎉 |
| Structural issues | 0 |
