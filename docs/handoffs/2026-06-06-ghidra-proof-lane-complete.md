# Session handoff — Ghidra proof lane complete

Date: 2026-06-06

## Summary

14 commits pushed. Ghidra proof lane fully complete (3/3 steps). All CI green. Clean git.

## Commits

### Cleanup (7 commits)

| Commit | Summary |
|--------|---------|
| `9751372` | fix: Python 2→3 except clause syntax across 7 scripts (14 occurrences) |
| `d2b8d14` | docs: Python 2→3 except syntax fix handoff |
| `b0fac43` | docs: reconcile manifest stats in knowledge.md and project-summary.md |
| `d0fd418` | docs: fix stale OBJ counts and gate status across active docs |
| `f8d8fa3` | docs: fix knowledge.md — dedup cleanup, test count, stale refs |
| `d8c933d` | docs: definitive project completion handoff |
| `f0ada88` | docs: fix stale OBJ counts and gate contradictions in current-status.md |

### Ghidra proof lane (5 commits)

| Commit | Step | Summary |
|--------|------|---------|
| `03fe72c` | Step 2 | feat: `SampleByteAgreement` proof fields — 184/184 blocks pass |
| `3e8b448` | Step 2 | docs: Ghidra proof status update — Step 2 complete |
| `d517aae` | Step 3 | feat: `--ghidra-body-offset` flag + `BuildNifMeshBoundStreamSummaries` wiring |
| `234fd42` | Step 3 | feat: wire flag through remaining 3 body-slicing sites |
| `69e2cdd` | Step 3 | docs: Ghidra proof status — Step 3 complete |

### Testing (1 commit)

| Commit | Summary |
|--------|---------|
| `31a77e9` | test: unit test for 1-byte Ghidra offset shift relationship |

### Validation (1 commit — implicit)

| What | Result |
|------|--------|
| Discovery suite `--full` | 7/7 steps, 5/5 guards passing |
| CLI smoke test | `--ghidra-body-offset` recognized by parser |

## Ghidra proof lane — all 3 steps complete

1. ✅ **Parser field proof guard** — passing, no premature promotion
2. ✅ **Sample-byte agreement proof** — `SampleByteAgreement`, `SampleByteAgreementDetail`, `SampleByteAgreementBlocks` fields in `nidatastream-layout` report. 184/184 blocks show `true` with "First N bytes agree (1-byte shift)"
3. ✅ **Narrow parser patch** — `--ghidra-body-offset` boolean flag on `AppOptions`. When set, `PayloadPrefixBytes` (28-byte Ghidra-aligned) becomes primary body offset; legacy `LegacyPayloadOffset` (29-byte) becomes sidecar. Wired through all 4 body-slicing sites:
   - `BuildNifMeshBoundStreamSummaries` (geometry decode path)
   - `ProbeNifMesh` stream probe
   - `inventory-nif-stream-bodies`
   - `probe-nif-stream-body`

## Technical details — narrow parser patch

**What changes:**

- `AppOptions` record: added `bool GhidraBodyOffset`
- `BuildNifMeshBoundStreamSummaries`: added `bool ghidraBodyOffset = false` parameter
- Body slicing: when flag set, `SliceNifDataStreamGhidraBody` becomes primary (`body`), `SliceNifDataStreamLegacyBody` becomes sidecar (`ghidraBody`)
- `headerBytes` / `bodyOffset` uses `PayloadPrefixBytes` (28) instead of `LegacyPayloadOffset` (29) when flag set
- All 5 call sites pass `options.GhidraBodyOffset`

**What doesn't change:**

- Default behavior: flag is `false`, all existing behavior preserved
- `SliceNifDataStreamLegacyBody` and `SliceNifDataStreamGhidraBody` functions unchanged
- `AnalyzeNifDataStreamLayout` unchanged (already computed both offsets)
- Export gates: unchanged

## Project state

| Metric | Value |
|--------|-------|
| OBJs | 350 (270 faced, 80 pos-only) |
| Promotion gates | 7/7 CLEARED |
| Proof guards | 8/8 PASSING |
| .NET tests | 51/51 |
| Python tests | 80/80 |
| ruff | 0 violations |
| mypy | 0 errors |
| Git | clean, on `main` |

## Remaining work

1. **End-to-end OBJ comparison**: Export a mesh with attribute sets (`--export-obj`) both with and without `--ghidra-body-offset`, diff the OBJs. Requires finding a mesh with attribute-set support (not `0603cce7cee15eb8`).
2. **Promote to default**: Consider removing the opt-in gate and making the Ghidra 28-byte offset the default, now that all 3 proof steps pass with 184/184 agreement.
3. **Documentation refresh**: `knowledge.md` and `current-status.md` should reflect the completed Ghidra proof lane.
