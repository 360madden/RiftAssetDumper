# Phase 1 M1.1 — Curated Ranked Probe Queue (from ID Curator Subagent)

**Source**: Completed subagent task 019e8655-c7c1-7851-b421-d23747fb4827 (explore type, 45 tool calls, 179s).

**Date of curation**: 2026-06
**Status**: Candidate-only. For use in systematic mesh-probe expansion on mesh#7 and mesh#34 variants in the meshSize=329 source-binding family (stream@212/#28).

**Ranked 12 IDs for deep probing** (prioritized for vector/payload coverage, extra @304 pattern representation, existing probe richness, and diversity):

| Rank | Asset ID              | Primary Vectors | Payload (bytes) | Notes / Existing Probes Highlights |
|------|-----------------------|-----------------|-----------------|------------------------------------|
| 1    | 69da9507d49c42ff     | 77             | 924            | Top priority. Existing detailed mesh#34 probe showing extra @304 position-like. |
| 2    | f2c347fe81a5e3b2     | 64             | 768            | Strong high-end. Existing mesh#34 probe with @304 position-like. |
| 3    | 07c733b4eee3ed2e     | 56             | 672            | High unprobed vector count. |
| 4    | 83df87e22bff4a94     | 52             | 624            | Good high-mid coverage. |
| 5    | 7f3e71246752afb2     | 49             | 588            | Continues high-end expansion. |
| 6    | 0364ea142bc00ce7     | 48             | 576            | **Anchor example**. Rich multi-probe data on both #7/#34, explicit @304 (pos on #34, UV on #7), attr differences documented in role-analysis handoff. |
| 7    | 4eb7745610adf8c7     | 46             | 552            | Strong mid-high. |
| 8    | b57694c1f202ec07     | 38             | 456            | Rich mesh#7 attr-extra probe data (attr=1). |
| 9    | 04de901531a091ab     | 37             | 444            | Second detailed extra@304 trio member (both #7/#34 probed). |
| 10   | acccb682df4d4ad8     | 36             | 432            | Mesh#7 attr-extra probe data. |
| 11   | 1c4f0a1acdb5e141     | 23             | 276            | Low-mid for contrast + mesh#7 attr data. |
| 12   | 066fa520a8ce62e3     | 22             | 264            | Completes the rich documented extra@304 set (both variants probed). |

**Recommended first wave (top 8)** for immediate mesh-probe execution on both mesh#7 and mesh#34:

1. 69da9507d49c42ff
2. f2c347fe81a5e3b2
3. 07c733b4eee3ed2e
4. 83df87e22bff4a94
5. 7f3e71246752afb2
6. 0364ea142bc00ce7 (anchor — re-probe or validate if needed)
7. 4eb7745610adf8c7
8. b57694c1f202ec07

**Usage**:

- Assign batches to prober subagents via updated task files.
- Run via `python scripts/rift_workflow.py mesh-probe --id <ID> --mesh-block <7 or 34> --skip-build`.
- Collect per-ID JSON + extract for matrix (attributeSets, roles at key offsets @212/@220/@296/@304, payloads, vectors, confidence).
- All outputs candidate-only under Exports/.

**Anti-drift**: This queue is the approved controlled list for M1.1. No IDs outside this family or this ranked set without explicit main-agent approval and roadmap update.

Reference: Full curator output in subagent result (task 019e8655-c7c1-7851-b421-d23747fb4827). See also `docs/roadmap/phase1-m1.1-id-list.md` for the unranked 23.
