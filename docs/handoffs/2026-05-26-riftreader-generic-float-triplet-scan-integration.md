# Handoff: RiftReader generic float-triplet scan integration

Date: 2026-05-26

## Goal

Keep the Assets live-memory workflow aligned with the existing RiftReader scanner rather than adding another Assets-local scanner path.

## What changed

- Updated Step 49 status to note that RiftReader now exposes bounded `--scan-float-triplet <x,y,z>` probes.
- Updated the 50-step tracker and AI workflow docs to prefer RiftReader for candidate float3 live probes.
- Kept the existing Step 49 evidence candidate-only; the prior single-float probe remains noisy and not cluster-confirmed.

## Evidence / validation

- RiftReader commits:
  - `97a38d6` (`feat: expose generic float triplet scan`)
  - `36ea28d` (`feat: add bounded float triplet scans`)
  - `994ead8` (`fix: route float triplet scans`)
- RiftReader validation before push:
  - `dotnet test reader/RiftReader.Reader.Tests/RiftReader.Reader.Tests.csproj --no-restore`
  - `dotnet build RiftReader.slnx --no-restore`
- Assets validation for this docs/status update is tracked in the associated commit gate.

## Known blockers

- The generic triplet command enables the next probe, but Step 49 still needs a bounded live run and a shared-stream/cluster comparison before completion.
- Parser/export promotion remains blocked.

## Generated-output policy

Any Step 49 live scan reports must stay under ignored `Exports/discovery-plan/stage5-live/`.

## Next recommended actions

1. Run bounded `--scan-float-triplet <x,y,z> --scan-region-base <address> --scan-region-size <bytes>` probes for guarded static vertex samples.
2. Compare returned hit regions/offsets across multiple vertices for one shared stream.
3. Keep all detailed live reports ignored.
4. Update `docs/live-memory-step49-status.json` only after the cluster result is clear.
5. Do not promote parser/export behavior until a separate guard-backed proof exists.
