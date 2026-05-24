# Ghidra role-delta ranking handoff — 2026-05-24

## Status

Implemented a read-only MeshBindings report ranking for legacy `RoleStats` versus Ghidra-aligned `GhidraRoleStats`.

No decoder, pairing, attribute-set, OBJ, or export behavior changed. Legacy role consumers still use the historical offset-29 body slice.

## What changed

- Added `TopGhidraRoleDeltas` to `inventory-nif-mesh-bindings`.
- Grouping dimensions:
  - legacy role
  - Ghidra-aligned role
  - declared payload bytes
  - `DataStreamUsage` / `DataStreamAccess`
  - mesh block size
- Each group carries:
  - count and distinct NIF payload count
  - average legacy/Ghidra confidence
  - mesh payload offset histogram
  - legacy/Ghidra first-16-byte histograms
  - concrete samples with existing stream sidecar fields
- Python `mesh-bindings` workflow summaries now print the top delta families.
- Added a Python summary regression test for the new output line and missing-field compatibility.

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
| Pair-compatible meshes | 1,949 |
| Pair-compatible links | 4,199 |

Top delta families from the run:

| Mesh size | Payload | Usage/access | Legacy role | Ghidra role | Count |
|---:|---:|---|---|---|---:|
| 325 | 72 | usage=0 access=19 | `index-u16be-strip-lead` | `index-u16le-lead` | 135 |
| 325 | 288 | usage=1 access=19 | `normal-float3-ror1-lead` | `normal-float3-lead` | 134 |
| 301 | 144 | usage=0 access=19 | `index-u16be-strip-lead` | `index-u16le-lead` | 64 |
| 321 | 288 | usage=1 access=19 | `normal-float3-ror1-lead` | `normal-float3-lead` | 64 |
| 321 | 72 | usage=0 access=19 | `index-u16be-strip-lead` | `index-u16le-lead` | 60 |

## Interpretation

This makes the previous aggregate delta count actionable. The leading groups show the likely one-byte legacy-body-shift compensation patterns:

- legacy `index-u16be-*` roles can become Ghidra-aligned little-endian index roles;
- legacy rotate-right-1 normal roles can become direct Ghidra-aligned float3 roles;
- some small UV/normal payload families still collapse into low-confidence repeated-pattern bodies and should not be promoted without more guards.

## Remaining unwired pieces

- Export/decode code still uses legacy `RoleStats`.
- Pairing and attribute-set logic still consume legacy roles.
- No role names were promoted or renamed.
- No OBJ/export behavior was changed.
- No guard/switch exists yet to compare legacy pairings against Ghidra-aligned pairings.

## Recommended next milestone

Add a candidate-only Ghidra-aligned pairing summary that runs the existing pairing finder over `GhidraRoleStats` without changing the default `TopPairings`, exports, or guards. Compare pair-compatible mesh/link counts against the legacy path before considering any promotion switch.
