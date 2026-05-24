# NiDataStream layout helper migration handoff — 2026-05-24

## Status

Implemented the next guarded C# migration after `docs/handoffs/2026-05-24-nidatastream-layout-mismatch.md`.

Decoder/export behavior remains unchanged. The existing legacy role fields still use the historical body slice at offset `29`; new sidecar fields expose the Ghidra-aligned layout/body/role evidence for comparison.

## What changed

- Added shared C# `AnalyzeNifDataStreamLayout(...)` logic.
- Added synthetic unit tests for:
  - `28-byte prefix + declared payload + 1-byte trailing flag`
  - declared-payload-past-block rejection
- Added layout fields to stream reports:
  - `LegacyPayloadOffset`
  - `PayloadPrefixBytes`
  - `PayloadTrailerBytes`
  - `TrailingFlag`
  - `GhidraStyleLayoutValid`
  - `LegacyOffsetMinusPayloadPrefixBytes`
- Added sidecar Ghidra-aligned body evidence:
  - `GhidraBodyFirst16` / `GhidraBodyFirst128`
  - `GhidraRoleStats` / `GhidraStats`
- Kept legacy fields unchanged:
  - `HeaderBytes`
  - `BodyFirst16`
  - `RoleStats`
  - existing pairing/export behavior

## Validation evidence

### Stream-body inventory

Command:

```powershell
python scripts/rift_workflow.py stream-bodies --limit 25
```

Result:

| Metric | Result |
|---|---:|
| NIF payloads | 5,111 |
| `NiDataStream` blocks | 31,777 |
| Valid stream bodies | 31,777 |
| Invalid stream bodies | 0 |
| Ghidra-style layout valid stream bodies | 31,777 |
| Legacy offset shifted stream bodies | 31,777 |
| Ghidra classification deltas | 20,792 |

### Mesh-binding inventory

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

## Interpretation

The offset mismatch is no longer just a Python/Ghidra side report. The C# reports now carry enough sidecar truth to compare legacy analysis against the Ghidra-aligned body slice.

The large delta counts are expected and important:

- legacy body slice starts at byte `29`
- Ghidra-aligned body slice starts at byte `28`
- many existing `*-ror1-*` roles are likely compensating for the one-byte shift

## Remaining unwired pieces

- Export/decode code still uses legacy `RoleStats`.
- Pairing/attribute-set logic still consumes legacy roles.
- No role names were promoted or renamed.
- No OBJ/export behavior was changed.
- The next patch should add a guard/promotion switch that can intentionally choose Ghidra-aligned stats for candidate comparison before touching export output.

## Recommended next milestone

Add a report-only comparison that groups legacy role -> Ghidra-aligned role deltas by payload size, usage/access, and mesh size. Use that to decide the smallest safe promotion path for `position/normal/uv/index` role consumers.
