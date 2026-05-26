# 50-step plan current position

Date: 2026-05-26

## Summary

The original `docs/discovery-plan-50.md` is a 50-step plan grouped into six stages, not 50 separate stages.

Current position in that plan:

```text
Stage 5 — Live-Game Safe Read-Only Validation
Current/next step: Step 47 — Implement read-only process memory scanner
```

Step 46 is now complete via `docs/live-memory-readonly-safety-boundary.md`.

## Why this is Step 47

The repo later completed or superseded the original offline steps through Stage 4:

| Original stage | Steps | Current disposition | Evidence |
|---|---:|---|---|
| Stage 0 — Foundation | 1-5 | Complete/superseded | `docs/handoffs/2026-05-20-stage0-baseline.md` |
| Stage 1 — Safe Geometry Decode | 6-15 | Complete/superseded | `docs/handoffs/2026-05-21-stage1-geometry-decode.md` |
| Stage 2 — Position Source Discovery | 16-25 | Complete/superseded | `docs/handoffs/2026-06-02-stage2-position-source-enhanced-findings.md` |
| Stage 3 — Proof Guard Migration | 26-35 | Complete/superseded | Python guards and workflow tests |
| Stage 4 — Discovery Automation Suite | 36-45 | Complete/superseded | `discovery-suite` command and Stage 14+ handoffs |
| Stage 5 — Live Read-Only Validation | 46-50 | Active | Step 46 complete; Step 47 next |

## Active safety boundary

The Stage 5 live validation lane is high-risk and must remain read-only.

Current boundary:

- Safety boundary doc exists: `docs/live-memory-readonly-safety-boundary.md`
- Actual live process read executed: **false**
- Live process scanner implemented: **false**
- Parser/export promotion allowed: **false**

## Next action

Implement Step 47 as a safe scanner scaffold:

1. Add a dedicated `scan-live-memory` command.
2. Require dry-run/list mode first.
3. Require `--experimental-live` and a separate confirmation flag for actual live process reads.
4. Add fixture-backed tests; CI must not attach to a live process.
5. Write output only under ignored `Exports/discovery-plan/stage5-live/`.
