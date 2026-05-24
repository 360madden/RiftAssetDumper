# Ghidra mesh-probe sidecar pairings handoff — 2026-05-24

## Status

Implemented focused `probe-nif-mesh` sidecar output for Ghidra-aligned pairings.

This remains candidate-only/read-only. Legacy `Pairings`, attribute sets, export, OBJ, and proof guards are unchanged.

## What changed

- `probe-nif-mesh` now computes Ghidra-aligned per-mesh pairings by reusing the existing sidecar role summaries.
- Added top-level probe count:
  - `GhidraPairings`
- Added per-mesh probe field:
  - `GhidraPairings`
- Console output now prints `ghidraPairings=...` and per-mesh `ghidra-pairing` rows.
- Python `MeshProbe` summaries now show top Ghidra pairings when present.
- Added Python summary regression coverage for the new `MeshProbe` Ghidra pairing output.

## Validation evidence

Build:

```powershell
dotnet build RiftAssetDumper.slnx --no-restore
```

Result: PASS with existing warnings only:

- SharpCompress `NU1902`
- nullable `CS8602` warnings in existing code

Focused workflow smoke:

```powershell
python scripts/rift_workflow.py mesh-probe --id 25f30ec90608eab7 --mesh-block 7 --skip-build
```

Result:

| Metric | Result |
|---|---:|
| Candidate stream links | 4 |
| Legacy pairings | 0 |
| Ghidra pairings | 3 |
| Attribute sets | 0 |

Focused sidecar pairings found for mesh#7 / meshSize=301:

| Index stream | Ghidra index role | Vertex stream | Ghidra vertex role | Vertex count | Confidence |
|---|---|---|---|---:|---:|
| `@184/#18` | `index-u16le-lead` | `@268/#22` | `normal-float3-lead` | 8 | 55 |
| `@184/#18` | `index-u16le-lead` | `@276/#24` | `position-float3-lead` | 8 | 55 |
| `@184/#18` | `index-u16le-lead` | `@192/#20` | `u32-repeated-pattern-body` | 8 | 35 |

Generated-output guard passed; generated probe output stayed ignored under `Exports/`.

## Interpretation

The review-report top sample can now be inspected through the normal `mesh-probe` workflow without manually reading the full inventory. This confirms why the review row was ranked: the same mesh has no legacy pairings but has three Ghidra sidecar pairings.

This still does not prove exportable geometry. One Ghidra vertex role is `position`, one is `normal`, and one is `other`; the role transition remains candidate evidence until a deeper byte/vector/index probe explains it.

## Remaining unwired pieces

- No export, OBJ, attribute-set, or proof-guard behavior consumes `GhidraPairings`.
- No detailed decoded legacy-vs-Ghidra vector/index stats report exists yet.
- No promotable whitelist exists for Ghidra semantic transitions.

## Recommended next milestone

Add a deeper candidate-only probe detail section for each Ghidra pairing:

- index distinct/degenerate/max/count stats,
- vertex role stats and first decoded vector samples,
- legacy-vs-Ghidra body first bytes side by side,
- a clear `CandidateOnly=true` note in JSON.
