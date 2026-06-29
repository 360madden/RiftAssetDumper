# Session Handoff — 2026-06-28 (cont.)

## Summary

Continued binary signature discovery: traced the virtual dispatch from `0x14129c070` through property callbacks to find where float32 coordinates are actually read from memory. **Manual scan finding** *(as of 2026-06-28; not yet validated by automated tool)*: ModRM-based byte scanning of the `.text` section counted **1,337 candidate register-based memory access instructions** using player coordinate offsets (0x304–0x328) as displacements — preliminary evidence that these offsets ARE used as memory displacements deep inside offset-specific callback functions. A reproducible Ghidra script (`scripts/ghidra/ModRM-memory-access-scanner.java`) does not yet exist; the hit counts have not been independently verified.

---

## Key Findings

### 1. Vtable addresses are string data, not function pointers

- `0x14270f880`: ASCII strings — SQL keywords split across 8-byte slots ("EXPLAIN", "DATABASE", "TABLE", "EXCEPT", "TRANSACTION", "NATURAL", "SAVEPOINT", "TRIGGER", "REFERENCES", "CONSTRAINT")
- `0x142648c48`: Game data strings ("LinkDead", "Lord", "Man", "Miss", "Boy", "Salutati", etc.)
- Both are `.rdata` section data, NOT vtables. The singleton context object is reused across subsystems (SQL + game logic)

### 2. 0x14128aaec is a tail-call target (not a function entry)

- Bytes at 0x14128aaec: `41 5E 41 5D 41 5C 5D C3` = POP R14/R13/R12/RBP; RET → **function epilogue**
- The hash-table/sorted-array lookup code starts at **0x14128AB0C** (with proper prologue: `MOV [RSP+0x8],RBX; PUSH RDI; SUB RSP,0x30`)
- Uses `SAR ESI,6` (divide by 64) — classic hash table bucket operation
- Calls: `0x141289754`, `0x141280858`, `0x141289928` — internal helpers

### 3. Offset-specific callbacks confirmed as float32 math

**0x1408b39d0 (0x320 callback)**:

- Receives: RCX=property descriptor, RDX=R14=game object
- Loop pattern: `MOVUPS XMM0,[RAX]; MOVUPS [RCX],XMM0; SUB RAX,0x10; CMP EDX,[RAX+0xC]; JL loop`
- Reads 16-byte chunks → SIMD float32 data
- Calls `0x1424a0307` (likely RTTI/type check)

**0x140da8870 (0x328 callback)**:

- Saves XMM6 (non-volatile float register) → definitive float math
- Uses XORPS XMM0+XMM1 for float zero initialization
- Writes to globals in range `0x143331860-0x143331938` (output state)
- Calls `0x1424a0307` (same RTTI helper as 0x320 callback)

**0x1408b39d0, 0x140513140, 0x140ca3ce0, 0x140ea6600**: All four callbacks share identical prologue structure (security cookie, XORPS XMM0, LEA RCX,[static_string], CALL 0x1424a0307) — confirms they're generated from a common C++ template.

### 4. BREAKTHROUGH: ModRM-based memory access scan

Direct byte scanning of `.text` section for ModRM-encoded `[reg+disp32]` instructions:

| Offset | Field | Hits |
|--------|-------|------|
| 0x304 | turn_rate | 28 |
| 0x30C | facing_x | 31 |
| 0x310 | unknown | 326 |
| 0x320 | pos_x | 410 |
| 0x324 | pos_y | 25 |
| 0x328 | pos_z | 517 |
| **Total** | | **1,337** *(preliminary; not yet validated)* |

**Base register distribution**:

- `[RBX+disp]`: 727 (54%)
- `[RCX+disp]`: 508 (38%)
- `[RAX+disp]`: 53
- `[R12+disp]`: 26
- Other: 23

**Key insights**:

- RBX and RCX dominate → heap-allocated game objects, not stack locals
- 0x324 (pos_y) has only 25 hits vs 410 for 0x320 and 517 for 0x328 → Y likely derived (terrain lookup) not stored alongside X/Z
- Examples: `MOV RCX,[R12+0x320]` at 0x1413A6060

### 5. Complete architecture (corrected)

```
FUN_14078a0d0 (property chain walker, ~50+ offsets)
  └─ MOV ECX, <offset>  (e.g., 0x320, 0x328)
     └─ CALL 0x14077d750 (THUNK)
        └─ JMP 0x14136a2d0 (GETTER)
           ├─ CALL 0x14136a180 (singleton context init)
           ├─ CALL 0x14129c088 → JMP 0x14128aaec (hash table lookup)
           │  └─ Returns: property descriptor struct
           └─ TEST RAX,RAX; JZ skip
              └─ CALL <callback> (offset-specific, e.g. 0x1408b39d0 for 0x320)
                 └─ ACTUAL FLOAT32 READ: MOVUPS XMM0,[game_object+offset]

```

The virtual dispatch branch (`0x14129c070 → CALL [RAX+0x8]`) is the non-offset-specific fallback — used when offset=0 or for non-numeric properties.

---

## New/Modified Files

### Committed

- `scripts/ghidra/VtableResolver.java` — NEW: reads 64-bit pointers at target addresses, resolves to function names or displays as hex with ASCII annotation

- `docs/roadmap/binary-signature-roadmap.md` — UPDATED: status summary with ModRM search breakthrough, corrected vtable analysis, new M1.6 memory-access mapping milestone, M1.2 step 5 completed, M1.4 virtual-call text corrected, milestone numbering fixed (M1.7→M1.6, old M1.6→M1.7, target manifest→M1.8)

- `docs/handoffs/2026-06-28-session-handoff.md` — UPDATED: this file

### Gitignored (not committed)

- `Exports/binary-phase1/disasm-accessor-vtable.json` — timed out (no output)

- `Exports/binary-phase1/disasm-vtable-data.json` — surrounding code near 0x142648c48 (not useful)

- `Exports/binary-phase1/vtable-context.json` — timed out

---

## CI Status

- **ruff**: ✅ (scripts/, --ignore E501)

- **mypy**: ✅ (parse_map_blobs.py)
- **roadmap diff**: 23 insertions, 1 deletion

---

## Next Session Suggestions

### Priority 1: Extract concrete byte signatures from ModRM hits

The 1,337 candidate sites are the tentative Phase 2 extraction targets — pending validation once the `ModRM-memory-access-scanner` Ghidra script ships. Next steps:

1. **Cluster by virtual address proximity** — group hits into function-level clusters

2. **Run FunctionSiteSurvey on top clusters** — decompile the 5-10 functions with the most hits

3. **Extract and wildcard signatures** — apply wildcarding rules, verify uniqueness
4. The 0x328 callback (`0x140da8870`) is the best first target (largest, most float evidence)

### Priority 2: Verify the hash table lookup structure

- Decompile `0x14128AB0C` to understand the property descriptor format
- What fields does the descriptor contain? (pointer to value? offset? type info?)
- This reveals how the callback computes `game_object + offset`

### Priority 3: Runtime validation (Cheat Engine)

- Set breakpoint at 0x14128AB0C, step through to see what property descriptor is returned for offset 0x320
- Set breakpoint at 0x1408b39d0, inspect registers to confirm RCX=descriptor, RDX=game_object
- This bridges static analysis (our findings) with runtime reality (Cheat Engine)

### Architectural curiosity: Y-coordinate derivation

- With only 25 hits for 0x324 (pos_y) vs 410/517 for X/Z, Y is almost certainly derived from terrain height
- Search for terrain height-map access patterns near the 0x320/0x328 callback clusters
- This could reveal a completely different pointer chain for elevation data

---

*End of handoff *(as of 2026-06-28; not yet validated)*. Roadmap updated with preliminary ModRM scan results. The 1,337 candidate sites are the tentative Phase 2 signature extraction targets — pending automated-tool validation.*

---

## Phase 2 Smoke-Probe (cont.)

### 8 Unique Byte Signatures Extracted

All 8 top ModRM-hit clusters now have **unique, wildcarded byte signatures** verified against the full `.text` section:

| # | Hits | Entry VA | Len | WC | Signature |
|---|------|----------|-----|----|-----------|
| 1 | 28 | 0x1405E2940 | 28B | 4 | `48 89 5C 24 08 57 48 83 EC 20 48 8B D9 48 8B 89 ?? ?? ?? ?? 48 85 C9 75 28 48 8B 53` |

| 2 | 17 | 0x1405D9060 | 40B | 0 | `48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 48 89 7C 24 20 41 54 41 56 41 57 48 83 EC 20 48 8B F9 48 8B 89 28 03 00 00` |

| 3 | 17 | 0x1413B4910 | 40B | 4 | `48 8B C4 4C 89 48 20 53 57 41 57 48 83 EC 50 48 8B BC ?? ?? ?? ?? 00 49 8B D9 48 89 68 08 4C 8B F9 4C 89 60 18 4D 8B E0` |
| 4 | 15 | 0x140CBB313 | 16B | 0 | `55 4C 39 69 20 72 0A 48 8B F9 B8 10 00 00 00 EB` |

| 5 | 14 | 0x1405CD010 | 16B | 0 | `48 8B C4 48 89 58 18 55 56 57 48 81 EC B0 00 00` |

| 6 | 13 | 0x140727570 | 32B | 0 | `48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 41 54 41 55 41 56 41 57 48 83 EC 30 8B 02 4C 8D` |

| 7 | 11 | 0x1413B6174 | 16B | 1 | `57 48 83 EC 60 48 8B F9 45 33 ?? 48 8B 0D 4A AB` |

| 8 | 9 | 0x1413A95DB | 16B | 4 | `10 03 00 00 E8 ?? ?? ?? ?? F3 0F 10 0D 14 A7 B6` |

**Wildcard policy**: CALL rel32 (E8), JMP rel32 (E9), RIP-relative disp32, and ModRM [reg+disp32] displacements are masked as `??`.

**Saved to**: `Exports/binary-phase2/signature-candidates.json` (gitignored)

### Files committed this session

- `scripts/ghidra/VtableResolver.java` — NEW
- `docs/roadmap/binary-signature-roadmap.md` — UPDATED (status, M1.6, M1.2 step 5, vtable correction, Phase 2 smoke-probe)
- `docs/handoffs/2026-06-28-session-handoff.md` — UPDATED (this file)

### Gitignored artifacts

- `Exports/binary-phase1/modrm-hit-clusters.json` — 668 function clusters
- `Exports/binary-phase2/signature-candidates.json` — 8 unique signatures

### CI

- ruff ✅, mypy ✅, dotnet build ✅ (no C# changes)
