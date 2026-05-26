# 50-step plan current position

Date: 2026-05-26

## Summary

The original `docs/discovery-plan-50.md` is a 50-step plan grouped into six stages, not 50 separate stages.

Current position in that plan:

```text
Stage 5 — Live-Game Safe Read-Only Validation
Current step: Step 48 — Scan for @264/#15 index buffer pattern in live memory (dry-run target wired; live read gated)
```

Step 46 is complete via `docs/live-memory-readonly-safety-boundary.md`. Step 47 is complete via the gated `scan-live-memory` workflow command and fixture-backed scanner core.

## Why this is Step 48

The repo later completed or superseded the original offline steps through Stage 4:

| Original stage | Steps | Current disposition | Evidence |
|---|---:|---|---|
| Stage 0 — Foundation | 1-5 | Complete/superseded | `docs/handoffs/2026-05-20-stage0-baseline.md` |
| Stage 1 — Safe Geometry Decode | 6-15 | Complete/superseded | `docs/handoffs/2026-05-21-stage1-geometry-decode.md` |
| Stage 2 — Position Source Discovery | 16-25 | Complete/superseded | `docs/handoffs/2026-06-02-stage2-position-source-enhanced-findings.md` |
| Stage 3 — Proof Guard Migration | 26-35 | Complete/superseded | Python guards and workflow tests |
| Stage 4 — Discovery Automation Suite | 36-45 | Complete/superseded | `discovery-suite` command and Stage 14+ handoffs |
| Stage 5 — Live Read-Only Validation | 46-50 | Active | Steps 46-47 complete; Step 48 in progress |

## Active safety boundary

The Stage 5 live validation lane is high-risk and must remain read-only.

Current boundary:

- Safety boundary doc exists: `docs/live-memory-readonly-safety-boundary.md`
- Actual live process read executed: **false**
- Live process scanner implemented: **true**
- Step 48 dry-run target manifest ready: **true**
- Parser/export promotion allowed: **false**

## Next action

Implement Step 48 as a dry-run live-index scan plan first:

1. Generate or review the tracked dry-run plan with `python scripts/rift_workflow.py scan-live-memory --live-pattern-file docs/live-memory-scan-targets.json --list-json`.
2. Review the exact PID, pattern, output paths, and limits before any live read.
3. Keep actual live reads gated behind `--execute-live-read --experimental-live --confirm-live-read --pid`.
4. Write any live evidence only under ignored `Exports/discovery-plan/stage5-live/`.
5. Do not promote parser/export behavior from live evidence without a later guard-backed patch.
