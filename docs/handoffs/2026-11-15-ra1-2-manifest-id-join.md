# RA-1.2 — Manifest-ID and PAK-path candidate join

**Date:** November 15, 2026 (America/New_York)
**Host:** AMD-DESKTOP
**Repository:** C:\RIFT MODDING\Assets
**Branch:** feat/ra1-source-provenance
**Upstream RA-1.1:** [TWAD source provenance](2026-11-15-ra1-twad-source-provenance.md)
**Status:** RA-1.2 delivered; candidate ID joins only, not payload/type promotion.

## Scope

Reuse the existing authoritative C# TWAM manifest parser, rather than implement a second parser in Python. The previously unfiltered list-entries CLI exported all manifest rows. It now accepts the existing --id option to select exact matching manifest rows, retaining *all* duplicate ID matches in their original order and applying --limit **after** filtering. Without --id, original listing and limit behavior remain unchanged. Invalid IDs fail before an output file is created.

A small producer-only Python join tool consumes:
1. The prior raw TWAD/packed-byte RA-1.1 evidence report.
2. The exact-ID C# list-entries JSONL outputs for the sampled IDs.
3. The C# list-paks JSONL output from assets64.manifest.
4. The raw assets64.manifest file only for its SHA-256, **not** parsing or reimplementing TWAM.

The join tool validates names, IDs, matching row IDs, PAK indexes and relative PAK paths; refuses missing/duplicate PAK indexes, malformed or absolute names, missing input files, and outputs outside ignored Exports/. It sorts rows deterministically and labels unmatched/ambiguous IDs separately.

## Confirmed real inputs and results

Original game source: C:\Program Files (x86)\Glyph\Games\RIFT\Live

Primary assets64.manifest:
- Size: 24,158,080 bytes
- SHA-256: 6e3c79b453ce5a4caa2eb5eeddb0240c7dcad9d5d54f6ce2a0f3d532b468715c
- Parsed via existing C# tool: 404,348 manifest entries, 2,078 PAK listings.

| TWAD source | Archive entry | Archive ID | Exact manifest row | Manifest PAK index | Manifest PAK path |
| --- | ---: | --- | ---: | ---: | --- |
| assets.001 | 0 | 1a157e1f7056ab59 | 159072 | 1398 | assets/texture/texture_ui_core_0.pak |
| assets.100 | 0 | c8d4fe94a8f0ae8f | 352498 | 1603 | ep1_assets/map/world2/world2geometry_48.pak |
| assets.200 | 3 | 962c30ac0b6af596 | 224957 | 1221 | assets/texture/texture_71.pak |

Each ID had exactly **one** manifest row from the primary manifest (3 unique / 0 unmatched / 0 ambiguous).

**Crucial qualification boundary:** The archive entry's stored SHA-1 field and its packed size differ from each corresponding manifest entry's hash and compressed size fields. This may reflect different file/container representations, but no such explanation has been proven. Matching IDs do **not** establish byte-identical payloads or archive-to-PAK offset correspondence. The PAK paths above come from the **manifest's PAK table**; they are not independently decoded file-type or 3D-world semantic proof.

This tool explicitly reports:
- archive-ID-to-manifest-ID matching status;
- raw manifest record values and PAK path from C# CLI;
- observed equality/non-equality of stored hash and size fields, without assigning semantic equivalence;
- packed-payload equivalence, decoded asset type, world placement, native collision and traversal = **unqualified**;
- cli_exports_confirmed_same_manifest_epoch = false. SHA-256 hashes bind each supplied input file, but the CLI exports do not cryptographically attest that they were generated from the specific hashed manifest version. In this session they were generated freshly against the same installed manifest; future reuse must verify freshness.

## Generated evidence (ignored, not backed up in Git)

- Exports/ra1/manifest-joined-samples.json
  - SHA-256: ec6c7aff40e7f188294f328a8dc3054047d2f0bca4f91b19673d0a3d49e40130
- Exports/ra1/assets64-paks.jsonl
  - SHA-256: db5ec77be16a727fd1338522b6a6b5da5e12b518d3895665c57235e83f432df6
- Exports/ra1/manifest-join-assets-001-1a157e1f7056ab59.jsonl
- Exports/ra1/manifest-join-assets-100-c8d4fe94a8f0ae8f.jsonl
- Exports/ra1/manifest-join-assets-200-962c30ac0b6af596.jsonl
- Exports/ra1/live-archive-samples.json (RA-1.1 source report).

## Reproduction

Run in PowerShell from C:\RIFT MODDING\Assets. The environment prefix is only set for the individual Python-launched .NET commands and does not alter Windows settings:

~~~powershell
$live = "C:\Program Files (x86)\Glyph\Games\RIFT\Live"
$env:DOTNET_ROLL_FORWARD = "Major"
dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj --no-build -- list-paks --root $live --manifest "$live\assets64.manifest" --out Exports/ra1/assets64-paks.jsonl
dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj --no-build -- list-entries --root $live --manifest "$live\assets64.manifest" --id 1a157e1f7056ab59 --out Exports/ra1/manifest-join-assets-001-1a157e1f7056ab59.jsonl
dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj --no-build -- list-entries --root $live --manifest "$live\assets64.manifest" --id c8d4fe94a8f0ae8f --out Exports/ra1/manifest-join-assets-100-c8d4fe94a8f0ae8f.jsonl
dotnet run --project src/RiftAssetDumper/RiftAssetDumper.csproj --no-build -- list-entries --root $live --manifest "$live\assets64.manifest" --id 962c30ac0b6af596 --out Exports/ra1/manifest-join-assets-200-962c30ac0b6af596.jsonl
Remove-Item Env:DOTNET_ROLL_FORWARD
.\.venv\Scripts\python.exe scripts/join_live_archive_manifest_samples.py --manifest-file "$live\assets64.manifest"
~~~

The reproduction shows an optional temporary environment variable removal; the test runs in this session used a Python subprocess environment dictionary instead, without setting that variable in the interactive terminal.

## Verification

- .NET build: PASS (zero warnings/errors).
- .NET unit tests: **61 passed**, 0 failed (five new targeted-listing tests, including original no-filter behavior).
- dotnet format --verify-no-changes: PASS.
- Focused Python join/sample tests: **29 passed**, 0 failed (join tests include missing/duplicate/mismatched ID controls, missing PAK, absolute paths and CLI output confinement).
- Ruff scripts/tests: PASS. mypy scripts: PASS.
- Full pytest: **1,173 passed / 17 failed / 70 skipped**, 3 subtests passed. These are the same 17 historical missing-generated-artifact failures from RA-0 and RA-1.1; full CI remains **red**, not waived.
- Live join CLI executions: all 4 of list-paks and 3 filtered list-entries exited 0; the join CLI wrote 3 unique candidate rows, 0 unmatched, 0 ambiguous.

## Next: RA-1.3

Select the sampled assets.100 / world2geometry_48 source chain for **bounded read-only payload-type evidence** using the existing extraction/probe reader. Determine what the referenced bytes actually decode to (NIF, texture, non-model, or unknown) and whether archive/manifest differences can be explained through verified format semantics. Do not assign world placement based on the string "world2geometry", do not infer live location/physics, and do not change RiftWorld/ RR2. Preserve the 17 historical generated-data test failures until the actual inputs are restored or legitimately regenerated.
