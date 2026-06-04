# Phase 8 Prep Note — Semantic Gate Clearance

**Date**: 2026-06
**Type**: Phase Prep — Phase 8 Entry
**Status**: **COMPLETE** — Phase 8 EXITED; M8.2 delivered, M8.1/M8.3 deferred to Phase 9
**Parent(s)**: `docs/roadmap/project-roadmap.md`, `docs/handoffs/2026-06-m7.5-phase7-exit-consolidation.md`
**Entry**: Phase 7 EXITED — 3 gates CLEARED, 1 RETIRED, gate 5 reframing documented; 49 tests, 58 descriptor lines, 31,777-block population inventory

**Roadmap Reference**: This prep supports **Phase 8: Semantic Gate Clearance**. Per the Phase 7 exit handoff: "Use Ghidra-level analysis and population-cross-referencing to resolve the remaining semantic blockers (bytes 1-2, role mapping for 3/5 patterns) while evaluating the gate 5 reframing decision."

**Anti-drift**: Phase 8 targets the hardest remaining gates — byte-level semantics and role mapping. These likely require Ghidra analysis for bytes 1-2 and substantial cross-referencing for role semantics. Gate 6 (safety brake) remains intentionally held. Phase 8 should not force clearance where evidence is insufficient.

## Objective

Resolve the remaining semantic blockers identified in Phase 7:
- **Gate 1b** (`descriptor-field-semantics-complete`): What do bytes 1-2 encode? (element width? component count? stride hint?)
- **Gate 2** (`descriptor-semantic-map`): What stream roles do the remaining 3/5 descriptor patterns map to?
- **Gate 5** (`pairing-impact-proof`): Reframing evaluation (human review — documented but not autonomously actioned)

## Phase 7 Foundation (ready for Phase 8)

| Finding | Phase 8 implication |
|---|---|
| 3 structural gates cleared (M7.1-M7.3) | Foundation is proven — semantic analysis can build on solid base |
| 31,777-block population inventory available | Descriptor-to-role cross-reference at population scale is feasible |
| Gate 5 reframing documented (M7.4) | If accepted by human review, gate 5 would CLEAR (4th clearance) |
| Bytes 1-2 opaque — no code uses them | Ghidra analysis is the only evidence path for byte-1/byte-2 semantics |
| 3/5 patterns have family labels but no verified role | Role mapping requires cross-referencing descriptor → stream usage/access → mesh binding |
| Gate 6 safety brake held | Must remain held until all other gates pass |

## Remaining Gate Landscape (Phase 8 Entry)

| Gate | Status | Blocker | Phase 8 Target |
|---|---|---|---|
| `descriptor-field-semantics-complete` (1b) | BLOCKED | Bytes 1-2 unknown | M8.1: Ghidra analysis |
| `descriptor-semantic-map` (2) | improved (usage-level) | 4/5 patterns no specific role | M8.2: Usage-level evidence (all 5) |
| `pairing-impact-proof` (5) | CANDIDATE | attrSets=0 architecture | M8.3: Human review |
| `narrow-parser-patch` (6) | BLOCKED | Safety brake | Not before M8.4 |

## Proposed Milestones

### M8.1 — Ghidra Byte 1-2 Analysis (PLANNING)
- Target: what do descriptor bytes 1 and 2 encode?
- Hypotheses: element width (0x04 = 4 bytes = float32), component count (0x03 = 3-component = vec3), stride hint, flags
- Approach: Ghidra decompilation of NiDataStream registry/reading code in `rift_x64.exe`
- Expected input: Static analysis of code paths that consume the 4-byte descriptor
- If successful: byte-1 and/or byte-2 semantics resolved → gate 1b advances
- Tools required: Ghidra (`.tools.json` — JDK 21 + Ghidra 12.1 installed)

- [x] Cross-referenced descriptor patterns with Usage/Access values from population inventory (31,777 blocks aggregate, 16 rep samples)
- [x] All 5 patterns now have usage-level role evidence:
  - `37040300` → usage=1 → position/normal/UV (role-agnostic) — MAPPED
  - `36040200` → usage=1 → float vertex data variant — family-mapped
  - `15020100` → **usage=0** → index stream descriptor (ucorrected from "u16-vertex-data") — KEY FINDING
  - `10010400` → usage=1 → vertex data descriptor — family-mapped
  - `3c010400` → usage=1 → vertex data descriptor — family-mapped
- [x] Gate 2 (`descriptor-semantic-map`) advanced from "blocked (improved)" to "improved — usage-level evidence for all 5 patterns"
- [x] 3 patterns gain usage-level semantics (15020100=index, 10010400=vertex, 3c010400=vertex)

### M8.3 — Gate 5 Reframing Evaluation (PLANNING)
- Human review of M7.4 recommendation: accept `attrSets=0` as architectural norm
- Decision: CLEAR gate 5 on reframed criterion OR explicitly hold gate 5 with documented rationale
- If CLEARED: 4th gate clearance in Phase 8

### M8.4 — Phase 8 Exit Consolidation
- [x] Exit handoff: `docs/handoffs/2026-06-m8.4-phase8-exit-consolidation.md`
- [x] Gate 2 advanced; M8.1 (Ghidra) and M8.3 (human review) deferred to Phase 9
- [x] Phase 9 entry assessment with 6 recommendations

## Commands

```bash
dotnet build RiftAssetDumper.slnx --nologo
dotnet test RiftAssetDumper.slnx --nologo
dotnet format RiftAssetDumper.slnx --verify-no-changes

# Ghidra dry-run (verify tooling)
python scripts/rift_workflow.py ghidra-dry-run

# If running Ghidra analysis:
python scripts/rift_workflow.py ghidra-run --ghidra-project-name RiftPhase8 \
  --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project \
  --ghidra-timeout 900 --ghidra-script scripts/ghidra/FunctionSiteSurvey.java
```

## Validation Gates

- [ ] Build: 0 errors
- [ ] Tests: 49/49 pass
- [ ] `dotnet format --verify-no-changes` clean
- [ ] `FieldOrderPromoted` still false (gate 6 blocks)
- [ ] `ParserExportPromotionAllowed` still false (gate 6 blocks)
- [ ] At least 1 semantic finding documented (byte 1-2 or role mapping)
- [ ] Gate 5 reframing decision recorded

## Gate Clearance Strategy (Phase 7-8)

```
Phase 7 (structural):  Phase 8 (semantic):
────────────────────►  ──────────────────────►
3 CLEARED ✅          Gate 1b: bytes 1-2 ────► Ghidra analysis
1 RETIRED             Gate 2: role mapping ──► Population cross-reference
Gate 5: documented    Gate 5: reframing ─────► Human review
3 BLOCKED             Gate 6: safety ────────► Held

Target: 2+ gates advanced (1b and/or 2), gate 5 decision recorded
```

## Anti-Drift Rules

- Ghidra analysis must be targeted to specific byte semantics questions (not general exploration).
- Role-semantic mapping must use existing population data — no new probes unless a specific hypothesis needs testing.
- Gate 5 reframing is a human-review decision — autonomous lane documents the evidence but does not clear.
- Gate 6 (safety brake) remains intentionally held.
- Both promotion flags (`FieldOrderPromoted`, `ParserExportPromotionAllowed`) remain false.
- No decode/export code changes unless and until gate 6 is cleared.

---

See `docs/roadmap/project-roadmap.md` (Phase 8), `docs/handoffs/2026-06-m7.5-phase7-exit-consolidation.md` (Phase 7 exit), `docs/handoffs/2026-06-m7.4-formal-decision-record.md` (M7.4).
