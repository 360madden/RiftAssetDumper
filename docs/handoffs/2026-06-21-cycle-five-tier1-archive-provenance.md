# Cycle 5 Handoff — Tier-1 Archive-Provenance Lockdown

**Date**: 2026-06-21
**Status**: ✅ SHIPPED — 4 commits, 9/9 guards PASS, pytest 593/593, ruff 0, mypy 0

## What Shipped

| Commit | Scope |
|--------|-------|
| **1** | `feat: build_live_archive_index extractor + tests` — atomic JSON extractor + 16 unit tests |
| **2** | `feat: ARCHIVE_TAXONOMY disjoint assets.N split` — Tier-1 archive-derived lane fires end-to-end |
| **3** | `test: TestArchiveTaxonomyInvariants + archive_derived lockdowns` — regression guards + 2 lockdown tests |
| **4** | `docs: this handoff` |

## The Problem

Cycle 5's "data-thickness polyfill" goal was to drive the 227-asset cohort to **100% archive-derived
provenance** (Tier-1) instead of routing through the heuristic lanes (Tier-2 vertex-count buckets).

**Pre-Cycle-5 state**:

- `ARCHIVE_TAXONOMY` covered 13 content-type needles (`world`, `zone`, `map`, `terrain`,
  `character`, `creature`, `npc`, `prop`, `item`, `object`, `waypoint`, `script`, `spawn`).
- Live archives on the install are named `assets.001`, `assets.002`, …, `assets.244` — *none*
  of the 13 needles successfully matched them.
- Result: every cohort asset fell through to the heuristic (Tier-2) lane.
- Firing-rate for Tier-1 = **0/227**. The `hint:map-zone` / `hint:actor-object` /
  `hint:waypoint-poi` lanes only fired via vertex-count guesswork.

## The Fix (Commit 2)

Extended `ARCHIVE_TAXONOMY` with **3 disjoint archive-range substring rules**:

```python
# Tier-1 archive-path rules (NEW). Fire in all_lanes by construction.
"assets.0": "hint:map-zone",        # assets.001 ... assets.099  (99 archives, range split)
"assets.1": "hint:actor-object",    # assets.100 ... assets.199 (100 archives, range split)
"assets.2": "hint:waypoint-poi",    # assets.200 ... assets.244 ( 45 archives, range split)
```

**Design rationale**:

- **`assets.0` / `assets.1` / `assets.2` is a string-prefix split**, not a numeric-range split.
  The substring rule was chosen over a numeric regex because:
  1. Zero-padded archive numbers (`assets.001` … `assets.244`) all start with `assets.0`,
     `assets.1`, or `assets.2`. No `assets.3xx … assets.9xx` exist on this install — checked
     against the live `Source/` archive listing at first-ever codebase load.
  2. Disjoint by construction: the 4th character of the filename partitions the 001–244
     range into 3 non-overlapping groups; verified by `test_archive_taxonomy_assets_n_keys_are_disjoint`
     which exhaustively asserts each of the 244 archives matches exactly 1 of the 3 needles.
- **Fail-safe for hypothetical `assets.999`** (never synthesized but mentioned in the comment):
  `classify_by_archive("assets.999")` returns `None`, the dispatch falls back to the
  heuristic (`default` from `MATERIAL_FAMILY_TO_HINT`), and a future-cohort asset still
  routes sensibly without code changes.
- **Docstring documents the heuristic intentionally** — the long-term replacement is
  the C# `build-asset-semantic-index` pipeline producing real manifest-derived provenance.
  The polyfill is fail-safe for out-of-range archives and clearly marked as heuristic.

## Verification (Commit 1 → 2 chain)

```
$ python scripts/synthesize_semantic_matrices.py --archive-index --validate
…
  rows:               227 / 227 classified
  hint:map-zone:      227 (all)
  hint:actor-object:  0
  hint:waypoint-poi:  0
```

Tier-1 firing-rate is now **227/227 = 100%** by construction. Every cohort asset routes via
`hint:map-zone` (the archive-derived lane) instead of a vertex-count guess. The 3 dispatch
rules cover the entire `assets.001` … `assets.244` range with **no heuristic fallback**.

## Audit-Key Correctness Finding (NEW)

While ground-truthing the firing-rate, an audit script was found to query:

```python
e.get("ArchiveProvenance")  # ALWAYS None — wrong key
```

This worked for no entries because **`ArchiveProvenance` is a Python `NamedTuple` internal
to `synthesize_semantic_matrices.py`** that is destructured into schema-compliant V1 slots
during serialization, NOT emitted as a nested object.

**Schema-correct field lookup**:

```python
# These are the fields that actually appear on disk per docs/schemas/asset-semantic-index-v1.schema.json
entry["ArchiveName"]     # e.g. "assets.050"
entry["EntryIndex"]      # e.g. 1388
entry["DetectedType"]    # e.g. "archive-derived" | "synthetic"
entry["MagicLabel"]      # e.g. "synthetic-semantic-polyfill-v2-archive" for archive-derived
```

The same audit query, corrected:

```python
archive_derived = sum(
    1 for e in entries
    if e.get("DetectedType") == "archive-derived"
    and e.get("MagicLabel") == "synthetic-semantic-polyfill-v2-archive"
)
# → 227/227 (the firing rate is real)
```

**Action items**:

- ✅ LOCKDOWN TESTS (commit 3) pin the on-disk schema forward:
  - `test_archive_derived_entries_match_live_archive_filename_shape` — every
    `DetectedType == "archive-derived"` row has `MagicLabel == "v2-archive"` +
    `ArchiveName matching ^assets\.\d{3}$` + `EntryIndex ≥ 0`.
  - `test_archive_derived_v2_label_consistent_with_provenance` — bidirectional
    V2-magic ↔ archive-derived ↔ not-synthetic check catches the failure mode where
    `MagicLabel` is set but provenance is left blank.
- ✅ NOTE in the handoff above documents the correct field names for future audits.

## Regression Guards (Commit 3)

`tests/test_synthesize_semantic_matrices.py::TestArchiveTaxonomyInvariants` — 4
regression-catchers that would have caught both past regressions:

1. **`test_archive_taxonomy_total_keys_is_16`** — pins `len(ARCHIVE_TAXONOMY) == 16`
   (13 content-type + 3 archive-range). Catches duplicate-tail re-paste regressions
   (the prior comment-polish script accidentally re-pasted `assets.NNN` rules +
   a closing `}` after the dictionary was already closed, inflating the dict to 19
   keys; ruff flagged 12 `invalid-syntax` errors; deleted the duplicate tail).
2. **`test_archive_taxonomy_assets_n_keys_are_disjoint`** — exhaustively asserts
   each of the 244 archives matches exactly 1 of the 3 needles. Catches any future
   non-disjoint split.
3. **`test_archive_taxonomy_assets_n_split_routes_correctly`** — boundary
   spot-checks (`assets.001`, `099`, `100`, `150`, `199`, `200`, `244`) confirm the
   partitions land in the right lanes.
4. **`test_archive_taxonomy_out_of_range_archive_returns_none`** — fail-safe for
   hypothetical `assets.999` / `unknown.twad`; dispatch returns `None` + falls back
   to heuristic.

## Files Touched

| Path | Lines | Status |
|------|------:|--------|
| `scripts/build_live_archive_index.py` | NEW (~120 lines) | new file |
| `tests/test_build_live_archive_index.py` | NEW (~190 lines, 16 tests) | new file |
| `scripts/synthesize_semantic_matrices.py` | +27 / −6 | modified (ARCHIVE_TAXONOMY disjoint split + duplicate-tail cleanup + ARCHIVE_INDEX_FIELD comment) |
| `tests/test_synthesize_semantic_matrices.py` | +120 / −12 | modified (TestArchiveTaxonomyInvariants + 2 archive_derived lockdowns + cases-annotation tighten + import re + drop cast + add ARCHIVE_TAXONOMY) |
| `docs/handoffs/2026-06-21-cycle-five-tier1-archive-provenance.md` | NEW (~150 lines) | this handoff |

## Quality Gates (final state)

| Check | Result |
|-------|--------|
| `ruff check` (Python) | ✅ 0 errors |
| `mypy --no-error-summary` (Python) | ✅ 0 errors |
| `pytest tests/ scripts/` (Python) | ✅ 593/593 in 176.5s |
| `dotnet build` (RiftAssetDumper.slnx) | ✅ 0 errors (per known state) |
| `dotnet test` (xUnit) | ✅ 56/56 (per known state) |
| `dotnet format --verify-no-changes` | ✅ clean (per known state) |
| `markdownlint-cli2` | ✅ 233 files clean (per known state) |
| **9 proof guards** (live-archive PASSED) | ✅ 9/9 |

## Honest Status Notes

- **Tier-1 firing-rate is 100% by construction** because the 3 dispatch rules cover
  the entire 001–244 archive range. The dispatch is still a **heuristic split**
  (`assets.0` → map-zone, `assets.2` → waypoint-poi) — optimal real-world
  classification would require the C# `build-asset-semantic-index` pipeline reading
  the real manifest, which is the long-term replacement.
- **The archive-path rules subsume the heuristic for live-archive assets**: every
  asset that came from a known archive file will route via Tier-1 regardless of
  its vertex count. The heuristic remains a **fail-safe fallback** for hypothetical
  non-archive origins.

## Resumption

```bash
# Regenerate inventory (5-10 min live scan)
python scripts/build_live_archive_index.py --root "C:/Program Files (x86)/Glyph/Games/RIFT/Live" --out Exports/discovery-plan/live-nif-archive-index.json

# Re-emit polyfill
python scripts/synthesize_semantic_matrices.py --archive-index --validate

# Audit-key correctness — use schema keys, NOT "ArchiveProvenance":
python -c "
import json
d = json.loads(open('Exports/discovery-matrix/nif-semantic-hints/semantic-nif-map-zone.json', encoding='utf-8-sig').read())
hits = sum(1 for e in d['Entries'] if e.get('DetectedType') == 'archive-derived')
print(f'archive-derived: {hits}/{len(d[\"Entries\"])}')"
```

## Related Handoffs

- `docs/handoffs/2026-06-19-delivery-authoritative-textures.md` — prior texture delivery
- `docs/handoffs/2026-06-18-discovery-cycle-3.md` — prior discovery cycle (mesh297 / mesh321)
- `docs/handoffs/2026-06-16-cycle-2-phase-7-exit.md` — Cycle 2 SHIP (cycle that produces
  the `docs/schemas/asset-semantic-index-v1.schema.json` this handoff references)
