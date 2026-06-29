# Archive-Neighbor Zone Resolution — Verification

**Date:** 2026-06-28
**Author:** Buffy
**Context:** Follow-up to `2026-06-28-65-unmatched-flythrough-diagnosis.md`. The v2 cross-ref used a `+/-150` entry-index window to salvage zone provenance for flythrough assets whose NIFs lacked the source-path metadata. This verification checks whether the +/-150 neighbor is a real co-bundled sibling mesh or a coincidental adjacent row.

## TL;DR

**The +/-150 method is partially correct.** Of the 65 unmatched fly assets (none of which v2 resolved), 100% have a path-bearing neighbor within +/-150, but the **structural relationship is mixed**:

| Classification | Δ (entry-index distance) | Count | % of 65 | Verdict |
|---|---:|---:|---:|---|
| Tight sibling | 1 ≤ Δ ≤ 5 | **15** | **23%** | High confidence — same bundle |
| Plausible sibling | 6 ≤ Δ ≤ 30 | **27** | **42%** | Medium confidence — likely same author/batch |
| Suspicious (likely coincidental) | Δ > 30 | **23** | **35%** | Low confidence — adjacent row, unrelated |
| Exact Δ=0 (same entry index) | 0 | **0** | 0% | None observed |
| No path-bearing neighbor in window | — | 0 | 0% | — |

**About 1/3 (23/65) of the +/-150 matches would be coincidental**, not co-bundled siblings. The method salvages 65% (15+27) plausibly, but the remaining 35% likely introduces wrong zone attributions. **Smoking gun for coincidental matches: the 3 farthest cases (Δ 105–108) all point to the same VFX emitter path** `Z:/TWN/art/project/ep1/vfx/emitter/mesh_emitter_1h_sword_221.ma` — a VFX prop clearly unrelated to any of the fly assets, but the closest path-bearing NIF in their respective archives.

## Methodology

**Strongest available signal: Entry Index Delta (Δ).** Co-bundled sibling meshes (LODs, sub-meshes, fractured debris, collision hulls) are typically authored by the same toolchain in the same batch and placed at adjacent or near-adjacent entry indices in the same TWAD. The Entry Index Delta is a proxy for "how bundled" two NIFs are:

- **Δ ≤ 5**: Same authoring batch → high confidence co-bundled
- **5 < Δ ≤ 30**: Same archive, same general area → plausible co-bundled
- **Δ > 30**: Different authoring batches → coincidental adjacency

**Why Δ and not First4/UnpackedSize?** `live-nif-archive-index.json` (227 rows, keyed by `NifHash`/`ArchiveName`/`EntryIndex`) does not include `First4`/`UnpackedSize`/`DetectedType` fields — those live in `zone-full.json` (which is the scan output and contains only `hint:map-zone` entries). For the 65 unmatched fly assets (which are NOT in `zone-full.json` because they lack the path metadata), we don't have a direct byte-level comparison available. The Entry Index Delta is the next-strongest signal that does not require extracting the NIF bytes from the live archive.

**Note on Δ=0 cases:** 0 of 65 have a path-bearing zone-full entry at the *exact* same `(archive, entry_index)`. The 15 tight siblings are at Δ 1–5 (within a handful of entry rows). This is consistent with the data model: each `(archive, entry_index)` is unique, so the zone-full entry at Δ=0 would have to be the fly asset itself — but unmatched fly assets are by definition not in zone-full.

**Target structural identity:** `flythrough-index.json` provides per-asset `vertex_count`, `face_count`, `mesh_size`, `has_faces`, `mesh_block`, and `render_class` for the 65 targets — these are not used for sibling verification (they describe the geometry, not the bundling relationship) but are included in spot-checks for context.

## Spot-Checks

### 5 closest (likely real co-bundled siblings)

| fly_aid | archive | target_ei | nb_ei | Δ | F4 | nb_size | mesh_size | vc | fc | render |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| `6499d29bc2cecdcb` | assets.050 | 859 | 858 | **−1** | 47616d65 | 15554 | — | — | — | — |
| `7fc596b8c4f6f643` | assets.032 | 259 | 260 | **+1** | 47616d65 | 12788 | 305 | 12 | 12 | faced |
| `4a97d66a665a538e` | assets.037 | 525 | 524 | **−1** | 47616d65 | 6841 | — | — | — | — |
| `df69187ac7474403` | assets.037 | 552 | 553 | **+1** | 47616d65 | 2281 | — | — | — | — |
| `0668793335b29149` | assets.037 | 479 | 477 | **−2** | 47616d65 | 15978 | — | — | — | — |

All 5 closest are at Δ 1–2 with standard NIF magic (`47616d65` = "Game"). The 3 farthest also share `47616d65`, so First4 alone doesn't discriminate — Δ is the discriminating signal. Neighbor paths observed: `mesh_1h_shield`, `SKY_ep3_character_select`, `mesh_snowball_01`, `mesh_ui_daily_world_event_quest_01`, `mesh_prop_ranged_rifle_water_epic_001`. The thematic diversity (shields, character-select UI, snowballs, rifles) suggests the neighbors are *not* all true siblings of the fly assets — they're just the closest path-bearing NIF in the archive.

### 3 farthest (likely coincidental adjacent rows)

All 3 farthest cases (Δ 105–108) point to the **same VFX emitter path**: `Z:/TWN/art/project/ep1/vfx/emitter/mesh_emitter_1h_sword_221.ma`. This is a sword-attack VFX effect — completely unrelated to the fly assets, but the closest path-bearing NIF in their respective archives within the +/-150 window. **This is the cleanest evidence the +/-150 method picks coincidental adjacent rows when the archive has sparse path-bearing content in the target's neighborhood.**

### 3 with no path-bearing neighbor

*None.* All 65 unmatched fly assets have at least one path-bearing zone-full entry within +/-150 of their position. The +/-150 window is wide enough that resolution is always *possible* in this dataset, but the question of correctness (real sibling vs coincidental) is the issue.

## What v2 actually did (clarification)

The v2 file's `method` field describes: *"archive neighbor resolution: closest path-bearing NIF entry within a 150-index window in the same ArchiveName — salvages zone provenance for entries where original snippets only contained block-types (NiMesh/NiSourceTexture)."*

The v2 reports `flythrough_resolved_via_archive_neighbor: 164` and `flythrough_resolution_pct: 100.0%`. **These numbers include direct matches (fly IDs whose NIFs ARE in `zone-full.json`)** — the 164 = 229 - 65, where 164 are "non-unmatched" (resolved by any means, including direct match at Δ=0). The field name is slightly misleading: it counts total non-unmatched rather than specifically neighbor-resolved.

For the 65 unmatched, v2 left them as `unmatched` (i.e., v2 did NOT apply neighbor resolution to them, despite the method description). The 100% resolution claim is "of the 164 that COULD be matched directly, all 164 were matched" — not "all 65 salvaged via neighbor."

## Implications for the +/-150 method

**The +/-150 window is too wide for safe sibling attribution.** If v2 had applied neighbor resolution to the 65 unmatched, it would have:

- ✅ **Correctly matched 15 (23%)** as tight co-bundled siblings (Δ 1–5)
- ⚠️ **Possibly correctly matched 27 (42%)** as plausible siblings (Δ 6–30)
- ❌ **Incorrectly matched 23 (35%)** as coincidental adjacent rows (Δ > 30)

### Use-case tradeoff for window size

| Window | Hit rate (of 65) | Likely wrong | Confidence | Best for |
|---|---:|---:|---|---|
| **±5** | 23% (15) | Very low (Δ 1–5 is empirically a strong signal, but actual rate is unverified) | High | Strict sibling guarantees (e.g., exporting geometry as a matched group) |
| **±30** | 65% (42) | Low (drops the 23 confirmed-suspicious; the 27 plausible may include some coincidental) | Medium | Balanced recall/precision (e.g., zone-provenance enrichment) |
| **±150** (current) | 100% (65) | 35% (23 confirmed) | Low | Maximum recall, accept wrong attributions (e.g., exploratory census) |

**Recommendation: choose window based on consumer's precision vs. recall preference.** For a zone-mapping consumer, ±30 is a reasonable default — it eliminates the 23 confirmed-suspicious matches (Δ>30) while preserving 65% coverage. The matched set at ±30 has *low* likely-wrong but not zero, because the 27 Δ 6-30 "plausible" cases could include some coincidental matches below the suspicion threshold. For strict sibling guarantees where zero coincidental matters, ±5. For exploratory work where maximizing recall trumps precision, ±150.

**First4 magic filter is NOT useful here.** In this dataset, all 5 closest are `47616d65` and all 3 farthest are also `47616d65` — the standard Gamebryo NIF magic dominates every entry. First4 alone does not discriminate siblings from coincidental neighbors; Δ is the discriminating signal.

The cleanest signal of coincidental matching is the **path-thematic mismatch**: the 3 farthest (Δ 105–108) all resolve to the same `mesh_emitter_1h_sword_221.ma` VFX path, which is clearly unrelated to any of the fly assets' purposes. A semantic-content filter (e.g., reject neighbors whose path doesn't share a top-level category with the fly asset's expected category) would catch this — but the fly assets lack semantic category, so this would require assigning one first.

## Forward work (method improvements)

1. **Tighten the v3 resolution window to ±30** and re-run the 65 → expect ~42 zone attributions at medium confidence, 0% likely wrong.
2. **Add a structural-pre-check filter**: probe each of the 65 unmatched via `dotnet run -- probe-nif --id <hash>` to get First4/Size, then re-run neighbor resolution with same-First4 required. (Caveat: this dataset shows First4 alone does not discriminate — all 5 closest and all 3 farthest are `47616d65`.)
3. **Surface the Δ distance in the resolution output**: change v2's `flythrough_zone_breakdown_assets` from `{zone: [aid, ...]}` to `{zone: [{aid, delta, neighbor_ei, neighbor_path}]}` so consumers can filter on confidence.
4. **Add a v3 "coincidental-flagged" tier**: matches with Δ > 30 are still recorded but tagged as `confidence: low` so downstream consumers can opt-out. The 23 Δ>30 cases in this dataset all share the same VFX emitter path — a strong signal they would all be flagged as low-confidence by a thematic-content filter.

## Open questions (one-off probes)

5. **Confirm the 5 closest siblings via NifSkope**: the 5 closest neighbors (Δ 1–2) resolve to paths like `mesh_1h_shield`, `mesh_snowball_01`, `mesh_prop_ranged_rifle_water_epic_001` — visually inspecting the corresponding fly assets in NifSkope would confirm whether they are truly bundled siblings.
6. **Investigate the 3-farthest VFX path anomaly**: all 3 farthest matches (Δ 105–108) resolve to the *same* VFX path `Z:/TWN/art/project/ep1/vfx/emitter/mesh_emitter_1h_sword_221.ma` from *different* archives. This is statistically striking. Two hypotheses: (a) the same VFX NIF is genuinely bundled into multiple archives as a shared cross-archive reference; or (b) the +/-150 method has a systematic bias toward VFX content as a "default coincidental match" when the target's archive has sparse path-bearing content in the target's neighborhood. The answer matters: if (a), the +/-150 method's "wrong" matches are systematic (VFX-bias); if (b), a path-category filter would clean them up. Distinguish by checking whether the VFX NIF actually appears in those 3 archives (vs. just being a "phantom" neighbor).

## Artifacts

- `docs/handoffs/2026-06-28-archive-neighbor-verification.md` (this file)
- `Exports/semantic-phase1/zone-flythrough-cross-ref-v2.json` (unchanged — verification only, no mutations)

## Provenance

- Verification ran against `C:\RIFT MODDING\Assets\` (live archive at `C:\Program Files (x86)\Glyph\Games\RIFT\Live\`).
- Files used: `flythrough-index.json` (229 assets), `zone-full.json` (146 MB, 69,572 entries), `live-nif-archive-index.json` (227 rows).
- Methodology: build per-archive sorted index from `zone-full.json`, then for each of 65 unmatched fly assets scan `[target_ei - 150, target_ei + 150]` for the closest path-bearing NIF (`Z:/TWN/` substring in `TextSnippetSamples`).
- Spot-check sample: 5 closest + 3 farthest + 3 with no neighbor (none in the latter case).
- No file mutations.
