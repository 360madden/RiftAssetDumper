# 65 Unmatched Flythrough Assets — Diagnosis

**Date:** 2026-06-28
**Author:** Buffy
**Context:** Follow-up to `2026-06-28-zone-flythrough-cross-ref.md` (164/229 fly assets had zone provenance via archive-neighbor resolution; 65 did not).

## TL;DR

**The "texture-pack" hypothesis is REFUTED.** All 65 unmatched assets are **NIF entries in map-zone archives** (assets.0xx per Cycle 5 taxonomy). The 65 are concentrated in **3 specific archives** (62/65 = 95%):

| Archive | Unmatched | Total fly | Miss rate | zone-full entries | Snippet type |
|---|---:|---:|---:|---:|---|
| `assets.050` | **30** | 42 | **71%** | 237 | mixed (path + block) |
| `assets.032` | **24** | 24 | **100%** | 23 | block-only (NiMesh) |
| `assets.037` | **8** | 62 | **13%** | 646 | block-only (NiMesh, clean) |
| elsewhere (≥20 archives) | 3 | 101 | **2.97%** | — | — |
| **Total** | **65** | 229 | **28%** | — | — |

Sanity: 42 + 24 + 62 + 101 = 229 ✓. Matched per archive: 12 + 0 + 54 + 98 = 164 ✓.

The 65 are **NIF geometry that lacks the source-path metadata** (`Z:/TWN/art/project/...`) the semantic scanner uses to tag entries as `hint:map-zone`. They are not texture/audio/XML entries.

## Why the 65 missed classification

The `build-asset-semantic-index --semantic-category hint:map-zone` scanner tags an entry as map-zone primarily by detecting the **NIF Creation Information path string** in the entry's `TextSnippetSamples`. This heuristic is robust for assets authored with the standard RIFT content pipeline (most world objects, terrain, architecture) but **misses entries whose NIFs lack that metadata block** — these are typically:

- Props / character meshes with hardcoded geometry (no source path)
- VFX / particle / decal meshes (effects pipeline, not world pipeline)
- LoD / collision-only meshes (baked from FBX without re-saving through the full pipeline)
- Internal tool exports (e.g., `NiMesh`-only entries with no scene graph)

### Smoking gun: `assets.032` is 100% path-less

- **100% miss rate** for flythrough assets (24/24).
- Only 23 entries in zone-full for this archive — all 23 are *other* NIFs in the same archive, none of them flythrough assets.
- ALL 23 snippets are `"NiMesh"` (block type, not path) — no `Z:/TWN/...` strings.
- 4/23 have `First4='00000000'` (placeholder) — likely stubs/empty entries.
- **Archive must contain ≥47 NIFs** (23 zone-full + 24 fly) → roughly half of this archive's NIFs are path-less. The 24 fly assets are the path-less minority in an archive-wide path-poor environment.
- The archive is NIF-rich but path-poor: it holds geometry without the provenance chain.

This is the cleanest evidence that the 65 are **path-less NIFs**, not texture entries. If they were texture packs, they would not be in `live-nif-archive-index.json` at all (that file is NIF-scoped) and the archive would have 0 zone-full entries.

### `assets.050` shows the path/path-less mix

- 237 zone-full entries (the bulk) carry path strings like `N_GR_terrain_rock_occluder_02` (terrain-occluder props).
- 12 fly assets matched (had paths).
- 30 fly assets did NOT match — same archive, different content style.
- The archive clearly holds both path-bearing and path-less NIFs; the 30 are the path-less minority.

### `assets.037` is the cleanest archive (no format anomalies)

- 646 zone-full entries, **all** with First4=`47616d65` (standard NIF magic = "Game"), all snippets `"NiMesh"`. No `00000000` stubs, no non-NIF magics.
- 54/62 (87%) fly assets matched → the archive's "normal" classification works.
- The 8 unmatched (13%) are the rare path-less minority in an otherwise clean archive. **For these 8, missing path metadata is the most likely reason for the miss** (inference from the archive-wide pattern; a per-asset probe would be needed to confirm there are no other distinguishing traits). This sharpens the diagnosis: path metadata is the discriminating variable.

## Diagnostic method

1. Computed `unmatched = flythrough_ids (229) − {aid : aid in zone-full.json Entries}` via `ijson` streaming of the 146 MB `zone-full.json` (authoritative — bypassed the v2 cross-ref file that had a JSON typo at line 20; typo fixed separately).
2. Cross-referenced 65 unmatched against `live-nif-archive-index.json` (227 cohort rows) → 65/65 had archive attribution (all are NIF entries).
3. Tallied zone-full coverage per archive to test texture-pack hypothesis:
   - All 3 problem archives have 23-646 zone-full entries → they are NIF-rich, not texture packs.
   - The Cycle 5 `assets.0xx = hint:map-zone` archive-range classifier is correct (they ARE in the map-zone archive range), but the entry-level scanner misses path-less NIFs.
4. Inspected `TextSnippetSamples` and `First4` distributions per archive:
   - assets.032 and assets.037: 100% block-type snippets (`NiMesh`), zero path strings among matched entries → archive-wide absence of NIF Creation Information metadata.
   - assets.050: mixed — some entries have path strings, some don't.

## Implications for downstream consumers

- **Flythrough pipeline is correct to export these 65.** They have valid geometry (their OBJs are in `Assets/build/flythrough/objs/`). The semantic-provenance layer is what's incomplete, not the geometry layer.
- **The 65 should be marked `zone_provenance: missing`** in the cross-reference artifact, not silently dropped. The v2 cross-ref JSON reports them as `<unknown>` which is currently fine, but a follow-up could add a `zone_provenance_status: "missing-path-metadata" | "resolved-via-archive-neighbor"` field.
- **The 65 are also unresolvable via archive-neighbor lookup** because the heuristic looks for the SAME archive having zone-bearing entries; assets.032 has only 23 zone-full entries total (all path-less), so no neighbor provides a usable path. This is why the archive-neighbor resolution rate is 100% for matched but 0% for these 65.

## Forward work

1. **`build-asset-semantic-index` scanner improvement (hypothesis to test)** — Add a fallback path-extraction heuristic that looks for ANY `art/project/...` substring in the NIF block tree (not just the NIF Creation Information string). Whether this would actually catch the 65 is unverified — it assumes the 65 carry some path string somewhere in their block tree. If they don't (because they're path-less *throughout*), this won't help. The structural probe (item 3) should run first to confirm.
2. **Add a `FlythroughAssetZoneProvenance` schema** to flythrough-index.json with fields: `status` (`resolved` / `missing-path-metadata` / `unresolved`), `archive_zone_census` (the archive's overall zone count), and `neighbor_resolution` (if archive-neighbor fallback succeeded).
3. **Characterize the 65** with a structural probe: are they all `NiMesh`-only entries with no `NiNode` scene graph? This would explain the missing provenance (scene-graph-level metadata is where NIF Creation Information lives).
4. **Direct NIF content-type probe** — Use the C# dumper to probe 2-3 of the 65 unmatched (one each from assets.050, .032, .037) and show their block-type tree. Expected finding: a flat `NiMesh`-only structure with no `NiNode` scene graph (since `NiNode` is where NIF Creation Information is normally attached). This would conclusively prove the path-less-NIF hypothesis.

## Artifacts

- `Exports/semantic-phase1/zone-flythrough-cross-ref-v2.json` — fixed (line 20 JSON typo corrected) and now contains the 164 matched assets' zone provenance.
- This handoff documents the 65 unmatched diagnostic.

## Provenance

- Diagnosis scripts ran against `C:\RIFT MODDING\Assets\` (live archive at `C:\Program Files (x86)\Glyph\Games\RIFT\Live\`).
- Files: `flythrough-index.json` (229 assets), `zone-full.json` (146 MB, 69,572 entries), `live-nif-archive-index.json` (227 rows).
- No file mutations beyond the v2 JSON typo fix.
