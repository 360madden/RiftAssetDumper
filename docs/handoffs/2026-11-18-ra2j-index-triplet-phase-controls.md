# RA-2j — SHA-bound native INDEX triplet phase controls

**Date:** November 18, 2026 (America/New_York)
**Machine:** AMD-DESKTOP (Workbridge 0.16.5-dev)
**Repository:** C:/RIFT MODDING/Assets
**Branch / parent:** feat/ra1-source-provenance / e45638c (RA-2i)
**Scope:** Offline source-only candidate evaluation. No game input, debugger, memory access, world-patch edit, native face export, copied game payload in Git, or consumer-contract promotion.

## Why this next experiment

RA-2f rejected BE/LE direct uint16 triangle lists and continuous strips. RA-2i then proved the two terrain NIFs have the same 196,608-byte INDEX body, 98,304 16-bit words, two BE words outside the 16,641-position grid (16767 and 16765), and 7,477 degenerate BE fixed triplets.

A bounded raw inspection revealed that grouping disjoint BE triplets beginning **two words after the INDEX body's start** removes all duplicate-index triplets. This is worth testing but cannot prove primitive type or byte order. The first two raw words and final one raw word are omitted by that offset; no rule explains those edge words.

## Inputs and reproducibility gates

- Build-1179 game update provenance remains owned by the sibling Update Helper repository. The selected terrain NIFs still come from the verified, unchanged `assets.100` archive after the patch.
- First NIF ID `c8d4fe94a8f0ae8f`, decoded SHA-256 `39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69`.
- Second NIF ID `70e3afc2555b8ee6`, decoded SHA-256 `1a65d2b3ab4a5c1521c87b473e2c957c7a3d47b3aeff20733b5627ab030c1ddc`.
- Both carry exactly the **same** NiDataStream #20 INDEX body SHA-256 `fab639976345b5c90f91e9de30ec2b12d842a882f23c1c89516a69e2b1fb6c07`. These are distinct NIFs and differing source normals, **not independent INDEX-byte exemplars**.
- Existing bounded NiDataStream header/body checks, ROR1 position/normal decoding, and expected NIF/INDEX SHA-256 requirements remain in effect.

New `scripts/audit_nif_index_phase_controls.py` reuses RA-2i source guards and RA-2f's established normal/winding scorer. It compares three disjoint-triplet starts (0, 1, or 2 uint16 words) for each BE/LE interpretation. It records leading/trailing omitted words explicitly, tests range, duplicate, zero-area, locality and source-normal agreement, and **never selects a byte order, word offset, primitive, or native triangle set**. All six candidate profiles are diagnostic only.

## Verified results: big-endian word phases

First terrain NIF:

| Start offset (words) | Candidate triplets | Omitted start / end words | Out-of-range | Duplicate index | Zero area | Local neighbor | Negative normal |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 32,768 | 0 / 0 | 2 | 7,477 | 1,385 | 6,112 | 14,085 |
| 1 | 32,767 | 1 / 2 | 2 | 6,176 | 982 | 6,825 | 15,348 |
| 2 | 32,767 | 2 / 1 | 2 | **0** | **0** | **14,952** | **16,280** |

Second terrain NIF (the same INDEX content but different positions/normals):

| Start offset (words) | Out-of-range | Duplicate index | Zero area | Local neighbor | Negative normal |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2 | 7,477 | 0 | 6,112 | 14,345 |
| 1 | 2 | 6,176 | 0 | 6,825 | 15,285 |
| 2 | 2 | **0** | **0** | **14,952** | **16,217** |

The original BE outliers occur at raw word offsets 65,533 (16767) and 65,537 (16765), in the neighborhood of otherwise high terrain grid indices. Neither is a proven sentinel, skirt vertex, restart marker, or valid vertex in the decoded 16,641-record position grid.

All three LE profiles were also evaluated for both sources; each is contradicted by the source consistency checks. The higher BE-offset-2 locality is a useful clue but the negative-normal counts remain approximately half the scored candidate triplets. **No candidate passes.** Phase re-grouping alone cannot establish native topology, winding, world frame, collision, or RiftWorld model/scene/patch readiness.

The secondary NIF's independently known steep-region normal-vs-gradient mismatch from RA-2g remains unresolved. RA-2j does not relax that prior gate; it scores supplied raw source normals without promoting the secondary tile as gradient-qualified.

## Artifacts and verification

New code/tests (only these and docs are eligible to commit):

- `scripts/audit_nif_index_phase_controls.py`
- `tests/test_audit_nif_index_phase_controls.py` (10 new tests, including source hash refusal, malformed lengths, bad normal count, wrong INDEX SHA, and a valid synthetic triangle list that **still must not be promoted**)

Local ignored generated receipts (never stage):

- `Exports/ra2j/first-phase-controls-build1179.json` — SHA-256 `8257667df3562ef82fb7bbaf03019e39c65b32ff3f4f1d35c49530017d93cd7b`.
- `Exports/ra2j/second-phase-controls-build1179.json` — SHA-256 `4650c3d037a8f71cf68b14c8001ac7d6aa4444f583fc12e1fcd6336cae6d7938`.

| Validation | Outcome |
| --- | --- |
| Focused RA-2j + RA-2i + RA-2f | **33 passed** |
| Ruff lint all scripts/tests | PASS |
| Ruff format, new files | PASS |
| mypy all scripts | PASS |
| Two live-source SHA-bound index phase receipts | PASS; all six candidates contradicted |
| Full Python suite | **1,274 passed, 17 failed, 70 skipped, 3 subtests passed** |

The same 17 generated-artifact-dependent integration tests failed before this work. Full CI remains red; no failures were hidden. The 91-test .NET suite passed in the prior RA-2i work; .NET was not changed or re-run for RA-2j.

## Decision and follow-up priorities

**Decision:** RA-2j is a non-promotional, source-bounded ordering study. The BE offset-2 result warrants a more discriminating experiment, but every hypothesis remains contradicted. No native topology, geometry or downstream patch is qualified.

1. RA-2k: classify negative normal agreement by bounded source grid regions/windows and parity; seek consistent segment-level orientation evidence.
2. Find a third terrain NIF with a **different INDEX-body SHA-256** before generalizing an ordering model.
3. Inspect NiDataStream #20 source descriptor and primitive metadata for independently documented segmentation hints.
4. Test whether the two outlier words have genuine matching vertex records in a distinct source family; do not relabel them as restart sentinels prematurely.
5. Compare shifted grouping against explicit synthetic strip/list/meshlet negative controls.
6. Examine 129x129 grid neighborhood locality by source row without deriving or emitting model faces.
7. Distinguish actual normals from finite-difference derived normals on the second steep terrain tile.
8. Preserve the RA-2a versioned source-only receipt while native geometry is unqualified.
9. Restore original historical generated fixtures to resolve 17 full-Python failures; do not suppress them.
10. Review older unmerged July navmesh work separately from November's Assets-as-source roadmap.

**Exit:** Small tested RA-2j diagnostic and reproducible real-source negative evidence delivered. RA-2k is next.
