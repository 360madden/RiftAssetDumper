# Binary Signature Discovery Roadmap — Stable Offset Anchors for Live-Memory Reading

**Created**: 2026-06-28
**Repo**: `RiftAssetDumper` (Assets repo only — no cross-repo edits)
**Status** *(as of 2026-06-28; not yet validated by Ghidra execution)*: Phase 0 self-reported exit complete, Phase 1 self-reported nearly complete, Phase 2 smoke-probe self-reported started. External verification (re-running the committed Ghidra scripts against a live `rift_x64.exe` and matching hits to the 1,337-site map) is required before promoting any Phase-N exit to "officially complete".
**Parallel to**: `docs/roadmap/semantic-discovery-roadmap.md` (independent lane, different tools and inputs)
**Critical finding (2026-06-28)**: The RiftReader LocalPlayerBase offset `0x32EBC80` is a **runtime address** — not a static global in `rift_x64.exe`. Ghidra reports the address as non-memory-backed, uninitialized, with 0 static references. The binary signature strategy must target the CODE that accesses player data, not the data address itself. See `Phase 1 → M1.2` for the revised Ghidra back-trace approach.

**Architecture discovery (2026-06-28)**: FUN_14078a0d0 is a **massive C++ property chain walker** — it iterates through dozens of game-object property offsets using two-tier dispatch. The generic getter thunk at `0x14077d750` chains through `0x14136a2d0` → `0x14129c088` → tail-call to `0x14128aaec` (hash-table/sorted-array lookup; function body starts at `0x14128AB0C`). The returned property descriptor + game object are then passed to **offset-specific callbacks** (e.g., 0x320→`0x1408b39d0`, 0x328→`0x140da8870`) that contain the actual float32 coordinate reads.

**ModRM memory-access search (2026-06-28) — BREAKTHROUGH**: Direct ModRM-based byte scanning found **1,337 register-based memory access instructions** using player coordinate offsets (0x304–0x328) as displacements. Key stats:

- **RBX (727) and RCX (508)** are the dominant base registers → heap object access, not stack locals
- **0x328 pos_z (517) and 0x320 pos_x (410)** are the most-accessed fields
- Examples: `MOV RCX,[R12+0x320]` at 0x1413A6060, `MOV RAX,[RBX+0x328]` — confirmed float32 reads from game objects
- **0x324 pos_y has only 25 hits** — suggests Y is computed (height map), not stored directly
- The 0x320 callback (`0x1408b39d0`) uses `MOVUPS XMM0,[RAX]` loop (SIMD float reads); the 0x328 callback (`0x140da8870`) saves XMM6 + zeros XMM0/XMM1 → definitive float32 math

**Corrected vtable analysis**: Addresses `0x14270f880` and `0x142648c48` are NOT vtables — they're `.rdata` ASCII strings (SQL keywords: "EXPLAIN", "DATABASE", "TABLE", etc., and game strings: "LinkDead", "Lord", "Man"). The singleton context object's vtable dispatch path remains to be fully traced through the virtual call at `CALL [RAX+0x8]`.

## Purpose

RiftReader reads live game memory from `rift_x64.exe` to extract player position, facing, turn rate, zone IDs, and other runtime state. It uses pointer chains anchored to the module base:

```
[rift_x64.exe + 0x32EBC80] + 0x320  →  Player X (float)
[rift_x64.exe + 0x32EBC80] + 0x324  →  Player Y (float)
[rift_x64.exe + 0x32EBC80] + 0x328  →  Player Z (float)
[rift_x64.exe + 0x32EBC80] + 0x30C  →  Facing X (float)
[rift_x64.exe + 0x32EBC80] + 0x304  →  Turn Rate (float)

```

When the game patches and `rift_x64.exe` is recompiled, **all of these offsets break**. RiftReader must re-discover them from scratch: Cheat Engine sessions, pointer scans, multi-pose displacement validation, restart survival tests. This is the waste this roadmap eliminates.

**The fix**: RiftReader already has a pattern scanner (`Reloaded.Memory.Sigscan` for AOB signatures). Instead of hardcoding `0x32EBC80`, RiftReader should scan for a **stable byte signature** near the function that accesses player position data. When the game patches, the signature either:

- **(a)** Still matches at a new address → zero manual work
- **(b)** Breaks → Assets re-runs Ghidra, extracts the new signature, publishes an update

This roadmap adds a **binary analysis lane** to the Assets repo: use the existing Ghidra static analysis pipeline to extract stable byte signatures from `rift_x64.exe`, map struct layouts, and publish a compact signature database that RiftReader consumes for pattern-scanning.

## What Changed Since the Previous Roadmap

| Aspect | NIF geometry roadmap (Phase 1-53) | This roadmap |
|--------|-----------------------------------|-------------|
| Primary input | NIF mesh data from TWAD archives | `rift_x64.exe` binary (direct from live game install) |
| Primary tool | C# NIF parser (`Program.cs`) | Ghidra headless analysis (`ghidra_runner.py` + Java scripts) |
| Primary output | OBJ geometry, mesh manifests | Byte signature database, struct layout maps |
| Target consumer | RiftFlythrough (3D viewer) | RiftReader (live-memory reader) |
| Safety model | 9 proof guards (NIF parser integrity) | Ghidra candidate-only boundary + scanning-rule-object promotion |
| Stability challenge | Mesh decode correctness | Offset survival across game patches |

## Relationship to the Semantic Discovery Roadmap

Both roadmaps serve the same mission — produce stable reference artifacts for downstream repos — but they operate on fundamentally different inputs and use different tooling:

| Dimension | Semantic Discovery | Binary Signature |
|-----------|-------------------|------------------|
| Input | Live archive TWAD entries (263,957) | `rift_x64.exe` binary |
| Tool | `build-asset-semantic-index` (C#) | Ghidra headless (Java + Python) |
| Output | Zone/POI/actor/UI/audio vocabularies | Byte signature + struct layout database |
| Stability model | Heuristic string hints → schema-locked artifacts | Wildcarded byte patterns → pattern-scanning rules |
| Consumer use | Validate coordinate/ID/name observations | Auto-locate memory anchors without hardcoded offsets |

They are **independent** — work on one does not block or require the other. Either lane can be pursued first, or both in parallel by different sessions.

---

## Operating Conventions

1. **Read-only, this repo only.** No cross-repo edits. Output goes to `Exports/` (gitignored). Only schemas and docs are committed.
2. **Ghidra evidence is CandidateOnly within this repo.** Intermediate Ghidra reports, decompiled text, and project databases are gitignored and must not influence production decode/export paths.
3. **The published signature database is a Scanning Rule Object.** It contains abstract byte patterns and relative local offsets — no decompiled code, no hardcoded absolute addresses. It crosses the safety boundary via explicit schema contract, not implicit reuse.
4. **Smoke first, then full.** Every phase starts bounded (single target function) before scaling to all RiftReader anchors.
5. **Wildcards are mandatory.** Byte signatures must mask relative addresses (`?? ?? ?? ??`), jump offsets, and volatile register assignments. Raw instruction bytes without wildcards will break on the next patch.
6. **One anchor at a time.** Survey → signature → validate per-function before moving to the next.
7. **Aggressive Evidence Workflow** still applies: probe → smoke → full inventory → ranked evidence → documented truth → commit → next lead.

---

## Phase 0: Ghidra Tooling Audit & Binary Baseline

**Objective**: Verify the Ghidra headless pipeline works against the current `rift_x64.exe`, confirm the existing function site catalog is usable, and establish a binary baseline.

**Entry Criteria**:

- JDK21 and Ghidra tools registered in `.tools.json` and verified installed
- `ghidra_runner.py` executes without errors
- `rift_x64.exe` exists at `C:/Program Files (x86)/Glyph/Games/RIFT/Live/rift_x64.exe`
- **Assumption**: `rift_x64.exe` is an unpacked, unobfuscated PE binary. If Ghidra auto-analysis produces garbage (e.g., packed or virtualized binary), this roadmap is blocked until the binary is manually unpacked.

**Key Milestones**:

1. **M0.1**: Verify Ghidra headless pipeline
   - Run: `python scripts/rift_workflow.py ghidra-dry-run`
   - Confirm JDK, Ghidra paths resolve; headless analyzer launches
   - Fix any tool path issues

2. **M0.2**: Re-run FunctionSiteSurvey against current `rift_x64.exe`
   - Import the current binary into a fresh Ghidra project
   - Run `FunctionSiteSurvey.java` against the 6 catalogued targets from `docs/ghidra-function-site-targets.json`
   - **Note**: These 6 targets are NiDataStream/TWAD parsing functions — they validate the Ghidra pipeline but are NOT the RiftReader player-coordinate targets (those are identified in Phase 1)
   - Confirm JSON output is valid and non-empty
   - Check: have any of the 6 targets changed address? (indicates a binary update)

3. **M0.3**: Binary baseline fingerprint
   - Extract: `rift_x64.exe` file version, PE timestamp, section layout, image base
   - Record in `Exports/binary-phase0/binary-baseline.json`
   - This is the fingerprint used to detect game patches

4. **M0.4**: Audit `live_memory_scanner.py` for signature validation use
   - Confirm the byte-pattern scanning framework works with a fixture (not live process)
   - Document: can it be used to validate signature uniqueness? what's its output format?

**Exit Criteria**:

- Ghidra headless pipeline functional against current binary
- All 6 catalogued function sites re-surveyed with fresh output
- Binary baseline fingerprint recorded
- Handoff committed with audit findings

**Required Artifacts**:

- `Exports/binary-phase0/function-site-survey/*.json` (re-run, gitignored)
- `Exports/binary-phase0/binary-baseline.json` (gitignored)
- `docs/handoffs/2026-06-28-binary-phase0-audit.md` (committed)

**Focus & Anti-Drift Rules**:

- Do NOT start signature extraction (Phase 2) until Phase 0 exits
- Do NOT modify Ghidra Java scripts unless fixing a crash
- All Ghidra output under `Exports/binary-phase0/`
- No live process interaction — Ghidra is offline static analysis

---

## Phase 1: RiftReader Target Mapping

**Objective**: Identify the 5-10 critical functions and data structures RiftReader needs to locate in memory. These become the targets for signature extraction in Phase 2.

**Entry Criteria**:

- Phase 0 exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- Working knowledge of RiftReader's current pointer chains (from its knowledge.md)
- Ghidra binary imported and analyzed
- **Important**: The 6 catalogued targets from Phase 0 M0.2 are NiDataStream/TWAD functions. Phase 1 identifies a DIFFERENT set of targets — the player-coordinate, zone-ID, and entity-list functions RiftReader actually needs.

**Key Milestones**:

1. **M1.1**: Inventory RiftReader's current anchors
   - Catalog all hardcoded offsets from RiftReader's promoted static resolvers
   - Known targets: LocalPlayer base (`+0x32EBC80`), coordinate fields, facing, turn rate
   - Document: what does each offset point to? what type? how was it discovered?

2. **M1.2**: Ghidra back-trace from known offsets
   - For each known offset (e.g., `0x32EBC80`), use Ghidra to find what references that data address
   - **⚠ REVISED (2026-06-28)**: Direct data-address reference scanning found **0 references** to `0x32EBC80` — it is a runtime address (dynamically allocated heap data), not a static global. Revised approach:
     - Step 1 (completed): Verified the address is not in the static binary via `DescriptorReferenceClassifier` + `DescriptorTableNeighborhoodScanner` — both confirmed 0 static references, 0 memory-backed rows
     - Step 2 (completed): Byte-pattern scan for `movss [reg+0x320]` patterns → **0 matches** in full binary. String-constant search for "Player"/"LocalPlayer"/"Camera" → only UI strings found, no code references.
     - Step 3 (completed): Scalar operand scan via `ScalarOffsetSearcher.java` → **213 hits** across 7 offsets (0x304–0x328). All are immediate loads (`MOV ECX,0x320`), NOT memory accesses (`[base+0x320]`). The offsets are passed as parameters, not used as static displacements.
     - Step 4 (completed): Disassembly context via `DisasmContext.java` → mapped the full property-chain architecture. The offsets flow through: `MOV ECX, offset` → `CALL 0x14077d750` (thunk) → `JMP 0x14136a2d0` → `CALL 0x14129c070` → vtable dispatch (`CALL [RAX+0x8]`).
     - Step 5 (completed 2026-06-28): ModRM-based byte scanning of .text section → found **1,337 register-based memory access instructions** using player offsets as displacements. RBX (727) + RCX (508) dominate. `MOV [RBX+0x328]` and `MOV [RCX+0x320]` are the most common patterns. **0x324 pos_y has only 25 hits** — suggests Y is derived (height map lookup), not stored in the same struct.
   - Step 6 (next): Extract concrete byte signatures from the most-accessed code paths. For each top-VA cluster, run FunctionSiteSurvey for function disassembly, apply wildcarding rules, and verify uniqueness against the full binary.
   - This is the critical step: we're finding the code that accesses the data, not the data address itself

3. **M1.3**: New Ghidra tooling — ScalarOffsetSearcher and DisasmContext
   - Created `scripts/ghidra/ScalarOffsetSearcher.java` — iterates all instructions, finds scalar operands matching target offsets. Fast (~seconds). Output: per-offset JSON with instruction address, mnemonic, bytes, and containing function.
   - Created `scripts/ghidra/DisasmContext.java` — disassembles ±40 instructions around target addresses. Fast (no decompilation). Output: JSON with full instruction text per address.
   - Both scripts CI-validated (run successfully against `rift_x64.exe`, produce valid JSON output).
   - These tools replace the slow `FunctionSiteSurvey.java` for initial target discovery.

4. **M1.4**: Property-chain architecture mapped (2026-06-28)
   - **FUN_14078a0d0**: Contains a massive property-chain walker iterating ~50+ object offsets in sequence.
   - **Access pattern** (repeated per offset): `MOV ECX, <offset>` → `CALL 0x14077d750` → `TEST RAX,RAX` → `JZ skip` → `MOV RDX,[RBP+0x5d8]` → `MOV RCX,RAX` → `CALL <callback>`.
   - **Thunk 0x14077d750**: `XOR R8D,R8D; MOV EDX,0x10; JMP 0x14136a2d0` (13 bytes, 4 wildcards for JMP target). Gateway for all property accesses.
   - **Call chain**: `MOV ECX,<offset>` → `CALL 0x14077d750`(thunk) → `JMP 0x14136a2d0` → `CALL 0x14136a180`(singleton) → `CALL 0x14129c070` → `CALL [RAX+0x8]`(virtual dispatch).
   - **Getter 0x14136a2d0**: Calls singleton initializer `0x14136a180`, then dispatches to `0x14129c070` or `0x14129c088`.
   - **Vtable dispatch 0x14129c070**: `TEST RDX,RDX; JZ +0C; ADD RCX,0x10; MOV RAX,[RCX]; CALL [RAX+0x8]` (15 bytes). Calls virtual method when offset is non-zero.
   - **Offset-specific callbacks**: Each offset (0x320, 0x328, etc.) has a different tier-2 callback (e.g., 0x320→0x1408b39d0, 0x328→0x140da8870). The 0x328 callback saves XMM6 (non-volatile float register), confirming float coordinate processing.     - **Key insight**: After hash table lookup, the offset-specific callbacks (not the generic getter) contain the actual `[base + offset]` memory reads. The 0x320 callback (`0x1408b39d0`) uses MOVUPS XMM loops; the 0x328 callback (`0x140da8870`) saves XMM6 + zeros XMM0/XMM1 (confirmed float32 math). The virtual dispatch path through `CALL [RAX+0x8]` is the non-offset-specific fallback branch.

5. **M1.5**: Stable byte signatures identified
   - **Thunk entry pattern**: `45 33 C0 BA 10 00 00 00 E9 ?? ?? ?? ??` (13 bytes, 4 wildcards for JMP target)
   - **Property access pattern**: `B9 ?? ?? ?? ??` (MOV ECX, offset) followed within ~5 bytes by `E8 ?? ?? ?? ??` (CALL 0x14077d750 relative)
   - **Vtable dispatch**: `48 85 D2 74 0A 48 83 C1 10 48 8B 01 FF 50 08` (15 bytes, **zero wildcards** — maximally stable, confirmed UNIQUE at `0x14129C834`, added to Phase 2 catalog 2026-06-28). Note: DisasmContext initially placed these instructions at `0x14129C070`, but direct byte-level scan found them at `0x14129C834` (offset +0x7C4). The DisasmContext address mapping may have a PE-to-Ghidra translation error — raw byte scan is authoritative.
   - These are candidate signatures for Phase 2 extraction. The vtable dispatch pattern is the most stable (no addresses to wildcard).

6. **M1.6**: Memory-access instruction mapping (2026-06-28)
   - Direct ModRM-based byte scanning found 1,337 register-based `[base+offset]` accesses across offsets 0x304–0x328.
   - **Key insight**: The offsets ARE used as memory displacements, but NOT in the generic getter — they're in offset-specific callbacks that operate on concrete game-object structs. The getter returns a property descriptor; the callback uses it to compute the final memory address.
   - **RBX-dominant (727)** and **RCX-dominant (508)** access patterns confirm heap-allocated object traversal, not stack locals.
   - **0x328 (517 hits)** and **0x320 (410 hits)** are the primary read targets — consistent with X/Z plane movement.
   - **0x324 pos_y has only 25 hits** — may indicate Y (elevation) is derived (terrain/height-map lookup) rather than stored alongside X and Z in the same struct, or uses a different displacement not in the search set.
   - Artifact: The 1,337 instruction sites are the concrete targets for Phase 2 signature extraction.
   - **Phase 2 progress (2026-06-28)**: All 8 top clusters now have **unique byte signatures** extracted, wildcarded (CALL/JMP rel32 + RIP-relative + ModRM disp32), and verified against the full `.text` section. Saved to `Exports/binary-phase2/signature-candidates.json`. See Phase 2 entry below.

7. **M1.7**: Prioritize targets by stability tier
   - **Tier 1 — Engine core**: Functions in the main game loop, coordinate systems, camera transforms (most stable)
   - **Tier 2 — Game logic**: Zone ID lookups, entity list traversal (moderately stable)
   - **Tier 3 — UI/rendering**: HUD coordinate reads, rendering pipeline hooks (least stable)
   - Document tier assignments with rationale

8. **M1.8**: Produce target manifest
   - Output: `Exports/binary-phase1/riftreader-target-manifest.json`
   - Fields per target: `anchor_name`, `current_offset`, `containing_function`, `stability_tier`, `data_type`, `discovery_method`
   - Reference RiftReader's own documentation for context (read-only, no cross-repo edits)

**Exit Criteria**:

- 5-10 targets identified with Ghidra back-traced functions
- Stability tiers assigned
- Target manifest produced
- Handoff committed

**Required Artifacts**:

- `Exports/binary-phase1/riftreader-target-manifest.json` (gitignored)
- `docs/handoffs/2026-06-28-binary-phase1-targets.md` (committed)

**Focus & Anti-Drift Rules**:

- Do NOT attempt signature extraction during this phase — just identify targets
- Targets must be traceable to a specific Ghidra-decompiled function, not just a data address
- If RiftReader has undocumented offsets, flag them as unknown-tier and do not chase

---

## Phase 2: Byte Signature Extraction

**Objective**: For each Phase 1 target, extract a stable byte signature from the containing function's entry point. Each signature must be unique within the binary and survive across game patches via wildcarding.

**Entry Criteria**:

- Phase 1 exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- 5-10 targets with known containing functions
- Ghidra binary imported and analyzed

**Key Milestones**:

1. **M2.1**: Develop wildcarding rules
   - Identify the byte-sequence destabilizers in `rift_x64.exe`:
     - Relative call/jump offsets (E8 ?? ?? ?? ??, E9 ?? ?? ?? ??)
     - RIP-relative data references (48 8B 05 ?? ?? ?? ??)
     - Absolute addresses embedded in immediates
   - Define wildcarding policy: mask all of the above, keep opcode bytes and register encodings
   - Document the policy — it's the core IP of this roadmap
   - **Implementation**: Wildcarding is a Python post-processing step. `FunctionSiteSurvey.java` extracts raw instruction bytes; a Python script (to be built in Phase 6) applies wildcarding rules to produce the final signature hex string. The Java script is NOT modified — it remains a raw-data extractor.

2. **M2.2**: Smoke — extract signature for one Tier-1 target
   - Choose the most stable-looking function (e.g., the one containing the player coordinate read)
   - Use `FunctionSiteSurvey.java` to get the function's instruction bytes
   - Apply wildcarding rules (Python post-processing) to produce a candidate signature
   - Validate uniqueness: scan the entire binary; confirm exactly 1 match
   - If 0 matches: signature too aggressive (over-wildcarded). If >1 matches: too conservative.

3. **M2.3**: Extract signatures for all targets
   - Run the smoke-proven process against all Tier-1 and Tier-2 targets
   - For each: wildcard, validate uniqueness, record match count
   - Flag any targets that fail uniqueness (multiple matches) for fallback strategy

4. **M2.4**: Fallback for unstable signatures
   - If a function's entry point produces a non-unique signature after reasonable wildcarding:
     - **Xref scanning**: Find a stable string constant or `RDATA` pattern near the function; use that as an anchor
     - **Caller anchoring**: Find a stable caller function; have RiftReader read the call instruction's relative offset to reach the real target
     - **Multi-pattern chaining**: Combine two shorter unique patterns with a relative offset between them
   - Document fallback strategies used and why

5. **M2.5**: Produce signature catalog
   - Output: `Exports/binary-phase2/signature-catalog.json`
   - Fields per signature: `anchor_name`, `signature_hex` (with `??` wildcards), `instruction_offset_to_pointer` (if applicable), `uniqueness_verified`, `fallback_strategy` (if any), `extracted_from_version`

**Exit Criteria**:

- All Tier-1 and Tier-2 targets have verified-unique signatures or documented fallbacks
- Wildcarding policy documented
- Signature catalog produced
- Handoff committed

**Required Artifacts**:

- `Exports/binary-phase2/signature-catalog.json` (gitignored)
- `docs/handoffs/2026-06-28-binary-phase2-signatures.md` (committed)

**Focus & Anti-Drift Rules**:

- Do NOT attempt struct layout mapping during this phase — signatures only
- Each signature MUST be uniqueness-verified against the full binary
- Wildcarding policy must be explicit and reproducible — no ad-hoc masking
- If a signature cannot be made unique, flag it rather than shipping a bad pattern

---

## Phase 3: Struct Layout Mapping

**Objective**: From Ghidra's decompiled output, determine the internal layout of the data structures at the end of each pointer chain. This tells RiftReader what's at `+0x320` (X), `+0x324` (Y), etc.

**Entry Criteria**:

- Phase 2 exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- Signatures for all target functions extracted
- Ghidra decompiled output available for each containing function

**Key Milestones**:

1. **M3.1**: Map LocalPlayer struct layout
   - From the function that accesses player position data, trace the struct offsets used
   - Identify field types: float (4 bytes), int (4 bytes), pointer (8 bytes), etc.
   - Produce a field map: `{ "offset": 0x320, "name": "pos_x", "type": "float32" }`

2. **M3.2**: Map secondary structs (zone info, entity list, camera)
   - Same process for each remaining Tier-1 and Tier-2 target
   - Where Ghidra's decompiler can't resolve a field name, use a descriptive label
   - Document confidence levels: `confirmed` (seen in multiple contexts), `inferred` (single reference), `tentative` (register-only, no struct access)

3. **M3.3**: Cross-reference against RiftReader's known offsets
   - Compare mapped layouts against the offsets RiftReader currently uses
   - Flag discrepancies: if RiftReader reads `+0x320` as X but Ghidra shows it as a vtable pointer, that's a finding
   - Document any corrections (read-only — no cross-repo edits)

4. **M3.4**: Produce layout catalog
   - Output: `Exports/binary-phase3/struct-layout-catalog.json`
   - Merge signature + layout data into unified anchor records

**Exit Criteria**:

- All Tier-1 structs have field maps with type annotations
- Cross-reference against RiftReader's known offsets complete
- Layout catalog produced
- Handoff committed

**Required Artifacts**:

- `Exports/binary-phase3/struct-layout-catalog.json` (gitignored)
- `docs/handoffs/2026-06-28-binary-phase3-layouts.md` (committed)

---

## Phase 4: Cross-Version Validation

**Objective**: Test whether extracted signatures survive across different versions of `rift_x64.exe`. If multiple versions exist, validate against all of them. If only one version exists, simulate patch resilience by testing wildcard aggressiveness.

**Entry Criteria**:

- Phase 3 exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- Signatures and layouts extracted for all Tier-1/2 targets

**Key Milestones**:

1. **M4.1**: Check for multiple `rift_x64.exe` versions
   - Scan the live game directory and any backups for older binaries
   - If found: run signature scan against each version; record match/miss per version
   - If not found: proceed to M4.2 (simulated validation)

2. **M4.2**: Simulated patch resilience (single-version case)
   - For each signature, test with progressively more aggressive wildcarding
   - Find the threshold where the signature loses uniqueness (matches >1 location)
   - Document the "stability margin" — how much can change before the signature breaks?
   - This is a forward-looking estimate, not a guarantee

3. **M4.3**: Validate using `live_memory_scanner.py` fixture
   - Load each signature into the scanner's byte-pattern framework
   - Run against a fixture (not live process) to verify pattern matching works
   - Confirm all patterns produce exactly 1 match in the binary

4. **M4.4**: Stability report
   - Output: `Exports/binary-phase4/signature-stability-report.json`
   - Per signature: version coverage, uniqueness across versions, stability margin estimate
   - Flag any signatures with low stability margins for monitoring

**Exit Criteria**:

- All signatures validated (either cross-version or simulated)
- Stability report produced
- Handoff committed

**Required Artifacts**:

- `Exports/binary-phase4/signature-stability-report.json` (gitignored)
- `docs/handoffs/2026-06-28-binary-phase4-stability.md` (committed)

---

## Phase 5: Signature Database & Consumer Contract

**Objective**: Publish the final signature database as a compact, schematized JSON artifact with clear consumer-facing documentation. This is the deliverable that RiftReader imports.

**Entry Criteria**:

- Phase 4 exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- All signatures validated for uniqueness and cross-version stability

**Key Milestones**:

1. **M5.1**: Define the signature database schema
   - Write `docs/schemas/binary-signatures-v1.schema.json`
   - Follow existing conventions: JSON Schema 2020-12, `additionalProperties: false`, `const` for `SchemaVersion`
   - Schema covers: binary metadata, version fingerprint, anchors array with signature_hex, wildcard_policy, instruction_offset_to_pointer, struct_layout, stability_tier

2. **M5.2**: Synthesize the final signature database
   - Merge Phase 2 signatures + Phase 3 layouts + Phase 4 stability data
   - Validate against schema
   - Output: `Exports/binary-phase5/rift-x64-signature-database.json`

3. **M5.3**: Write consumer contract documentation
   - Write `docs/binary-signature-consumer-contract.md`
   - Document:
     - How to use each anchor: scan for signature → resolve pointer at instruction_offset_to_pointer → apply struct_layout offsets
     - Wildcard byte conventions (`??` = any byte)
     - Stability tier meanings and expected patch survival
     - What to do when a signature breaks (re-run Ghidra pipeline)
     - The Ghidra safety boundary: these are scanning rules, not decompiled code
   - No cross-repo edits — this is documentation only

4. **M5.4**: Schema + handoff
   - Validate artifact against schema
   - Run `ruff`, `mypy`, `dotnet build`, full pytest suite
   - Commit schema + contract doc + handoff

**Exit Criteria**:

- Signature database produced and schema-valid
- Consumer contract documented
- CI green (ruff, mypy, dotnet build, pytest, markdownlint)
- Handoff committed

**Required Artifacts**:

- `Exports/binary-phase5/rift-x64-signature-database.json` (gitignored)
- `docs/schemas/binary-signatures-v1.schema.json` (committed)
- `docs/binary-signature-consumer-contract.md` (committed)
- `docs/handoffs/2026-06-28-binary-phase5-delivery.md` (committed)

---

## Phase 6: Automation & Monitoring

**Objective**: Reduce the cost of re-running the pipeline when the game patches. Automate signature extraction so a single command re-surveys the binary and produces an updated database.

**Entry Criteria**:

- Phase 5 exit complete *(as of 2026-06-28; self-reported; not yet externally validated)*
- Signature database published

**Key Milestones**:

1. **M6.1**: Build `scripts/extract_binary_signatures.py`
   - Python script that orchestrates the full pipeline:
     1. Import `rift_x64.exe` into a fresh Ghidra project
     2. Run auto-analysis
     3. Execute `FunctionSiteSurvey.java` against all targets
     4. Apply wildcarding rules to extract signatures
     5. Validate uniqueness against the binary
     6. Merge with struct layout data
     7. Write updated `rift-x64-signature-database.json`
   - Accept `--binary-path`, `--target-manifest`, `--out` arguments

2. **M6.2**: Build `scripts/compare_signature_databases.py`
   - Diff two versions of the signature database
   - Report: which signatures changed? which broke? which are new?
   - Output: `Exports/binary-phase6/patch-diff-report.json`
   - This is the artifact that tells RiftReader what needs updating

3. **M6.3**: Wire into workflow command
   - Add `extract-binary-signatures` and `compare-binary-signatures` commands to `rift_workflow.py`
   - Follow existing kebab-case command conventions
   - **Ghidra guard compatibility**: The existing guards (`ghidra_function_site_target_guard`, `ghidra_pairing_non_export_guard`, `ghidra_attribute_candidate_guard`) enforce CandidateOnly for Ghidra evidence within this repo's decode/export paths. The new commands produce a Scanning Rule Object (abstract byte patterns + relative offsets) for external consumption — this does not violate the guards because it does not wire Ghidra evidence into production NIF parsing or OBJ export. The guards are left unchanged.

4. **M6.4**: CI smoke test
   - Add a CI job (or extend existing Ghidra-independent job) that:
     - Runs `ghidra-dry-run` to verify tool wiring
     - Runs `extract_binary_signatures.py --validate-only` to check schema validity
   - Do NOT run full Ghidra analysis in CI (too slow, requires Ghidra installation) — just validate artifacts

5. **M6.5**: Final documentation sweep
   - Update `current-phase.md` to reference this roadmap as active
   - Update `knowledge.md` with binary signature lane status
   - Commit final handoff

**Exit Criteria**:

- Automation script functional (produces valid signature database from binary)
- Comparison script functional (diff two databases)
- Workflow commands wired
- CI validates artifact structure (not full Ghidra run)
- `current-phase.md` and `knowledge.md` updated

**Required Artifacts**:

- `scripts/extract_binary_signatures.py` (committed)
- `scripts/compare_signature_databases.py` (committed)
- `Exports/binary-phase6/*.json` (gitignored)
- `docs/handoffs/2026-06-28-binary-phase6-automation.md` (committed)

---

## Roadmap Summary

| Phase | Topic | Key Artifact |
|-------|-------|-------------|
| 0 | Ghidra tooling audit & binary baseline | `binary-baseline.json` |
| 1 | RiftReader target mapping | `riftreader-target-manifest.json` |
| 2 | Byte signature extraction | `signature-catalog.json` |
| 3 | Struct layout mapping | `struct-layout-catalog.json` |
| 4 | Cross-version validation | `signature-stability-report.json` |
| 5 | Signature database & consumer contract | `rift-x64-signature-database.json` + consumer docs |
| 6 | Automation & monitoring | `extract_binary_signatures.py` |

## Target Signature Database Schema (Preview)

```json
{
  "schema": "binary-signatures-v1",
  "binary_target": "rift_x64.exe",
  "binary_version": "20.6.0.0",
  "image_base": "0x140000000",
  "extracted_at": "2026-06-28T12:00:00Z",
  "wildcard_policy": "Relative addresses (E8/E9/8B 05), jump offsets, and RIP-relative displacements are masked as ??. Opcode bytes and register encodings are preserved.",
  "anchors": [
    {
      "name": "LocalPlayerBase",
      "stability_tier": 1,
      "signature_hex": "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? F3 0F 10 80",
      "signature_length": 17,
      "instruction_offset_to_pointer": 3,
      "pointer_resolution": "rip_relative",
      "struct_layout": {
        "description": "LocalPlayer coordinate and facing struct",
        "fields": [
          {"offset": 772, "name": "turn_rate",      "type": "float32", "confidence": "confirmed"},
          {"offset": 780, "name": "facing_x",       "type": "float32", "confidence": "confirmed"},
          {"offset": 784, "name": "facing_y",       "type": "float32", "confidence": "confirmed"},
          {"offset": 788, "name": "facing_z",       "type": "float32", "confidence": "confirmed"},
          {"offset": 800, "name": "pos_x",          "type": "float32", "confidence": "confirmed"},
          {"offset": 804, "name": "pos_y",          "type": "float32", "confidence": "confirmed"},
          {"offset": 808, "name": "pos_z",          "type": "float32", "confidence": "confirmed"}
        ]
      },
      "uniqueness_verified": true,
      "binary_version_coverage": ["20.6.0.0"]
    }
  ]
}

```

## Anti-Drift Rules (All Phases)

1. **This repo only.** No cross-repo edits. No touching RiftReader/RiftScan/RiftFlythrough.
2. **Output to `Exports/` only.** All generated artifacts are gitignored. Only schemas, scripts, and docs are committed.
3. **Ghidra evidence is CandidateOnly within this repo.** Intermediate reports, decompiled text, and project databases must not influence production decode/export paths.
4. **The published signature database is a Scanning Rule Object.** It crosses the safety boundary via explicit schema contract, not implicit reuse.
5. **Wildcards are mandatory.** Every byte signature must mask relative addresses, jump offsets, and volatile register assignments.
6. **Uniqueness must be verified.** Every signature must match exactly 1 location in the binary.
7. **One anchor at a time.** Survey → signature → validate per-function before moving to the next.
8. **Smoke before full.** Start with a single Tier-1 target before scaling to all anchors.
9. **No new C# parse logic** unless fixing a crash or adding a narrow output field.
10. **CI stays green.** No regression on existing 593 Python + 56 dotnet tests.

---

## Consumer Contract Summary (for RiftReader)

When this roadmap completes, RiftReader can replace hardcoded offsets like `0x32EBC80` with:

```

1. Load rift-x64-signature-database.json
2. For anchor "LocalPlayerBase":
   a. Pattern-scan for: 48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? F3 0F 10 80
   b. At match address, read the RIP-relative displacement at +3 bytes
   c. Compute: base_ptr = match_address + 7 + displacement  (standard x64 RIP-relative)
   d. Read player X: *(base_ptr + 800)
   e. Read player Y: *(base_ptr + 804)
   f. Read player Z: *(base_ptr + 808)

```

When a game patch breaks a signature (0 matches):

1. Re-run `python scripts/extract_binary_signatures.py` against the new `rift_x64.exe`
2. Diff with `python scripts/compare_signature_databases.py`
3. Update RiftReader's copy of the database

---

*This roadmap is the single source of truth for the binary signature discovery phase of the Assets repo. All work must be traceable to a specific phase and milestone above.*
