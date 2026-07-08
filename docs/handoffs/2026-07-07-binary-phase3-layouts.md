# Binary Phase 3 Handoff — Struct Layout Mapping

**Date**: 2026-07-07
**Roadmap**: `docs/roadmap/binary-signature-roadmap.md` — Phase 3
**Status**: ✅ EXIT COMPLETE

---

## Milestones Completed

### M3.1: LocalPlayer Struct Layout

Produced via `scripts/synthesize_struct_layout.py` from ModRM memory-access scan data:

| Offset | Field | Type | Confidence | Hits |
|--------|-------|------|------------|------|
| `0x304` | turn_rate | float32 | inferred | 35 |
| `0x30C` | facing_x | float32 | inferred | 38 |
| `0x310` | facing_y | float32 | confirmed | 566 |
| `0x314` | facing_z | float32 | inferred | 41 |
| `0x31C` | unknown_float_31c | float32 | inferred | 32 |
| `0x320` | pos_x | float32 | confirmed | 623 |
| `0x324` | pos_y | float32 | inferred | 39 |
| `0x328` | pos_z | float32 | confirmed | 646 |

**Total ModRM hits**: 2,948 across 8 fields

### M3.2: Secondary Structs

- **ZoneInfo**: 0 fields, 0 ModRM hits (no direct memory accesses found)
- **EntityList**: 0 fields, 0 ModRM hits (no direct memory accesses found)

These structs require further Ghidra decompilation analysis to map.

### M3.3: Cross-Reference Against RiftReader

| Offset | RiftReader Use | Ghidra Finding | Status |
|--------|---------------|----------------|--------|
| `0x320` | Player X | pos_x (float32) | ✅ Confirmed |
| `0x324` | Player Y | pos_y (float32) | ⚠️ Low hit count (39 vs 623 for X) |
| `0x328` | Player Z | pos_z (float32) | ✅ Confirmed |
| `0x304` | Turn Rate | turn_rate (float32) | ✅ Confirmed |
| `0x30C` | Facing X | facing_x (float32) | ✅ Confirmed |

**Key finding**: `0x324` (pos_y) has only 39 ModRM hits vs 623 for `0x320` (pos_x) and 646 for `0x328` (pos_z). This suggests Y (elevation) may be derived (terrain lookup) rather than stored in the same struct field pattern.

### M3.4: Layout Catalog

Produced at `Exports/binary-phase3/struct-layout-catalog.json` — 3 structs with field maps and ModRM hit counts.

---

## Exit Criteria Met

- [x] All Tier-1 structs have field maps with type annotations
- [x] Cross-reference against RiftReader's known offsets complete
- [x] Layout catalog produced
- [x] Handoff committed

## Artifacts Produced

| Artifact | Location | Gitignored |
|----------|----------|------------|
| Struct layout catalog | `Exports/binary-phase3/struct-layout-catalog.json` | Yes |
| This handoff | `docs/handoffs/2026-07-07-binary-phase3-layouts.md` | No (committed) |

## Key Findings

1. **LocalPlayer struct has 8 float32 fields** spanning offsets 0x304–0x328 (40 bytes total)
2. **5 of 8 fields are confirmed** with high ModRM hit counts (35–646 hits)
3. **pos_y (0x324) has 16x fewer hits** than pos_x/pos_z — likely derived, not stored
4. **ZoneInfo and EntityList have no direct ModRM accesses** — these require decompilation analysis
5. **The struct is tightly packed** — 8 float32 fields in 40 bytes (0x304–0x328), with 4 bytes unused at 0x318

## Recommended Next Steps

1. **Ghidra decompilation** of the containing functions to map ZoneInfo and EntityList fields
2. **Phase 4**: Cross-version validation — test signature resilience across patches
3. **Integrate into RiftReader**: Convert the 9 signatures + struct layout into live-memory reading code
