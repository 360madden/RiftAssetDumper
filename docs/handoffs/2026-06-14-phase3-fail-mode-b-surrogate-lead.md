# 2026-06-14 — Phase 3 FAIL Mode B — Surrogate lead recorded (Step 49 still closed-negative)

**Date**: 2026-06-14 (filled at decision time)
**Type**: Phase 4 lead handoff — recorded alongside a §8.4 FAIL Mode B verdict
**Scope**: Documents the surrogate address set discovered in the out-of-region hits; proposes Phase 4 probe directions; Step 49 status remains `closed-negative-current-live-state`
**Status**: Pending (template — operator fills at decision time)
**Trigger**: §8.4 FAIL verdict with mode-B classification (0 in-region, ≥1 out-of-region)
**Originating handoffs**:
`docs/handoffs/2026-06-14-phase3-fail-step49-stays-closed.md` (parent FAIL record),
`docs/handoffs/2026-06-13-phase3-bounded-triplet-invocation.md` (Phase 3 invocation),
`docs/handoffs/2026-06-13-phase2-co-location-at264-invocation.md` (Phase 2 anchor A)

## Pre-flight (operator confirms before creating this handoff)

- [ ] §8.4 FAIL template filled in `docs/handoffs/2026-06-14-phase3-fail-step49-stays-closed.md` with mode-B verdict
- [ ] Per-vertex out-of-region hit addresses captured from the four `phase3-bounded-triplet-<UTC>-vN.json` files
- [ ] At least one out-of-region hit address recorded (mode-B prerequisite)

## Source data (operator fills from the four Phase 3 JSONs)

### Raw out-of-region hits (per-vertex)

| Vertex | Triplet | Out-of-region addresses |
|---|---|---|
| v0 | `(8.458028, 55.920349, 11.567474)` | TBD, TBD, … |
| v1 | `(5.999848, 54.718262, 13.064880)` | TBD, TBD, … |
| v2 | `(7.556799, 52.199829, 11.407593)` | TBD, TBD, … |
| v3 | `(5.999830, 52.299988, 12.751602)` | TBD, TBD, … |

### Deduplicated surrogate address set

A hit from multiple vertices at the same address is the strongest signal of a shared surrogate buffer; record these first. The remaining addresses (single-vertex hits) are weaker candidates.

| Address | Vertices that hit it | Hit count | Strength |
|---|---|---:|---|
| `0x<HEX>` | v0, v1, v2, v3 (all four) | 4 | Strongest — shared surrogate across all vertices |
| `0x<HEX>` | v0, v2 (two) | 2 | Strong — shared surrogate across a subset |
| `0x<HEX>` | v3 (single) | 1 | Weak — single-vertex coincidence |
| `0x<HEX>` | v0, v1, v2, v3 (different addresses per vertex) | 1 each | Weakest — per-vertex dispersion, likely staging/transient |

**Strength scoring rule:** the more vertices that share an address, the more likely it is a real surrogate buffer (vs. random noise). A 4/4 shared address is the most actionable lead; 1/1 addresses are the least.

## Candidate classification

The surrogate address pattern disambiguates between four candidate live representations. Pick the dominant pattern from the table above and record the classification:

| Candidate | Pattern signature | Probe direction |
|---|---|---|
| **Instanced geometry buffer** | 4/4 vertices share one address | `probe-nif-scene-graph` on the asset ID; check the instance transform path |
| **Transformed/animated positions** | 1/1 addresses per vertex (no sharing) | Look for an animation update function in the Ghidra decompilation; check float4 matrix-multiply residency |
| **GPU upload staging buffer** | Random 1/1 addresses, no structure | `probe-binary` against `d3d11.dll` or `d3d12.dll` upload paths; check for transient write patterns |
| **LOD / simplified version** | 2-3/4 vertices share an address; the other 1-2 are different | `probe-nif-mesh` on alternate MeshSize families for the same asset ID; check LOD chains |

**Classification**: TBD

## Proposed Phase 4 probe directions

The Phase 4 follow-up would disambiguate the candidate classification above. The probe direction depends on the dominant surrogate address pattern. Record the proposed probe (or set of probes) here; each is an operator-side action item for a future load state.

### Probe A: shared 4/4 surrogate → instanced geometry

- [ ] Run `dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj -- probe-nif-scene-graph --id 6fc01704d4a509d5` in a different load state (different zone, same asset)
- [ ] Cross-reference the instance transform path with the surrogate address
- [ ] Decision: if the address maps to a known instance buffer, the representation is **instanced**, not raw-contiguous-static; Step 49 stays `closed-negative-current-live-state` but the live representation is now understood

### Probe B: 1/1 per-vertex dispersion → transformed/animated

- [ ] Spawn a Ghidra survey against `rift_x64.exe` looking for animation update functions (matrix-multiply residency on the surrogate addresses)
- [ ] Cross-reference the Ghidra findings with the per-vertex addresses
- [ ] Decision: if the dispersion matches an animation update, the representation is **transformed per-frame**, not raw-contiguous-static

### Probe C: random 1/1 → GPU upload staging

- [ ] Run `probe-binary` against the D3D upload path for the surrogate addresses
- [ ] Check for transient write patterns (write-and-forget within a single frame)
- [ ] Decision: if staging is confirmed, the representation is **GPU-side transient**, not raw-contiguous-static; this would be a permanent Step 49 negative result with no useful in-process surrogate

### Probe D: 2-3/4 shared → LOD chain

- [ ] Run `probe-nif-mesh` on alternate MeshSize families for the same asset ID
- [ ] Check `infer_meshsizes.py` for sibling MeshSize family relationships
- [ ] Decision: if the alternate MeshSize family is the actual rendered mesh, the representation is **LOD-resolved**, not raw-contiguous-static

## Status decision

Step 49 status: `closed-negative-current-live-state` (UNCHANGED)

- File: `docs/live-memory-step49-status.json` — no change
- No schema validation required
- No proof-guard re-run required (closed-negative result preserves current baselines)
- This handoff is a **follow-up lead**, not a status update

## Commit pattern (two-commit sequence)

1. First: the §8.4 FAIL template commit
   - Filename: `docs/handoffs/2026-06-14-phase3-fail-step49-stays-closed.md`
   - Commit message: `docs: phase3 FAIL — step49 stays closed-negative-current-live-state (mode B)`
2. Then: this Phase 4 lead handoff commit
   - Filename: `docs/handoffs/2026-06-14-phase3-fail-mode-b-surrogate-lead.md` (this file)
   - Commit message: `docs: phase3 FAIL mode B — surrogate lead recorded (step49 still closed-negative)`

The two commits land consecutively in `git log` so the FAIL verdict and the lead discovery are temporally traceable.

## Cross-references

- §8.4 FAIL template (parent decision record): `docs/handoffs/2026-06-14-phase3-fail-step49-stays-closed.md`
- §8.4 PASS template (sibling): `docs/handoffs/2026-06-14-phase3-pass-step49-status-update.md`
- Phase 3 invocation: `docs/handoffs/2026-06-13-phase3-bounded-triplet-invocation.md`
- Phase 2 invocation: `docs/handoffs/2026-06-13-phase2-co-location-at264-invocation.md`
- Phase 1 invocation: `docs/handoffs/2026-06-13-phase1-live-read-invocation.md`
- Operator load-state handoff: `docs/handoffs/2026-06-13-operator-load-state-target-assets.md`
- Step 49 status file (unchanged): `docs/live-memory-step49-status.json`
- Step 49 schema: `docs/schemas/live-memory-step49-status-v1.schema.json`
- Parser UX follow-up (still unblocked — ships after the two-commit sequence lands): `docs/handoffs/2026-06-14-parser-ux-region-pin-hint.md`
- Follow-up batch cross-ref: `docs/handoffs/2026-06-13-m3-safe-followup-batch.md` §"Deferred items"
- §8.4 decision pre-draft (consolidated commit templates + status-update payloads + schema-widening + proof-guard gate): `docs/handoffs/2026-06-14-phase3-decision-pre-draft.md`

## Decision log

- 2026-06-14: Template pre-staged by autonomous session continuation. To be filled at decision time and committed as the second of two commits in the §8.4 FAIL Mode B path.
