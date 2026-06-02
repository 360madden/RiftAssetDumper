# Task for Block 34 Prober Agent

**Milestone**: Phase 1 M1.1 — 329 Family Attribute & Role Matrix

**Assignment**: First batch — mesh-block 34 (sibling variant) probes

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

**Command template**:
python scripts/rift_workflow.py mesh-probe --id <ID> --mesh-block 34 --skip-build

**Focus extraction** (critical for this milestone):
- attributeSets (expect 0)
- @212 role and whether it matches the primary from block 7
- @304 role (frequently scored as extra position)
- Normal stream details
- @296 u32 pattern body
- Payload and vector counts for comparison

Produce per-ID structured data + batch comparison notes vs block 7 results.

Update the coordination file when complete.

**✅ COMPLETE (Block 34 Prober subagent execution)**: All 8 IDs probed on mesh-block 34 via exact `python scripts/rift_workflow.py mesh-probe --id <ID> --mesh-block 34 --skip-build`. 

Raw JSONs: `Exports/probe-nif-mesh-*-mesh34.json` (8 files).

Key candidate findings (meshSize=329 family):
- attributeSets: 0 for all 8 (vs. 1 on block#7 sibling for 0364ea14...)
- @212: always position-float3-ror1-lead (c=75) — matches primary from block 7
- @304: always extra position-float3-ror1-lead (c=75) — the sibling variant "extra position-like" stream
- @296: always u32-repeated-pattern-body (c=25)
- @220: normal-float3-ror1-lead (c=85) or uv-float2-ror1-lead (c=80) — per-ID role variant
- Payloads / vector counts match id-list expectations (e.g., 924B ≈ 77 verts for 69da...)

Full structured table + 1:1 block7 vs #34 example (0364) in subagent execution record. Strictly scoped, candidate-only, high-reasoning path per task-routing-safety-policy.md and Phase 1 M1.1 in current-phase.md / project-roadmap.md. No new families, no promotion. Coordination.md updated.

Next for synthesizer: integrate with block7 batch results + produce matrix.
