# Stage 0 — Foundation & Baseline Validation

**Date:** 2026-05-20  
**Status:** ✅ Complete  
**Plan:** `docs/discovery-plan-50.md` Steps 1-5  

---

## ✅ Step 1 — Build & Test Baseline

| Check | Result |
|-------|--------|
| `dotnet build` | ✅ 0 errors, 0 warnings |
| Python tests (46/46) | ✅ All passed |
| Python imports (3 modules) | ✅ All OK |
| Git status | 4 commits ahead of origin/main, 1 untracked handoff |

---

## ✅ Step 2 — Proof Guard Refresh

### @264/#15 Probe: `6fc01704d4a509d5` mesh block 6

| Signal | Value | Status |
|--------|-------|--------|
| VertexCount | 128 | ✅ |
| MeshSize | 297 | ✅ |
| Topology | `implicit-strip-or-quad-candidate` | ✅ |
| Strip triangles | 126 | ✅ |
| Quad count | 32 | ✅ |
| Position role | `position-float3-ror1-lead` (Block 16) | ✅ |
| Normal role | `normal-float3-ror1-lead` (Block 17) | ✅ |
| UV role | `uv-float2-ror1-lead` (Block 21) | ✅ |
| Index role | `uint16-compatible-body` (Block 15, offset 264) | ✅ |
| Index encoding | **UInt16 big-endian** (confirmed) | ✅ |
| Index prefix | `0001 0002 0002 0001 0003...` | ✅ degenerate-bridge |
| UInt16BigEndianPrefix | `[1,2,2,1,3,4,5,6,6,5,...]` | ✅ |
| UInt16 max value | 127 (matches vertex count 128) | ✅ |
| UInt16 distinct | 127 | ✅ |
| Degenerate repeats | Confirmed (e.g. 25→25→24) | ✅ |

### @264/#15 Probe: `caa9a88e94ec8db0` mesh block 6

**Identical structure to 6fc01704d4a509d5** — same vertex count, same index stream pattern, same roles. Proof is consistent across both siblings.

### Mesh-Bindings Inventory

| Metric | Count |
|--------|-------|
| InspectedPayloads | 40,203 |
| NifPayloads | 5,111 |
| MeshBlocks | 5,507 |
| CandidateLinks | 11,564 |
| AttributeCompatibleMeshes | 52 |
| AttributeCompatibleSets | 52 |
| PairCompatibleMeshes | 0 |
| TopAttributeTopologies | 33 groups |
| `implicit-strip-or-quad-candidate` count | 5 (meshSize 297, 329) |
| `implicit-triangle-strip-or-fan-candidate` count | 13 |
| `implicit-triangle-list-candidate` count | 7 |
| RoleGroups | 9 |

### ⚠️ Noted Differences from Legacy PS Guard Output

- The new C# mesh-bindings JSON restructured the output format (no more `AttributeExtraStreamGroups`, `AttributeTopologyGroups`)
- Preference (raw-zero-based vs subtract-one) counts are now stored in individual probe JSONs, not at the inventory top-level
- Guard assertions from the legacy `Invoke-RiftAssetWorkflow.ps1` cannot run directly due to PS syntax errors (deprecated per plan)
- **Mitigation:** Individual `probe-nif-attribute-extra` probes confirm all proof signals intact

### Verdict: 🟢 Proof signals unchanged. No regressions detected

---

## ✅ Step 3 — Baseline Exports Captured

| File | Size | Content |
|------|------|---------|
| `nif-mesh-binding-inventory.json` | 59 MB | Full 40,203-payload inventory |
| `probe-attr-extra-6fc017-mesh6-extra264.json` | ~30 KB | @264 probe #1 |
| `probe-attr-extra-caa9a8-mesh6-extra264.json` | ~30 KB | @264 probe #2 |

All under `Exports/discovery-plan/stage0-baseline/` (ignored, non-conflicting).

---

## ✅ Step 4 — Command Inventory

### 44 CLI Commands Available

**Archive/Asset Discovery (8):** `probe`, `extract-archives`, `match-ids`, `list-paks`, `list-entries`, `hash-name`, `match-names`, `inventory-archives`

**Binary/Asset Analysis (5):** `scan-compression`, `mine-strings`, `inventory-asset-signatures`, `build-asset-semantic-index`, `inventory-binary-signatures`

**NIF Probing (4):** `probe-binary`, `probe-nif`, `probe-nif-streams`, `probe-nif-mesh`

**NIF Geometry (1):** `decode-nif-geometry` [--write-obj] [--experimental]

**NIF Attribute/Stream (2):** `probe-nif-attribute-extra`, `probe-nif-stream-body`

**NIF Inventory (7):** `inventory-nif`, `inventory-nif-blocks`, `inventory-nif-mesh-streams`, `inventory-nif-mesh-bindings`, `inventory-nif-stream-headers`, `inventory-nif-stream-bodies`, `inventory-nif-stream-endianness`, `inventory-nif-index-candidates`

**NIF References/Textures/Bundles (7):** `mine-nif-references`, `link-nif-textures`, `extract-linked-textures`, `extract-nif-bundle`, `extract-nif-bundles`, `inventory-nif-bundles`, `plan-nif-bundle-archives`

**Key Flags:** `--root`, `--out`, `--id`, `--mesh-block`, `--extra-offset`, `--write-obj`, `--experimental`, `--max-total`, `--limit`

### DecodeNifGeometry Current State

- OBJ export exists but produces **point cloud only** ("No faces/indices decoded")
- Experimental UInt16 path exists for position decode
- Face/index injection point identified → **Stage 1 task**

---

## 📋 Stage 0 Disposition

**Pass to Stage 1.** Foundation is healthy:

- Builds clean, tests pass
- @264 proof signals intact on both sibling samples
- 52 attribute-compatible meshes available for Stage 1 cross-validation
- decode-nif-geometry OBJ export ready for face addition

**Risk:** The legacy PS guards have syntax errors and can't run. Individual probe validation covers the same proof surface.

**Next:** Stage 1 — Add degenerate-bridge triangle decode to OBJ export.
