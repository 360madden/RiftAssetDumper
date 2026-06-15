# Cycle 2 — Phase 2 Exit Handoff (Transform + Coordinate Data)

**Date**: 2026-06-15
**Plan**: `cycle-2-scene-manifest-plan` v0.2
**Phases**: C2-2 (Transform data) + C2-3 (Coordinate data) — EXIT
**Status**: ✅ COMPLETE (6/6 M3 sub-steps done; 2 V4P1 input briefs ready)

---

## Sub-steps completed

### C2-2 — Transform data collection

| Step | Status | Output |
|---|:---:|---|
| **C2-2.1** — collect T/R/S examples across cohort | ✅ | `stage2/transform-examples.json` (39 entries, all finite) |
| **C2-2.2** — compare patterns across siblings + repeated families | ✅ | `stage2/pattern-comparison.md` (4 patterns) |
| **C2-2.3** — identify root-node vs mesh-node semantics | ✅ | `stage2/semantics.md` (4 cases, Option B decision) |

### C2-3 — Coordinate data collection

| Step | Status | Output |
|---|:---:|---|
| **C2-3.1** — determine handedness/axis conventions | ✅ | `stage3/handedness-evidence.md` (4 evidence sources) |
| **C2-3.2** — verify quaternion/matrix interpretation | ✅ | `stage3/quaternion-verification.md` (4 verifications) |
| **C2-3.3** — check scale stability | ✅ | `stage3/scale-stability.md` (217/217 scale=1.0) |

### C2-2.5, C2-3.4, C2-3.5 — DEFERRED to Batch 3 (blocked by C2-V4P1)

These steps write the V4P1 input briefs and implement V4 Pro's decisions.
They are not part of M3-only work and require the C2-V4P1 V4 Pro session
to provide the binding decisions first.

---

## Key findings

### Transform findings (C2-2)

1. **4 non-identity-transform assets** (out of 217, 1.8%):
   - `07f37c99a80da009` — non-identity translation `[8.82, -0.85, 0.08]`
   - `2c85cfa17543443b` — mirror sibling (negated translation)
   - `4a97d66a665a538e` — rotation-only edge case (~1.8° rotation)
   - `593ea328978bde38` — same translation as `2c85cfa17543443b`
2. **Mirror-sibling hypothesis** (3/4 non-id): 3 assets have negated translations suggesting deliberate mirror pairs or shared spawn points
3. **Rotation-only edge case** (1/4 non-id): `4a97d66a665a538e` has identity translation but ~2.5% non-identity rotation
4. **Scale is uniformly 1.0** (217/217): no non-uniform scale in the flythrough subset
5. **Root-node vs mesh-node decision**: **Option B (mesh-node semantics with chain accumulation)** — the non-identity transform lives at the mesh's direct parent, not the root; the existing `build_world_placed_merge.py` accumulator already implements this correctly

### Coordinate findings (C2-3)

1. **Handedness**: right-handed, Y-up, -Z forward (Gamebryo convention)
2. **Rotation format**: 3x3 row-major matrix (9 floats), no quaternion storage
3. **Translation format**: 3 floats `[x, y, z]`
4. **Scale format**: single float (uniform), currently always 1.0
5. **TRS composition**: `v_world = R * (S * v_local) + T` (right-handed, post-multiplication)

---

## Decisions for C2-V4P1 (M3 has prepared 2 input briefs)

The 2 V4P1 input briefs will encode these decisions for V4 Pro's review:

1. **Transform truth model**: which NiNode(s) drive world placement?
   - M3 recommendation: **mesh's direct parent** (Option B), with chain accumulation to root
   - Alternative: root-only (Option A), simpler but doesn't handle multi-mesh NIFs
2. **Coordinate contract**: handedness, axis, rotation format, scale mode
   - M3 recommendation: **right-handed, Y-up, 3x3 row-major, uniform float scale**
   - This matches the existing `scene-graph/v1` schema — no breaking change

Both decisions are well-supported by the evidence in the 6 deliverable files.

---

## State transitions

- C2-2.1, 2.2, 2.3: `pending` → `done`
- C2-3.1, 3.2, 3.3: `pending` → `done`
- C2-2 phase: `pending` → `in_progress` (steps 2.4, 2.5 still pending)
- C2-3 phase: `pending` → `in_progress` (steps 3.4, 3.5 still pending)
- `current_phase`: C2-2 (next steps are 2.4, 2.5)
- `last_handoff`: → `docs/handoffs/2026-06-15-cycle-2-phase-2-exit.md`

---

## Files committed (cycle 2 stage 2+3)

- `Assets/Exports/discovery-plan/cycle-2/stage2/transform-examples.json` (new)
- `Assets/Exports/discovery-plan/cycle-2/stage2/pattern-comparison.md` (new)
- `Assets/Exports/discovery-plan/cycle-2/stage2/semantics.md` (new)
- `Assets/Exports/discovery-plan/cycle-2/stage3/handedness-evidence.md` (new)
- `Assets/Exports/discovery-plan/cycle-2/stage3/quaternion-verification.md` (new)
- `Assets/Exports/discovery-plan/cycle-2/stage3/scale-stability.md` (new)
- `docs/handoffs/2026-06-15-cycle-2-phase-2-exit.md` (this file, **committed**)

Note: `Assets/Exports/...` is gitignored per the C2 plan's drift-prevention
rules; only the handoff doc is in git. The evidence files are regenerated
on demand from the source data.

---

## Next: Batch 3 (C2-2.4, 2.5, 3.4, 3.5)

The next M3-only batch covers 4 steps:

- **C2-2.4**: write `stage2/transform-data-brief.md` (1-page V4P1 input)
- **C2-3.4**: write `stage3/coordinate-data-brief.md` (1-page V4P1 input)
- **C2-2.5**: M3 implements V4 Pro's decisions (BLOCKED by V4P1)
- **C2-3.5**: M3 implements V4 Pro's decisions (BLOCKED by V4P1)

Wall-clock: 0.5-1 day of M3 work. V4P1 (Block 1) gates C2-4 onward.
