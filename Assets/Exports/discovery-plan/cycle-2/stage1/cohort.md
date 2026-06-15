# C2-1.4 — Curated Cohort (~25 assets)

**Generated**: 2026-06-15
**Step**: C2-1.4
**Plan version**: v0.3 (was v0.2 = 39 assets; trimmed in v0.3 for V4 Pro 1-page brief fit)
**Source data**: `Assets/build/flythrough/flythrough-index.json` (217 assets)
**Cohort file**: `cohort.json` (machine-readable)

---

## Composition

The cohort is a **stratified subsample** of ~25 assets selected from the 217-asset
flythrough set, balancing the dimensions most relevant to cycle 2's world-reconstruction
goal: scene-graph complexity, MeshSize family coverage, and materialization edge cases.

Sized to fit comfortably on a V4 Pro 1-page brief (v0.2 was 39 — too dense for review).

| Stratum | Count | Rationale |
|---|---:|---|
| **Non-identity transform** | 4 | Verified by walking the 217 `world.json` files: actual count is **4** (plan §0 said "5" — stale). Cohort reflects ground truth. See `artifacts.md` for the 4 IDs + their transforms. |
| **MeshSize 325 family** | 5 | Top family by asset count. Sets "default" expectations. |
| **MeshSize 321 family** | 5 | Second-largest family. Catches MeshSize-specific behavior. |
| **MeshSize 305 family** | 5 | Includes 2 of the 4 non-id assets (MS-305 family). |
| **MeshSize 329 family** | 3 | Plan cap = 5, but the flythrough subset only has 3. Capped at family size. Focus of M1.1/M1.2 attribute role matrix work. |
| **Multi-mesh edge case** | 1 | `1ecdbaf5a2576ba5` (11 meshes — max). |
| **MB-variant edge case** | 1 | `42024b768fcd2e2b` (MeshSize 305, MB=6 float2 + MB=34 float3 — proven Z-source pair from Phase 17). |
| **Orphan-mesh regression test** | 1 | `6fc01704d4a509d5` (single-mesh NIF in `TestOrphanMeshResolution`). |
| **Pos-only no-texture** | 1 | One of the 5 unresolvable textureless assets (`0e0c61ad75d2af1e`). |
| **Total** | **~25** | Target band: 20-30. |

---

## Selection rules (applied deterministically)

1. **Non-identity transform**: the 4 IDs from the C2-1.2 walk of all 217 `world.json`
   files (translation any component > 1e-6, OR rotation ≠ identity matrix, OR scale ≠ 1.0).
2. **Per-family selection**: for the top 4 MeshSize families (325, 305, 329, 321),
   take the first 5 (or family-size, whichever is smaller) alphabetically-sorted
   members. **Note**: MS=329 has only 3 members in the flythrough subset; cohort
   reflects actual family size.
3. **Edge cases**: 3 hand-picked by ID, prioritizing the highest-complexity NIFs
   and the assets already referenced in regression tests. Was 5 in v0.2; trimmed
   `multi-mesh-32` (32-mesh NIF, same scenario as `multi-mesh-11` at smaller scale)
   and `large-hierarchy` (17-node — superseded by the merged 11/32-mesh coverage).
4. **Pos-only no-texture**: 1 of 5 unresolvable textureless assets, subsampled to
   keep cohort size in band.

**Determinism**: the same `flythrough-index.json` always yields the same cohort.
If the index grows (LOD expansion in C2-8, or new MeshSize families discovered),
the cohort is regenerated; no other cycle 2 step depends on the specific IDs.

**Reproducibility**: `scripts/build_cycle_2_cohort.py` re-derives the cohort from
`Assets/build/flythrough/flythrough-index.json` + the live `Assets/build/flythrough/objs/worlds/`
directory. Run it any time the index changes; the output is byte-stable for an
unchanged index.

---

## How the cohort is used downstream

| Phase | Use |
|---|---|
| **C2-2.1** (T/R/S examples) | Compute Scale/Rotate/Translate per asset; ~25 rows × 3 = ~75 fields to verify finite-ness. |
| **C2-2.2** (pattern comparison) | Compare patterns across the 4 non-identity + ~21 identity; expect a clean 2-cluster split. |
| **C2-2.3** (semantics) | Use the multi-mesh member to decide which NiNode drives world placement. |
| **C2-2.4** (handedness/axis/quaternion/scale) | Hand-verify 2-3 cohort members in Blender against computed transforms. |
| **C2-V4P1+2** (transform + schema contract) | Single combined V4 Pro session reviewing transform truth + scene-manifest v1 schema. |
| **C2-3.x** (material closure) | Per-asset texture/material resolution chain; coverage stats. |
| **C2-4.x** (schema prep) | Pre-validate `scene-manifest/v1` draft against cohort samples. |
| **C2-5.x** (batch reconstruction) | Generate per-asset manifests for the cohort. |
| **C2-6.x** (consumer validation) | Load the cohort into RiftFlythrough, render Blender screenshots, check placements. |
| **C2-7.x** (scale-out) | Expand from ~25 → 200-500 assets; the ~25 become the "known-good" reference set. |

---

## v0.2 → v0.3 cohort delta

- **Removed**: 2 edge cases (`multi-mesh-32`, `large-hierarchy`) — covered by `multi-mesh-11` and the merged C2-2 phase.
- **Trimmed**: per-family take 10→5 (MS=325/321/305/329; 14 fewer family assets).
- **Kept**: 4 non-id, 1 pos-only no-texture (both stratified dimensions).
- **Net**: 39 → ~25 (~36% reduction). Fits V4 Pro 1-page brief; same statistical power for the 4 non-id decisions.

---

## Drift prevention

If `flythrough-index.json` changes during cycle 2:

1. Re-run `python scripts/build_cycle_2_cohort.py --out Assets/Exports/discovery-plan/cycle-2/stage1/cohort.json`:
   same script, same rules, same IDs (modulo assets dropped from the index — a major event).
2. If a cohort member's `world.json` is missing, the per-asset manifest will
   fail C2-5 and surface in `coverage-stats.md`.
3. The 4 non-identity IDs may change if a world.json is regenerated with
   different transforms. C2-2's "transform truth" output is the durable
   source; the cohort is just a sample.

The cohort is **not durable truth** — it's a working subset. C2-5 (per-asset
manifests) is the durable output.
