# 50-step plan current position

Date: 2026-05-26

## Summary

The original `docs/discovery-plan-50.md` is a 50-step plan grouped into six stages, not 50 separate stages.

Current position in that plan:

```text
Stage 5 — Live-Game Safe Read-Only Validation
Current step: Step 49 — Scan for position float3 clusters matching mesh bounds
Status: in progress; initial RiftReader single-float probe executed, cluster not confirmed
```

Step 46 is complete via `docs/live-memory-readonly-safety-boundary.md`. Step 47 is complete via the gated `scan-live-memory` workflow command and fixture-backed scanner core. Step 48 is complete via the preferred RiftReader live-memory scanner provider. Step 49 has candidate-only live evidence in `docs/live-memory-step49-status.json`, but it is not complete because static mesh `v0-v3` triplets did not match the first four bounded live candidate regions. RiftReader now exposes a bounded `--scan-float-triplet <x,y,z> --scan-region-base <address> --scan-region-size <bytes>` command for focused triplet/cluster probes.

## Why this is Step 49

The repo later completed or superseded the original offline steps through Stage 4:

| Original stage | Steps | Current disposition | Evidence |
|---|---:|---|---|
| Stage 0 — Foundation | 1-5 | Complete/superseded | `docs/handoffs/2026-05-20-stage0-baseline.md` |
| Stage 1 — Safe Geometry Decode | 6-15 | Complete/superseded | `docs/handoffs/2026-05-21-stage1-geometry-decode.md` |
| Stage 2 — Position Source Discovery | 16-25 | Complete/superseded | `docs/handoffs/2026-06-02-stage2-position-source-enhanced-findings.md` |
| Stage 3 — Proof Guard Migration | 26-35 | Complete/superseded | Python guards and workflow tests |
| Stage 4 — Discovery Automation Suite | 36-45 | Complete/superseded | `discovery-suite` command and Stage 14+ handoffs |
| Stage 5 — Live Read-Only Validation | 46-50 | Active | Steps 46-48 complete; Step 49 in progress |

## Active safety boundary

The Stage 5 live validation lane is high-risk and must remain read-only.

Current boundary:

- Safety boundary doc exists: `docs/live-memory-readonly-safety-boundary.md`
- Actual live process read executed: **true**
- Live process scanner implemented: **true**
- Step 48 dry-run target manifest ready: **true**
- Step 48 live pattern found by RiftReader: **true**
- Step 49 initial single-float probe by RiftReader: **true**
- Step 49 bounded float-triplet positive-control hits: **2**
- Step 49 expected static `v0` hits in that bounded region: **0**
- Step 49 expected static `v0-v3` hits across four bounded regions: **0**
- Step 49 position float3 cluster confirmed: **false**
- Parser/export promotion allowed: **false**

## Next action

Continue Step 49 as a candidate-only position-cluster confirmation lane:

1. Derive bounded float3 cluster byte patterns from guarded static decode/bounds evidence.
2. Prefer the existing RiftReader memory scanner/provider for live reads; use bounded `--scan-float-triplet <x,y,z>` for candidate float3 checks.
3. Treat the existing single-float probe as noise-prone evidence only.
4. Write any live evidence only under ignored `Exports/discovery-plan/stage5-live/`.
5. Do not promote parser/export behavior from live evidence without a later guard-backed patch.
