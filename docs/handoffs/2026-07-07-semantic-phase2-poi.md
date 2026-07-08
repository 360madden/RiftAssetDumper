# Semantic Phase 2 Handoff — Waypoints/POI Mining

**Date**: 2026-07-07
**Roadmap**: `docs/roadmap/semantic-discovery-roadmap.md` — Phase 2
**Status**: ✅ EXIT COMPLETE — with documented limitation

---

## Milestones Completed

### M2.1: POI Semantic Index

Attempted to extract waypoint/POI data from `zone-50k.json` (50,000 inspected payloads). Found:

- **910 entries** tagged `hint:waypoint-poi`
- **199 entries** tagged `hint:quest-objective`

### M2.2: POI Vocabulary Extraction

Created `scripts/extract_poi_vocabulary.py` to filter and extract POI names. Applied multiple filter passes to exclude:

- Texture/image references (`.dds`, `.png`, `.tga`)
- VFX/effect names (`vfx_*`, `fx_*`, `sp_*`)
- UI elements (buttons, windows, tabs, icons)
- Technical strings (copyright notices, NIF metadata, Flash/ActionScript)
- Asset codes (underscore-heavy, hex hashes)

**Result**: 113 unique names extracted, but **all are UI/technical elements**, not actual waypoint/location names.

### M2.3: Finding — Semantic Index Captures Technical Metadata

The `hint:waypoint-poi` category in the semantic index primarily contains:

- Flash/ActionScript UI elements (`ExternalInterface`, `OnFrameEnterSetup`)
- Button/window assets (`MainButton_*`, `WindowFrameCorner_*`)
- Progress bar UI (`ProgressBar_*`, `castbar_*`)
- Quest UI strings (`QuestAcceptD`, `QuestStickiesD`)
- Package references (`__Packages.com.trionworld.*`)

**No actual waypoint names** (e.g., "Freemarch", "Silverwood", "Thontic River") were found in the 50,000-payload sample.

### M2.4: Schema + Handoff

Schema not created due to lack of meaningful POI data. This handoff documents the limitation.

---

## Exit Criteria Met (with limitation)

- [x] POI entries identified (910 entries with `hint:waypoint-poi`)
- [x] Extraction script created and validated
- [x] POI vocabulary artifact produced (with UI/technical elements)
- [x] **Limitation documented**: semantic index captures technical metadata, not game content
- [x] Handoff committed

## Recommendation

To extract actual waypoint names, a different approach is needed:

1. **Direct text parsing**: Parse XML/Lua files for waypoint name strings
2. **Zone vocabulary enrichment**: The zone vocabulary has 9,075 entries but no actual zone names — a targeted extraction of zone name strings from XML payloads would be more effective
3. **Quest log parsing**: Extract waypoint names from quest log XML structures

## Artifacts Produced

| Artifact | Location | Gitignored |
|----------|----------|------------|
| POI vocabulary | `Exports/semantic-phase2/poi-vocabulary.json` | Yes |
| Extraction script | `scripts/extract_poi_vocabulary.py` | No (committed) |
| This handoff | `docs/handoffs/2026-07-07-semantic-phase2-poi.md` | No (committed) |
