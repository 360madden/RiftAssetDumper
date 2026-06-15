# Cycle 2 — Phase 1 Exit Handoff

**Date**: 2026-06-15
**Plan**: `cycle-2-scene-manifest-plan` v0.2
**Phase**: C2-1 (Bootstrap) — EXIT
**Status**: ✅ COMPLETE (5/5 sub-steps done)

---

## Success criteria (from §0 of the plan)

| Criterion | Status |
|---|---|
| Baseline snapshot archived (build/test/pytest/ruff/mypy) | ✅ `stage1/baseline/baseline.json` |
| Cohort file exists and validates (30-50 assets) | ✅ 39 assets, `stage1/cohort.json` |
| Scene-graph artifacts snapshotted | ✅ `stage1/artifacts/` (10 files) |
| `batch_scene_graph.py` audited (5 sections, ≥3 failure modes) | ✅ `stage1/audit.md` (10 failure modes, 6 recommendations) |
| Charter handoff written | ✅ This document |
| All 8 proof guards PASS | ✅ Baseline confirms |
| `dotnet build/test/pytest/ruff/mypy` all green | ⚠ 5/5 PASS; mypy has 2 pre-existing warnings in `tests/*` (not in scripts/), tracked |
| No V4 Pro session used yet | ✅ 0/5 used |

---

## Kill criteria (none triggered)

- Closure rate <50% would KILL the cycle. **Not yet applicable** — closure
  rate is computed at C2-4.5.
- `mypy` failure is **not** a kill criterion. The 2 warnings are in test
  files added on 2026-06-14 and are not introduced by cycle 2 work.

---

## Premium-session allocation (5 total, 0 used so far)

| Block | Used at | Status |
|---|---|---|
| **C2-V4P1** (transform truth + coordinate contract) | After C2-2.5 + C2-3.5 | ⏸ pending |
| **C2-V4P2** (schema v1 design lock) | After C2-5.5 | ⏸ pending |
| **C2-V4P3** (material-closure escalation) | Conditional — only if 50-79% closure | ⏸ pending |
| **C2-V4P4** (scale-out feasibility) | After C2-8.5 | ⏸ pending |
| **C2-V4P5** (ship/kill decision) | After C2-9.4 | ⏸ pending |

---

## Cohort definition summary (39 assets)

Full breakdown in `Assets/Exports/discovery-plan/cycle-2/stage1/cohort.md` and
`cohort.json`. Composition:

- 4 non-identity transform assets (C2-1.2 walk)
- 10 + 10 + 6 + 3 = 29 from top-4 MeshSize families (325, 321, 305, 329)
- 6 edge cases (multi-mesh 11, multi-mesh 32, large-hierarchy 17-node, MB-variant,
  orphan-mesh regression, pos-only no-texture)

**Cohort is a working subset, not durable truth.** C2-6 produces per-asset
manifests which are the durable cycle 2 output.

---

## Baseline snapshot reference

`Assets/Exports/discovery-plan/cycle-2/stage1/baseline/baseline.json` records:

- `dotnet build` ✅ 0 errors
- `dotnet test` ✅ 56/56 passed
- `pytest` ✅ 395 tests passed in ~5.7s
- `ruff` ✅ all checks passed
- `mypy` ⚠ 2 pre-existing warnings (textbook: missing type args for generic `dict`)
- 217 world.jsons at 100% coverage, 4 non-identity transforms
- 212/217 (97.7%) assets textured
- 7/7 promotion gates cleared, 8/8 proof guards passing

---

## The 4 non-identity-transform assets

Computed by walking the 217 `world.json` files through the same Scale → Rotate →
Translate accumulator used by `scripts/build_world_placed_merge.py`. These
are the only 4 assets where the world-placed merge actually shifts vertices:

| Asset | MeshSize | World translation | Scale | Notes |
|---|---|---|---:|---|
| `07f37c99a80da009` | 305 | `[8.8207, -0.8490, 0.0759]` | 1.0 | 12-node hierarchy |
| `2c85cfa17543443b` | 305 | `[-8.8207, 0.8490, -0.0759]` | 1.0 | Mirror sibling |
| `4a97d66a665a538e` | 240 | `[0.0, 0.0, 0.0]` | 1.0 | Identity translation, non-identity rotation |
| `593ea328978bde38` | 305 | `[-8.8207, 0.8490, -0.0759]` | 1.0 | Mirror sibling |

---

## Audit highlights (C2-1.3)

`stage1/audit.md` covers 5 sections (hash extraction, output path semantics,
10 failure modes, implicit cohort, world.json assumptions) + 6 deferred
recommendations for C2-5+.

**Key finding**: `batch_scene_graph.py` writes a thin `asset-mesh-manifest/v1`
that takes only `NiNodes[0]`, while the canonical scene-graph lives in a
separate `world.json` (scene-graph/v1). C2-5's `scene-manifest/v1` schema
must bridge these two.

---

## State transitions

State file: `Assets/build/cycle-2/.state.json`

- C2-1.1: `in_progress` → `done`
- C2-1.2: `pending` → `done`
- C2-1.3: `pending` → `done`
- C2-1.4: `pending` → `done`
- C2-1.5: `pending` → `done`
- C2-1 (phase): `in_progress` → `done`
- `current_phase`: `C2-1` → `C2-2`
- `current_step`: `C2-1.1` → `C2-2.1`
- `last_handoff`: → `docs/handoffs/2026-06-15-cycle-2-phase-1-exit.md`

---

## Next: C2-2 (Transform data collection)

The next phase covers 5 steps of M3 data prep:

- C2-2.1: collect T/R/S examples across the 39-asset cohort → `stage2/transform-examples.json`
- C2-2.2: compare patterns across siblings + repeated families → `stage2/pattern-comparison.md`
- C2-2.3: identify root-node vs mesh-node semantics → `stage2/semantics.md`
- C2-2.4: write the V4P1 input brief → `stage2/transform-data-brief.md`
- C2-2.5: M3 implements V4 Pro's decisions (BLOCKED until V4P1 returns)

Wall-clock: 1-2 days of M3 work. V4P1 (Block 1) gates C2-4 onward.

---

## Files committed (cycle 2 stage 1)

- `Assets/Exports/discovery-plan/cycle-2/stage1/baseline/baseline.json` (new)
- `Assets/Exports/discovery-plan/cycle-2/stage1/artifacts/artifacts.md` (new)
- `Assets/Exports/discovery-plan/cycle-2/stage1/artifacts/scene-graph-v1.schema.json` (copy)
- `Assets/Exports/discovery-plan/cycle-2/stage1/artifacts/scene-graph-manifest.json` (copy)
- `Assets/Exports/discovery-plan/cycle-2/stage1/artifacts/scripts/batch_scene_graph.py` (copy)
- `Assets/Exports/discovery-plan/cycle-2/stage1/artifacts/scripts/build_world_placed_merge.py` (copy)
- `Assets/Exports/discovery-plan/cycle-2/stage1/artifacts/worlds/*.world.json` (6 sample copies)
- `Assets/Exports/discovery-plan/cycle-2/stage1/audit.md` (new)
- `Assets/Exports/discovery-plan/cycle-2/stage1/cohort.json` (new, 39 assets)
- `Assets/Exports/discovery-plan/cycle-2/stage1/cohort.md` (new)
- `docs/handoffs/2026-06-15-cycle-2-phase-1-exit.md` (this file)

Note: `Assets/build/cycle-2/.state.json` is gitignored; the state advancement
is durable on disk but not in git history.
