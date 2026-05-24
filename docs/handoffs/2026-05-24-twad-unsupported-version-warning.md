# TWAD unsupported-version warning handoff — 2026-05-24

## Stage completed

Added a warning-only guard for TWAD archive version words above the client-proven supported range.

## Why

The Ghidra proof showed the client reads the archive header version word at offset `+4` and accepts version words `<= 1`. Local copied/live archives observed so far use version word `1`. The parser already reads the header and continues report-only probing, so this patch adds a warning without changing extraction or decode behavior.

## Files changed

- `src/RiftAssetDumper/Program.cs`
- `src/RiftAssetDumper.Tests/BasicTests.cs`
- `docs/handoffs/2026-05-24-twad-unsupported-version-warning.md`

## Safety boundary

- Warning-only.
- No archive parsing, extraction, decompression, NIF decoding, Ghidra pairing, or OBJ/export behavior was promoted or changed.
- The warning aligns with current Ghidra evidence and keeps unsupported headers visible during probe/inventory work.

## Validation

```powershell
dotnet test RiftAssetDumper.slnx --no-restore
dotnet build RiftAssetDumper.slnx --no-restore --nologo
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Remaining

- If future real archives show a version word above `1`, capture a new Ghidra/function-site proof before changing parse behavior.
