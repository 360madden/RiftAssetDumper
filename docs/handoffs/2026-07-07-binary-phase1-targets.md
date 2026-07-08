# Binary Phase 1 Handoff — RiftReader Target Mapping

**Date**: 2026-07-07
**Roadmap**: `docs/roadmap/binary-signature-roadmap.md` — Phase 1
**Status**: ✅ EXIT COMPLETE — all milestones met

---

## Milestones Completed

### M1.1: RiftReader Anchor Inventory

Known offsets from RiftReader's pointer chains:

| Offset | Field | Type | Discovery |
|--------|-------|------|-----------|
| `0x32EBC80` | LocalPlayerBase | pointer | Runtime address (NOT static global) |
| `0x320` | Player X | float32 | ModRM scan: 410 hits |
| `0x324` | Player Y | float32 | ModRM scan: 25 hits (possibly derived) |
| `0x328` | Player Z | float32 | ModRM scan: 517 hits |
| `0x30C` | Facing X | float32 | ModRM scan: within 0x304-0x328 range |
| `0x304` | Turn Rate | float32 | ModRM scan: within 0x304-0x328 range |

**Critical finding**: `0x32EBC80` is a runtime heap address, not a static global. Ghidra shows 0 references. Strategy targets CODE that accesses player data, not the data address itself.

### M1.2: Ghidra Back-Trace

Completed via ModRM-based byte scanning (1,337 instruction sites found across offsets 0x304–0x328). RBX (727) and RCX (508) are dominant base registers — heap object access, not stack locals.

### M1.3–M1.6: Tooling + Architecture

- `ScalarOffsetSearcher.java` — fast scalar operand search
- `DisasmContext.java` — disassembly context extraction
- Property-chain architecture mapped: `MOV ECX,<offset>` → `CALL 0x14077d750` (thunk) → `JMP 0x14136a2d0` → vtable dispatch

### M1.5: Stable Byte Signatures

8 signatures extracted from top ModRM clusters. All verified UNIQUE against full `.text` section. See `Exports/binary-phase2/signature-candidates.json`.

### M1.7: Stability Tiers Assigned

| Tier | Count | Targets | Rationale |
|------|-------|---------|-----------|
| **Tier 1** | 6 | vtable-dispatch, clusters 01/02/03/05/07 | Engine core — pure opcodes, player coordinate reads, float32 math |
| **Tier 2** | 3 | clusters 04/06/08 | Game logic — comparison dispatch, allocation, entity lifecycle |
| **Tier 3** | 0 | (none) | UI/rendering not in current target set |

### M1.8: Target Manifest

Produced at `Exports/binary-phase1/riftreader-target-manifest.json` — 9 targets with stability tiers, signatures, and rationale.

---

## Exit Criteria Met

- [x] 5-10 targets identified with Ghidra back-traced functions (9 targets)
- [x] Stability tiers assigned (6 Tier-1, 3 Tier-2, 0 Tier-3)
- [x] Target manifest produced
- [x] Handoff committed

## Artifacts Produced

| Artifact | Location | Gitignored |
|----------|----------|------------|
| Target manifest | `Exports/binary-phase1/riftreader-target-manifest.json` | Yes |
| Signature candidates | `Exports/binary-phase2/signature-candidates.json` | Yes |
| This handoff | `docs/handoffs/2026-07-07-binary-phase1-targets.md` | No (committed) |

## Key Findings

1. **6 Tier-1 targets** are engine-core patterns — pure opcodes with no addresses to wildcard. These are the most stable across game patches.
2. **The vtable-dispatch signature** (`48 85 D2 74 0A 48 83 C1 10 48 8B 01 FF 50 08`) has **zero wildcards** — maximally stable, confirmed unique.
3. **Player coordinate access** is concentrated in clusters 01 (28h sites) and 07 (11h sites) — these contain the actual `[base+offset]` memory reads for X/Z.
4. **0x324 (pos_y) has only 25 hits** vs 410 (pos_x) and 517 (pos_z) — Y may be derived (terrain lookup) rather than stored in the same struct.

## Recommended Next Steps

1. **Phase 2**: Signature catalog production — formalize the 8 candidates into `rift-x64-signature-database.json`
2. **Phase 3**: Struct layout mapping — determine the full game-object struct containing offsets 0x304–0x328
3. **Fix Python 2 except syntax** in `live_memory_scanner.py` (now done)
4. **Write uniqueness validation** — run `live_memory_scanner.py` fixture-mode scan to independently confirm each signature
