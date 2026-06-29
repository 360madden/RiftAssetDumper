# Semantic Discovery Roadmap — Ground-Truth Asset Data for Live-Memory Validation

**Created**: 2026-06-28
**Repo**: `RiftAssetDumper` (Assets repo only — no cross-repo edits)
**Status** *(as of 2026-06-28; not yet validated)*: Phase 0 self-reported pending; lane work not started. No external verification performed.

## Purpose

The original `project-roadmap.md` ran 53 phases of NIF geometry discovery to completion — all gates cleared, all leads exhausted, 3 proven mesh families exported. That pipeline is **done**.

This roadmap is the **sequel** — shifting the repo's mission from "decode mesh geometry" to **"mine the live archive for semantic ground-truth data"**. The output is compact JSON artifacts that downstream repos can consume to validate live-memory observations.

**Foundation document**: `docs/asset-guided-runtime-reacquisition-strategy.md` defines the 5 priority lanes. This roadmap implements them, one phase per lane, from highest to lowest priority.

## What Changed Since the Last Roadmap

| Aspect | Old roadmap (Phase 1-53) | New roadmap |
|--------|--------------------------|-------------|
| Primary input | Deleted `Source/` copied set (NIF-focused) | Live archive path (`C:/Program Files (x86)/Glyph/Games/RIFT/Live`) |
| Primary output | OBJ geometry, mesh manifests, texture maps | Compact semantic vocabularies, zone/POI/actor reference packets |
| Target consumer | RiftFlythrough (3D viewer) | RiftReader (live-memory reader + navigation) |
| Asset scope | NIF meshes only (~5,500 blocks, 227 IDs) | All 263,957 archive entries — XML, text, Lua, binary, audio |
| Tooling | C# NIF parser, mesh probe, OBJ export | C# `build-asset-semantic-index`, `inventory-asset-signatures` |
| Safety model | 9 proof guards, 7 promotion gates | Heuristic hints only (`hint:*`), parser-backed where proven |

## Operating Conventions

1. **Read-only, this repo only.** No cross-repo edits. Output goes to `Exports/` (gitignored).
2. **One lane at a time.** Priority 1 completes before Priority 2 begins.
3. **Smoke first, then full.** Every phase starts with a bounded smoke run (`--max-total 500`) before scaling to full archive.
4. **Heuristic hints are leads, not truth.** `hint:*` categories are search aids. Parser-backed classifiers come later.
5. **Compact artifacts.** Output packets are schematized JSON designed for consumer-side import, not raw dumps.
6. **Aggressive Evidence Workflow** still applies: probe → smoke → full inventory → ranked evidence → documented truth → commit → next lead.

---

## Phase 0: Infrastructure Readiness & Live-Archive Baseline

**Objective**: Verify the semantic indexing pipeline works against the live archive path (no more `Source/`), fix any bit rot, and establish a baseline of what's in the archive.

**Entry Criteria**:

- All 9 proof guards pass
- 593/593 Python tests pass, 56/56 dotnet tests pass
- `build-asset-semantic-index` command exists in `Program.cs` and compiles

**Key Milestones**:

1. **M0.1**: Verify `build-asset-semantic-index` works against live archive
   - Run smoke: `--root "C:/Program Files (x86)/Glyph/Games/RIFT/Live" --max-total 100 --out Exports/semantic-phase0/smoke-semantic.json`
   - Confirm JSON output is valid and non-empty
   - Fix any path/API issues from `Source/` → live-archive migration

2. **M0.2**: Run full `inventory-asset-signatures` against live archive
   - `--root <live> --max-total 0` (all entries) or bounded by type
   - Produce `Exports/semantic-phase0/live-signature-inventory.json`
   - Answer: what types exist? how many XML/text/Lua/binary entries?

3. **M0.3**: Establish type distribution baseline
   - Count entries by detected type (xml, txt, lua, bin, nif, dds, riff, etc.)
   - Identify the largest type families — these dictate Phase 1-5 scope
   - Document findings in `docs/handoffs/2026-06-28-phase0-baseline.md`

4. **M0.4**: Schema audit
   - Verify `docs/schemas/asset-semantic-index-v1.schema.json` is current
   - Check `docs/schemas/asset-signature-inventory-v1.schema.json` if it exists
   - Ensure `Exports/semantic-phase0/` directory exists and is gitignored

**Exit Criteria**:

- `build-asset-semantic-index` runs successfully against live archive
- Type distribution known (counts per detected type)
- At least one smoke JSON artifact produced and schema-valid
- Handoff committed with baseline findings

**Required Artifacts**:

- `Exports/semantic-phase0/smoke-semantic.json` (smoke run, gitignored)
- `Exports/semantic-phase0/live-signature-inventory.json` (gitignored)
- `docs/handoffs/2026-06-28-phase0-baseline.md` (committed)

**Focus & Anti-Drift Rules**:

- Do NOT start lane work (Phase 1+) until Phase 0 exits
- Do NOT modify C# parse logic unless fixing a crash
- All output under `Exports/semantic-phase0/`

---

## Phase 1: Priority Lane 1 — Zone/Map Coordinate Systems & Bounds

**Objective**: Extract zone names, map identifiers, coordinate boundary data, and world/terrain references from XML and text payloads. This is the highest-value lane — it gives downstream consumers ground truth to validate navigation coordinates.

**Priority lane reference**: `docs/asset-guided-runtime-reacquisition-strategy.md` Priority 1

**Entry Criteria**:

- Phase 0 exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- Known XML/text entry counts from baseline
- `--semantic-category hint:map-zone` filter confirmed working

**Key Milestones**:

1. **M1.1**: Smoke zone-targeted semantic index
   - `build-asset-semantic-index --root <live> --type xml --semantic-category hint:map-zone --max-total 500 --out Exports/semantic-phase1/smoke-zone-xml.json`
   - Review: what zone names appear? what tag families? any coordinate-like numeric tables?

2. **M1.2**: Full XML map-zone scan
   - Remove `--max-total` limit, target all XML entries with map-zone hints
   - Output: `Exports/semantic-phase1/zone-xml-full.json`
   - Extract: zone name strings, tag family counts, structured table signatures

3. **M1.3**: Text/binary map-zone scan
   - Same as M1.2 but for `--type txt` and `--type bin` with map-zone hints
   - Output: `Exports/semantic-phase1/zone-txt-full.json`, `Exports/semantic-phase1/zone-bin-full.json`

4. **M1.4**: Zone vocabulary synthesis
   - Python script: deduplicate zone names across XML/text/binary sources
   - Cluster entries by shared zone name patterns
   - Identify coordinate-like numeric structures (bounding boxes, sector grids, etc.)
   - Output: `Exports/semantic-phase1/zone-vocabulary.json` — a compact artifact:

     ```json
     {
       "schema": "zone-vocabulary-v1",
       "zones": [
         {
           "name": "Freemarch",
           "source_hints": ["hint:map-zone"],
           "asset_count": 42,
           "candidate_tag_families": ["MapZone", "ZoneDef"],
           "coordinate_candidates": []
         }
       ]
     }

     ```

5. **M1.5**: Schema + guard
   - Write `docs/schemas/zone-vocabulary-v1.schema.json`
   - Add lightweight Python validation check
   - Commit schema + handoff

**Exit Criteria**:

- Zone names extracted and deduplicated
- Zone vocabulary artifact produced (`Exports/semantic-phase1/zone-vocabulary.json`)
- Schema defined and artifact validates against it
- Handoff committed

**Required Artifacts**:

- `Exports/semantic-phase1/zone-vocabulary.json` (gitignored)
- `docs/schemas/zone-vocabulary-v1.schema.json` (committed)
- `docs/handoffs/2026-06-28-phase1-zone-vocabulary.md` (committed)

**Focus & Anti-Drift Rules**:

- Only map/zone/terrain/world/bounds hints — do NOT chase actor or waypoint hints yet
- Heuristic extraction only — zone names are string leads, not parser-proven schemas
- No cross-repo packaging — just produce the artifact in `Exports/`

---

## Phase 2: Priority Lane 2 — Waypoints, Objectives & POIs

**Objective**: Extract named waypoints, quest objectives, points of interest, and journal/task strings. These become navigation targets for route-running systems.

**Priority lane reference**: `docs/asset-guided-runtime-reacquisition-strategy.md` Priority 2

**Entry Criteria**:

- Phase 1 exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- Waypoint/POI hint filter confirmed: `--semantic-category hint:waypoint-poi`

**Key Milestones**:

1. **M2.1**: Smoke POI semantic index
   - XML + text payloads filtered to `hint:waypoint-poi`
   - Identify naming patterns: waypoint names, objective descriptions, journal entries

2. **M2.2**: Full POI scan (XML, text, binary)
   - Unbounded scan across all matching types
   - Extract named locations, quest/objective strings

3. **M2.3**: POI vocabulary synthesis
   - Deduplicate and cluster by name patterns
   - Link POI names back to zone names from Phase 1 where possible
   - Output: `Exports/semantic-phase2/poi-vocabulary.json`

4. **M2.4**: Schema + handoff
   - `docs/schemas/poi-vocabulary-v1.schema.json`
   - Validation check
   - Commit

**Exit Criteria**:

- POI names extracted and deduplicated
- POI vocabulary artifact produced
- Schema defined; handoff committed

**Required Artifacts**:

- `Exports/semantic-phase2/poi-vocabulary.json` (gitignored)
- `docs/schemas/poi-vocabulary-v1.schema.json` (committed)
- `docs/handoffs/2026-06-28-phase2-poi-vocabulary.md` (committed)

---

## Phase 3: Priority Lane 3 — Actor/Model/Object ID References

**Objective**: Leverage existing NIF model ID data and texture reference graphs to build an actor-object vocabulary. Link model hashes to named actor/creature/NPC/object references found in text payloads.

**Priority lane reference**: `docs/asset-guided-runtime-reacquisition-strategy.md` Priority 3

**Entry Criteria**:

- Phase 2 exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- Existing NIF model data (`flythrough-index.json`, `link-nif-textures` output) available
- Semantic surface (`hint:actor-object`) already classified 212 assets

**Key Milestones**:

1. **M3.1**: Extract actor/creature/NPC string hints
   - `build-asset-semantic-index --semantic-category hint:actor-object` across text/XML
   - Cross-reference string hits with NIF model IDs where possible

2. **M3.2**: Model-to-name linkage
   - Match NIF hashes from texture linkage against actor string hints
   - Produce: which NIF models are creatures, NPCs, objects, etc.

3. **M3.3**: Actor vocabulary synthesis
   - Deduplicate actor names
   - Link to model IDs and texture references
   - Output: `Exports/semantic-phase3/actor-vocabulary.json`

4. **M3.4**: Schema + handoff
   - `docs/schemas/actor-vocabulary-v1.schema.json`
   - Commit

**Exit Criteria**:

- Actor-object vocabulary synthesized from NIF + text data
- Schema defined; handoff committed

---

## Phase 4: Priority Lane 4 — UI/Lua/XML Payload String Catalogs

**Objective**: Extract UI framework strings, Lua script references, addon/interface names, and XML tag/attribute families. These reveal client-side naming conventions without live memory writes.

**Priority lane reference**: `docs/asset-guided-runtime-reacquisition-strategy.md` Priority 4

**Entry Criteria**:

- Phase 3 exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- Lua and XML payload counts known from Phase 0 baseline

**Key Milestones**:

1. **M4.1**: XML tag/attribute family catalog
   - Scan all XML payloads (no semantic filter, or `hint:*`)
   - Extract unique tag names and attribute name families
   - Identify recurring structures (forms, panels, frames, layouts)

2. **M4.2**: Lua string catalog
   - Scan `.lua` detected payloads for addon names, function references, UI frame IDs
   - Extract naming conventions: event handlers, slash commands, saved variable names

3. **M4.3**: UI vocabulary synthesis
   - Merge XML + Lua findings
   - Output: `Exports/semantic-phase4/ui-vocabulary.json`

4. **M4.4**: Schema + handoff
   - `docs/schemas/ui-vocabulary-v1.schema.json`
   - Commit

**Exit Criteria**:

- UI/Lua/XML naming conventions cataloged
- UI vocabulary artifact produced
- Schema defined; handoff committed

---

## Phase 5: Priority Lane 5 — Audio/VFX Side References

**Objective**: Catalog RIFF/OGG audio assets and VFX/model path references. Secondary labels for world objects, encounters, and actor families.

**Priority lane reference**: `docs/asset-guided-runtime-reacquisition-strategy.md` Priority 5

**Entry Criteria**:

- Phase 4 exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- Audio asset counts known from Phase 0 baseline

**Key Milestones**:

1. **M5.1**: Audio asset inventory
   - `inventory-asset-signatures --type riff` and `--type ogg` against live archive
   - Count, size distribution, path reference patterns

2. **M5.2**: Audio-to-zone/actor cross-reference
   - Match audio path strings against zone names from Phase 1 and actor names from Phase 3
   - Identify music vs. SFX vs. ambient categories

3. **M5.3**: Audio vocabulary synthesis
   - Output: `Exports/semantic-phase5/audio-vocabulary.json`

4. **M5.4**: Schema + handoff
   - `docs/schemas/audio-vocabulary-v1.schema.json`
   - Commit

**Exit Criteria**:

- Audio asset catalog produced
- Cross-references to zones/actors where possible
- Schema defined; handoff committed

---

## Phase 6: Cross-Repo Artifact Packaging & Documentation

**Objective**: Finalize all vocabulary schemas, produce a unified cross-repo artifact index, and document the consumer-side import contract so downstream repos can integrate without ambiguity.

**Entry Criteria**:

- All 5 priority lane phases (1-5) exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- 5 vocabulary artifacts produced (zone, POI, actor, UI, audio)

**Key Milestones**:

1. **M6.1**: Unified vocabulary index
   - Single JSON artifact listing all 5 vocabularies with paths, schemas, and row counts
   - Output: `Exports/semantic-phase6/vocabulary-index.json`

2. **M6.2**: Consumer contract documentation
   - Write `docs/semantic-vocabulary-consumer-contract.md`
   - Document: schema locations, field meanings, `hint:*` vs parser-backed distinctions, stability guarantees
   - No cross-repo edits — this is documentation only

3. **M6.3**: Final schema validation sweep
   - Validate all 5 vocabulary artifacts against their schemas
   - Run `ruff`, `mypy`, `dotnet build`, full pytest suite
   - Commit handoff

4. **M6.4**: Update `current-phase.md` and `knowledge.md`
   - Mark semantic discovery roadmap as active
   - Update project state with lane completion stats

**Exit Criteria**:

- All 5 vocabulary artifacts schema-valid
- Consumer contract documented
- CI green (ruff, mypy, dotnet build, pytest, markdownlint)
- `current-phase.md` updated

**Required Artifacts**:

- `Exports/semantic-phase6/vocabulary-index.json` (gitignored)
- `docs/semantic-vocabulary-consumer-contract.md` (committed)
- `docs/handoffs/2026-06-28-phase6-packaging.md` (committed)

---

## Roadmap Summary

| Phase | Lane | Priority | Key Artifact |
|-------|------|:--------:|--------------|
| 0 | Infrastructure readiness | — | Live-archive baseline, smoke validation |
| 1 | Zone/map coordinate systems | **1** | `zone-vocabulary.json` |
| 2 | Waypoints/objectives/POIs | **2** | `poi-vocabulary.json` |
| 3 | Actor/model/object IDs | **3** | `actor-vocabulary.json` |
| 4 | UI/Lua/XML payloads | **4** | `ui-vocabulary.json` |
| 5 | Audio/VFX references | **5** | `audio-vocabulary.json` |
| 6 | Cross-repo packaging | — | `vocabulary-index.json` + consumer docs |

## Anti-Drift Rules (All Phases)

1. **This repo only.** No cross-repo edits, no touching RiftReader/RiftScan/RiftFlythrough.
2. **Output to `Exports/` only.** All generated artifacts are gitignored. Only schemas and docs are committed.
3. **Heuristic hints are leads.** `hint:*` categories must not be promoted as parser-backed truth without proof gates.
4. **One lane at a time.** Phase 1 must exit before Phase 2 begins.
5. **Smoke before full.** Every phase starts bounded (`--max-total 500`) before unbounded.
6. **No new C# parse logic** unless fixing a crash or adding a narrow, tested output field.
7. **CI stays green.** No regression on existing 593 Python + 56 dotnet tests.

---

*This roadmap is the single source of truth for the semantic discovery phase of the Assets repo. All work must be traceable to a specific phase and milestone above.*
