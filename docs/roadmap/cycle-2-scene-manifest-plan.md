# Cycle 2 Plan — Scene Manifest & World Reconstruction

**Status**: 🟡 **DRAFT v0.3** — awaiting kickoff approval (revised from v0.2)
**Version**: 0.3 (agentic, machine-checkable; cohort trimmed, phases merged, V4 Pro consolidated)
**Created**: 2026-06-12
**Last updated**: 2026-06-15 (v0.2 → v0.3 adjustments)
**Owner**: Assets repo (`RiftAssetDumper`)
**Consumer**: `C:\RIFT MODDING\RiftFlythrough` (sibling, Phase 21/50 of its own roadmap)

**v0.3 changes from v0.2:**

- Cohort trimmed 39 → ~25 (V4 Pro 1-page brief fit)
- C2-2 (transform data) + C2-3 (coordinate data) merged into single C2-2 phase (5 sub-steps)
- V4P1 (transform + coordinate) + V4P2 (schema design) combined into single V4P12 session
- V4 Pro sessions: 5 → 4 (V4P12 combined, V4P3 conditional, V4P4, V4P5)

**Cycle theme:** Move from *decoded meshes* → *placed, textured, consumer-usable world assets*

**Predecessor:** [Cycle 1 — Discovery Plan 50](../discovery-plan-50.md), Step 50/50 closed 2026-05-26.

**Pre-cycle state (snapshot at 2026-06-12):**

| Metric | Value |
|---|---:|
| OBJ files | 350 (270 faced, 80 pos-only) |
| Unique asset IDs | 217 |
| Promotion gates | 7/7 CLEARED |
| Proof guards | 8/8 PASSING |
| Flythrough Bridge Plan | FT-1..FT-7 complete, FT-8 skipped |
| Untracked work | `scripts/batch_scene_graph.py` (de facto start) |

**Naming convention:** This plan uses the **C2-N.M** prefix to avoid collision with the existing **Phase 0..49** numbering in `project-roadmap.md` and the **FT-N.M** numbering in `flythrough-bridge-plan.md`. The three plans are independent and address different problem spaces — the existing 0–49 plan covers NIF parser/descriptor work; the FT plan covers consumer-app integration; this C2 plan covers **scene-manifest & world reconstruction** as the post-completion frontier.

---

## 0. State (machine-checkable)

The current plan state is stored at `Assets/build/cycle-2/.state.json` (gitignored). An agent MUST read this file first; if absent, treat all steps as `pending`.

```json
{
  "plan": "cycle-2-scene-manifest-plan",
  "version": "0.2",
  "current_phase": "C2-1",
  "current_step": "C2-1.1",
  "phase_status": {
    "C2-1": "pending", "C2-2": "pending", "C2-3": "pending",
    "C2-4": "pending", "C2-5": "pending", "C2-6": "pending",
    "C2-7": "pending", "C2-8": "pending", "C2-9": "pending"
  },
  "step_status": {
    "C2-1.1": "pending", "C2-1.2": "pending", "C2-1.3": "pending",
    "C2-1.4": "pending", "C2-1.5": "pending"
  },
  "v4_pro_blocks": {
    "C2-V4P12": {"status": "pending", "used_at": null, "output_path": null, "summary": "Combined: transform truth + coordinate contract + scene-manifest v1 schema"},
    "C2-V4P3": {"status": "pending", "used_at": null, "output_path": null, "conditional": true},
    "C2-V4P4": {"status": "pending", "used_at": null, "output_path": null},
    "C2-V4P5": {"status": "pending", "used_at": null, "output_path": null}
  },
  "v4_pro_sessions_used": 0,
  "v4_pro_session_limit": 4,
  "plan_status": "draft",
  "last_handoff": null,
  "last_updated": "2026-06-12T00:00:00Z",
  "blocked_reason": null
}
```

### Status legend

| Symbol | Meaning |
|---|---|
| ⬜ pending | not started |
| 🟡 in_progress | an agent is currently working on it |
| ✅ done | acceptance criteria met, evidence committed |
| ❌ blocked | cannot proceed; `blocked_reason` populated |
| ⏸ paused | awaiting human review or V4 Pro session |
| 🚫 killed | cycle was explicitly killed (kill criterion triggered) |

### Validation command (run by any agent on resume)

```bash
python -c "import json; s=json.load(open('Assets/build/cycle-2/.state.json')); print(f\"current={s['current_phase']}.{s['current_step']} v4_used={s['v4_pro_sessions_used']}/5 last_handoff={s['last_handoff']}\")"
```

---

## 1. Single-command orchestrator

After this plan is loaded, an agent should be able to make progress with one command:

```bash
# Show current state and what's next
python scripts/cycle_2_plan.py status

# Run the next pending step (auto-resumes from .state.json)
python scripts/cycle_2_plan.py step --next

# Run a specific step
python scripts/cycle_2_plan.py step --id C2-5.3

# Mark a step done (with evidence)
python scripts/cycle_2_plan.py complete --id C2-5.3 --evidence <path>

# Mark a V4 Pro block done
python scripts/cycle_2_plan.py v4-done --id C2-V4P12 --output <path-to-v4-pro-output.md>
```

The orchestrator script (`scripts/cycle_2_plan.py`) is part of **C2-1.5** and ships with this plan. It mirrors `scripts/flythrough_plan.py`'s structure.

---

## 2. Model allocation: M3 (default) + DeepSeek V4 Pro (4 sessions in v0.3)

| | M3 (this model) | DeepSeek V4 Pro |
|---|---|---|
| Quota | Unlimited | 4 premium sessions (v0.3, was 5), resets every 24h |
| Strengths | Volume work, multimodal, unlimited iteration | Pattern recognition, multi-step reasoning, decision calls |
| Use for | All steps except the 4 V4 Pro blocks below | 4 specific decision blocks |

**V4 Pro block schedule (4 sessions, ~2.5 hours of premium work — v0.3):**

| Block | Trigger step | What V4 Pro does | Conditional? |
|:---:|:---:|---|:---:|
| **C2-V4P12** Transform truth + coordinate contract + scene-manifest v1 schema | After C2-2.5 (M3 transform+coord+schema brief ready) | Reviews M3's data + draft schema; locks 3 binding decisions (was 2 in v0.2 split) | No (guaranteed) |
| **C2-V4P3** Material-closure escalation | After C2-3.5 (closure rate known) | Rethinks approach if rate is 50-79% | **Yes** (skipped if ≥80%) |
| **C2-V4P4** Scale-out feasibility | After C2-6.5 (perf data ready) | Decides whole-live vs bounded cohort | No (guaranteed) |
| **C2-V4P5** Ship/kill decision | After C2-7.3 (success/kill evidence ready) | Final ship or kill call | No (guaranteed) |

**4 model switches total** (M3 → V4 Pro → M3, repeated 4 times). All switches happen at *boundaries*, never mid-step.

> **Note on autonomy:** This assistant is M3 only. When the plan says "V4 Pro does X", the user must manually switch models and paste the M3-prepared input brief. The plan is built around this discipline.

---

## 3. Switch notification conventions

Throughout this plan, look for these markers:

- **`🔄 SWITCH-TO-V4-PRO`** — Pause M3, switch to V4 Pro, paste the M3-prepared input brief (in `docs/roadmap/cycle-2-briefs/block-N-*.md`)
- **`🔄 SWITCH-BACK-TO-M3`** — V4 Pro session complete, paste the V4 Pro output back to M3, switch back

**V4 Pro session template (per block):**

1. M3 reads the brief at `docs/roadmap/cycle-2-briefs/block-N-*.md`
2. M3 prepares the input data (the 1-page data brief)
3. M3 prints `🔄 SWITCH-TO-V4-PRO` and waits
4. User switches to V4 Pro, pastes the brief + data
5. V4 Pro works for ~45-60 min (V4P12 combined; shorter ~30-45 min for V4P3/V4P4/V4P5), returns a 1-page decision doc
6. User pastes V4 Pro's output to M3
7. M3 prints `🔄 SWITCH-BACK-TO-M3` and implements the decision

> **v0.3 note:** Block 1 is the combined transform+coord+schema session (`C2-V4P12`). Expected length 45-60 min (was 30-45 in v0.2 split).

---

## 4. Resume protocol (cold start)

When any agent (or human) opens this repo to make progress on cycle 2, in this order:

1. **Read** `docs/roadmap/current-phase.md` — confirms cycle 2 is active
2. **Read** `Assets/build/cycle-2/.state.json` — current step is `current_phase.current_step`
3. **Read** the latest handoff in `docs/handoffs/` matching `*cycle-2*`
4. **Read** the **Pre-flight** section of the current step below
5. **Execute** the step per its **Prompt template** and **Expected output**
6. **Validate** per the step's **Acceptance** checks
7. **Update** `.state.json` with the new current step + last handoff
8. **Commit** with the convention `cycle2: <short description>`
9. **Hand off** by writing `docs/handoffs/2026-MM-DD-cycle-2-phase-N-exit.md` (when phase exits)

---

## 5. Drift prevention (cross-phase invariants)

| Rule | Programmatic check |
|---|---|
| All cycle-2 outputs under `Exports/discovery-plan/cycle-2/` | `ls Assets/Exports/discovery-plan/cycle-2/` |
| State file at `Assets/build/cycle-2/.state.json` (gitignored) | `git check-ignore Assets/build/cycle-2` |
| Never write to `Source/`, `Extracted/`, or shared `Exports/` root | (convention; no script checks) |
| Live install is read-only | grep for write paths in cycle 2 scripts |
| Every step has evidence | `ls Assets/Exports/discovery-plan/cycle-2/stage{N}/` |
| Schemas validate | `python -c "import jsonschema; jsonschema.validate(...)"` |
| No mid-step model switches | `.state.json` `v4_pro_blocks` entries have explicit timestamps |
| V4 Pro sessions ≤ 5 | `.state.json` `v4_pro_sessions_used` field |
| One phase = one handoff doc | `ls docs/handoffs/*cycle-2-phase{N}-*` |

---

## 6. Phase C2-1 — M3 Bootstrap (Steps C2-1.1 to C2-1.5)

**Model:** M3 only
**Wall-clock estimate:** 1-2 days
**Goal:** Confirm baseline, snapshot scene-graph state, define cohort, lock the cycle charter.

### C2-1.1 — Re-confirm completion baseline

| Field | Value |
|---|---|
| **Agent** | M3 (this assistant) |
| **Pre-flight** | `git status --short` clean |
| **Prompt template** | "Run `dotnet build RiftAssetDumper.slnx --nologo`, `dotnet test RiftAssetDumper.slnx --nologo`, `pytest tests/`, `ruff check scripts/`, `mypy scripts/ --no-error-summary`. Re-run all 8 proof guards: `python scripts/rift_workflow.py attribute-extra-proof-guard --full --skip-build` and the 7 other guards. Snapshot outputs to `Assets/Exports/discovery-plan/cycle-2/stage1/baseline/`. Write `baseline.json` with timestamps + pass/fail per check." |
| **Expected output** | `Assets/Exports/discovery-plan/cycle-2/stage1/baseline/baseline.json` (8 guard results, build/test/pytest/ruff/mypy) |
| **Acceptance** | All checks green; baseline JSON exists and is valid |
| **Resume marker** | `baseline.json` with `all_green: true` |
| **Commit** | `cycle2: stage 1.1 baseline snapshot` |

### C2-1.2 — Snapshot scene-graph artifacts

| Field | Value |
|---|---|
| **Agent** | M3 |
| **Pre-flight** | C2-1.1 done |
| **Prompt template** | "Read `docs/handoffs/2026-06-10-flythrough-bridge-closure.md` and `docs/handoffs/2026-06-09-half-float-investigation-live-expansion.md`. Identify all scene-graph-related artifacts: `world.json` samples, `scene-graph-v1.schema.json`, `batch_scene_graph.py`, the 4 known non-identity-transform asset IDs. Copy them under `Assets/Exports/discovery-plan/cycle-2/stage1/artifacts/`. Write `artifacts.md` listing what was copied and why." |
| **Expected output** | `Assets/Exports/discovery-plan/cycle-2/stage1/artifacts/` populated + `artifacts.md` |
| **Acceptance** | Artifacts dir exists; MD lists ≥4 scene-graph items |
| **Resume marker** | `artifacts.md` |
| **Commit** | `cycle2: stage 1.2 scene-graph artifacts snapshot` |

### C2-1.3 — Audit `scripts/batch_scene_graph.py`

| Field | Value |
|---|---|
| **Agent** | M3 |
| **Pre-flight** | C2-1.2 done |
| **Prompt template** | "Read `scripts/batch_scene_graph.py` in full. Document: (1) hash extraction logic and edge cases, (2) output path semantics (`RiftFlythrough/objs/<hash>.obj.manifest.json`), (3) failure modes (no NiNodes, no probe output, file race), (4) implicit cohort (which assets are in `merged.obj`?), (5) what it assumes about `world.json`. Write `audit.md` with these 5 sections." |
| **Expected output** | `Assets/Exports/discovery-plan/cycle-2/stage1/audit.md` |
| **Acceptance** | Audit exists; 5 sections populated; ≥3 failure modes identified |
| **Resume marker** | `audit.md` |
| **Commit** | `cycle2: stage 1.3 batch_scene_graph.py audit` |

### C2-1.4 — Define curated cohort

| Field | Value |
|---|---|
| **Agent** | M3 |
| **Pre-flight** | C2-1.3 done |
| **Prompt template** | "Pick ~20-30 cohort assets (v0.3; was 30-50 in v0.2): (1) 4 known non-identity-transform assets, (2) 5 from each top MeshSize family (325, 305, 329, 321), (3) 3 edge cases (multi-mesh, MB-variant, orphan-mesh). Document each cohort member with: ID, family, why chosen, expected manifest output. Write `cohort.json` with the list + a `cohort.md` summary." |
| **Expected output** | `Assets/Exports/discovery-plan/cycle-2/stage1/cohort.json` + `cohort.md` |
| **Acceptance** | Cohort has 20-30 entries; documented rationale per entry; validates as JSON |
| **Resume marker** | `cohort.json` |
| **Commit** | `cycle2: stage 1.4 curated cohort defined` |

### C2-1.5 — Charter + Phase 1 handoff

| Field | Value |
|---|---|
| **Agent** | M3 |
| **Pre-flight** | C2-1.4 done |
| **Prompt template** | "Write `docs/handoffs/2026-06-12-cycle-2-phase-1-exit.md` with: (1) success criteria (from §0 of this plan), (2) kill criteria, (3) premium-session allocation table, (4) cohort definition summary, (5) baseline snapshot reference. Update `.state.json`: phase C2-1 → done, current_step → C2-2.1, last_handoff → phase-1-exit path." |
| **Expected output** | Handoff doc + updated `.state.json` |
| **Acceptance** | Handoff exists; `.state.json` updated; all C2-1 steps marked done |
| **Resume marker** | `.state.json` shows `current_phase=C2-2, current_step=C2-2.1` |
| **Commit** | `cycle2: stage 1.5 charter + phase 1 handoff` |

### C2-1 phase exit criteria

- [ ] All 5 sub-steps ✅ in `.state.json`
- [ ] Baseline snapshot archived
- [ ] Cohort file exists and validates
- [ ] Charter handoff written
- [ ] All 8 proof guards PASS
- [x] `dotnet build/test/pytest/ruff/mypy` all green
- [ ] No V4 Pro session used yet

---

## 7. Phase C2-2 — M3 Transform + Coordinate Data Collection (Steps C2-2.1 to C2-2.5)

**Model:** M3 only (V4 Pro is C2-V4P12, after this phase)
**Wall-clock estimate:** 1-2 days
**Goal:** Gather all the data V4 Pro will need to make the transform truth model, coordinate contract, AND scene-manifest v1 schema design decisions (all three locked in the same session).

> **v0.3 merge note:** In v0.2, this was two phases (C2-2 transform data, C2-3 coordinate data) feeding two V4 Pro sessions (V4P1, V4P2). v0.3 merges them into one phase + one combined V4 Pro session (V4P12), saving 1 handoff + 1 premium session.

### C2-2.1 — Collect T/R/S examples across cohort

### C2-2.2 — Compare patterns across siblings + repeated families

### C2-2.3 — Identify root-node vs mesh-node semantics

### C2-2.4 — Coordinate contract + schema sketch (handedness, axis, quaternion, scale + schema field set)

### C2-2.5 — Stage 2 handoff + combined brief for V4 Pro Block 1

| Step | Pre-flight | Expected output | Acceptance | Commit prefix |
|---|---|---|---|---|
| C2-2.1 | C2-1.5 done; cohort file exists | `stage2/transform-examples.json` with T/R/S per asset | JSON has 20+ entries; all fields finite | `cycle2: stage 2.1` |
| C2-2.2 | C2-2.1 done | `stage2/pattern-comparison.md` | Identifies ≥2 patterns | `cycle2: stage 2.2` |
| C2-2.3 | C2-2.2 done | `stage2/semantics.md` with root vs mesh decision tree | ≥3 cases documented | `cycle2: stage 2.3` |
| C2-2.4 | C2-2.3 done | `stage2/coordinate-contract.md` (handedness/axis/quaternion/scale decisions) + `stage2/schema-sketch.md` (v1 field set) | Both files have evidence-backed decisions; schema validates as draft JSON Schema 2020-12 | `cycle2: stage 2.4` |
| C2-2.5 | C2-2.4 done | `stage2/combined-brief.md` (1 page for V4P12) + handoff + `.state.json` updated | Brief has transform+coord+schema data + 3-5 open questions; state advanced | `cycle2: stage 2.5` |

---

## 🔄 8. V4 Pro Block 1 — Transform truth + coordinate contract + scene-manifest v1 schema (C2-V4P12)

**🔄 SWITCH-TO-V4-PRO**

When C2-2.5 is done, switch to V4 Pro. The pre-drafted input brief is at:

```
docs/roadmap/cycle-2-briefs/block-1-transform-schema.md
```

V4 Pro returns a 1-page decision doc with 3 binding decisions:

1. **Transform truth model** — which NiNode(s) drive world placement
2. **Coordinate contract** — handedness, axis, quaternion format, scale mode
3. **Scene-manifest v1 schema** — locked field set + types

**Expected V4 Pro session length:** 45-60 min (combined; was 30-45 in v0.2 split)

After V4 Pro returns, M3 implements the decisions in:

- `scripts/batch_scene_graph.py` (transform extraction)
- `docs/schemas/scene-manifest-v1.schema.json` (locked v1 schema)

V4 Pro session counter: **1/4 used**.

**🔄 SWITCH-BACK-TO-M3**

---

## 10. Phase C2-3 — M3 Material Closure (Steps C2-3.1 to C2-3.5) — was C2-4 in v0.2

**Model:** M3 only (V4 Pro is C2-V4P3, conditional)
**Wall-clock estimate:** 1-2 days
**Goal:** Quantify texture/material closure rate on the cohort.

### C2-3.1 — Re-baseline texture-link coverage

### C2-3.2 — Map meshes to texture/material references

### C2-3.3 — Add provenance markers

### C2-3.4 — Define "materialized asset bundle" + closure rate

### C2-3.5 — Stage 3 handoff + closure-rate decision

| Step | Pre-flight | Expected output | Acceptance | Commit prefix |
|---|---|---|---|---|
| C2-3.1 | C2-2.5 + V4P12 done | `stage3/texture-coverage.json` per cohort asset | All 25+ assets profiled | `cycle2: stage 3.1` |
| C2-3.2 | C2-3.1 done | `stage3/material-map.json` | Per-asset resolution chain | `cycle2: stage 3.2` |
| C2-3.3 | C2-3.2 done | `stage3/provenance.json` | `provenance` field populated | `cycle2: stage 3.3` |
| C2-3.4 | C2-3.3 done | `stage3/closure-rate.md` | Materialized rate computed | `cycle2: stage 3.4` |
| C2-3.5 | C2-3.4 done | Handoff + closure-rate decision | State advanced | `cycle2: stage 3.5` |

### 🚦 Closure rate decision (CRITICAL GATE at C2-4.5)

| Closure rate | Action |
|---|---|
| **≥80%** | Skip C2-V4P3. Continue to C2-5. |
| **50-79%** | Pause. Spawn **C2-V4P3** (V4 Pro escalation) to rethink the closure approach. |
| **<50%** | **KILL the cycle.** Write `docs/handoffs/2026-MM-DD-cycle-2-killed.md` with the kill rationale. Save 4 V4 Pro sessions for the next cycle. |

---

## 🔄 11. V4 Pro Block 3 — Material-closure escalation (C2-V4P3, conditional)

**🔄 SWITCH-TO-V4-PRO** (only if closure rate is 50-79%)

The pre-drafted input brief is at:

```
docs/roadmap/cycle-2-briefs/block-3-material-closure.md
```

V4 Pro returns a revised closure approach.

**🔄 SWITCH-BACK-TO-M3**

---

## 12. Phase C2-4 — M3 Batch Reconstruction (Steps C2-4.1 to C2-4.5)

**Model:** M3 only
**Wall-clock estimate:** 1-2 days
**Goal:** Generate per-asset manifests for the cohort using the V4P12-locked schema; build aggregate pack, deduplicate, emit stats.

### C2-4.1 — Generate per-asset manifests

### C2-4.2 — Build aggregate scene-manifest pack

### C2-4.3 — Deduplicate repeated transforms/refs

### C2-4.4 — Emit summary stats

### C2-4.5 — Stage 4 handoff

| Step | Pre-flight | Expected output | Acceptance | Commit prefix |
|---|---|---|---|---|
| C2-4.1 | C2-2.5 + V4P12 done | Per-asset manifests for full cohort | ≥95% of cohort has manifest | `cycle2: stage 4.1` |
| C2-4.2 | C2-4.1 done | `scene-manifest-pack-v1.json` | Pack validates against v1 schema | `cycle2: stage 4.2` |
| C2-4.3 | C2-4.2 done | Deduplicated pack + size-delta report | Dedupe ratio documented | `cycle2: stage 4.3` |
| C2-4.4 | C2-4.3 done | `stage4/coverage-stats.md` | Coverage, failures, missing textures tabulated | `cycle2: stage 4.4` |
| C2-4.5 | C2-4.4 done | Handoff + `.state.json` updated | 9th guard (scene-manifest) PASS | `cycle2: stage 4.5` |

---

## 13. Phase C2-5 — M3 Consumer Validation (Steps C2-5.1 to C2-5.5) — was C2-7 in v0.2

**Model:** M3 only
**Wall-clock estimate:** 1-2 days
**Goal:** Test ingestion in RiftFlythrough, validate visually, attribute failures.

### C2-5.1 — Test ingestion in RiftFlythrough

### C2-5.2 — Visual placement validation

### C2-5.3 — Texture/material resolution validation

### C2-5.4 — Mismatch taxonomy

### C2-5.5 — Schema-vs-consumer attribution

| Step | Pre-flight | Expected output | Acceptance | Commit prefix |
|---|---|---|---|---|
| C2-5.1 | C2-4.5 done | `stage5/ingestion-test.md` | RiftFlythrough load + console errors | `cycle2: stage 5.1` |
| C2-5.2 | C2-5.1 done | `stage5/visual-validation/` with screenshots | Meshes at distinct positions | `cycle2: stage 5.2` |
| C2-5.3 | C2-5.2 done | `stage5/material-resolution.md` | Resolved + missing categories | `cycle2: stage 5.3` |
| C2-5.4 | C2-5.3 done | `stage5/mismatch-taxonomy.md` | Mismatches categorized | `cycle2: stage 5.4` |
| C2-5.5 | C2-5.4 done | `stage5/attribution-table.md` + handoff | Each mismatch → schema or consumer | `cycle2: stage 5.5` |

**🔄 SWITCH-TO-V4-PRO**

Pre-drafted input brief at:

```
docs/roadmap/cycle-2-briefs/block-2-schema-design.md
```

V4 Pro reviews the draft schema, refines the field set, returns the locked v1.

**Expected V4 Pro session length:** 45-60 min

After V4 Pro returns, M3 implements the locked schema in `docs/schemas/scene-manifest-v1.schema.json`.

V4 Pro session counter: **2/5 used** (or 3/5 if C2-V4P3 fired).

**🔄 SWITCH-BACK-TO-M3**

---

## 14. Phase C2-6 — M3 Scale-out (Steps C2-6.1 to C2-6.5) — was C2-8 in v0.2

**Model:** M3 only
**Wall-clock estimate:** 1-2 days
**Goal:** Expand from ~25 cohort to 200-500 assets, profile performance, optimize, decide whole-live feasibility.

### C2-6.1 — Define expanded cohort (200-500 assets)

### C2-6.2 — Profile runtime, timeouts, archive hot spots

### C2-6.3 — Optimize batching/caching/reuse

### C2-6.4 — Re-run closure stats at scale

### C2-6.5 — Stage 6 handoff + scale-out brief for V4 Pro

| Step | Pre-flight | Expected output | Acceptance | Commit prefix |
|---|---|---|---|---|
| C2-6.1 | C2-5.5 done | `stage6/expanded-cohort.json` | 200-500 assets defined | `cycle2: stage 6.1` |
| C2-6.2 | C2-6.1 done | `stage6/perf-profile.md` | Wall-clock per asset, archive hot spots | `cycle2: stage 6.2` |
| C2-6.3 | C2-6.2 done | Optimized runner + new wall-clock | Optimization measurable | `cycle2: stage 6.3` |
| C2-6.4 | C2-6.3 done | `stage6/scaled-closure.md` | Closure rate at scale | `cycle2: stage 6.4` |
| C2-6.5 | C2-6.4 done | Handoff + `stage6/scale-out-brief.md` (1 page for V4 Pro) | Brief has perf + closure + question | `cycle2: stage 6.5` |

---

## 15. Phase C2-7 — M3 Validation + V4 Pro Ship/Kill (Steps C2-7.1 to C2-7.5) — was C2-9 in v0.2

**Model:** M3 (C2-7.1 to C2-7.3) + V4 Pro (C2-V4P5)
**Wall-clock estimate:** 1 day
**Goal:** Add scene-manifest validation test + 9th guard; full CI run; ship/kill decision.

### C2-7.1 — Add `test_scene_manifest_validation.py`

### C2-7.2 — Add `scene_manifest_validation_guard` (9th guard)

### C2-7.3 — Full CI validation

### C2-7.4 — Write cycle-2-ship-kill-brief.md + draft handoff

### C2-7.5 — Final handoff commit (after V4P5)

| Step | Pre-flight | Expected output | Acceptance | Commit prefix |
|---|---|---|---|---|
| C2-7.1 | C2-6.5 + V4P4 done | `tests/test_scene_manifest_validation.py` | Tests pass | `cycle2: stage 7.1` |
| C2-7.2 | C2-7.1 done | `scripts/cycle_2_validation_guard.py` | 9/9 guards PASS | `cycle2: stage 7.2` |
| C2-7.3 | C2-7.2 done | CI run report | All green | `cycle2: stage 7.3` |
| C2-7.4 | C2-7.3 done | `stage7/cycle-2-ship-kill-brief.md` + draft handoff | Brief has criteria + evidence | `cycle2: stage 7.4` |
| C2-7.5 | C2-V4P5 done | Final handoff + commit | Decision recorded; state → done or killed | `cycle2: stage 7.5` |

---

## 17. V4 Pro Block 4 — Scale-out feasibility (C2-V4P4) — was §17 in v0.2, kept identical in v0.3

**🔄 SWITCH-TO-V4-PRO**

Pre-drafted input brief at:

```
docs/roadmap/cycle-2-briefs/block-4-scale-out.md
```

V4 Pro returns a binding decision: whole-live scanning yes/no + cohort size to freeze at.

**Expected V4 Pro session length:** 20-30 min

V4 Pro session counter: **3/5 used** (or 4/5 if C2-V4P3 fired).

**🔄 SWITCH-BACK-TO-M3**

---

## 16. Phase C2-7 — M3 Validation + V4 Pro Ship/Kill (Steps C2-7.1 to C2-7.5) — was C2-9 in v0.2

**Model:** M3 (C2-7.1 to C2-7.3) + V4 Pro (C2-V4P5)
**Wall-clock estimate:** 1 day

### C2-7.1 — Add `test_scene_manifest_validation.py`

### C2-7.2 — Add `scene_manifest_validation_guard` (9th guard)

### C2-7.3 — Full CI validation

### C2-7.4 — Write cycle-2-ship-kill-brief.md + draft handoff

### C2-7.5 — Final handoff commit (after V4P5)

---

## 🔄 19. V4 Pro Block 5 — Ship/kill decision (C2-V4P5)

**🔄 SWITCH-TO-V4-PRO**

Pre-drafted input brief at:

```
docs/roadmap/cycle-2-briefs/block-5-ship-kill.md
```

V4 Pro returns an explicit decision: SHIP / KILL / SHIP-WITH-FOLLOWUPS + rationale + follow-up items.

**Expected V4 Pro session length:** 20-30 min

V4 Pro session counter: **4/5 used** (or 5/5 if C2-V4P3 fired). The 5th session is reserved for post-cycle surprises.

**🔄 SWITCH-BACK-TO-M3**

---

## 20. Execution dependencies (DAG) — v0.3

```
C2-1 (Bootstrap) ──► C2-2 (Transform + Coordinate data) ──► 🔄 C2-V4P12 (transform + coord + schema)
                                                                       │
                                                                       ▼
                                          C2-3 (Material closure) ◄──┘
                                                │
                                                ├── if closure ≥80%: skip V4P3
                                                ├── if closure 50-79%: ──► 🔄 C2-V4P3
                                                └── if closure <50%: KILL CYCLE
                                                                                │
                                                                                ▼
                                                                       C2-4 (Batch reconstruction)
                                                                                │
                                                                                ▼
                                                                       C2-5 (Consumer validation)
                                                                                │
                                                                                ▼
                                                                       C2-6 (Scale-out)
                                                                                │
                                                                                ▼
                                                                          🔄 C2-V4P4
                                                                                │
                                                                                ▼
                                                                       C2-7 (Validation + ship/kill)
                                                                                │
                                                                                ▼
                                                                          🔄 C2-V4P5
                                                                                │
                                                                                ▼
                                                                          SHIP / KILL
```

> **v0.3 diff from v0.2**: Removed C2-5 (schema prep) as a separate phase — folded into C2-2.4 + V4P12. Merged C2-2 (transform data) + C2-3 (coordinate data) into single C2-2 phase. Numbering shift: old C2-2/3/4/5/6/7/8/9 (8 phases) → new C2-2/3/4/5/6/7 (7 phases; C2-2 is the merged phase).

---

## 21. Drift prevention (cross-phase invariants)

| Rule | Programmatic check |
|---|---|
| `.state.json` is the single source of truth for "what's next" | `cat Assets/build/cycle-2/.state.json` |
| Each step has evidence | `ls Assets/Exports/discovery-plan/cycle-2/stage{N}/` |
| State file is gitignored but never deleted | `git check-ignore Assets/build/cycle-2` |
| Each phase has a handoff | `ls docs/handoffs/*cycle-2-phase{N}-*` |
| Schemas validate | `python -c "import jsonschema, json; jsonschema.validate(json.load(open(p)), json.load(open(s)))"` |
| All C# changes go through `dotnet build` + `dotnet test` | `dotnet build RiftAssetDumper.slnx --nologo && dotnet test RiftAssetDumper.slnx --nologo` |
| All Python changes go through ruff + mypy + tests | `ruff check scripts/ tests/ && mypy scripts/ tests/ --no-error-summary && pytest tests/ -q` |
| V4 Pro sessions ≤ 5 | `cat .state.json \| grep v4_pro_sessions_used` |
| No mid-step model switches | V4 Pro blocks have explicit `used_at` timestamps |

---

## 22. Optimal agent routing

| Work type | Agent | Model | Why |
|---|---|---|---|
| M3 default work | M3 (this assistant) | M3 (unlimited) | Volume work, multimodal, file pickers, code search, routine edits |
| Routine Python script | M3 | M3 | M3 is the right default for Python |
| New C# command, complex | `cs-architect-gpt` (when available) | DeepSeek V4 Pro | Multi-step reasoning across 15K-line `Program.cs` |
| Stream data investigation | `investigator-gpt` (when available) | DeepSeek V4 Pro | Pattern recognition, experimental decode |
| Schema design | DeepSeek V4 Pro (V4P2 block) | DeepSeek V4 Pro | Cross-system contract design |
| Decision choke points | DeepSeek V4 Pro (V4P1, V4P4, V4P5) | DeepSeek V4 Pro | Multi-step reasoning, "when to call it" |
| Code review | M3 or `code-reviewer-minimax-m3` | M3 | Mechanical, well-bounded |
| Smoke command runs | `basher` | — | Shell only, no LLM |

---

## 23. Time & budget projection (v0.3)

| Phase | M3 wall-clock | V4 Pro | V4 Pro block | Cumulative |
|---|:---:|:---:|:---:|:---:|
| C2-1 Bootstrap | 1-2 days | — | — | 1-2 days |
| C2-2 Transform + coordinate data (merged v0.3) | 1-2 days | — | — | 2-4 days |
| C2-V4P12 (transform + coord + schema) | — | 1 session | Block 1 (combined) | 2-4 days + ~60 min |
| C2-3 Material closure | 1-2 days | — (or 1 session) | (Block 3 if needed) | 3-6 days |
| C2-4 Batch reconstruction (was C2-6 in v0.2) | 1-2 days | — | — | 4-8 days |
| C2-5 Consumer validation (was C2-7 in v0.2) | 1-2 days | — | — | 5-10 days |
| C2-6 Scale-out (was C2-8 in v0.2) | 1-2 days | — | — | 6-12 days |
| C2-V4P4 | — | 1 session | Block 4 | 6-12 days + ~30 min |
| C2-7 Validation + ship/kill (was C2-9 in v0.2) | 1 day | — | — | 7-13 days |
| C2-V4P5 | — | 1 session | Block 5 | 7-13 days + ~30 min |

**Total:** ~7-13 days (1-2.5 weeks) for the full cycle (v0.3; was 10-16 days in v0.2).
**V4 Pro sessions:** 3 guaranteed, 4 if C2-V4P3 fires (v0.3; was 4-5 in v0.2).
**M3 wall-clock:** 5-10 days of M3 work (v0.3; was 7-13 in v0.2).
**Saves:** ~3 days wall-clock + 1 V4 Pro session from the C2-2+C2-3 merge and V4P1+V4P2 combination.

---

## 24. Related documents

- `docs/roadmap/current-phase.md` — pointer to active plan (will be updated to point here)
- `docs/roadmap/project-roadmap.md` — the **separate** Phase 0–49 plan (NIF parser/descriptor work, COMPLETE)
- `docs/roadmap/flythrough-bridge-plan.md` — the **separate** FT plan (consumer-app integration, COMPLETE)
- `docs/discovery-plan-50.md` — the **separate** Cycle 1 plan (Step 50/50 closed)
- `docs/50-step-plan-current-position.md` — Cycle 1 closure position
- `docs/handoffs/` — session handoffs (one per C2 phase completion)
- `docs/schemas/` — JSON schemas (existing + new ones for C2)
- `docs/roadmap/cycle-2-briefs/` — 5 pre-drafted V4 Pro input briefs
- `Assets/build/cycle-2/.state.json` — gitignored state file
- `Assets/Exports/discovery-plan/cycle-2/` — all cycle-2 outputs
- `knowledge.md` — top-level project knowledge (will be updated to reference this plan)
- `C:/RIFT MODDING/RiftFlythrough/knowledge.md` — consumer-side project knowledge

---

*Last updated: 2026-06-15 (v0.3 — cohort 39→26, C2-2+C2-3 merged, V4P1+V4P2 combined)*
