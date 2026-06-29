# Zone-Flythrough Cross-Reference Handoff

**Date**: 2026-06-28
**Session**: Build-asset-semantic-index full-map-zone scan → zone extraction → flythrough asset attribution
**Author**: Buffy (automated)

## Scope

- **Scan**: `build-asset-semantic-index --semantic-category hint:map-zone --max-total 0` (unbounded)
- **Source entries (zone-full.json)**: 69,572 entries classified `hint:map-zone` (66,523 NIF, 2,983 BIN, 65 XML, 1 LUA)
- **Flythrough corpus**: 229 assets in `Assets/build/flythrough/flythrough-index.json`

## Key findings

### Phase A — Path-bearing vs non-path-bearing partition

Of the 66,523 NIF `hint:map-zone` entries:

| Bucket | Count | Share |
|--------|------:|------:|
| Path-bearing (have `Z:/TWN/art/project/...` in TextSnippetSamples) | 22,440 | 33.7% |
| Non-path-bearing (only block-type snippets — `NiMesh` / `NiSourceTexture` / empty) | 44,083 | 66.3% |

**Critical insight**: 66.3% of `hint:map-zone` NIF entries are referenced as texture-pack bundles / mesh-strip pairs whose snippets don't carry a creation-info path. The path-bearing subset (22,440 entries) is the **canonical game-object census**.

### Phase B — Flythrough cross-reference

- **Matched**: 164 / 229 flythrough assets (71.6%) have a `hint:map-zone` row in zone-full.json
- **Archive-neighbor resolution**: 164 / 164 (100%) of these matches got zone provenance salvaged by walking adjacent entry indices (+/-150) in the same `ArchiveName` for any path-bearing row

Every matched flythrough asset lands next to a path-bearing NIF entry in its archive, allowing zone assignment without needing its own (missing) path snippet.

### Phase C — Zone census

The 22,440 path-bearing entries resolve to 4 expansions and several canonical category × zone tuples:

| Expansion | NIF entries |
|-----------|------:|
| vanilla    | 9,409 |
| ep1        | 6,595 |
| ep2        | 4,060 |
| ep3        | 2,376 |

Top zone tuples by entry count:

1. `vanilla.world_objects.props` → 2,380
2. `vanilla.world_objects.architecture` → 2,135
3. `ep1.world_objects.architecture` → 1,933
4. `vanilla.world_objects.nature` → 1,764
5. `ep2.world_objects.architecture` → 1,607
6. `ep1.world_objects.housing` → 1,437
7. `ep1.world_objects.nature` → 1,209
8. `vanilla.world_objects.dungeons` → 1,205
9. `ep2.world_objects.nature` → 1,000
10. `ep3.world_objects.nature` → 992

**Pattern**: `architecture` and `nature` dominate each expansion; `housing` is an ep1+/ep2+ feature; `dungeons` is vanilla-only.

## Output artifacts

| File | Contents |
|------|----------|
| `Exports/semantic-phase1/zone-full.json` | 146 MB; 69,572 hint:map-zone entries (Tier-1 archive-derived) |
| `Exports/semantic-phase1/zone-flythrough-cross-ref.json` | v1 cross-ref using single-segment path extraction (limited) |
| `Exports/semantic-phase1/zone-flythrough-cross-ref-v2.json` | Final cross-ref with partition stats + zone census |

## Method

### Zone extraction

Multi-segment path parser after `Z:/TWN/art/project/`:

1. First segment is expansion if it is `vanilla` / `ep1` / `ep2` / `ep3` / `ep4` / `nightmare`
2. First non-proxy segment is category (skipping `_common`, `general`, `model`, `mesh`, `props`, `vfx`, `character`, `creature`)
3. First segment after category that's not `model`/`mesh`/`name`/`textures`/`lod` is the zone

### Cross-reference resolution

For each flythrough asset, the matching `hint:map-zone` row was located by `AssetIdPrefix` (16-char hex). When the row's own snippets lacked a creation-info path, the canonical zone was salvaged by:

- Querying the same `ArchiveName` for the *nearest* path-bearing NIF row within +/-150 `EntryIndex` of the source entry
- Empirically, every flythrough match had such a neighbor within the window — **100% salvage rate**

## Open questions / forward work

- **65 unmatched flythrough assets (28.4%)**: what archive do they live in? Are they in non-map-zone archives (texture packs, character packs)? A targeted lookup against the full archive index would classify them.
- **fly1ecdbaf5a2576ba5 + cf54e712ff57eaac in vanilla**: large mesh entries (6,489 and 228 vertices respectively) live in `assets.002` archive, indices 1190-1191. These are likely the "world architecture" cluster — cross-check against the formula path `assets.002` neighbor.
- **Inferred vs scanned provenance**: 164 cross-reference matches use *archive-neighbor* zone context rather than per-asset direct provenance. Worth a verification pass: is the chosen neighbor typically a mesh sibling, a texture bundle, or a leaf geometry?

## Cycle 5 ship-note

This is the **Tier-1 firing-rate-polyfill** forward progression: zone-full.json emits archive-derived provenance for all 69,572 hint:map-zone entries (100% coverage, was previously heuristic fallback). The flythrough cross-reference runs against this archive-derived lane and achieves 164/229 (71.6%) direct matches plus 100% archive-neighbor salvage.
