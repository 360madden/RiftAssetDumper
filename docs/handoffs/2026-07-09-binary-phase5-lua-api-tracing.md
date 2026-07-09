# Handoff: Binary Signature NEW Phase 5 — Lua API Object-Discovery Tracing

**Date**: 2026-07-09
**Lane**: Binary Signature (Pivoted)
**Phase**: 5 (Lua API Object-Discovery Tracing)
**Status**: ✅ COMPLETE

---

## Summary

Phase 5 traced the C implementation of `Inspect.Unit.Detail` to find how the game locates player objects at runtime. The game uses a table-driven Lua API registration system with string constants in .rdata, pointer tables in .data, and handler functions that process field lookups.

## Artifacts Produced

| Artifact | Path | Size |
|----------|------|------|
| Lua API Trace | `Exports/binary-phase5/lua-api-trace.json` | 9,827 bytes |

## Key Findings

| Component | Address | Description |
|-----------|---------|-------------|
| String | `0x1426772D8` | `"Inspect.Unit.Detail"` in .rdata |
| Pointer Table | `0x142EECD08` | .data entry pointing to the string |
| Registration Func | `0x1409A7F60` | Loads table entries, sets up API methods |
| Handler Func | `0x140989570` | Processes field lookups including `player` |
| Player String | `0x14266F21C` | `"player"` field name, 15 code references |

## Architecture Discovered

The game uses a **table-driven Lua API registration system**:

1. **String constants** in `.rdata` — 92 `Inspect.*` strings confirmed
2. **Pointer table** in `.data` — QWORD array mapping method names to handlers and field lists
3. **Table structure**: `MethodName → Category → Collection → Handler → DetailsHandler → FieldNames...`
4. **Registration function** (`0x1409A7F60`) reads this table and calls Lua C API registration functions
5. **Handler function** (`0x140989570`) processes individual field lookups — contains 5 references to the `"player"` string

## Unit Detail Fields (from pointer table)

`id, name, nameSecondary, guild, titlePrefixName, titleSuffixName, titlePrefixId, titleSuffixId, player, relation, level, warfront, offline, afk, ready, health, healthMax, healthCap, calling, mana, manaMax, charge, chargeMax, energy, energyMax, combo, power, loot, pvp, guaranteedLoot, mark, vitality, planar, planarMax`

## Next Steps

1. **Ghidra decompile** `0x140989570` to see how `player` field is read from the game object
2. **Trace unit object pointer chain** from Lua stack to game object struct
3. **Identify hash table/lookup mechanism** for field name resolution
4. **Map complete unit object structure** including the `player` flag offset

## Next Phase

**Phase 6: Unit Registry Mapping**

- Map the data structure that stores unit objects (including the player)
- Identify player entry identification method
- Extract registry accessor signature
- Map field offsets within unit objects

---

*This handoff is the single source of truth for Phase 5 completion.*
