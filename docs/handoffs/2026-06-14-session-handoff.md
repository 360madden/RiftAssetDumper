# Session Handoff — June 14, 2026

**Date**: 2026-06-14
**Type**: Session Handoff
**Status**: **COMPLETE** — Ghidra scanner shipped, texture coverage improved to 212/217 (97.7%), FT plan finalized, CI green

---

## Git Operations

- **Pushed** 12 ahead commits (`d8c1a3e`…`50fd9a0`) to `origin/main` — flythrough texture tooling batch
- **Reviewed, fixed, and committed** `scripts/ghidra/NifHashCrossReferenceScanner.java` (`7fe667e`)
  - Fixed report key casing (`schemaVersion` → `SchemaVersion`, `candidateOnly` → `CandidateOnly`)
  - Added required guard fields (`FieldOrderPromoted: false`, `ParserExportPromotionAllowed: false`)
  - Per `docs/nidatastream-ghidra-schema-policy.md`

---

## Ghidra Scanner: `NifHashCrossReferenceScanner.java`

New Ghidra Java script that searches the RIFT binary for NIF hash IdPrefixes as:

- ASCII string literal (16 bytes)
- Raw 8-byte LE uint64 value

Reports occurrences with containing function, cross-references, decompiled context, and nearby labeled strings.

**Tested against `cf54e712ff57eaac`**: 0 matches in `rift_x64.exe` — confirms the hash is not hardcoded in the main executable. Scanner writes proper `CandidateOnly`-guarded JSON reports.

**Runner command**:

```
python scripts/ghidra_runner.py --project-name RiftAnchorSurvey --process rift_x64.exe --no-analysis --script scripts/ghidra/NifHashCrossReferenceScanner.java --keep-project --timeout 1200 --script-args <nif-hash> <output-json>
```

---

## Texture Coverage: 207/217 → 212/217 (97.7%)

### Live-Provenance Re-Linking (4 assets resolved)

The original `link-nif-textures` ran against the deleted `Source/` copied set, missing 4 live-provenance assets. Re-ran against the live game root:

| Step | Result |
|------|--------|
| `link-nif-textures --root <live>` | 81K models, 703K texture links |
| Filtered to 4 assets | 63 links (`1ecdbaf5a2576ba5`, `838831f8fb617ecc`, `95d9b14a964e67c8`, `cf54e712ff57eaac`) |
| `extract-linked-textures` | 62 DDS extracted, 0 failures |
| Merged into `flythrough-texture-links.jsonl` | 63 new links appended |
| `link_flythrough_textures.py` | 50 new PNGs converted, coverage → 211/217 |
| `build_texture_map.py --copy-textures` | 56 PNGs synced to RiftFlythrough |

### Manual Texture Borrowing (1 asset resolved)

`fa78ee2d8c3abca7` (meshSize=280, 32v/30f) had no DDS references but identical geometry to textured sibling `6f35dbcdb1ecf0ec`. Manually borrowed its 2-texture set (`378d4de6_n_dr_flowers_01_c.png`, `cb959623_n_dr_grass_01_s.png`). Added `borrowed_textures_from` and `borrow_rationale` metadata fields for traceability.

**Coverage → 212/217 (97.7%)**, `texture_map.js` updated with 691 entries.

### 5 Remaining Unresolvable Assets

| Asset | Reason |
|-------|--------|
| `1e8d2bcc6546b548` | Position-only (0 faces) |
| `35ca1d9dbad6d245` | Position-only (0 faces) |
| `b5dc665faa848f85` | Position-only (0 faces) |
| `0e0c61ad75d2af1e` | No DDS refs, 0 same-meshSize siblings |
| `1601c1f75e0a6022` | No DDS refs, 1 sibling but position-only |

All 6 were investigated via triage + DDS recovery + borrowing analysis. 1 resolved (borrowing), 5 fundamentally unresolvable.

---

## Discovery Suite & Proof Guards

All checks re-run and confirmed green:

| Guard | Status |
|-------|:------:|
| Ghidra Function Site Target Guard | ✅ PASSED |
| Ghidra Pairing Non-Export Guard | ✅ PASSED |
| Ghidra Attribute Candidate Guard | ✅ PASSED |
| Post-50 Validation Suite (8/8 checks) | ✅ ALL PASSED |
| Position source lanes | 🔒 Locked candidate-only (correct) |
| 50-Step Plan | 50/50 complete |

---

## Flythrough Bridge Plan

- Advanced FT-7.3 to **DONE** (LOD detector shipped: 10 high-confidence groups, 193/217 classified)
- **FT-1 through FT-7: DONE**
- **FT-8: SKIPPED** (mod-injection contradicts read-only mandate)
- Plan state machine: `.state.json` updated

---

## CI — All Green

| Check | Result |
|-------|--------|
| `dotnet build` | ✅ 0 errors, 0 warnings |
| `dotnet test` | ✅ 55/55 |
| `ruff check` | ✅ Clean |
| `mypy` | ✅ Clean |
| `pytest` | ✅ 372/372 |

---

## Smoke Bundle Validation

- **PASSED** — 349 OBJs, 0 issues, 0 missing textures, 0 MTL issues
- 79 zero-face geometries (expected position-only exports)

---

## World-Placed Merge

- `build_world_placed_merge.py` rebuilt `world-placed-merged.obj` (2.57 MB, 217 assets, 4 non-identity transforms)
- Copied to `RiftFlythrough/merged.obj`

---

## Files Changed

| File | Change | Committed? |
|------|--------|:----------:|
| `scripts/ghidra/NifHashCrossReferenceScanner.java` | New | ✅ `7fe667e` |
| `Assets/build/flythrough/flythrough-index.json` | Updated (linked_textures, borrow metadata) | ❌ gitignored |
| `Assets/build/flythrough/flythrough-texture-links.jsonl` | Merged 63 new links | ❌ gitignored |
| `Assets/build/flythrough/textures/converted-manifest.json` | 50 new PNG entries | ❌ gitignored |
| `Assets/build/flythrough/textures/converted/` | 50 new PNG files | ❌ gitignored |
| `Assets/build/flythrough/textures/linked-dds/recovered/` | 62 new DDS files | ❌ gitignored |
| `Assets/build/flythrough/.state.json` | FT-7.3 complete | ❌ gitignored |
| `Assets/build/flythrough/world-placed-merged.obj` | Rebuilt | ❌ gitignored |
| `Exports/ghidra-reports/nif-hash-cross-reference-cf54e712ff57eaac.json` | Scan output | ❌ gitignored |

---

## Current State Summary

- **212/217 (97.7%)** textured assets in RiftFlythrough
- **FT Bridge Plan: COMPLETE** (FT-1..FT-7 DONE, FT-8 SKIPPED)
- **CI: ALL GREEN**
- **All 8 proof guards: PASSED**
- **Commit `7fe667e` pushed** (`ghidra: add NifHashCrossReferenceScanner`)
- **World-placed-merged.obj** rebuilt and synced to RiftFlythrough
- **5 position-only assets** remain fundamentally unresolvable

---

## Next Best Actions

1. **Open RiftFlythrough** to visually verify the 212 textured assets with the new `merged.obj`
2. **Scan remaining 9 textureless hashes** through the Ghidra scanner (confirm all 0 matches)
3. **Run FT-6 validation** against the rebuilt `world-placed-merged.obj`
4. **Consider Ghidra scan of game DLLs** (not just `rift_x64.exe`) for NIF hash references
5. **Write the `NifHashCrossReferenceScanner` test** as a Python test fixture
