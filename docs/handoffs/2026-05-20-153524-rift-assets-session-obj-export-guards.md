# RIFT Assets — Session Handoff: OBJ Export + Proof Guard PS→Py Migration + C# Gate Fixes

**Date:** 2026-05-20 15:35 EDT
**Branch:** `main`
**HEAD:** `80f80db` (C# gate fixes + fitness guard dual-path completion)
**Supersedes:** none
**Continues from:** `2026-05-19-213000-rift-assets-session-comprehensive-handoff.md` (8 commits ahead, from `ed66963` → `80f80db`)

---

## TL;DR

Three commits this session, all on the @264 explicit-index lane:

| Commit | What |
|--------|------|
| `896e7fa` | **OBJ face export** from `@264` UInt16BE degenerate-bridge triangle strip |
| `90f9ef8` | **Port `AttributeExtraProofGuard` + `AttributeExtraSiblingProofGuard`** from PS to Python with hardened type accessors |
| `80f80db` | **C# gate fixes** (`StartsWith("index-")` → `IndexStats is not null`) + **fitness guard dual-path** (`_attribute_extra_proof_guard_fitness()`) |

---

## Commit 1: `896e7fa` — OBJ face export

Added `--write-obj` support to `decode-nif-geometry` that produces actual triangle faces (not just point cloud) from `@264` UInt16BE degenerate-bridge triangle strip streams.

**What changed:**

- `Program.cs`: new `WriteObjGeometry` export path that decodes uint16 big-endian strip indices, handles degenerate bridges (ABBC pattern), generates face normals and UV coordinates, and writes a full Wavefront `.obj` with vertex positions, normals, UVs, and face groups per material/segment
- Works for the known `meshSize=297` / `v=128` / `@264` sample (`6fc01704d4a509d5`), behind `--experimental` flag

**Key details:**

- Strips decoded with bridge-stitch handling: degenerate `A B B C` → `A B C` triangle
- Segments delineated by restart patterns
- Per-segment face groups in OBJ output
- Bounded first-segment triangle proof still emitted for validation

**Safety:** Behind `--experimental` + `--write-obj` flags; does not run by default.

---

## Commit 2: `90f9ef8` — PS→Py Proof Guard Migration

Ported two PowerShell proof guards to Python modules with hardened type accessors.

**What changed:**

- `scripts/rift_workflow_guards.py`: new file with `attribute_extra_proof_guard()` (inventory-level) and `attribute_extra_sibling_proof_guard()` (per-asset deep proof)
- `scripts/rift_workflow_utils.py`: added `required_json_boolean()` accessor, hardened `required_json_number()`/`required_json_integer()` with boolean rejection (bool is not number)
- `scripts/rift_workflow.py`: added `attribute-extra-proof-guard` and `attribute-extra-sibling-proof-guard` command routing
- `scripts/Invoke-RiftWorkflow.ps1`: updated thin wrapper with the two new Python commands

**Guard details:**

- `attribute_extra_proof_guard()`: validates `TopAttributeExtraMappingFitness` exists, checks 4 vertex-count groups (128/95/80/64) at `meshSize=297`, `extra@264`, role `index-u16be-strip-lead`. Asserts raw-zero-based is preferred, degenerate-bridge-stitch structure, sentinel/parity-break/dropped-cross at zero, positive edge/normal/area deltas.
- `attribute_extra_sibling_proof_guard()`: deep per-asset proof of exact stream/block shape, index prefix, mapping candidates, stitch structure, first-segment triangle proof, and raw-vs-subtract-one fitness gaps.

**Known divergence:** C# role classifier returns `"uint16-compatible-body"` for many `@264` extra streams (not `"index-u16be-strip-lead"`), so index-compatibility analysis (`IndexCompatibility`, `MappingPositionFitness`, `StripStructure`) is missing from inventory output. The guards are written to assert against available data (BodyStats, Topology, RoleCandidates, RoleEvidence).

---

## Commit 3: `80f80db` — C# Gate Fixes + Fitness Guard Dual-Path

Root-caused and fixed why `TopAttributeExtraMappingFitness` was not populating, then added dual-path routing to the proof guard.

**What changed:**

- `Program.cs`:
  - **Inventory loop (L3949):** `StartsWith("index-")` → `IndexStats is not null` — this was preventing `TopAttributeExtraMappingFitness` from populating for `uint16-compatible-body` extra streams
  - **Probe loop (L2602):** Same fix — `StartsWith("index-")` → `IndexStats is not null`
  - **Fitness accumulation:** Removed `if (preferredMapping != "insufficient")` gate so fitness runs unconditionally
- `scripts/rift_workflow_guards.py`:
  - Added `_attribute_extra_proof_guard_fitness()` — validates @264 aggregate edge-delta, area-gap, strip-structure, segment, parity, and sentinel regressions against 4 vertex-count groups
  - `attribute_extra_proof_guard()` now routes dual-path: fitness path when `TopAttributeExtraMappingFitness` is populated, falls back to stream-level (`TopAttributeExtraStreams`) existence guard
- `docs/current-status.md`: updated with detailed notes on all changes

**Validation:**

- JSON field names verified against actual C# output — all match
- Proof guard passes on both limited and full inventories
- 49/49 Python unit tests pass
- C# build: 0 errors

---

## Current @264 Lane State

| Claim | Status | Evidence |
|-------|--------|----------|
| `@264/#15` is an explicit-index extra stream | ✅ Proven | 4 vertex-count groups (128/95/80/64), consistent role, degenerate-bridge stitch structure |
| Raw-zero-based index mapping is preferred | ✅ Proven across inventory (5/5) | Edge deltas, area gaps, normal gaps, UV gaps all favor raw over subtract-one |
| Strip structure is degenerate-bridge-stitch | ✅ Proven | 0 sentinels, 0 dropped cross-segment windows, mirrored bridge motifs |
| Parity proof is clean | ✅ Proven | 0 non-alternating parity transitions for both mappings across all groups |
| OBJ face export works | ✅ Behind experimental flag | Decodes strip indices, handles ABBC degenerate bridges, writes valid .obj |
| Proof guards are ported to Python | ✅ Complete | Both inventory-level and per-asset guards pass on current output |
| Role classifier returns `uint16-compatible-body` | ⚠️ Observed | Index-compatibility analysis doesn't run for these streams |
| Position source for `meshSize=325` / `v=24` family | ❌ Not yet | Still the strongest indexed-family lead without proven position stream |

---

## Safety Boundaries

| Boundary | Status |
|----------|--------|
| No live game interaction | ✅ |
| No copied assets committed | ✅ |
| OBJ export behind `--experimental` + `--write-obj` | ✅ |
| Generated output guard active | ✅ — `generated_output_guard()` in Python |
| Proof guard regressions protected | ✅ — dual-path (fitness/stream) guard active |
| No uncommitted generated output | ✅ — working tree clean |

---

## Validation (Current Session)

| Check | Result |
|-------|--------|
| `python scripts/test_rift_workflow_utils.py` | ✅ 49/49 pass |
| `dotnet build src/RiftAssetDumper/RiftAssetDumper.csproj` | ✅ 0 errors |
| JSON field name match (C# ↔ guard expectations) | ✅ All match |
| `attribute_extra_proof_guard` on limited inventory | ✅ Passes |
| `attribute_extra_proof_guard` on full inventory | ✅ Passes |
| `attribute_extra_sibling_proof_guard` on v=128 samples (`6fc01704d4a509d5`, `caa9a88e94ec8db0`) | ✅ Passes |
| Working tree: no uncommitted changes | ✅ Clean after push |

---

## Resume Prompt

```text
Resume in C:\RIFT MODDING\Assets. Work Assets-only.
main is at 80f80db with three session milestones:
1. OBJ face export from @264 UInt16BE degenerate-bridge triangle strip (896e7fa)
2. AttributeExtraProofGuard + AttributeExtraSiblingProofGuard ported PS→Py (90f9ef8)
3. C# gate fixes + fitness guard dual-path completion (80f80db)

Current @264 lane state: raw-zero-based preferred across all 4 vertex-count groups
(128/95/80/64), degenerate-bridge stitch structure, parity clean. OBJ export works
behind --experimental. Proof guards pass on both limited and full inventories.

Role classifier returns "uint16-compatible-body" (not "index-u16be-strip-lead"),
so index-compatibility fields (IndexCompatibility, MappingPositionFitness) are
null/empty for many streams. Fitness path activates when data is available;
stream-level existence path is fallback.

11 guard/report functions still deferred from PS→Py migration:
usage-access-correlation-guard, residual-lead-guard, residual-position-classifier-report,
residual-position-cluster-probe-report, position-source-gap-report,
position-source-sibling-* family (6 functions).

Validate with: dotnet build, python tests, attribute-extra-proof-guard,
attribute-extra-sibling-proof-guard (run via Invoke-RiftWorkflow.ps1 or direct Python).

Quick validation:
```

dotnet build --nologo
python scripts/rift_workflow.py attribute-extra-proof-guard --full --skip-build
python scripts/rift_workflow.py attribute-extra-sibling-proof-guard --id 6fc01704d4a509d5 --skip-build

```
```

---

## Optional Top 10 Next Actions

| # | Action |
|---:|--------|
| 1 | Run `decode-nif-geometry --write-obj --experimental` on more v=128 siblings to validate OBJ output consistency |
| 2 | Extend OBJ export to handle other vertex-count groups (v=95, v=80, v=64) |
| 3 | Port `Invoke-UsageAccessCorrelationGuard` from PS to Python |
| 4 | Port `Invoke-ResidualPositionClusterProbeReport` from PS to Python (~400 lines) |
| 5 | Investigate position source for `meshSize=325` / `v=24` family (strongest indexed-family without proven position) |
| 6 | Add index-family topology scoring directly to mesh-binding pair reports |
| 7 | Open exported OBJ files in external NIF/Gamebryo tooling for visual validation |
| 8 | Cross-validate UInt16-packed positions against float32 positions for same mesh |
| 9 | Port remaining `position-source-sibling-*` family (6 functions) from PS to Python |
| 10 | Add `ExportSafetyAssertion` to `decode-nif-geometry` OBJ export path |
