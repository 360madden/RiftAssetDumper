# RA-1.5b — Opt-in uniqueness guard for ID-only probes

**Date:** November 16, 2026 (America/New_York)
**Host:** AMD-DESKTOP
**Repo:** C:\RIFT MODDING\Assets
**Branch:** feat/ra1-source-provenance
**Parent HEAD:** a6d8dc4 (RA-1.5a)
**Scope:** small C# probe selector guard + synthetic tests + real read-only acceptance.

## Result

ID-only probe-binary calls previously returned the **first** primary-manifest row for a content ID even if thousands of different filename/PAK rows shared the same content bytes. RA-1.5a added exact manifest-index selection, but default ID-only behavior intentionally remained for compatibility.

RA-1.5b reuses the existing opt-in --require-unique argument to make ID-only probe selection **fail closed** when more than one manifest row has the same content ID. The guard inspects the current manifest entries, stops after detecting two matches, and raises an explicit error recommending --manifest-index. It does not modify the global default: bare --id still uses the previous first-row behavior.

When --manifest-index is provided, that explicit row still takes priority and the guard does **not** incorrectly reject shared content. ID/index/FNV consistency checks from RA-1.5a remain in force.

The existing --require-unique behavior for match-names (exclude FNV-hash collisions) is preserved; only its ID-only probe interpretation is extended. Command help documents both meanings.

## Synthetic red-to-green verification

Two additional synthetic TWAM/TWAD tests in src/RiftAssetDumper.Tests/ManifestTargetSelectionTests.cs:
- ProbeBinary_RequireUniqueRefusesDuplicateIdWithoutExactIndex: content ID with two distinct name/PAK rows must fail without output.
- ProbeBinary_RequireUniqueAllowsExactRowForDuplicateId: the same content ID plus exact manifest index 2 and --require-unique must succeed with row 2.

Before the guard, **1 of 7 target tests failed** (strict duplicate was silently accepted); after the guard **7 of 7 passed**.

Validation:
- dotnet build RiftAssetDumper.slnx: PASS, 0 warnings, 0 errors.
- dotnet format --verify-no-changes --no-restore: PASS.
- Full .NET suite: **68 passed / 0 failed / 0 skipped**, process-local DOTNET_ROLL_FORWARD=Major using existing .NET 10 runtime.
- No Python code changed. Previous full Python baseline still has 17 historical generated-artifact failures, not fixed or suppressed here.

## Real installed-client acceptance: 31,324 manifest duplicates

Content ID: 202d25ec6d206c7a

Decoded file: a valid 128x128 DDS of **65,664 bytes**, every 65,536 pixel bytes zero. Live TWAD source assets.002 entry 1262. The primary manifest has **31,324** different filename hashes referencing this same content ID (78 PAKs); the name-specific file world2_terrain_8960_6400_baked.dds has row index **386332**.

Strict ID-only request:
~~~text
probe-binary --root <RIFT Live> --manifest <RIFT Live>/assets64.manifest --archive assets.002 --id 202d25ec6d206c7a --require-unique --out Exports/ra1/ra15b-strict-reject-should-not-exist.json
~~~
Observed: exit **1**, error says content ID matches multiple manifest rows and directs caller to specify --manifest-index. **No output created.**

Exact row with strict flag:
~~~text
probe-binary --root <RIFT Live> --manifest <RIFT Live>/assets64.manifest --archive assets.002 --id 202d25ec6d206c7a --manifest-index 386332 --require-unique --out Exports/ra1/ra15b-strict-exact-baked.json
~~~
Observed: exit **0**, Source.ManifestEntryIndex=**386332**, Source.PakIndex=**1719**, Type=dds, Length=65,664. Output lives in ignored Exports/ and was not committed.

## Evidence and qualification limits

A content ID is a hash-prefix-derived identity for decoded payload bytes, not a unique filename, material slot, world placement, or PAK owner.

Exact manifest-index selection makes source metadata refer to the intended name-specific record, but still does not prove that its PAK file's payload was independently read. The decoder continues reading the qualified live TWAD archive by content ID.

The guard is opt-in. Callers using bare --id without --require-unique must **not** treat returned PAK metadata as filename-specific truth.

No gameplay, debugger, process memory, game asset modification, or RiftWorld/RR2 edits. No generated game outputs committed or published.

## Next narrow step: RA-1.5c

Investigate --id combined with --fnv when --manifest-index is absent. Today the ID-first legacy selector can still ignore an accompanying FNV. A backward-compatible plan is to make the **joint ID+FNV selector** resolve only matching row(s), fail on a mismatch or true FNV collision, and retain bare-ID behavior with a separate --require-unique switch. Add synthetic duplicate records and a real baked DDS FNV acceptance. Avoid weakening either explicit index consistency or content provenance flags.

After that, assess the smallest compatible Assets-to-RiftWorld source contract from existing models. Do not create another navigation system.
