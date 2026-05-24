# Ghidra pairing overlap handoff — 2026-05-24

## Status

Implemented a report-only overlap/gap surface comparing default legacy pairings to candidate-only Ghidra-aligned pairings.

Default export/OBJ behavior remains unchanged. `TopPairings` still uses legacy/default `RoleStats`; Ghidra comparison fields are sidecar evidence only.

## What changed

- Added top-level pairing comparison counts:
  - `GhidraSharedPairings`
  - `LegacyOnlyPairings`
  - `GhidraOnlyPairings`
- Added `TopGhidraPairingComparisons`.
- Shared/only identity is based on:
  - same NIF payload,
  - same mesh block,
  - same index stream offset/block,
  - same vertex stream offset/block.
- Comparison groups retain:
  - status: `shared`, `legacy-only`, or `ghidra-only`,
  - mesh size,
  - legacy index/vertex roles,
  - Ghidra index/vertex roles,
  - average legacy/Ghidra confidence,
  - concrete samples with both pairing records when available.
- Python `mesh-bindings` summary now prints the overlap/gap counts and top comparison groups.
- Extended the Python workflow-report regression test.

## Validation evidence

Command:

```powershell
python scripts/rift_workflow.py mesh-bindings --limit 25 --skip-build
```

Result:

| Metric | Result |
|---|---:|
| NIF payloads | 5,111 |
| NiMesh blocks | 5,507 |
| Candidate stream links | 11,564 |
| Valid declared stream bodies | 11,564 |
| Invalid declared stream bodies | 0 |
| Ghidra-style layout valid stream bodies | 11,564 |
| Legacy offset shifted stream bodies | 11,564 |
| Ghidra role deltas | 10,880 |
| Legacy pair-compatible meshes | 1,949 |
| Legacy pair-compatible links | 4,199 |
| Ghidra pair-compatible meshes | 1,972 |
| Ghidra pair-compatible links | 4,259 |
| Shared pairings | 4,195 |
| Legacy-only pairings | 4 |
| Ghidra-only pairings | 64 |

Top comparison groups:

| Status | Mesh size | Count | Legacy roles | Ghidra roles |
|---|---:|---:|---|---|
| shared | 301 | 276 | `index-u16be-strip-lead -> uv-float2-ror1-lead` | `index-u16le-lead -> position-float3-lead` |
| shared | 325 | 192 | `index-u16be-strip-lead -> normal-float3-ror1-lead` | `index-u16le-lead -> normal-float3-lead` |
| shared | 301 | 178 | `index-u16be-strip-lead -> normal-float3-ror1-lead` | `index-u16le-lead -> normal-float3-lead` |
| shared | 309 | 165 | `index-u16be-strip-lead -> uv-float2-ror1-lead` | `index-u16le-lead -> position-float3-lead` |
| shared | 325 | 143 | `index-u16be-strip-lead -> uv-float2-ror1-lead` | `index-u16le-lead -> uv-float2-ror1-lead` |

## Interpretation

The Ghidra-aligned path overlaps strongly with the legacy pairing path: `4,195` of `4,199` legacy pair links have a same-stream Ghidra counterpart.

The Ghidra-only delta is small (`64` links), but it is not automatically promotable. Some shared groups also change vertex role labels in surprising ways, e.g. legacy UV becoming Ghidra `position-float3-lead`. This supports more focused role/attribute review before touching export behavior.

## Remaining unwired pieces

- No export, OBJ, or guard behavior consumes Ghidra pairings.
- No promotable whitelist exists for Ghidra role transitions.
- No focused sample-probe command yet ranks the `64` Ghidra-only links.
- Attribute-set logic still uses legacy/default roles.

## Recommended next milestone

Add a candidate-only review report for Ghidra-only pairings and suspicious shared role transitions:

- prioritize the 64 Ghidra-only links,
- rank shared rows where vertex semantic class changes,
- include samples with stream offsets, first bytes, usage/access, and confidence deltas,
- keep output under ignored `Exports/` and do not modify export behavior.
