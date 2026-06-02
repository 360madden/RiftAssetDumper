# Post-50 meshSize=329 Family — Role & Binding Pattern Analysis (Autonomous Cycle)

Date: 2026-06
Parent: `docs/handoffs/2026-06-post50-mesh329-family-evidence-update.md`

## Objective (Autonomous Choice)

After confirming the full family scale (23 evidence groups / 46 links), the next optimal step was to move from aggregate family proof to **per-mesh deep role analysis** on the strongest examples. This follows the Aggressive Evidence Workflow cadence: family existence → detailed structural comparison on top representatives.

## Top Examples Probed

1. `0364ea142bc00ce7` (48 primary vectors) — strongest example that also appeared in prior extra-stream compare.
2. `f2c347fe81a5e3b2` (64 primary vectors) — one of the largest payloads in the family.

Both were probed on mesh-block 7 and mesh-block 34 (the recurring sibling pair in this family).

## Key Findings — Repeatable Pattern

### Consistent Configuration on mesh#7 (in this family)
- `attributeSets = 1`
- Position stream: `@212 → #28` (payload varies 576–768), role=`position-float3-ror1-lead` (c=75)
- Normal stream: `@220 → #29` (or equivalent), role=`normal-float3-ror1-lead` (c=85)
- UV stream: `@304 → #33`, role=`uv-float2-ror1-lead` (c=80)
- Extra u32-repeated-pattern body at `@296 → #32`

### Consistent Configuration on mesh#34 (sibling)
- `attributeSets = 0`
- Shares the **exact same** primary position reference: `@212 → #28`, role=`position-float3-ror1-lead` (c=75)
- Own normal stream (different block, e.g. #53)
- Own `@304` stream (e.g. #57) is classified by the probe as **position-float3-ror1-lead** (c=75), **not** UV
- Same extra u32 pattern body at `@296`

## Interpretation (Candidate-Only)

This reveals a **repeatable structural variant** within the meshSize=329 source-binding family:

- mesh#7 instances appear to carry "full" attribute sets (position + normal + UV) using the shared primary position source.
- mesh#34 instances re-use the identical primary position source (`@212/#28`) but present a different vertex attribute layout:
  - No complete attribute set recognized by current probe logic.
  - Their `@304` stream is being interpreted as a secondary/duplicate position stream rather than texture coordinates.
  - This may indicate lower-LOD geometry, alternative vertex format, or a different binding convention for the same underlying position data.

The u32-repeated-pattern body at @296 is consistently present on both but does not participate in the main attribute sets in these examples.

## Updated Blockers

- `mesh34-complete-geometry-binding-not-proven` (still holds — attributeSets=0 on mesh#34)
- `mesh329-variant-attribute-layout-not-classified` (new)
- `position-vs-extra-stream-role-ambiguity-in-siblings` (new)
- `parser-export-promotion-not-allowed`

## Value of This Evidence

This is higher-resolution than pure family counting. We now have concrete, repeatable differences in how the two mesh variants in the family consume the shared position source. This is excellent input for future:
- Role scoring refinement
- Attribute set completion proofs
- Binding guard development
- Potential discovery of LOD / variant handling in the RIFT NIF data

## Generated Artifacts (this autonomous cycle)
- `Exports/probe-nif-mesh-0364ea142bc00ce7.json` (both blocks)
- `Exports/probe-nif-mesh-f2c347fe81a5e3b2.json` (both blocks)

All outputs under ignored Exports/.

## Validation
- GeneratedOutputGuard passed on all runs.
- No policy violations (all candidate-only, offline, Python-driven).

## Autonomous Next Lead Recommendation

After this role analysis, the highest-leverage continuation is one of:

**Option A (Recommended):** Targeted attribute-set completion analysis on the mesh#7 side of the strongest 329-family examples, combined with checking whether any mesh#34 examples ever achieve attributeSets > 0 under current parsing.

**Option B:** Apply the same deep probe + role comparison treatment to the #2 family (meshSize=305, stream@188, residual payload 288) to see if similar sibling + extra-position patterns exist there.

**Option C:** Invest in improving the stream role classifier / attribute set detection logic so that the current "candidate-only" status on mesh#34 can be more precisely characterized (or ruled out).

I will pause here and let the next autonomous decision (or user input) select among these, while keeping all evidence strictly gated.