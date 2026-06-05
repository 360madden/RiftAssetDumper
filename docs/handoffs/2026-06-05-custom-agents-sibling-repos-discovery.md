# Handoff: Custom agent definitions + sibling repo assessment + CI baseline

**Date:** 2026-06-05  
**Parent:** `docs/handoffs/2026-06-02-stage2-position-source-enhanced-findings.md`  
**Status:** ✅ Complete — build 0 errors, 6/6 tests pass, format clean, ruff 0, mypy 5 pre-existing

---

## What was done this session

### 1. Custom agent definitions created (8 total)

Created `.agents/` directory with 8 custom agent definition files embedding project-specific domain knowledge. Each agent has appropriate model routing, tool restrictions, and spawnable-agent references as defined by the `agent-definition.ts` schema.

| # | Agent | Model | Purpose | Read-only? |
|---|-------|-------|---------|:----------:|
| 🔴 1 | `nif-probe-agent` | deepseek-v4-flash (high) | Autonomous NIF mesh probing, stream roles, @264 analysis, geometry decode | ✅ yes |
| 🔴 2 | `discovery-orchestrator` | deepseek-v4-flash (medium) | Runs full 7-stage pipeline: build→inventory→guards→workbench→summary | ❌ spawns runners |
| 🔴 3 | `safety-guardian` | claude-sonnet-4.5 (high) | Enforces safety policy, privacy audit, export gate compliance, commit review | ✅ yes |
| 🟡 4 | `program-cs-editor` | deepseek-v4-pro (high) | Safe targeted edits to 15K-line Program.cs single file | ❌ edits code |
| 🟡 5 | `proof-guard-agent` | deepseek-v4-flash (high) | Run/maintain/update all 4 proof guards + baselines | ❌ edits guards |
| 🟢 6 | `obj-export-validator` | deepseek-v4-flash (medium) | Structural validation of exported OBJ files | ✅ yes |
| 🟢 7 | `handoff-summarizer` | deepseek-v4-flash (high) | Generates timestamped session handoffs to `docs/handoffs/` | ✅ yes |
| 🔵 8 | `autonomous-worker` | deepseek-v4-flash (medium) | Accepts task queue, delegates to specialists, reports structured output | ❌ spawns agents |

Each agent embeds project-specific knowledge: NiDataStream 29-byte invariant, @264/#15 index lead, degenerate-bridge strip semantics, experimental-position-source flags, safety policy rules, proof guard structure, etc.

All definitions were code-reviewed by `@code-reviewer-deepseek-flash` — issues found and fixed:

- `proof-guard-agent` was missing write tools (needed for guard baseline updates) — fixed
- `autonomous-worker` was missing `spawn_agents` in toolNames — fixed
- `autonomous-worker` had stale `autoContinue` param — removed
- `autonomous-worker` had `@mention` syntax in instructions — replaced with `spawn_agents` tool calls
- Rule 6 in autonomous-worker still used `@code-reviewer-deepseek-flash` — fixed

### 2. CI baseline run (full suite)

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | **dotnet build** | ✅ PASSED | 0 errors, 4 warnings (NU1902 SharpCompress ×2, CS8602 null ref ×2) |
| 2 | **dotnet format** | ✅ PASSED | Auto-fixed 1 whitespace issue (2-space indent on `Console.WriteLine("  --write-obj")`) |
| 3 | **dotnet test** | ✅ PASSED | 6/6 passed, 0 failed, 0 skipped |
| 4 | **Python syntax** | ✅ PASSED | All 13 script files compile clean |
| 5 | **ruff lint** | ✅ PASSED | 0 violations |
| 6 | **mypy type check** | ⚠️ 5 pre-existing | 1 unused ignore in `rift_workflow.py:1566`, 4 `no-untyped-call` in `live_inventory.py` |

**Bottom line:** 5 of 6 CI checks pass. The 5 mypy errors are pre-existing and were not introduced by any session changes.

### 3. Sibling repo assessment (RiftReader + Riftscan)

Discovered and explored two sibling repos on the local machine:

**RiftReader** (`../RiftReader/`) — Live game client memory reader

- Player/target coordinate anchors (`PlayerCoordAnchor*`, `CoordTrace*`)
- Lua addon bridge (`ReaderBridgeSnapshot`, `ValidatorSnapshot`)
- Player orientation analysis (`PlayerOrientation*`)
- String/float/numeric scanners for runtime memory probing
- Signature discovery methodology
- **Best for:** Live validation — attach to running RIFT, read actual coordinates, compare against NIF-decoded positions

**Riftscan** (`../Riftscan/`) — Memory discovery pipeline

- `FloatTripletStructureAnalyzer` — finds Vec3 coordinate data in memory (directly relevant)
- `StructureClusterAnalyzer` — could find known NIF block patterns
- `Vec3TruthPromotionService` — pipeline for promoting 3D data candidates to truth
- Byte delta analysis — identifies position-changing memory regions
- Session comparison + xref analysis — validates static vs runtime behavior
- Passive memory capture — offline-friendly
- **Best for:** Cross-validation — capture memory, find float triplets, verify against NIF vertex positions

**Integration potential:** Riftscan's `FloatTripletAnalyzer` and `Vec3TruthPromotionService` map cleanly to our position-source decode validation. A cross-validation script could read Riftscan's output format and compare against our probe JSONs.

### 4. knowledge.md updated

Updated with:

- Custom agent definitions directory structure and usage
- Architecture summary with C#/Python/PowerShell quickstart table
- Full proof guard status and lane-level TL;DR
- CI pipeline configuration
- Sub-agent routing for safety policy enforcement
- Sibling repo references (RiftReader, Riftscan)

### 5. Uncommitted changes summary

| File | Change | Status |
|------|--------|:------:|
| `knowledge.md` | Updated with agent definitions, CI, sibling repos, architecture | 📝 modified |
| `src/RiftAssetDumper/Program.cs` | Whitespace fix: 6→4 space indent on `Console.WriteLine("  --write-obj")` | 📝 modified |
| `.agents/autonomous-worker.ts` | New: task-queue agent with specialist delegation | ➕ untracked |
| `.agents/discovery-orchestrator.ts` | New: pipeline runner | ➕ untracked |
| `.agents/handoff-summarizer.ts` | New: handoff generator | ➕ untracked |
| `.agents/nif-probe-agent.ts` | New: NIF mesh probe specialist | ➕ untracked |
| `.agents/obj-export-validator.ts` | New: OBJ validator | ➕ untracked |
| `.agents/program-cs-editor.ts` | New: Program.cs editor | ➕ untracked |
| `.agents/proof-guard-agent.ts` | New: proof guard maintainer | ➕ untracked |
| `.agents/safety-guardian.ts` | New: safety policy enforcer | ➕ untracked |

---

## Current project state

### OBJ export inventory (from Stage 13 baseline)

| Metric | Value |
|-------|:-----:|
| Total OBJs | **29** (23 faced, 6 position-only) |
| Total faces | **3,177** |
| Total vertices | **1,881** |
| Mesh families covered | **13** |
| Exhaustive probe complete? | ✅ Yes — 12 of 13 unprobed sizes have PairCompatible=0 |
| meshSize=465 | ❌ Dead end — all 3 samples missing from copied archives |

### Proof guard status (all 4 PASSED)

| Guard | Status | Key assertions |
|-------|:------:|---------------|
| `attribute-extra-proof-guard` | ✅ PASSED | 4 @264 groups intact, raw-zero-based 5/5, degenerate-bridge-stitch, parity 0/0 |
| `usage-access-correlation-guard` | ✅ PASSED | 5 roles, 0 pairing exceptions |
| `position-source-sibling-lead-guard` | ✅ PASSED | Guards leads intact |
| `residual-lead-guard` | ✅ PASSED | meshSize=305: 119 residuals, 5 @188 candidates |

### Position discovery status

- **No position gaps** in the five indexed target mesh sizes (297, 305, 321, 325, 329)
- **5 sibling position-source groups** confirmed (strongest: meshSize=329 × 23 groups sharing stream@212)
- **Residual classifier:** 5 candidate rows at plausible 0.8283–0.9444 (below strict 0.95)
- **Magic-43606 pattern** identified in payload 288 at meshSize=305 stream@188 — promising packed uint16 position lead
- **Export blocked** — `GeometryTruthPromoted=false` on all rows

### Sibling repo cross-reference opportunity

```
Current pipeline:   TWAD → NIF → decode geometry → OBJ export
                          ↓
Riftscan would add:       → FloatTripletAnalyzer (runtime Vec3 validation)
RiftReader would add:     → live coordinate anchors (in-game position verification)
```

---

## Known limitations (unchanged from Stage 2)

1. Faces are trivial triangle fan in fallback mode (vertex 0 to consecutive pairs)
2. Only first float32 candidate per role used; multiple candidates skipped
3. 5,455 meshes (99%) have 0 attribute sets — fallback handles where linked streams contain float32 data
4. `--write-obj` path overlap with probe-report JSON directory
5. 5 pre-existing mypy errors not addressed
6. All position-source residual rows remain candidate-only — export blocked

---

## Files changed this session

| File | Change type | Description |
|------|:-----------:|-------------|
| `docs/handoffs/2026-06-05-custom-agents-sibling-repos-discovery.md` | + NEW | This handoff document |
| `knowledge.md` | 📝 modified | Updated with agent definitions, CI, sibling repos, architecture |
| `src/RiftAssetDumper/Program.cs` | 📝 modified | Whitespace indent fix (cosmetic, `dotnet format`) |
| `.agents/autonomous-worker.ts` | + NEW | Task queue agent with specialist delegation |
| `.agents/discovery-orchestrator.ts` | + NEW | Pipeline runner |
| `.agents/handoff-summarizer.ts` | + NEW | Handoff generator |
| `.agents/nif-probe-agent.ts` | + NEW | NIF mesh probe specialist |
| `.agents/obj-export-validator.ts` | + NEW | OBJ validator |
| `.agents/program-cs-editor.ts` | + NEW | Program.cs editor |
| `.agents/proof-guard-agent.ts` | + NEW | Proof guard maintainer |
| `.agents/safety-guardian.ts` | + NEW | Safety policy enforcer |

---

## Next recommended steps (top 10)

1. **Commit the `.agents/` directory + `knowledge.md` + handoff** — stable milestone, unlocks agent `@mention` usage
2. **Run `@discovery-orchestrator`** to do a full discovery suite refresh against current codebase
3. **Run `@nif-probe-agent`** on the magic-43606 payload 288 candidate at meshSize=305 stream@188
4. **Run `@proof-guard-agent`** to re-validate all 4 guards after the Program.cs whitespace change
5. **Explore Riftscan integration** — write cross-validation script reading Riftscan `FloatTripletAnalyzer` output against our probe JSONs
6. **Run `@autonomous-worker`** with a task queue for multi-step exploration (e.g., build → inventory → guards → report)
7. **Run `@safety-guardian`** for a privacy scan + commit readiness audit
8. **Address the 5 pre-existing mypy errors** in `live_inventory.py` and `rift_workflow.py`
9. **Run `batch-export-264`** to re-export all 5 known @264 indexed OBJs and verify they still match the 71,435 byte baseline
10. **Investigate the meshSize=465 gap** — determine what archive(s) contain its 3 sample IDs
