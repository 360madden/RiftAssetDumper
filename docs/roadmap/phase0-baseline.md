# Phase 0 Baseline — Current State Snapshot

**Date**: 2026-06 (during roadmap creation)
**Purpose**: Capture the exact state at the moment the structured roadmap was adopted, so all future work has a clear "before" reference.

## Key Status Commands Run
- `post50-position-source-status`: Confirmed meshSize=329 source-binding family remains the #1 recommended lane (23 evidence groups). Strong recommendation to classify mesh#34 @304 extra position-like streams.

## Current Strongest Signals (from status)
1. source-binding-family meshSize=329 stream@212 — 23 groups (top priority)
2. source-binding-extra-position meshSize=329 mesh#34 @304/#57 — 3 groups
3. residual-packed-position meshSize=305 stream@188 payload 288 (0.9444 plausible) — candidate only
4. residual-cluster-structure meshSize=305 — candidate only

## Major Blockers (unchanged)
- All promotion-related gates locked (`parser-export-promotion-not-allowed`)
- No complete geometry bindings proven for residual candidates
- mesh329 family proof still candidate-only

## Recent Autonomous Work (pre-roadmap)
- Deep `mesh-probe` analysis on top 329-family examples (IDs including 0364ea14..., f2c347fe..., 69da9507...).
- Consistent pattern observed:
  - mesh#7: attributeSets=1 (position @212 + normal + UV)
  - mesh#34: attributeSets=0, shares primary position, extra @304 stream scored as additional position
- Two focused handoffs created:
  - `docs/handoffs/2026-06-post50-mesh329-family-evidence-update.md`
  - `docs/handoffs/2026-06-post50-mesh329-family-role-analysis.md`

## Python Workflow State
- Fully migrated. All complex modes and guards in Python.
- `rift_workflow.py` is the primary tool.
- `grok-here.py` is the recommended launcher.

## Safety & Process State
- Aggressive Evidence Workflow is the approved operating mode.
- Task-routing safety policy active (high/extra-high reasoning for all truth/proof work).
- No new PowerShell allowed.

## Next per Roadmap
Transition to Phase 1 (Position Source Family Proof & Role Classification) once Phase 0 artifacts are complete.

This baseline should be referenced in the Phase 1 kickoff handoff.