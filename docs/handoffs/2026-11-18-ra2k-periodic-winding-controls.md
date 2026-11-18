# RA-2k — Held-out periodic winding diagnostic (source-only)

**Date:** November 18, 2026 (America/New_York)
**Host:** AMD-DESKTOP, Workbridge 0.16.5-dev
**Repo:** C:/RIFT MODDING/Assets
**Branch / pre-work HEAD:** feat/ra1-source-provenance / de96c5c (RA-2j)
**Scope:** Offline, read-only game-source comparison and bounded Python diagnostic. No client input, live process/memory, RiftWorld/RR2 edits, native-face export, game-payload commit or release.

## Scientific problem

RA-2j found that BE u16 disjoint triplets with a *two-word* leading offset contain zero duplicated index groups and zero zero-area source triangles, versus 7,477 duplicates for direct offset zero. However two index values are outside the 16,641-point source grid and raw normal signs are roughly half positive/half negative. A global positive, negative or simple alternating winding rule cannot explain them.

A new direct source examination found a **candidate repeating eight-triplet sign motif**:

`+++----+`

The motif reverses its polarity in source regions. It was **discovered from these particular source samples** and must not be mistaken for a formally decoded primitive format or a pre-registered independent model. This experiment instead asks a narrower question: does a one-bit polarity fitted on a short prefix predict held-out groups more often than simple uniform/alternating sign controls?

## Input proof and model design

- Build-1179 recovery inherited from RA-2i; the source `assets.100` archive hash matched both pre-/post-patch Update Helper evidence.
- First NIF `c8d4fe94a8f0ae8f`, SHA-256 `39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69`.
- Second NIF `70e3afc2555b8ee6`, SHA-256 `1a65d2b3ab4a5c1521c87b473e2c957c7a3d47b3aeff20733b5627ab030c1ddc`.
- Shared INDEX-body SHA-256 `fab639976345b5c90f91e9de30ec2b12d842a882f23c1c89516a69e2b1fb6c07` (two separate NIF/normal samples, **one** INDEX-byte exemplar).
- Source header, stream lengths, decoded ROR1 position and normal vectors, square-grid count and optional exact INDEX SHA are rechecked. RA-2g's second-tile strict normal-versus-gradient discrepancy is **not** reclassified or relaxed.
- Only source-observed BE/offset-2 candidate triplets are classified by dot-product of their cross-product against the supplied average normal; strong positive is dot >0.9, strong negative is dot < -0.9, and weak/invalid is unscored. This emits **signs only**, never geometry or world placement.
- For each non-overlapping 128-, 512- or 2,048-triplet window, the first at most 64 groups train one polarity bit for a fixed sign template, and the remaining groups are held out. Uniform sign (period 1), simple alternation (period 2) and observed eight-group motif (period 8) are compared identically.
- No global template is auto-selected; no window can qualify a native face; poorly scored windows remain explicit evidence against a universal rule. Model selection and repeated testing on the same INDEX body are limitations, even with held-out groups and two distinct terrain normals.

New Python diagnostic: `scripts/audit_nif_index_periodic_winding.py`, with synthetic/negative tests in `tests/test_audit_nif_index_periodic_winding.py`.

## Real-source outcome: held-out agreement

Counts across the candidate shifted triplets:

| Metric | First NIF | Second NIF |
| --- | ---: | ---: |
| Candidate triplets | 32,767 | 32,767 |
| Strong positive sign | 16,484 | 16,319 |
| Strong negative sign | 16,142 | 15,376 |
| Weak/neutral sign | 139 | 1,070 |
| Out-of-range index triplets | 2 | 2 |
| Duplicate / zero-area groups | 0 / 0 | 0 / 0 |

The two invalid source words are still 16767 and 16765. Shifted grouping still omits the first two and final one words of the 98,304-word body, with no source-proven explanation.

| Window size | Model | First NIF windows >=90% held-out | Second NIF windows >=90% held-out | Mean held-out, first / second |
| ---: | --- | ---: | ---: | --- |
| 128 | Uniform sign | 0 / 256 | 0 / 256 | 50.78% / 51.69% |
| 128 | Alternating sign | 0 / 256 | 0 / 256 | 50.17% / 51.33% |
| 128 | Observed eight-group motif + local polarity | **240 / 256** | **240 / 256** | **93.90% / 94.37%** |
| 512 | Observed eight-group motif + local polarity | **56 / 64** | **56 / 64** | **91.70% / 92.03%** |
| 2,048 | Observed eight-group motif + local polarity | **12 / 16** | **12 / 16** | **86.21% / 86.44%** |

A longer window crosses more unexplained polarity boundaries. Every case preserves the low-scoring windows instead of filtering or smoothing them away. This is a useful periodic ordering clue but not a stable native triangle decoder.

## Reproducible receipts and validation

Six source-hash-bound reports under ignored `Exports/ra2k/` (not committed):

| Source | Window size | JSON SHA-256 |
| --- | ---: | --- |
| first | 128 | `f8e4fd5d09ce38035560534858cc509790ea3f567ba30a1225b1857f3a2ccdf0` |
| first | 512 | `917c062b5d3b5fb529dc3fcb4875aa5e5e6db14d71dcfc07878244115dfda862` |
| first | 2,048 | `2e78be52e7ad01c4f216316c2f0f97b3a36054650064e42e31bf433d5efc0065` |
| second | 128 | `340df6592aaa2248c58679ea0c2803a6e918e236ae7836b96ca0fa7b4aed507f` |
| second | 512 | `266ed41a7e3a6a717da100466e2e26f516dc5937d65ef41cd15efa81b676204e` |
| second | 2,048 | `d6f6481f38ff0c99e57ea068586b471c865440772405e2dadf5e47b7836185a5` |

Validation on AMD-DESKTOP:

- **34 focused tests passed**, including **24 new** RA-2k synthetic, corruption and held-out negative tests. A deliberate polarity flip *inside the unseen portion* of a window scores zero rather than accidentally passing.
- Ruff lint all scripts/tests: PASS. Ruff formatting on both new files: PASS. mypy all scripts: PASS.
- Full Python suite: **1,298 passed, 17 failed, 70 skipped, 3 subtests passed**. The 17 failures are identical historical missing-generated-artifact dependencies; full CI remains red. No C# source changed; .NET's prior RA-2i 91/91 pass is historical for this milestone.

## Qualification boundary

The newly observed periodic sign cycle is a **source-derived hypothesis**, not a native primitive, winding rule, geometry serializer, collision mesh, placement or RiftWorld patch. The source continues to have invalid indices, omitted edge words, unresolved segment boundaries and unexplained exceptions. The second tile has an independent steep-normal discrepancy. Two distinct NIFs sharing exactly the same INDEX stream do **not** satisfy the next independent-format gate.

All readiness and promotion flags in the new diagnostic remain false/null. No original faces, OBJ or consumer model/scene packet is emitted. Only generated JSON under ignored Exports changes.

## Ten prioritized next actions

1. **RA-2l:** qualify a third terrain/mesh NIF with a **different** INDEX-body hash before generalizing any periodic rule.
2. Inspect NiDataStream #20's own source descriptor/usage and the owning NiMesh primitive metadata for actual index grouping hints.
3. Map locations of the 16 low-scoring 128-triplet windows per tile and compare with candidate sign inversions, without silently dropping them.
4. Test periodic-template prediction against independently chosen NIF families, not only variants sharing a byte-identical buffer.
5. Investigate the unexplained 16767/16765 outliers against actual source vertex counts, not guessed restart semantics.
6. Test deliberately incorrect fixed-period and segment templates as additional negative controls.
7. Determine whether candidate polarity reversals correlate with raw source-grid row or quadtree neighborhood transitions.
8. Resolve the RA-2g steep normal/gradient mismatch using a separate scientific lane, preserving first-tile strictness.
9. Restore genuine missing generated fixtures to address 17 historical failures rather than suppressing tests.
10. Review the deferred historical July navmesh PR and existing RiftWorld contract boundaries before any cross-repo integration.

**Decision:** bounded periodic-structure lead accepted for further *investigation only*. Original topology, world placement, collision and downstream patch readiness remain unqualified.
