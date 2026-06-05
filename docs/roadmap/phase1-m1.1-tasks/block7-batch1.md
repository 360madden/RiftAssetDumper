# Task for Block 7 Prober Agent

**Milestone**: Phase 1 M1.1 — 329 Family Attribute & Role Matrix

**Assignment**: First batch — mesh-block 7 probes

**IDs to probe** (Curated Ranked Batch from completed ID Curator subagent task 019e8655-c7c1-7851-b421-d23747fb4827 — see docs/roadmap/phase1-m1.1-curated-probe-queue.md):

Priority first wave (top 8 from curator ranking):

1. 69da9507d49c42ff (77v — highest)
2. f2c347fe81a5e3b2 (64v)
3. 07c733b4eee3ed2e (56v)
4. 83df87e22bff4a94 (52v)
5. 7f3e71246752afb2 (49v)
6. 0364ea142bc00ce7 (48v — rich anchor)
7. 4eb7745610adf8c7 (46v)
8. b57694c1f202ec07 (38v — rich mesh#7 attr data)

**Command template** (run for each ID):
python scripts/rift_workflow.py mesh-probe --id <ID> --mesh-block 7 --skip-build

**Required outputs per ID**:

- Full raw JSON saved to Exports/
- Extracted structured data:
  - attributeSets count
  - All streams with offset, target block, role, payload size, vector count, confidence
  - Special attention to @212, @220, @296, @304

Save a summary table (markdown or JSON) when batch is complete.

Update docs/roadmap/phase1-m1.1-coordination.md with your progress when done.

**✅ COMPLETE (Block 7 execution subagent for M1.1)**: Ran exact commands `python scripts/rift_workflow.py mesh-probe --id <ID> --mesh-block 7 --skip-build` for all priority + anchor (69da9507d49c42ff, f2c347fe81a5e3b2, 07c733b4eee3ed2e, 83df87e22bff4a94, 7f3e71246752afb2, 4eb7745610adf8c7, b57694c1f202ec07, 0364ea142bc00ce7).

Raw JSONs: Exports/probe-nif-mesh-*.json (plain from workflow) + suffixed Exports/probe-nif-mesh-*-mesh7.json (naming ensured for matrix; see coordination update).

Key candidate findings (meshSize=329 family, #7):

- attributeSets: 1 for all 8 (pos@212 + normal@220 + uv@304 + extra u32@296)
- Consistent roles/conf across: @212 position-float3-ror1-lead (c=75), @220 normal-float3-ror1-lead (c=85), @296 u32-repeated-pattern-body (c=25 extra), @304 uv-float2-ror1-lead (c=80)
- vec counts (vtx from attr): 77,64,56,52,49,46,38,48 matching curator queue
- extras always 1 (@296)
- Paired with #34 (attr=0, @304 as position c=75) now 8/8 for this wave + more =12 total pairs in matrix.

See full extracts + matrix in coordination.md + Exports/mesh329-family-attribute-role-matrix.md
All candidate-only, 329-family only. Updated coordination + matrix. References roadmap Phase 1 M1.1.
