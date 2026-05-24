# Ghidra pairing comparison handoff — 2026-05-24

## Status

Implemented a candidate-only pairing comparison path for Ghidra-aligned stream roles.

Default pairing/export behavior remains unchanged. Legacy `PairCompatibleMeshes`, `PairCompatibleLinks`, and `TopPairings` still use legacy `RoleStats`.

## What changed

- Added `GhidraPairCompatibleMeshes`.
- Added `GhidraPairCompatibleLinks`.
- Added `TopGhidraPairings`.
- Reused the existing pairing finder over a cloned stream-summary list where `RoleStats` is replaced by `GhidraRoleStats`.
- Kept the Ghidra pairing output separate from existing legacy pairing fields.
- Python `mesh-bindings` summaries now print Ghidra pairing counts and `Top Ghidra pairings` when present.
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
| Ghidra pair-compatible meshes | 0 |
| Ghidra pair-compatible links | 0 |

## Interpretation

The comparison is now wired, but it proves the Ghidra-aligned role path is **not promotion-ready**.

The leading role deltas still look useful, but current Ghidra-aligned pairing produces zero compatible pairs. That suggests at least one required role-stat field is still not equivalent to the legacy path. A likely next target is little-endian index statistics for `index-u16le-lead`, because the current role classifier still carries the older big-endian index stats shape.

Update: `docs/handoffs/2026-05-24-ghidra-little-endian-index-stats.md` implements that follow-up. Candidate-only Ghidra pairings now produce nonzero pair counts after `index-u16le-*` roles use separate little-endian index bounds.

## Remaining unwired pieces

- No Ghidra pairing field is used by export, OBJ, or guards.
- Ghidra-aligned pairings currently produce zero compatible pairs.
- Little-endian index max/count truth is not yet independently represented.
- Attribute-set logic still consumes only legacy pairings/roles.

## Recommended next milestone

Add report-only little-endian uint16 index statistics for Ghidra-aligned `index-u16le-*` streams, then rerun the same candidate-only Ghidra pairing comparison. Do not promote pairing/export behavior until Ghidra pair counts become explainable and guardable.
