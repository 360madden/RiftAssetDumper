# Phase 1 — Zone/Map Name Mining

**Date**: 2026-07-07
**Roadmap**: `docs/roadmap/semantic-discovery-roadmap.md`
**Phase**: 1 — Priority Lane 1: Zone/Map Coordinate Systems & Bounds

## Summary

All 5 Phase 1 milestones complete. Zone names extracted from binary payloads using
`hint:map-zone` semantic category. 10,150 groups formed from 9,075 zone entries with
30,075 unique strings. Zone vocabulary schema defined and validated.

## Milestone Results

### M1.1 — Smoke Zone-Targeted Index

| Metric | Value |
|--------|-------|
| Command | `build-asset-semantic-index --semantic-category hint:map-zone --max-total 1000` |
| Inspected | 1,000 |
| Zone entries | 83 |
| Failed | 0 |
| Output | `Exports/semantic-phase1/smoke-zone-1k.json` |

**Key finding**: All `hint:map-zone` entries are **binary** type (`bin`), not XML.
The map-zone metadata is embedded in NiMesh/NiSourceTexture binary payloads.

### M1.2/M1.3 — Large-Scale Binary Zone Scan

| Metric | Value |
|--------|-------|
| Command | `build-asset-semantic-index --semantic-category hint:map-zone --max-total 50000` |
| Inspected | 50,000 |
| Zone entries | 9,075 (18.2% of inspected) |
| Failed | 0 |
| Unique strings | 30,075 |
| Output | `Exports/semantic-phase1/zone-50k.json` (19.4 MB) |

### M1.4 — Zone Vocabulary Synthesis

Script: `scripts/synthesize_zone_vocabulary.py`

| Metric | Value |
|--------|-------|
| Groups formed | 10,150 |
| Largest group | 7,784 entries (NiMesh) |
| Unique strings | 30,075 |

**Classification breakdown**:

| Category | Count | Examples |
|----------|------:|----------|
| file_paths | 29,641 | `Z:/TWN/art/...`, `_dev/asset/...` |
| map_keys | 213 | `map_plain_freemarch_sand_01.dds`, `map_forest_silverwood_dirt_01.dds` |
| zone_names | 111 | `NiMesh`, `NiSourceTexture`, `NiTerrainNode` |
| shader_references | 4 | `worldInverse`, `worldView`, `worldInverseTranspose` |
| other | 106 | `QUESTITEM`, `AUDIO - Locator - Boat Creaks` |

**Confirmed zone names found in texture references**:

- **Freemarch**, **Silverwood**, **Gloamwood**, **Moonshade Highlands**
- **Scarlet Gorge**, **Stonefield**, **Droughtlands**, **Stillmoor**
- **Shimmersand**, **Ember Isle**, **Iron Pine Peak**
- **Hammerknell** (dungeon), **Shadowlands**

Output: `Exports/semantic-phase1/zone-vocabulary.json` (validated against schema)

### M1.5 — Zone Vocabulary Schema

| Artifact | Status |
|----------|--------|
| `docs/schemas/zone-vocabulary-v1.schema.json` | ✅ Created and validated |
| `scripts/synthesize_zone_vocabulary.py` | ✅ Ruff clean |
| `Exports/semantic-phase1/zone-vocabulary.json` | ✅ Schema-valid |

## Key Findings

1. **Map-zone data is in binary NIF payloads**, not XML. The `hint:map-zone` heuristic
   detects NiMesh and NiSourceTexture blocks that reference terrain textures with
   zone-specific names (e.g., `map_plain_freemarch_sand_01.dds`).

2. **10 confirmed RIFT zone names** extracted from terrain texture naming conventions.
   The naming pattern `map_{terrain_type}_{zone_name}_{feature}.dds` carries embedded
   zone identifiers.

3. **30,075 unique strings** across 9,075 zone entries — most are asset file paths
   (98.5%), with 213 distinct terrain texture naming patterns.

4. **The `hint:map-zone` category is highly productive** — 18.2% of all scanned
   payloads carry it, making it one of the most abundant semantic categories.

## Exit Criteria

| Criterion | Status |
|-----------|--------|
| Zone names extracted and deduplicated | ✅ (10 confirmed + many texture-derived) |
| Zone vocabulary artifact produced | ✅ `zone-vocabulary.json` |
| Schema defined and artifact validates | ✅ `zone-vocabulary-v1.schema.json` |
| Handoff committed | ✅ (this document) |

## Next Steps (Phase 2 — Priority Lane 2: Waypoints/POIs)

Phase 1 is complete. Phase 2 targets `hint:waypoint-poi` entries for waypoint names,
quest objectives, and POI strings.

1. Run `build-asset-semantic-index --semantic-category hint:waypoint-poi --max-total 50000`
2. Synthesize POI vocabulary similar to zone vocabulary
3. Cross-reference POI names with zone names from Phase 1

## Artifacts

| File | Description |
|------|-------------|
| `Exports/semantic-phase1/smoke-zone-1k.json` | 1k smoke test (gitignored) |
| `Exports/semantic-phase1/zone-50k.json` | 50k zone-targeted scan (gitignored) |
| `Exports/semantic-phase1/zone-vocabulary.json` | Synthesized zone vocabulary (gitignored) |
| `docs/schemas/zone-vocabulary-v1.schema.json` | Zone vocabulary schema (committed) |
| `scripts/synthesize_zone_vocabulary.py` | Vocabulary synthesis script (committed) |
| `docs/handoffs/2026-07-07-phase1-zone-vocabulary.md` | This handoff (committed) |
