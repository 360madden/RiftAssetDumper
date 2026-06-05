# RiftAssetDumper Project Summary

**Last Updated**: 2026-06 (Phase 34)

**Purpose**: Comprehensive overview of all 34 completed phases, current state, key discoveries, and remaining work.

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

---

## 2. Phase Summary (34 Phases)

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
- 3 batch export scripts created: `batch_export_sibling.py`, `batch_export_float3.py`, `batch_export_mb6.py`
- Export manifest system (`build_export_manifest.py`, schema v2)
- Index stream family map (11+ MeshSize families, per-MB breakdown)
- 100% coverage of pairing-map reachable assets

---

## 3. Current State

### Export Totals

| Metric | Value |
|---|---|
| Total OBJ files | 268 |
| Unique asset IDs | 182 |
| **Faced** | **184** (68.7%) |
| **Position-only** | **84** (31.3%) |
| Total vertices | 19,797 |
| Total faces | 20,354 |
| Total bytes | 2,201 KB |
| Structural issues | 0 |

### Per-MeshSize Breakdown

| MeshSize | Faced | PosOnly | Total | % Faced |
|---|---|---|---|---|
| 240 | 1 | 0 | 1 | 100% |
| 297 | 5 | 0 | 5 | 100% |
| 301 | 19 | 0 | 19 | 100% |
| 305 | 17 | 31 | 48 | 35% |
| 309 | 16 | 0 | 16 | 100% |
| 321 | 7 | 1 | 8 | 88% |
| 325 | 42 | 0 | 42 | 100% |
| 329 | 0 | 2 | 2 | 0% |
| 345 | 3 | 0 | 3 | 100% |
| 361 | 1 | 0 | 1 | 100% |
| 365 | 1 | 0 | 1 | 100% |
| 370 | 0 | 1 | 1 | 0% |
| 389 | 0 | 2 | 2 | 0% |
| 465 | 1 | 17 | 18 | 6% |
| unknown | 71 | 30 | 101 | 70% |

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
Faced vs position-only is determined by **which mesh block you export**, not by asset. MB=6 is the canonical faced geometry block for MeshSizes 240-361. MB=7 and 27 are sister blocks for sibling pairing (position-only).

### Float3 Batch Export (Phase 30)
34 float3 IDs in the pairing map. 8 produce faced OBJs (have index streams), 26 are position-only. All 34 have been exported (100% coverage).

### MB=6 Export (Phase 31)
36 float2 IDs were confirmed to have no MB=6 block. They are genuinely position-only — no faced-capable mesh blocks exist for these assets.

---

## 5. Remaining Work

### Open Questions

1. **101 unknown MeshSize OBJs**: 71 faced + 30 position-only with unresolved MeshSize. These are from individual exports during Phases 1-20. Probes could resolve them but each requires a full `probe-nif-mesh` run.

2. **Auto-face reconstruction**: 84 position-only OBJs have valid vertex data but no index streams. Could faces be generated algorithmically from vertex adjacency or strip topology?

3. **@264 mesh variants**: 5 batch-264-* OBJs exist (v128, v64, v80, v95) but only 1 faced (v128). The other variants are position-only — likely different vertex-count encoding attempts.

### Known Limitations

- **No faces for float2-paired meshes**: Meshes that require sibling pairing for Z-sourcing will never have index streams. This is a fundamental encoding decision in the game engine.
- **MeshSize not in OBJ headers**: OBJ files don't include MeshSize in their comments. MeshSize must be determined via probe or cross-reference with the pairing map.
- **Inventory file too large (219MB)**: Full cross-referencing with the population inventory requires the streaming parser from Phase 15.5.

---

## 6. Script Reference

### Batch Export Scripts

| Script | Purpose | Output Dir |
|---|---|---|
| `scripts/batch_export_sibling.py` | Export float2 meshes with --include-close | `Exports/obj-exports/` |
| `scripts/batch_export_float3.py` | Export unexported float3 meshes | `Exports/float3-exports/` |
| `scripts/batch_export_mb6.py` | Export MB=6 for float2 IDs | `Exports/mb6-exports/` |

### Utility Scripts

| Script | Purpose |
|---|---|
| `scripts/build_export_manifest.py` | Generate comprehensive OBJ catalog |
| `scripts/analyze_z_source.py` | Streaming JSON parser for inventory analysis |
| `scripts/build_sibling_pairing_v2.py` | Build comprehensive pairing database |
| `scripts/verify_cross_type_nifs.py` | Verify cross-type NIF files |
| `scripts/batch_sweep.py` | 4-phase OBJ integrity + candidate discovery |

### Reference Documents

| Document | Contents |
|---|---|
| `docs/roadmap/project-roadmap.md` | Original phase roadmap (Phases 0-17) |
| `docs/roadmap/current-phase.md` | Living phase pointer + full history |
| `docs/roadmap/index-stream-family-map.md` | Per-MeshSize per-MB index stream reference |
| `docs/roadmap/project-summary.md` | This document — comprehensive overview |

---

## 7. Key Numbers

| Metric | Value |
|---|---|
| Total phases | 34 |
| Gates cleared | 7 |
| Descriptor patterns proven | 6 |
| Proof guards | 8 |
| C# tests | 50 |
| Python tests | ~50 |
| Batch export scripts | 3 |
| MeshSize families mapped | 14 |
| Float3 IDs tracked | 34 |
| Sibling pairs | 142 |
| Faced OBJs | 184 |
| Position-only OBJs | 84 |
| Total vertices exported | 19,797 |
| Total faces exported | 20,354 |
| Structural issues | 0 |
