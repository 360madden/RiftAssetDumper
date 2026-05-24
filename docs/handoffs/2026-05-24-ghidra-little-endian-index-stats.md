# Ghidra little-endian index stats handoff — 2026-05-24

## Status

Implemented separate little-endian uint16 index statistics for `index-u16le-*` stream roles.

This fixes the candidate-only Ghidra pairing comparison blocker from `docs/handoffs/2026-05-24-ghidra-pairing-comparison.md`: Ghidra-aligned `index-u16le-lead` streams were classified, but their `IndexMax` was still sourced from the older big-endian index-stat path.

Default export/OBJ behavior remains unchanged.

## What changed

- Added `AnalyzeNifUInt16LeIndex(...)`.
- Added `NifUInt16LeIndexStats`.
- Added `LittleEndianIndexStats` to `NifMeshStreamRoleStats`.
- Updated `AnalyzeNifMeshBoundStreamRole(...)` so `little-endian-u16-lead` uses:
  - little-endian distinct index count,
  - little-endian triangle/degen stats,
  - little-endian max index,
  - little-endian pair count.
- Added a C# unit test proving a synthetic little-endian index body resolves:
  - `PrimaryRole = index-u16le-lead`
  - `IndexMax = 23`
  - `IndexPairCount = 24`
- Reran the existing candidate-only Ghidra pairing comparison.

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

Top candidate-only Ghidra pairings now include:

| Mesh size | Count | Index role | Vertex role | Vertex count | Max index |
|---:|---:|---|---|---:|---:|
| 325 | 134 | `index-u16le-lead` | `normal-float3-lead` | 24 | 23 |
| 325 | 90 | `index-u16le-lead` | `uv-float2-ror1-lead` | 24 | 23 |
| 321 | 60 | `index-u16le-lead` | `normal-float3-lead` | 24 | 23 |
| 301 | 40 | `index-u16le-lead` | `u32-repeated-pattern-body` | 48 | 47 |
| 301 | 39 | `index-u16le-lead` | `position-float3-lead` | 48 | 47 |

## Interpretation

The earlier zero-pairing result was a stat-wiring problem, not proof that the Ghidra-aligned role path was unusable.

The Ghidra candidate path now has slightly more compatible mesh/link counts than the legacy path (`1,972/4,259` versus `1,949/4,199`), but it is still not export-ready because some top candidate pairings include low-confidence vertex-side classifications such as `u32-repeated-pattern-body`.

## Remaining unwired pieces

- Ghidra pairings remain report-only.
- Export, OBJ, pairing guards, and attribute-set promotion still consume legacy/default fields.
- No confidence/role whitelist exists yet for deciding which Ghidra pairings are promotable.
- Legacy-pairing versus Ghidra-pairing overlap/gaps are now summarized in `docs/handoffs/2026-05-24-ghidra-pairing-overlap.md`.

## Recommended next milestone

Add a report-only legacy-vs-Ghidra pairing overlap/gap summary:

- same mesh + same index/vertex stream offsets,
- legacy-only pairings,
- Ghidra-only pairings,
- shared pairings with role/confidence deltas.

Do not promote Ghidra pairing/export behavior until the Ghidra-only rows are explainable and guarded.
