# Phase 1 M1.2 Coordination — @304 Extra Stream Classification on mesh#34 Variants

**Status**: Attribute-extra-probe batch executor completed (2026-06); M1.1 complete; M1.2 active per `docs/roadmap/current-phase.md`. Analysis/quant subagent completed (produced `Exports/phase1-m1.2-@304-analysis-initial.json` + .md with per-ID tables, aggregates, candidate patterns). M1.2 handoff drafter completed (created `docs/handoffs/draft-2026-06-m1.2-@304-extra-stream-classification.md`). All candidate-only, strictly 329-family (meshSize=329), matrix targets only. Reference `docs/roadmap/phase1-m1.2-prep.md` + `Exports/mesh329-family-attribute-role-matrix.json`.

## Target List (from M1.1 matrix + prep)
Exact 8 top #34 from `Exports/mesh329-family-attribute-role-matrix.json` IDsCovered (prioritized per prep.md):
1. 69da9507d49c42ff
2. f2c347fe81a5e3b2
3. 07c733b4eee3ed2e
4. 83df87e22bff4a94
5. 0364ea142bc00ce7 (paired anchor)
6. 4eb7745610adf8c7
7. c5a1982e92e15b7b
8. 04de901531a091ab

## Batch Execution: attribute-extra-probe (Phase 1 M1.2)
Executed exactly per task + prep (using existing command only; --skip-build; 329 family; candidate-only):
- Command template (repeated for each): `python scripts/rift_workflow.py attribute-extra-probe --id <ID> --mesh-block 34 --extra-offset 304 --skip-build`

All 8 runs produced the same class of valid result data: "ERROR: no attribute extra stream was found at mesh payload offset @304 on NiMesh #34. No attribute extra streams were found for this mesh." (with JSON outputs in Exports/). This is key data for M1.2: the @304 "position" on #34 (from mesh-probe) is not a recognized "attribute extra" in the attr-probe logic (tied to attrSets=0 on #34).

Additional M1.2 supporting runs: refreshed sibling-extra-pos + compare (shows extra on the 3 anchors); stream-bodies for 69da #34 (14 valid bodies, top payloads incl. 456 (@304), signatures); for f2c3 #34 (similar, top 456/768); stream-endianness for 69da #34 (mixed-u16-body=12, big-endian-u16-lead=2). Swarm (analysis + handoff drafter) ingesting for quant tables and draft.

Swarm (analysis + handoff drafter) ingesting for quant tables and draft.
```
ERROR: no attribute extra stream was found at mesh payload offset @304 on NiMesh #34. No attribute extra streams were found for this mesh.
```
(Full dotnet command logged per run; C# exit 1; python wrapper raised "Step failed" but continued batch; GeneratedOutputGuard passed on every invocation.)

**Full per-ID command + outcome (from batch run logs):**
- 69da9507d49c42ff: `... --id 69da9507d49c42ff --mesh-block 34 --extra-offset 304 --out %WORKSPACE%\Exports\probe-nif-attribute-extra-69da9507d49c42ff-mesh34-extra304.json` → ERROR no attribute extra stream @304 on #34. (No JSON written.)
- f2c347fe81a5e3b2: `... --id f2c347fe81a5e3b2 ...probe-nif-attribute-extra-f2c347fe81a5e3b2-mesh34-extra304.json` → same ERROR.
- 07c733b4eee3ed2e: same pattern → ERROR (would-be: probe-nif-attribute-extra-07c733b4eee3ed2e-mesh34-extra304.json)
- 83df87e22bff4a94: same → ERROR (probe-nif-attribute-extra-83df87e22bff4a94-mesh34-extra304.json)
- 0364ea142bc00ce7: same → ERROR (probe-nif-attribute-extra-0364ea142bc00ce7-mesh34-extra304.json)
- 4eb7745610adf8c7: same → ERROR (probe-nif-attribute-extra-4eb7745610adf8c7-mesh34-extra304.json)
- c5a1982e92e15b7b: same → ERROR (probe-nif-attribute-extra-c5a1982e92e15b7b-mesh34-extra304.json)
- 04de901531a091ab: same → ERROR (probe-nif-attribute-extra-04de901531a091ab-mesh34-extra304.json)

**Raw JSONs in Exports/ (note naming):**
- No `probe-nif-attribute-extra-*-mesh34-extra304.json` written for any of the 8 (C# ProbeNifAttributeExtra returns before `File.WriteAllText` + report ctor when matches.Count==0 / attr extra not found at offset in attributeSets.ExtraStreams).
- Expected naming (per rift_workflow.py + C# ResolveOutputPath when --out has .json ext): `Exports/probe-nif-attribute-extra-<id>-mesh34-extra304.json`
- Existing related artifacts (from M1.1, used for cross-ref): `Exports/probe-nif-mesh-<id>-mesh34.json` (all 8 present), `Exports/mesh329-family-attribute-role-matrix.json` (and .md/.csv).
- Guard note: GeneratedOutputGuard passed for each run (no improper staging of generated data).

**Key fields extracted (from attribute-extra-probe outputs + cross-ref to mesh34 probe JSONs + matrix):**
- any extra streams found: **0** (explicit "No attribute extra streams were found for this mesh." for all 8 #34). Matches matrix "AttrExtraStreamCount": 0 .
- attributeSets (from mesh-probe JSONs + error context + matrix): 0 for all 8 (vs 1 on their #7 siblings).
- role/fit for target @304 stream (from mesh-probe JSON + matrix rows for #34): consistently "position-float3-ror1-lead" c=75 (even without being parsed as "attr extra").
  - Example payloads/vecs (from matrix/JSON): 69da: payload=456 (v~38); f2c3:304(~25v); 07c7:256; 83df:224; 0364:240; 4eb7:136; c5a1:200; 04de:280. (Scales with vertex coverage; lower than primary @212.)
- Streams at other key offsets (universal pattern across all 8, from mesh34 JSON extract):
  - @212/#28: position-float3-ror1-lead c=75 , payload scales with v (924 for 69da 77v down to 444 for 04de)
  - @296/#32: u32-repeated-pattern-body c=25 , payload ~4*v (e.g. 308 for 77v)
  - (normal @220 varies per ID)
- BodyFirst* (from mesh34 JSONs; detailed BodyFirst64/128 + histograms + samples are attribute-extra-probe JSON only and thus unavailable here):
  - @304 BodyFirst16 (unique per-ID, position-like floats encoded): 
    - 69da9507d49c42ff: a92cc2fd1bcf402ca52cc2da04cf4036
    - f2c347fe81a5e3b2: 9988c12e8a8b403e9c88c18bb78f4087
    - 07c733b4eee3ed2e: 5226c22ebb12416a7d26c2ccb512415e
    - 83df87e22bff4a94: d72dc24d31b440a3702dc2d28bb24026
    - 0364ea142bc00ce7: e525c24b420b41989825c2eba80b4165
    - 4eb7745610adf8c7: 022bc245761141fdb72ac22794114182
    - c5a1982e92e15b7b: 1f2ac2000b1241325529c25588144102
    - 04de901531a091ab: 022bc2500d074183022bc2c5390941e8
  - @212 BodyFirst16 (for comparison, also position): different per ID (e.g. 69da:87574189... ; 0364:993f4100...); @296 always "3a3aff3a3a3aff3a3a3aff3a3a3aff3a" (u32 repeated magic).
  - BodyFirst64 / BodyStats / histograms / index compat / PositionVertexSamples / MappingPositionFitness / GroupedViews / etc: **not present in outputs** (would be in successful attribute-extra-probe JSONs under ExtraStreams[0].* ; absent because no match in attributeSets.ExtraStreams for @304 when attrSets=0).
- Other: Matches=0; HeaderWarnings typically []; NifVersion consistent with family; probe targets the exact offset but parser path for "extra" (from FindNifMeshAttributeSets) yields empty for these #34 variants.
- Cross-ID consistency: 8/8 identical high-level pattern (attrSets=0 + @304 scored position c=75 + @296 u32 c=25 + primary pos@212 c=75). BodyFirst16 @304 vary (no obvious shared magic prefix in first16 across IDs).

**Links to artifacts:**
- Matrix (source of targets + @304 rows): `Exports/mesh329-family-attribute-role-matrix.json` (IDsCovered, MatrixRows for each with StreamsAt304 role/conf/payload/vec, AttrExtraStreamCount=0)
- Per-ID mesh34 probes (raw, used for BodyFirst16/roles): `Exports/probe-nif-mesh-*-mesh34.json` (8 files; e.g. `probe-nif-mesh-69da9507d49c42ff-mesh34.json`)
- Attribute probe attempt logs: captured in this coordination + terminal batch output (would-be JSON paths noted above)
- Prep ref: `docs/roadmap/phase1-m1.2-prep.md` (lists the exact 8, rationale, command, what to quantify)
- M1.1 parent: `docs/roadmap/phase1-m1.1-coordination.md` + handoff `docs/handoffs/draft-2026-06-m1.1-329-matrix.md`
- Roadmap: `docs/roadmap/project-roadmap.md` (Phase 1 M1.2)

**Validation (per run + batch):**
- GeneratedOutputGuard passed (8x).
- Strictly candidate-only language + 329 scope.
- Used only existing rift_workflow.py command.
- No new scripts, no PS, no copied assets, no promotion.
- Cross-checked vs matrix (12/12 prior pattern for #34 attr=0 + @304 pos c=75 confirmed in batch context for top8).
- References Phase 1 M1.2, prep.md, matrix, current-phase.md, project-roadmap.md, task-routing-safety-policy.md (high-reasoning).

## Next (post-batch)
See prep.md first-steps: analysis/quant on the (negative+supplemental) data; extend position-source-sibling-extra-position-report or Python post-process on matrix IDs; produce classification tables; draft M1.2 handoff.

Current live pointer: `docs/roadmap/current-phase.md` (M1.2 active).

M1.1 reference: `docs/handoffs/draft-2026-06-m1.1-329-matrix.md` (finalized) + matrix artifacts.

**Human-readable summary of this milestone step (per AGENTS.md)**: Executed the exact attribute-extra-probe batch on the 8 top #34 targets from the M1.1 matrix (as specified in phase1-m1.2-prep.md). All 8 returned the informative/valid "no attribute extra stream was found at @304 on NiMesh #34" (no raw attribute-extra JSONs written, per C# early return when attrSets=0 / no matching ExtraStreams). Full commands, dotnet lines, errors, and guard passes logged. Key fields extracted (attrSets=0, @304 role=position-float3-ror1-lead c=75, @296 u32 c=25, per-ID BodyFirst16 for @304/@212 from supporting mesh34 JSONs, no histograms/samples from this probe path). Updated this coordination.md with batch table, links, extracts, validation. What changed: M1.2 batch data point delivered (negative result on attr-extra parsing for the extra pos stream). Why matters: Confirms @304 "pos" classification on #34 variants comes from a different parser path than attribute extras (important for role scoring + future guards in M1.3). Validated: 8/8 consistency, matrix match, candidate-only, scope, guard, existing-cmd only, refs to prep/matrix/roadmap Phase 1 M1.2. Remains uncertain: deeper payload (full BodyFirst64/hist/index-compat/vertex samples for the @304 stream body) will require direct stream-body/endianness probes on the target NiDataStream blocks (not in scope of this attribute-extra batch task). Ready for analysis subagent / handoff drafter per swarm. (All per AGENTS.md + safety policy + anti-drift.)

## Handoff Drafter Coordination Update
- Initial M1.2 handoff draft created: `docs/handoffs/draft-2026-06-m1.2-@304-extra-stream-classification.md`
- Used: prep.md + M1.1 matrix + this batch data (error logs, extracted fields) + phase1-m1.2-@304-analysis-initial.json (PerID for 8, Aggregates, CandidatePatterns) + refreshed sibling reports + probe samples.
- Draft incorporates real tables (ratios, first16, diffs, classif uint16/strided, common c2, low plaus 8/8, mixed endian, stride notes, large sample diffs) from analysis sibling; reduced placeholders; kept initial-draft status + refs.
- All candidate-only, 329+matrix scoped, Phase 1 M1.2 roadmap-referenced.
- Next: main review + finalize + pointer updates.