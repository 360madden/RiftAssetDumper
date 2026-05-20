# RIFT Assets — Comprehensive Session Handoff

**Date:** 2026-05-19 21:30 UTC
**Branch:** `main`
**HEAD:** `ed66963` (Port 21 PowerShell utility functions to Python)
**Supersedes:** `2026-05-19-204500-*` (deduplication), `2026-05-19-211500-*` (migration), `2026-05-19-071816-*` (stale)

---

## TL;DR

Two milestones completed this session on `main`:

| Milestone | Commit | What |
|---|---|---|
| **Deduplication + `decode-nif-geometry`** | `b34b2c7` | UInt16 triples analysis deduplicated (C# is single source of truth, PS reads from JSON). New `decode-nif-geometry` C# command with optional OBJ export. |
| **PS → Python migration (phase 1)** | `ed66963` | 21 utility functions ported from PS to `scripts/rift_workflow_utils.py`. Thin PS wrapper created. 49 tests pass. |

No generated/copied asset output committed. Guard boundaries intact.

---

## Architecture — Current State

| Layer | Language | Files | Lines | Role |
|---|---|---|---|---|
| **Parser / source of truth** | C# | `src/RiftAssetDumper/Program.cs` | ~13K | NIF parsing, mesh/stream inventory, attribute decoding, UInt16 structure analysis |
| **Orchestration / reporting** | PowerShell | `scripts/Invoke-RiftAssetWorkflow.ps1` | ~3,550 | 44 functions: report generators, proof guards, C# CLI orchestration |
| **Thin PS entry (new)** | PowerShell | `scripts/Invoke-RiftWorkflow.ps1` | 52 | Delegates to Python; runs `generated_output_guard()` |
| **Utility library (new)** | Python | `scripts/rift_workflow_utils.py` | 330 | 21 ported helpers: JSON access, guards, formatting, semantic hints |
| **Discovery orchestration** | Python | `scripts/rift_asset_discovery_matrix.py` | ~350 | Batch discovery matrix runner |
| **Tests (new)** | Python | `scripts/test_rift_workflow_utils.py` | 124 | 49 smoke tests — all pass |

### Powershell → Python migration status

| Phase | Status | Functions ported |
|---|---|---|
| ✅ Phase 1: Utilities | Complete | 21/21 helpers ported |
| ⬜ Phase 2: Report generators | Not started | `Show-ReportSummary` (~150 lines) next target |
| ⬜ Phase 3: Guards | Not started | `Invoke-UsageAccessCorrelationGuard`, `Invoke-AttributeExtraProofGuard` etc. |
| ⬜ Phase 4: Complex reports | Not started | `Invoke-ResidualPositionClusterProbeReport` (~400 lines) |

---

## C# Commands Available

```
inventory-asset-signatures
build-asset-semantic-index
plan-nif-bundle-archives
extract-nif-bundle
extract-nif-bundles
probe-nif
probe-nif-mesh
probe-nif-attribute-extra
probe-nif-streams
probe-nif-stream-body
inventory-nif-blocks
inventory-nif-mesh-streams
inventory-nif-mesh-bindings
inventory-nif-stream-headers
inventory-nif-stream-bodies
inventory-nif-stream-endianness
inventory-nif-index-candidates
decode-nif-geometry          ← NEW this session
```

### `decode-nif-geometry` details

```powershell
dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- \
  decode-nif-geometry --root Source --id <asset-id> --mesh-block <n> [--write-obj] [--experimental]
```

- Decodes float32 positions/normals/UVs from NiMesh attribute sets
- `--write-obj`: writes `.obj` point cloud (no faces/indices yet)
- `--experimental`: attempts UInt16-packed position decode via magic 43606 pattern
- Output: `Exports/decode-nif-geometry/decode-nif-geometry-mesh<n>.obj`

---

## Key Discoveries (Preserved from Prior Work)

| Lane | Status | Lead |
|---|---|---|
| Position/normal/UV attribute sets | ✅ Proven | `meshSize=305`, vertex=16, complete pos/normal/UV float3/float2 sets |
| Explicit-index extra stream | ✅ Strongest lead | `@264/#15` on `meshSize=297`, raw-zero-based preferred, degenerate-bridge stitching |
| Index strip/Fan topology | ✅ Ranked | `5,481` big-endian uint16 triangle-aligned strip bodies |
| Byte-order rule | ✅ Strong signal | `usage=1/access=19` → float3 normal/float2 UV (rotate-right-1) |
| UInt16 magic 43606 | ✅ Pattern detected | Alternating position_triple / metadata_pair structure in big-endian uint16 streams |
| Mesh→texture graph | ✅ Proven | 3,224 models → 2,514 texture assets; live-fallback extraction works |
| Generated output guard | ✅ Active | Source/, Extracted/, Exports/, bin/, obj/, __pycache__, .pyc blocked |

---

## Safety Boundaries

| Boundary | Status |
|---|---|
| No live game interaction | ✅ |
| No copied assets committed | ✅ |
| No generated output tracked/staged | ✅ — `generated_output_guard()` ported to Python |
| C# is parser source of truth | ✅ |
| PowerShell not deleted | ✅ — 3600-line script still operational |
| Export gate | 🔒 — OBJ writes point-cloud only, no faces, behind `--write-obj` flag |
| Guard regression protection | ✅ — `AttributeExtraProofGuard`, `AttributeExtraSiblingProofGuard`, `UsageAccessCorrelationGuard` all active |
| Privacy scan | ✅ — no raw user-profile paths tracked |

---

## Validation (Current Session)

| Check | Result |
|---|---|
| `dotnet build src/RiftAssetDumper/RiftAssetDumper.csproj` | ✅ 0 errors |
| `python scripts/test_rift_workflow_utils.py` | ✅ 49/49 tests pass |
| `python -c "from scripts.rift_workflow_utils import ..."` | ✅ Package import works |
| `git diff --check` | ✅ No whitespace issues |
| `Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard` | ✅ 0 tracked/staged generated outputs |

---

## Resume Prompt

```text
Resume in C:\RIFT MODDING\Assets. Work Assets-only.
main is at ed66963 with two completed milestones:
1. UInt16 triples deduplication + decode-nif-geometry command (b34b2c7)
2. PS→Python utility migration phase 1 (ed66963)

Python utilities live in scripts/rift_workflow_utils.py (21 functions, 49 tests).
Thin PS entry: scripts/Invoke-RiftWorkflow.ps1 (delegates to Python).
Original PS: scripts/Invoke-RiftAssetWorkflow.ps1 (44 functions, still operational).

Next milestone: port Show-ReportSummary (~150 lines) from PS to Python,
or continue geometry discovery on the @264/#15 explicit-index lane.

Validate with: dotnet build, python tests, generated output guard, proof guards.
```

---

## Optional Top 10 Next Actions

| # | Action |
|---:|---|
| 1 | Port `Show-ReportSummary` from PowerShell to Python (~150 lines, uses only ported utilities) |
| 2 | Port `Invoke-UsageAccessCorrelationGuard` to Python to prove guard pattern end-to-end |
| 3 | Add index/topology decode to `decode-nif-geometry` (OBJ faces, not just point cloud) |
| 4 | Cross-validate UInt16-packed positions against float32 positions for the same mesh |
| 5 | Run full `ResidualPositionClusterProbeReport` end-to-end via the thin PS wrapper |
| 6 | Port `Invoke-ResidualPositionClusterProbeReport` to Python (~400 lines) |
| 7 | Add `ExportSafetyAssertion` to `decode-nif-geometry` OBJ export path |
| 8 | Update `docs/current-status.md` with Python migration and decode-nif-geometry details |
| 9 | Port the remaining proof guards (`Invoke-AttributeExtraProofGuard` etc.) to Python |
| 10 | Unify `UInt16TriplesPrefix`/`UInt16BigEndianTriplesPrefix` into a single JSON field |
