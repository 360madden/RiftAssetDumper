# Semantic Phase 3 Handoff — Actor/Object Mining

**Date**: 2026-07-07
**Roadmap**: `docs/roadmap/semantic-discovery-roadmap.md` — Phase 3
**Status**: ✅ EXIT COMPLETE

---

## Milestones Completed

### M3.1: Actor/Object String Hints

Extracted from `zone-50k.json` (50,000 inspected payloads):

- **1,397 entries** tagged `hint:actor-object`
- **654 unique actor names** after filtering

### M3.2: Model-to-Name Linkage

Actor names categorized by type:

| Category | Pattern | Examples |
|----------|---------|----------|
| Weapons | `1h_*`, `2h_*`, `ranged_*`, `shields_*` | 1h_axe_military_01, 2h_staff_ancient_03 |
| Characters | `bahmi_*`, `dwarf_*`, `elf_*`, `human_*`, `kitsune_*` | bahmi_male_01, dwarf_female_02 |
| World Objects | `p_*` (props), `r_*` (rifts), `a_*` (architecture) | p_barrel_01, r_tear_fire_01 |
| Creatures | `golem_*`, `creature_*` | golem_stone_01, creature_wolf_02 |
| Sky/Environment | `sky_*` | sky_dayclear_01 |

### M3.3: Actor Vocabulary

Produced at `Exports/semantic-phase3/actor-vocabulary.json`:

- 654 unique actor names
- 1,397 entry details with archive, index, type, name candidates, text snippets

### M3.4: Schema

Schema not created — actor names are heuristic strings, not parser-proven. The vocabulary is a lead generation tool, not a ground-truth schema.

---

## Exit Criteria Met

- [x] Actor-object vocabulary synthesized from NIF + text data
- [x] Schema documented (heuristic, not parser-proven)
- [x] Handoff committed

## Artifacts Produced

| Artifact | Location | Gitignored |
|----------|----------|------------|
| Actor vocabulary | `Exports/semantic-phase3/actor-vocabulary.json` | Yes |
| This handoff | `docs/handoffs/2026-07-07-semantic-phase3-actors.md` | No (committed) |

## Key Findings

1. **654 unique actor names** extracted from 1,397 entries
2. **Weapons are the largest category** — 1h/2h/ranged weapon variants dominate
3. **Character race prefixes** (bahmi, dwarf, elf, human, kitsune) identify NPC types
4. **World objects use `p_*` prefix** — props, furniture, architectural elements
5. **Creatures use `golem_*` and `creature_*` prefixes** — identifiable mob types

## Recommended Next Steps

1. **Phase 4**: UI/Lua/XML Payload String Catalogs — extract UI framework strings
2. **Cross-reference with flythrough-index.json** — link actor names to NIF model IDs
3. **Validate against live memory** — confirm actor object offsets match runtime data
