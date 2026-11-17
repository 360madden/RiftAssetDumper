# RA-1.5a — Exact TWAM manifest-row selection

**Date:** 2026-11-16 (America/New_York)
**Host:** AMD-DESKTOP
**Repo:** C:\RIFT MODDING\Assets
**Branch:** feat/ra1-source-provenance
**Parent HEAD:** ac82330 (RA-1.4b)
**Scope:** narrow C# CLI selector correction and synthetic tests; no live gameplay.

## Defect and correction

The pre-fix ResolveTargetEntry in src/RiftAssetDumper/Program.cs evaluated --id **before** --manifest-index. For duplicated content IDs, a request with both selectors silently used the first ID-indexed manifest row and misreported its manifest index, PAK index and PAK offset. A real terrain DDS filename had previously selected a different PAK from its exact filename-specific manifest record.

The correction evaluates --manifest-index **first** and validates that any simultaneously specified --id and/or --fnv agrees with the chosen row. Conflicts fail before decoding or creating output. If no explicit index is provided, existing ID-only and FNV-only behavior is unchanged for compatibility. **ID-only first-row attribution remains ambiguous for content IDs shared across multiple manifest rows; it is not filename-specific provenance.**

## Red-to-green reproducibility

New synthetic TWAM/TWAD fixture in src/RiftAssetDumper.Tests/ManifestTargetSelectionTests.cs contains two separate manifest rows with the same decoded content ID but different filename FNV, PAK index and offset, plus one row with another ID. It uses no game files.

Before correction: **2 passed, 3 failed**, reproducing explicit row ignored, conflicting ID accepted and conflicting FNV accepted.

After correction:
- **5/5 targeted .NET tests passed.**
- **66/66 entire .NET test suite passed**, no skips.
- dotnet build: PASS (zero warnings/errors).
- dotnet format --verify-no-changes --no-restore: PASS.
- No Python source changes; full Python suite remains at the prior RA-1.4a baseline **1,187 passed, 17 historical generated-data failures, 70 skipped** (not rerun in this slice; **full CI not green**).

All .NET test invocations used only process-local DOTNET_ROLL_FORWARD=Major. No .NET runtime was installed or changed globally.

## Real bounded acceptance

From the installed RIFT Live archive, the texture map_ec_sand_01.dds has content ID d912c1ed48657bf4, three manifest rows, and unique filename-specific manifest row **179255**.

Positive CLI:
~~~text
probe-binary --root <RIFT Live> --manifest <RIFT Live>/assets64.manifest --archive assets.152 --id d912c1ed48657bf4 --manifest-index 179255 --out Exports/ra1/ra15a-sand-exact.json
~~~

Observed exit 0, Source.ManifestEntryIndex=**179255**, Source.PakIndex=**1190**, ArchiveName=assets.152, exact IdPrefix, Type=dds, decoded Length=1,398,256. The file is ignored in Exports/.

Negative CLI: same ID with conflicting --manifest-index **179352** exited **1**, explicitly reporting row ID e407f97924d5f8ef disagreed with requested ID d912c1ed48657bf4. No output file was created.

## Boundaries and next step

- The selected manifest row is now exactly the requested row, **not** proof that its PAK payload was independently read at that manifest offset. Existing FindPayloadForId still reads the matching TWAD archive entry by ID.
- A first-by-ID lookup with no explicit manifest row still preserves legacy first-row semantics and can confuse distinct names with one decoded payload.
- No RiftWorld or RR2 edits, gameplay input, process attach, memory writes or game-file modification. All decoded/source data remains ignored.

**Next RA-1.5b:** Add an **opt-in duplicate-content-ID refusal** for probe-binary by reusing the existing --require-unique option where applicable, with a small synthetic test and a real 31,324-row baked DDS negative control. Keep default compatibility; exact --manifest-index must remain permitted with matching ID/FNV.
