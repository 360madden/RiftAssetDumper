# RA-2f — Native NiDataStream #20 direct index-format hypothesis audit

**Date:** November 16, 2026 (America/New_York)
**Machine:** AMD-DESKTOP
**Repository:** C:\RIFT MODDING\Assets
**Branch:** feat/ra1-source-provenance
**Parent HEAD:** f5164da (RA-2e)
**Scope:** Source-hash-bound offline read-only analysis of one previously verified terrain NIF; no process attach, game input, navigation, model export, collision, or RiftWorld/RR2 edits.

## Scientific objective and result

RA-2b recovered the source grid (16,641 positions, normal/UV correspondence), RA-2c recovered five source stream references, RA-2d established a local NiTerrainNode->NiMesh transform, and RA-2e corrected the native C# scene-graph reader.

Original native triangle topology remains unknown because the apparent uint16 index buffer, NiDataStream #20, fails straightforward indexing tests. RA-2f tested and **rejected four direct interpretations** against the independently validated source geometry and normals.

### Exact source evidence

- Source decoded NIF content ID: c8d4fe94a8f0ae8f
- Source decoded NIF SHA-256: 39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69
- Source NiDataStream #20 declared body: 196,608 bytes, 98,304 16-bit values.
- Stream body SHA-256: fab639976345b5c90f91e9de30ec2b12d842a882f23c1c89516a69e2b1fb6c07
- Position/normals: 16,641 verified source records each, 129x129 grid.
- Direct triangle interpretation cannot be promoted without all vertex indices in range, nondegenerate triangles, coherent winding/normal orientation and source schema agreement.

## Four bounded direct interpretations

| Tested interpretation | Candidate triangle groups | Groups with out-of-range index | Degenerate index groups | Negative normal agreement groups | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Big-endian uint16 list | 32,768 | 2 | 7,477 | 14,085 | Rejected |
| Big-endian uint16 continuous strip | 98,302 | 6 | 13,653 | 41,274 | Rejected |
| Little-endian uint16 list | 32,768 | 30,720 | 0 | 21 | Rejected |
| Little-endian uint16 continuous strip | 98,302 | 96,254 | 0 | 2,027 | Rejected |

A continuous-strip test uses sliding index windows with alternating triangle winding. It is **not** proof that the game uses a continuous strip (or no primitive restarts). No primitive restart or proprietary index/delta layout was inferred.

The big-endian interpretation has many more plausible local-grid index values than little-endian, but both direct list and continuous-strip versions still fail. Big-endian lists only have 6,112 strictly local-neighbor candidate triangles out of 32,768 groups. This is a strong negative result against the naïve claim that the block is already a valid fully decoded triangle list.

**Do not conclude the stream is not index data.** The layout may involve a different ordering, offset/base, stream packing, primitive groups, GPU optimization or obfuscation; these remain hypotheses, not verified facts. Original native triangles and exporter readiness remain unavailable.

## Reusable diagnostic

New Python tool:
scripts/audit_nif_native_index_candidates.py

It reuses RA-2b's immutable NIF SHA256 guard, five-stream reference evidence and ROR1-decoded source normals/positions. Scores only four explicit uint16 variants, with bounds, degeneracy, grid-locality and normal/winding diagnostics, and always leaves original topology unqualified even if a synthetic hypothesis has valid geometry.

Ignored local JSON evidence, not committed:
Exports/ra2f/index-hypotheses.json

Schema: ra2f-native-index-hypotheses/1
SHA-256: 1437846aebab157c2f7264bb83c7dca8bd08d396d27c1bc13e3a995cd94d1fce

Reproduction from the existing PowerShell 7 terminal, with cwd C:\RIFT MODDING\Assets:

    $source = Get-ChildItem "Exports\ra1\decoded-assets\assets-100" -Recurse -Filter "*_c8d4fe94a8f0ae8f.nif" -File | Select-Object -First 1 -ExpandProperty FullName
    .\.venv\Scripts\python.exe scripts\audit_nif_native_index_candidates.py --nif "$source" --nif-header-report "Exports/ra1/nif-header-probe-assets-100.json" --expected-nif-sha256 39c620f87f8492494fc1cd40e2f5d0180b10a25bfee48a246ffec358faa49a69 --out "Exports/ra2f/index-hypotheses.json"

No new PowerShell script was created; this is just a command example.

## Verification and preservation

- 11 new focused synthetic/negative pytest tests passed: candidate-only positive control, out-of-range, degenerate, wrong winding, byte-order rejection, strips never promoted, malformed lengths, mismatched source-grid counts and stable/nonmutating output.
- Ruff all scripts/tests: PASS.
- mypy all scripts: PASS.
- Full Python suite: **1,241 passed, 17 failed, 70 skipped**, plus 3 subtests passed. The exact same 17 historical missing-generated-artifact failures remain since the re-entry baseline. **Full CI is NOT green.**
- Previous RA-2e .NET suite: 83/83 passed. No C# code changed during this RA-2f experiment.
- git diff --check PASS; ignored Exports output verified.
- RiftWorld's active working tree and live RIFT client were untouched; game-source bytes were not copied into Git.

## Next ten optional high-leverage steps

1. **RA-2g:** Decode the exact 21-byte NiMesh stream-binding records and determine source primitive/topology hints before any new index-format claims.
2. Read source NiDataStream #20 descriptor and usage/access metadata as raw bytes and compare with C# classifications.
3. Obtain one second independently SHA-qualified terrain NIF with 5 matching streams to test whether the index-body pattern is source-specific.
4. Search source for bounded index permutations, tile order or per-record encoding hypotheses, with explicit counterexamples, not free-form guessing.
5. Add a synthetic negative check where a deliberately incorrect strip boundary would otherwise appear to pass.
6. Compare native index neighborhoods with independently recovered grid topology, preserving derived-vs-native distinction.
7. Confirm node-parent transforms under a second source tile with different translation values.
8. Keep original mesh geometry export blocked until source index topology and model-root transform are both qualified.
9. Ask RiftWorld owner to review RA-2a source receipt after its independent working-tree changes settle.
10. Recover true historical generated-input artifacts to address the existing 17 Python integration-test failures without bypasses.

**Exit gate:** Four naïve native-index interpretations closed negative; original triangle topology, RiftWorld model readiness and world placement remain unqualified. Continue with record-format source decoding, not speculative triangle generation.
