# Binary Phase 2 Handoff — Byte Signature Extraction

**Date**: 2026-07-07
**Roadmap**: `docs/roadmap/binary-signature-roadmap.md` — Phase 2
**Status**: ✅ EXIT COMPLETE — all milestones met

---

## Milestones Completed

### M2.1: Wildcarding Policy

**Documented** in `Exports/binary-phase2/signature-catalog.json` under `WildcardPolicy`. Rules:

| Rule | Pattern | Rationale |
|------|---------|-----------|
| CALL-rel32 | `E8 ?? ?? ?? ??` | Relative call offsets change on recompilation |
| JMP-rel32 | `E9 ?? ?? ?? ??` | Relative jump offsets change on recompilation |
| Jcc-rel32 | `0F 8? ?? ?? ?? ??` | Conditional jumps with 32-bit displacement |
| RIP-relative | `48 8B 05/0D/... ?? ?? ?? ??` | RIP-relative data references |
| ModRM-disp32 | displacement in `[reg+disp32]` | Memory operands with address displacement |
| MOV-imm32 | `B8-BF ?? ?? ?? ??` | Absolute addresses in immediates |
| LEA-RIP | `48 8D 05/0D/... ?? ?? ?? ??` | LEA with RIP-relative addressing |

**Preserved**: Opcode bytes, register encodings (ModRM reg, SIB), non-address immediates (e.g., 0x10, 0x20, 0x2B8).

### M2.2–M2.3: Signatures Extracted and Verified

9 signatures extracted from top ModRM clusters. All verified **UNIQUE** against full `.text` section (39,373,824 bytes):

| # | Anchor | Wildcards | Tier | Unique |
|---|--------|-----------|------|--------|
| 1 | vtable-dispatch | 0 | 1 | ✅ |
| 2 | cluster-01-player-access | 4 | 1 | ✅ |
| 3 | cluster-02-property-walker | 0 | 1 | ✅ |
| 4 | cluster-03-offset-dispatch | 4 | 1 | ✅ |
| 5 | cluster-04-legacy-access | 0 | 2 | ✅ |
| 6 | cluster-05-float-math | 0 | 1 | ✅ |
| 7 | cluster-06-alloc-path | 0 | 2 | ✅ |
| 8 | cluster-07-callback-chain | 8 | 1 | ✅ |
| 9 | cluster-08-entity-lookup | 8 | 2 | ✅ |

**5 of 9 signatures have zero wildcards** — maximally stable across patches.

### M2.4: Fallback Strategies

No fallbacks needed — all 9 signatures achieved uniqueness without fallback strategies.

### M2.5: Signature Catalog

Produced at `Exports/binary-phase2/signature-catalog.json` — 9 signatures with:

- `anchor_name`, `stability_tier`
- `signature_hex` (with `??` wildcards)
- `wildcard_count`, `uniqueness_verified`, `match_count`
- `containing_function` (Ghidra address)
- `description`, `usage` (how RiftReader should use each signature)
- `extracted_from_version`

---

## Exit Criteria Met

- [x] All Tier-1 and Tier-2 targets have verified-unique signatures (9/9)
- [x] Wildcarding policy documented
- [x] Signature catalog produced
- [x] Handoff committed

## Artifacts Produced

| Artifact | Location | Gitignored |
|----------|----------|------------|
| Signature catalog | `Exports/binary-phase2/signature-catalog.json` | Yes |
| Signature candidates | `Exports/binary-phase2/signature-candidates.json` | Yes |
| This handoff | `docs/handoffs/2026-07-07-binary-phase2-signatures.md` | No (committed) |

## Key Findings

1. **5/9 signatures have zero wildcards** — these are pure opcode/register patterns with no addresses. They are maximally stable across game patches.
2. **The vtable-dispatch signature** is the crown jewel: `48 85 D2 74 0A 48 83 C1 10 48 8B 01 FF 50 08` — 15 bytes, 0 wildcards, unique in the binary.
3. **Signature lengths range from 15 to 48 bytes** — short enough for fast scanning, long enough for uniqueness.
4. **All signatures target the .text section** (code), not .rdata or .data. This is intentional — code patterns are more stable than data layouts.

## Recommended Next Steps

1. **Phase 3**: Struct layout mapping — determine the full game-object struct containing offsets 0x304–0x328
2. **Integrate into RiftReader**: Convert the 9 signatures into Reloaded.Memory.Sigscan patterns for AOB scanning
3. **Patch detection**: After game updates, re-run the uniqueness check to detect signature drift
4. **Expand coverage**: Target additional functions (UI coordinates, zone ID lookups, entity list traversal)
