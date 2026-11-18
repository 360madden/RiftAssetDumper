# RA-2i — Build-1179 asset recovery and native INDEX word inventory

**Date:** November 18, 2026 (America/New_York)  
**Host:** AMD-DESKTOP, Workbridge 0.16.5-dev  
**Repo:** C:\RIFT MODDING\Assets  
**Branch / pre-work HEAD:** feat/ra1-source-provenance / 57bad4f  
**Scope:** read-only installed RIFT files, local generated metadata, Python diagnostic/tests and repo documentation. No game input, game writes, live-process attach, RiftWorld/RR2 edits, or copied assets committed.

## November 17 game-patch recovery

The independent Update Helper repo at C:\work\Update Helper owns the before/after game evidence. Its tracked PATCH_EVIDENCE_2026-11-17.md and verified ignored manifests establish:

- RIFT build STABLE-1-1177-a-1256632 → STABLE-1-1179-a-1256672.
- 7 modified installation files, 2 removed download records, 0 added, 265 unchanged.
- Assets/assets.242 and assets64.manifest changed; assets.100 and assets.200 did not.
- Recomputed on November 18 against the installed game: assets.100, assets.200, assets.242 and assets64.manifest each match the verified post-update SHA-256 in Update Helper. The first two also match their pre-update SHA-256.
- Changed assets.242 accepted a bounded TWAD-v1 table/packed-payload audit: one sample under the default 1 MiB sample cap, output Exports/ra1/post1179-assets242-samples.json. This is not a claim about every changed archive entry.

Post-update existing C# list-entries and probe-binary CLI checks (with process-local DOTNET_ROLL_FORWARD=Major, not a global install) returned:

| Source NIF asset ID | Manifest row | PAK index | Source TWAD entry | Decoded type/length |
| --- | ---: | ---: | --- | --- |
| c8d4fe94a8f0ae8f | 352498 | 1603 | assets.100 / 0 | NIF / 797,915 |
| 70e3afc2555b8ee6 | 64216 | 1603 | assets.100 / 2 | NIF / 797,915 |

Both IDs have exactly one current-manifest matching row; the primary manifest still has 404,348 entries and 2,078 PAK records. PAK #1603 still resolves to ep1_assets/map/world2/world2geometry_48.pak. These prove selected current-build lookup/decoder compatibility, not universal manifest equivalence or PAK payload identity. New reports are ignored in Exports/ra1/post1179-*.

## RA-2i code and source findings

Added scripts/audit_nif_index_structure.py and tests/test_audit_nif_index_structure.py.

- Reuses existing bounded NiDataStream extraction and position decoding, checks exact SHA-256 of each input NIF, and offers an optional required INDEX-body SHA-256.
- Inventories big-endian and little-endian 16-bit interpretations, explicit missing/out-of-range words, fixed-triplet invalid/duplicate/local counts and grid-cell ratio.
- Emits no faces, OBJ, path, world transform or collision evidence; selectedNativeByteOrder=null and originalTopologyQualified=false in every report.
- Writes generated JSON only under ignored Exports through the existing atomic output helper.

Two distinct SHA-verified terrain NIFs produced identical INDEX-body hash fab639976345b5c90f91e9de30ec2b12d842a882f23c1c89516a69e2b1fb6c07 and identical structural counts:

| Structural property | Big-endian view | Little-endian view |
| --- | ---: | ---: |
| Raw body bytes | 196,608 | 196,608 |
| 16-bit words | 98,304 | 98,304 |
| Source grid vertices | 16,641 (129 × 129) | 16,641 |
| Exactly six words per 16,384 grid cells | yes | yes |
| Out-of-range word occurrences | 2 | 73,209 |
| Out-of-range fixed triplets | 2 | 30,720 |
| Duplicate fixed triplets | 7,477 | 0 |
| Local-neighbor fixed triplets | 6,112 | 0 |

The big-endian distribution uses all ordinary vertex IDs 0..16639, lacks 16640, and has two additional values (16765 and 16767) each once. That is distribution evidence, **not** a proven primitive-restart, padding, strip, or topology interpretation. Existing RA-2f list/strip negative controls remain in force; in particular 7,477 degenerate fixed triplets and unresolved winding prevent any original-face promotion.

NIF content SHA-256 identities:
- First: 39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69.
- Second: 1a65d2b3ab4a5c1521c87b473e2c957c7a3d47b3aeff20733b5627ab030c1ddc.

Generated, ignored outputs:
- Exports/ra2i/first-index-structure-build1179.json — SHA-256 4a39ff5edab291c4f86df6463f2c19663702a3b3328aab237dca3fb2ef313715.
- Exports/ra2i/second-index-structure-build1179.json — SHA-256 f0f5703b706cc40eea2791d69caa2438488a4947f153a1b2176b27360513e757.

## Fresh validation on AMD-DESKTOP

| Check | Result |
| --- | --- |
| Focused new RA-2i + prior RA-2f tests | 23 passed |
| Earlier postpatch focused Python source tests | 33 passed |
| .NET 9 project tests with process-local major roll-forward | 91 passed, zero failed |
| Ruff lint all scripts/tests | PASS |
| Ruff format check, new files | PASS |
| mypy all scripts | PASS |
| Entire Python suite | **1,264 passed, 17 failed, 70 skipped, 3 subtests passed** |

All 17 full-suite failures match the pre-existing generated-artifact-dependent failures documented in RA-2h; none originated in the 12 new RA-2i tests. **Full CI remains RED** and was not bypassed or marked green.

## Qualification and ownership boundaries

- Update Helper owns game-file difference evidence, not Assets parser changes.
- Current selected terrain sources are requalified for build 1179; untouched archives alone do not establish that all new manifest interpretations or every model remain compatible.
- Second-tile steep-normal differences from RA-2g remain unresolved.
- The native INDEX topology, world coordinate frame, source placement, original collision and RiftWorld model/scene/patch readiness remain unqualified.
- No game payload, full archive, binary or ignored Exports output is staged.

## Ten prioritized next actions

1. RA-2j: inspect source INDEX stream ordering in small bounded windows, with explicit negative controls for every proposed mapping.
2. Review existing local C# and third-party NIF index decoders before adding new format logic.
3. Test whether outliers 16765/16767 are recurrent across unrelated terrain INDEX streams; do not name them sentinels without proof.
4. Locate a third SHA-verified source terrain NIF, ideally from another archive, to distinguish shared template from universal format.
5. Compare candidate byte-order/group patterns against actual source geometry locality and normals, including winding and degenerate refusal.
6. Resolve second-tile steep normal/gradient disagreement without relaxing the successful first-tile guard.
7. If RiftWorld needs it, deliver only versioned source-evidence metadata for the two stable NIFs; consumer owns promotion.
8. Restore genuine historical generated-data fixtures to address the 17 Python failures instead of suppressing tests.
9. Extend assets.242 postpatch inspection only for a concrete asset/consumer need; current one-sample audit is not full coverage.
10. Review the open July navmesh PR separately from the newer November source-first roadmap before any merge or navigation work.

**Decision:** RA-2i inventory shipped as candidate-only evidence. No original-triangle/world-patch promotion.
