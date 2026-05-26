# Handoff: Step 49 bounded RiftReader triplet probe

Date: 2026-05-26

## Goal

Use RiftReader as the primary live-memory scanner for a bounded candidate-only Step 49 float3 probe, avoiding another unbounded full-process scan.

## What changed

- Updated Step 49 status with the new bounded RiftReader triplet command:
  - `--scan-float-triplet <x,y,z>`
  - `--scan-region-base <address>`
  - `--scan-region-size <bytes>`
- Recorded the first bounded triplet probe result.
- Kept Step 49 in progress and parser/export promotion blocked.

## Evidence

- RiftReader commit with bounded scan routing: `994ead8`.
- Bounded probe region: `0x1C90E752000`, size `8192` bytes.
- Positive-control triplet from previously observed live context:
  - Hit count: `2`.
- Expected static mesh `v0` triplet in the same bounded region:
  - Hit count: `0`.
- Follow-up bounded expected-static batch:
  - Regions: `4`.
  - Static vertices: `v0-v3`.
  - Scans: `16`.
  - Timed out: `0`.
  - Expected-static hits: `0`.
- Interpretation: the bounded scanner works, but the first four single-float hit regions do not confirm the expected static position stream.

## Validation

- RiftReader:
  - `dotnet test reader/RiftReader.Reader.Tests/RiftReader.Reader.Tests.csproj --no-restore`
  - `dotnet build RiftReader.slnx --no-restore`
  - `python -m unittest scripts.test_coord_freshness_documentation`
- Assets validation for the tracked status/docs update is run in the associated commit gate.

## Generated-output policy

Detailed live reports remain ignored under `Exports/discovery-plan/stage5-live/` and were not staged.

## Known blockers

- Step 49 is still not complete.
- Need better region seeds or proof the target asset is actually loaded before declaring a shared live position stream.
- Parser/export promotion remains blocked.

## Next recommended actions

1. Derive better region seeds from module/asset-loading evidence or broader but still bounded scans.
2. Confirm whether the target mesh asset is expected to be loaded in the current character-selection state.
3. Confirm two or more expected static float3 samples share one live stream before marking Step 49 complete.
4. Keep live reports ignored.
5. Update `docs/live-memory-step49-status.json` only after each coherent candidate-only probe batch.
