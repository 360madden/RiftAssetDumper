# RA-1.5c — Joint content-ID and filename-FNV manifest selection

**Date:** 2026-11-16 (America/New_York)
**Host:** AMD-DESKTOP
**Branch:** feat/ra1-source-provenance
**Parent HEAD:** 2e33491 (RA-1.5b)
**Scope:** bounded C# CLI selector correction and synthetic tests; no gameplay or consumer-repository changes.

## Defect and remedy

After RA-1.5a/b, the shared ResolveTargetEntry still prioritized bare --id over simultaneously supplied --fnv when --manifest-index was absent. This can silently report the **wrong filename/PAK row** for content shared across multiple manifest names.

RA-1.5c introduces a jointly constrained selector for **--id plus --fnv**, with precedence:

1. Explicit --manifest-index first, with agreement checks against any --id / --fnv.
2. Joint --id and --fnv second: resolve rows in the existing primary-manifest FNV lookup that also have the requested content ID. Require **exactly one** matching row; refuse zero or multiple matches.
3. ID-only third: retain historical first-row behavior unless opt-in --require-unique refuses duplicate content IDs (RA-1.5b).
4. FNV-only last: preserve the pre-existing unique-FNV behavior.

When --require-unique is supplied **with both --id and --fnv**, the uniquely selected joint row remains allowed even if the decoded content ID is shared with thousands of other names. This is stronger than ID-only selection and avoids rejecting explicit filename identity unnecessarily.

## Test-first proof

Four new synthetic tests in src/RiftAssetDumper.Tests/ManifestTargetSelectionTests.cs use a controlled TWAM manifest and a tiny raw TWAD DDS. Before change, **4/11 targeted tests failed**:
- jointly specified ID/FNV silently picked the first same-content row;
- mismatch silently succeeded;
- strict combined selector incorrectly rejected a valid name;
- truly duplicated joint ID/FNV incorrectly succeeded.

After change, **11/11 targeted tests passed**, and the complete .NET suite **72 passed / 0 failed / 0 skipped**. dotnet build: PASS, zero warnings/errors. dotnet format --verify-no-changes --no-restore: PASS. Runtime compatibility uses process-local DOTNET_ROLL_FORWARD=Major; global .NET settings unchanged.

## Real 31,324-row content reuse acceptance

The previously qualified, uniformly black, 128-by-128 DDS from assets.002 entry 1262:
- decoded content ID: 202d25ec6d206c7a;
- primary manifest has 31,324 records with that content ID;
- exact filename world2_terrain_8960_6400_baked.dds has FNV-1 0xf47ce7f9;
- filename-specific primary-manifest row is **386332**, PAK **1719**.

The following **without --manifest-index** succeeded and returned Source.ManifestEntryIndex=386332, Source.PakIndex=1719, Type=dds, Length=65664:

~~~text
probe-binary --root <RIFT Live> --manifest <RIFT Live>/assets64.manifest --archive assets.002 --id 202d25ec6d206c7a --fnv 0xf47ce7f9 --require-unique --out Exports/ra1/ra15c-joint-baked-exact.json
~~~

A negative request with the same content ID but another DDS filename's FNV, 0x7192a6eb, exited **1** and created **no output file**. Synthetic controls additionally verify truly duplicate joint ID+FNV rows refuse selection.

## Remaining qualification boundary

This chooses a **specific manifest metadata row**, not independently verified PAK payload bytes or a renderer material slot. The archive decoder still reads the live TWAD entry by content ID. Filename FNV+length evidence is known for these exact verified assets, but this general API does not independently prove that an arbitrary user-provided FNV equals a particular string. Consumers must preserve source evidence, original hash/size comparisons and candidate-vs-qualified semantics.

All generated probe receipts remain ignored under Exports/ra1. No game file, process memory, RiftWorld or RR2 source changed. The historical full Python baseline still has 17 missing-generated-artifact failures; those tests were not rerun in this C#-only slice, and **full CI is not claimed green**.

## Recommended next small milestone: RA-2 contract readiness

Read and compare the existing RiftWorld model/scene/patch schemas in **read-only** mode against Assets' latest source, DDS-link, and manifest ID/FNV evidence. Write one narrow producer-to-consumer field mapping and a synthetic fixture **within Assets only**. Do not implement a second navmesh, collision subsystem, route planner, or game input. Identify where source hashes, selected manifest row identity and candidate texture semantics should be carried without inventing world transforms.
