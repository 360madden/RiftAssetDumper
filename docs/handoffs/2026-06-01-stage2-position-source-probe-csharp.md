# Stage 2 Handoff — C# Position Source Probe (Steps 17-19)

Date: 2026-06-01

## Summary

Added `probe-nif-position-source` C# command that scans NiMesh payload windows for inline float3 positions and unlinked NiDataStream neighbor blocks for orphan positions. Wired into command dispatch, switch cases, and usage text.

## Changes

### Modified: `src/RiftAssetDumper/Program.cs`

#### New record types

- `NifInlinePositionCandidate` — offset, stride, floatCount, vertexCount, firstFloat3 hex
- `NifOrphanPositionCandidate` — blockIndex, blockSize, offset, stride, declaredPayloadBytes, floatCount, vertexCount, firstFloat3 hex, blockTypeName
- `NifPositionSourceMeshProbe` — meshBlockIndex, meshSize, meshDataOffset, inlineCandidates, orphanCandidates
- `NifPositionSourceProbeReport` — BinaryAssetSource, length, nifVersion, meshBlockCount, meshesEmitted, meshes list

#### New functions

- `ProbeNifPositionSource(AppOptions)` — orchestrates probe: loads NIF, filters NiMesh blocks (supports `--mesh-block`), runs inline + orphan scans per mesh, emits JSON report to `nif-position-source.json`
- `FindNifInlinePositionCandidates` — scans mesh payload at 4-byte granularity for unclaimed float3-aligned spans with non-NaN/finite validation
- `FindNifOrphanPositionCandidates` — looks at unlinked NiDataStream/NiBinaryStream blocks within ±8 of mesh block, validates declared payload size, float3 divisibility, and NaN/Infinity

#### Command dispatch

- Added `case "probe-nif-position-source"` to switch statement
- Added `if-block` dispatch calling `ProbeNifPositionSource(options)`
- Added usage text: `dotnet run -- probe-nif-position-source --root <folder> --id <hex> [--mesh-block <n>]`

### New: `scripts/rift_position_gap_report.py`

Python script that reads a mesh-binding inventory JSON and produces a position-gap analysis report. Finds mesh sizes with strong normal + UV pairings but missing position streams, groups by role profile, and explains which families have the best chance of decoding from neighbor blocks or inline payload windows.

### Modified: `scripts/rift_workflow.py`

- Added `position-gap-report` command wiring
- Added import for `generate_position_gap_report`

## Validation

| Check | Result |
|---|---|
| C# build (`dotnet build`) | ✅ 0 errors, 0 warnings |
| Code review | ✅ patterns match existing probes, no logic issues |
| Python script syntax | ✅ compiles clean |

## Usage

```powershell
# C# position source probe (new)
dotnet run --project src/RiftAssetDumper -- probe-nif-position-source --root <SourceFolder> --id <16hex> [--mesh-block <n>]

# Python position gap report (new)
python scripts/rift_position_gap_report.py --inventory <path> --out <path>

# Via workflow orchestrator
python scripts/rift_workflow.py position-gap-report --inventory <path>
```

## Next steps (from Stage 2 plan)

- **Step 20** — Run position-source probe on top indexed families (e.g. `meshSize=325`, `meshSize=321`)
- **Step 21** — Attempt neighbor-block position decode (C#)
- **Step 22** — Wire position discovery into `decode-nif-geometry` (C#)
