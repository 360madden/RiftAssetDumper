# Post-50 meshSize=329 Source-Binding Family Evidence Update

Date: 2026-06 (current cycle)
Previous: `docs/handoffs/2026-05-26-final-50-step-session.md`

## Lead Selected (per Aggressive Evidence Workflow)

Strongest current offline signal per `post50-position-source-status`:

- `meshSize=329`, primary stream `@212/#28` (block 28), shared between mesh#7 and mesh#34.
- 23 evidence groups / 46 total links previously identified.

This cycle executed the two recommended narrow commands on this exact lead:

- `post50-mesh329-source-binding-compare` (smoke)
- `post50-mesh329-family-proof` (smoke)

## New Evidence (Candidate-Only)

### From `post50-mesh329-family-proof`
- Evidence groups: **23**
- Total stream links: **46**
- Distinct IDs: **23**
- Payload range: 168–924 bytes (very consistent remainder-0 pattern)
- All rows show shared `@212/#28` between mesh#7 and mesh#34.
- Family consistency checks: all passed.

### From `post50-mesh329-source-binding-compare`
- 3 detailed examples examined (IDs 0364ea14..., 04de9015..., 066fa520...).
- Primary @212/#28 vectors: 22–48
- mesh#34 carries consistent extra stream `@304/#57` (position-like role candidate) in addition to the shared primary.
- Extra vectors on mesh#34: 8–23
- mesh#34 attribute set count: **0** in examined examples
- mesh#34 UV streams: **0**
- Extra-to-primary vector ratios: 0.36–0.62

**Aggregate interpretation**: Strong, repeatable source-binding pattern. mesh#34 frequently appears as a "sibling + extra stream" variant of mesh#7 within the same family. No complete geometry bindings proven yet.

## Blockers (unchanged)
- `source-binding-family-candidate-only`
- `mesh34-complete-geometry-binding-not-proven`
- `parser-export-promotion-not-allowed`

## Updated Durable Truth

The meshSize=329 family remains the single strongest repeated source-binding signal in the current inventory. The pattern of mesh#7 and mesh#34 sharing `@212/#28` while mesh#34 often carries an additional `@304/#57` stream is now documented across 23 groups.

This is high-quality candidate evidence for future role scoring and binding proof work. It does **not** yet constitute exportable geometry.

## Next Recommended Lead (following cadence)

After strengthening the family proof:

1. **Highest priority**: Role / stream classification work on the primary (@212) and extra (@304) streams within this family (use mesh-probe + stream role scoring on top examples).
2. Parallel: Apply similar deep compare + proof treatment to the #2 family (meshSize=305, stream@188).
3. Longer term: Mesh-level attribute set completion checks on the strongest 329-family examples.

No live scanning or parser/export changes are warranted from this cycle.

## Artifacts Generated (this cycle)
- `Exports/post50-mesh329-source-binding-compare.json`
- `Exports/post50-mesh329-source-binding-compare.md`
- `Exports/post50-mesh329-family-proof.json`
- `Exports/post50-mesh329-family-proof.md`

All outputs correctly placed under ignored `Exports/`.

## Validation Performed
- GeneratedOutputGuard: passed (twice)
- Solution build: succeeded (pre-existing package warning only)

This cycle followed the approved Aggressive Evidence Workflow and post-50 guidance. All claims remain candidate-only.