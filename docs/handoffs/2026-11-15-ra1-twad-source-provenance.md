# RA-1.1 — Bounded TWAD table and packed-byte provenance

**Date:** November 15, 2026 (America/New_York)
**Host:** AMD-DESKTOP
**Repo:** C:\RIFT MODDING\Assets
**Branch:** feat/ra1-source-provenance
**Roadmap:** [November 2026 re-entry](../roadmap/2026-11-15-assets-reentry-roadmap.md)

## Outcome

**RA-1 first source-provenance slice delivered, not full asset coverage.**
The old build_live_archive_index.py default used extract_live_nifs.read_archive(), which reads an entire TWAD archive into RAM despite its header/table-only description. The new read_archive_table_streaming() reads only the 20-byte TWAD header and bounded 44-byte entry table, rejects malformed/truncated metadata, and is now the indexer's default. The original full archive reader used by extraction remains unchanged.

New Python CLI scripts/audit_live_archive_samples.py creates an atomic source-hash-bound report for 1–8 explicitly named archives. It uses full-file SHA-256 computed in chunks, entry-table identity, payload bounds and a limited number of raw **packed** payload SHA-256 values. Output is restricted to the repo's ignored Exports/ directory.

Evidence limits: id_prefix is an observed archive-table ID, not a semantic classification. stored_sha1_field is copied from the table and has **not** been independently verified. packed_sha256 is computed from packed source payload bytes. No NIF type, CDR, world placement, texture role, Havok collision, or traversal is established by this report.

## Real live-source evidence

Source is the existing installed RIFT files at C:\Program Files (x86)\Glyph\Games\RIFT\Live. Game files were not modified or copied.

| Archive | Bytes | Non-null entries | Hashed samples | Full-file SHA-256 |
| --- | ---: | ---: | ---: | --- |
| assets.001 | 7,592,640 | 1,489 | 4 | 9f16005337a83643895186d66e220e0715d6c8a6a31a92058ffe9e69abaa74f9 |
| assets.100 | 153,599,975 | 783 | 4 | 63c57c44a8c1cd506f394a3a90e5934748c9ba0c135b4d21354c45b882440227 |
| assets.200 | 153,599,888 | 524 | 4 | 8a83b8ed3057fb1ea6e763632c8870cd8c85f36a179e5afa0d12e0d13b4ab060 |

Selected table IDs:
- assets.001 entry 0 = 1a157e1f7056ab59
- assets.100 entry 0 = c8d4fe94a8f0ae8f
- assets.200 entry 3 = 962c30ac0b6af596 (15 earlier oversized payload candidates skipped within the 1 MiB/sample cap)

assets.243 and assets.244 also had structurally valid 1,489-entry tables with zero non-null entries. This does not prove those files are semantically empty.

Ignored output: Exports/ra1/live-archive-samples.json

Output SHA-256: ca43b58a7b77dd841e139f035bb257e61956e79243289ee7989a4fa7b9486ba1

An independent second run rebuilt the report in memory and matched the saved JSON exactly, confirming deterministic output for unchanged inputs.

## Reproduction

From the Assets repo root in PowerShell:

~~~powershell
.\.venv\Scripts\python.exe scripts/audit_live_archive_samples.py --archive assets.001 --archive assets.100 --archive assets.200 --samples 4 --out Exports/ra1/live-archive-samples.json
.\.venv\Scripts\python.exe scripts/audit_live_archive_samples.py --archive assets.001 --dry-run
.\.venv\Scripts\python.exe -m pytest tests/test_audit_live_archive_samples.py tests/test_live_archive_table_streaming.py tests/test_build_live_archive_index.py -q
.\.venv\Scripts\python.exe -m ruff check scripts/ tests/
.\.venv\Scripts\python.exe -m mypy scripts/ --no-error-summary
~~~

## Validation and remaining blockers

- **36 focused tests passed**, 0 failed: malformed/truncated tables, output confinement, bounds and hash validation, deterministic order, no-write dry runs and archive mutation refusal.
- Ruff for all scripts and tests: PASS. mypy for scripts: PASS.
- Full Python suite: **1,163 passed, 17 failed, 70 skipped**, 3 subtests passed. All 17 failures are the same historical generated-artifact cases recorded in [RA-0 handoff](2026-11-15-ra0-development-and-source-baseline.md). **Full CI is not green.**
- Previous RA-0 .NET check: 56/56 passed under process-only major roll-forward. No .NET behavior was changed in this slice.
- Five real archive metadata reads took about 0.008–0.009 seconds each in the bounded probe; this is not a controlled speed benchmark against the old reader.
- The full-archive file hash still processes the archive byte-for-byte, but in 1 MiB chunks. A size or mtime change mid-audit fails closed. Generated report contents are NOT backed up by source-code commits.

## Next: RA-1.2 manifest identity join

Use the installed assets64.manifest and existing project readers to join one proven source ID from each sampled archive to manifest entry/index, resource name/type where authoritative, and optionally a verifiable NIF/CDR payload. Include unmatched and conflicting-entry controls. Keep output under ignored Exports and source truth separate from candidate semantics.

Only after exact source identity is proven should the producer-side contract be compared to RiftWorld's existing riftworld.model/1 and riftworld.scene/1 models. Do not duplicate its navigation, collision or live input layers.
