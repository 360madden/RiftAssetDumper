# Handoff — NiDataStream nullable warning cleanup

Date: 2026-05-25

## Goal

Remove the repeated CI nullable warnings in the linked `NiDataStream` candidate scanner without changing decode/export behavior.

## What changed

- Added an explicit defensive `RoleStats` presence guard in `ScanNifLinkedStreamPositionCandidates`.
- Reused the checked local `roleStats` value for candidate role output.
- Kept the existing candidate scanner semantics intact.

## Evidence / validation

- `dotnet build RiftAssetDumper.slnx --no-restore`
  - Result: build passed.
  - Previous `CS8602` warnings at `Program.cs` lines 3378 and 3406 are gone.
  - Remaining warning: existing `SharpCompress` moderate vulnerability advisory (`NU1902`).
- `dotnet test RiftAssetDumper.slnx --no-build --no-restore`
- `python scripts/rift_workflow.py nidatastream-parser-export-non-consumption-guard`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

## Known blockers / guardrails

- This does not address the existing `SharpCompress` advisory; dependency upgrades should stay a separate dependency-audit slice.
- No parser/export promotion was performed.
- Build outputs under `bin/` and `obj/` remain generated/ignored.

## Next recommended actions

1. Commit this warning cleanup as a separate CI-hygiene slice.
2. Treat the remaining dependency advisory as a separate audited package-update lane.
