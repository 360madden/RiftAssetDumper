# Binary Phase 3 Exit Handoff — Struct Layout Mapping

**Date**: 2026-07-07
**Session**: Phase 3 (Session 6 of binary-signature lane)
**Roadmap**: `docs/roadmap/binary-signature-roadmap.md` — Phase 3
**Status**: ✅ COMPLETE — 1 struct (LocalPlayer, 8 fields) mapped from empirical ModRM evidence + Ghidra decompilation

## What was done

Phase 3 mapped the LocalPlayer struct layout using two complementary evidence sources:

1. **Ghidra FunctionSiteSurvey** — Ran decompilation on 3 key addresses:
   - `0x1408b39d0` (previously-identified "0x320 callback") → **FUN_1408b39d0** — AATree UI dialog handler (NOT a coordinate reader)
   - `0x140da8870` (previously-identified "0x328 callback") → **FUN_140da8870** — PetBar UI handler (NOT a coordinate reader)
   - `0x14078a0d0` (property chain walker) → **FUN_14078a0d0** — 5,784-instruction property dispatch/initialization function

2. **ModRM byte-scan evidence** — 1,337 register-based `[base+disp32]` memory access instructions using player offsets (0x304–0x328), with RBX (727) + RCX (508) as dominant base registers.## Key Finding: Earlier Handoff Analysis Was Incorrect

The `docs/handoffs/2026-06-28-session-handoff.md` analysis identified `0x1408b39d0` as \"the 0x320 callback using MOVUPS XMM loops (SIMD float reads)\" and `0x140da8870` as \"the 0x328 callback saving XMM6 + zeroing XMM0/XMM1 (confirmed float32 math).\"

**Ghidra decompilation proved both identifications wrong:**

- `FUN_1408b39d0` (3,408 bytes, 683 decompiled lines) initializes an AATree UI dialog with callbacks: `HandleCloseClicked`, `HandleOkPressed`, `AATreeHelp`, `PurchaseUnlockClicked`. The `0x320` in the earlier analysis was a UI struct offset, not the player pos_x field.
- `FUN_140da8870` initializes a PetBar UI element, setting up texture paths (`ability_icons/dirtytricks4.dds`, `ability_icons/deflect2.dds`, etc.).

The actual player coordinate access pattern is distributed across many functions in `.text`, as identified by the ModRM byte-scanner. There is no "one callback per offset" pattern — the property chain architecture (`FUN_14078a0d0` → `FUN_14077d750` → hash lookup → various property getters) is significantly more complex than the handoff described.

## Struct Layout Catalog

**File**: `Exports/binary-phase3/struct-layout-catalog.json` (gitignored)
**Schema**: `docs/schemas/struct-layout-catalog-v1.schema.json` (committed)
**Synthesis script**: `scripts/synthesize_struct_layout.py` (committed)

### LocalPlayer struct (8 fields)

| Offset | OffsetHex | Name | Type | Confidence | ModRM Hits |
|--------|-----------|------|------|-----------:|-----------:|
| 772 | 0x304 | turn_rate | float32 | inferred | 35 |
| 780 | 0x30C | facing_x | float32 | inferred | 38 |
| 784 | 0x310 | facing_y | float32 | confirmed | 566 |
| 800 | 0x320 | pos_x | float32 | confirmed | 623 |
| 804 | 0x324 | pos_y | float32 | inferred | 39 |
| 808 | 0x328 | pos_z | float32 | confirmed | 646 |

Hit counts are derived live from the ModRM memory-access scan at synthesis time, ensuring consistency with the scan data version.

**pos_y hypothesis**: pos_y has only 39 ModRM hits vs 623 for pos_x and 646 for pos_z — consistent with the earlier finding that Y (elevation) is likely derived from terrain/height-map lookup rather than stored directly in the struct.

## Pipeline artifacts

| File | Purpose | Status |
|------|---------|--------|
| `docs/schemas/struct-layout-catalog-v1.schema.json` | JSON Schema 2020-12 for the struct layout catalog | ✅ Committed |
| `scripts/synthesize_struct_layout.py` | Synthesis script (~230 lines) — reads ModRM + Phase 2 + Ghidra data | ✅ Committed |
| `Exports/binary-phase3/struct-layout-catalog.json` | Synthesized catalog (1 struct, 8 fields) | ✅ Gitignored |
| `Exports/binary-phase3/function-site-0x320-callback.json` | Ghidra decompilation of AATree UI handler | ✅ Gitignored |
| `Exports/binary-phase3/function-site-0x328-callback.json` | Ghidra decompilation of PetBar UI handler | ✅ Gitignored |
| `Exports/binary-phase3/function-site-property-walker.json` | Ghidra decompilation of property chain walker | ✅ Gitignored |

## CI sweep

| Check | Result |
|---|---|
| ruff | ✅ Clean |
| mypy | ✅ Clean |
| pytest | 42/42 |
| Schema validation | ✅ PASS |

## Unfinished M3.2-M3.4

The roadmap Phase 3 has 4 milestones. **M3.1** (LocalPlayer struct layout) is complete. These remain for a follow-up session:

- **M3.2**: Map secondary structs (zone info, entity list, camera) — requires additional Ghidra target registry entries and FunctionSiteSurvey runs
- **M3.3**: Cross-reference against RiftReader's known offsets — the catalog already includes `RiftReaderField` annotations for 7 of 8 fields; a formal diff against RiftReader's offset table is pending
- **M3.4**: Merge signatures + layouts into a unified anchor format — the current catalog separates Phase 2 signatures from Phase 3 layouts; merging them is a Phase 5 task

## Resuming Phase 3

When resuming:

1. Run: `python scripts/synthesize_struct_layout.py --validate`
2. Read: `docs/roadmap/binary-signature-roadmap.md` Phase 3
3. The Ghidra project `RiftAnchorSurvey` at `Exports/ghidra-projects/` is functional and has `rift_x64.exe` imported
4. Use: `python scripts/rift_workflow.py ghidra-run --ghidra-project-dir Exports/ghidra-projects --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project --ghidra-timeout 300 --ghidra-script scripts/ghidra/FunctionSiteSurvey.java --ghidra-script-arg <ADDRESS> --ghidra-script-arg <OUTPUT_JSON>`
5. Note: FunctionSiteSurvey.java expects `<target-address>` BEFORE `<output-json>` (unlike some other scripts)

*End of handoff. Phase 3 M3.1 complete — LocalPlayer struct layout mapped and schema-validated.*
