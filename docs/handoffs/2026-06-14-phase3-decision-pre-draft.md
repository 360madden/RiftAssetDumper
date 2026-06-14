# 2026-06-14 — §8.4 decision pre-draft: commit, status-update, and gate in one place

**Date**: 2026-06-14
**Type**: Pre-staged §8.4 decision skeleton
**Scope**: One-handoff checklist for the §8.4 commit (PASS, FAIL Mode A, or FAIL Mode B)
**Status**: DRAFT — unfilled, uncommitted. Pre-staged on `main` so the §8.4 decision is one keystroke away when Phase 3 lands.
**Trigger**: Operator posts Phase 3 hit counts (in-region / out-of-region per vertex), AI classifies Mode (A / B / C / D), operator selects the matching template below, applies the fill-in, runs the proof-guard-suite, and commits.

## Why this exists

The §8.4 decision is the load-bearing judgment for the parser-UX follow-up chain. The decision is mechanical once the Phase 1/2/3 results are known, but the commit message, status-JSON update, schema widening (PASS only), and pre-commit gate are all separate artifacts that have to land in the right order. This handoff consolidates them so the commit is a copy-paste-fill-test-push sequence, not a re-derivation.

## §8.4 commit message templates (one per Mode)

### Mode C/D: §8.4 PASS

```text
docs: phase3 PASS — step49 status-update to open-positive-live-<partial|confirmed>

Phase 3 bounded float3 triplet probe (4 × RiftReader --scan-float-triplet
invocations for v0..v3) produced <N> in-region hit(s) within ±4 MiB of the
Phase 2 co-resident anchor A=0x<HEX>.

- Closes the §8.4 Step 49 status decision path.
- Widens docs/schemas/live-memory-step49-status-v1.schema.json Step49ClosureMode
  const from "closed-negative-current-live-state" to enum
  ["closed-negative-current-live-state", "open-positive-live-partial",
  "open-positive-live-confirmed"].
- Updates docs/live-memory-step49-status.json:
  - Step49ClosureMode: "open-positive-live-<partial|confirmed>"
  - Step49ClosureDecision: "<one-sentence summary of the Phase 1/2/3 result chain>"
  - BoundedExpectedStaticBatchHitCount: <N>
  - NextAction: "<what the parser/export promotion-readiness check should do next>"
- Run python scripts/rift_workflow.py proof-guard-suite --full; expect 0 regressions.
- Companion handoffs (per-vertex tables, decision matrix, proof-guard output):
  docs/handoffs/2026-06-14-phase3-pass-step49-status-update.md (filled).

Refs: docs/handoffs/2026-06-13-phase3-bounded-triplet-invocation.md,
docs/handoffs/2026-06-13-phase2-co-location-at264-invocation.md,
docs/handoffs/2026-06-13-phase1-live-read-invocation.md.
```

### Mode A: §8.4 FAIL (representation rejected, no surrogate)

```text
docs: phase3 FAIL (Mode A) — step49 stays closed-negative-current-live-state

Phase 3 bounded float3 triplet probe (4 × RiftReader --scan-float-triplet
invocations for v0..v3) produced 0 in-region hits and 0 out-of-region hits.
The raw contiguous static float3 representation hypothesis is rejected for
the current live state.

- Step 49 status remains "closed-negative-current-live-state" (unchanged).
- docs/live-memory-step49-status.json: no changes (the existing closure
  already covers this outcome).
- No schema change required.
- Parser/export promotion remains blocked.
- Companion handoff (decision matrix): docs/handoffs/2026-06-14-phase3-fail-step49-stays-closed.md (filled).

Refs: docs/handoffs/2026-06-13-phase3-bounded-triplet-invocation.md.
```

### Mode B: §8.4 FAIL (representation rejected, surrogate present) — TWO-COMMIT sequence

**Commit 1 (FAIL record, same as Mode A but with the surrogate noted):**

```text
docs: phase3 FAIL (Mode B) — step49 stays closed-negative-current-live-state

Phase 3 bounded float3 triplet probe (4 × RiftReader --scan-float-triplet
invocations for v0..v3) produced 0 in-region hits and <M> out-of-region
hit(s) (surrogate present). The raw contiguous static float3 representation
hypothesis is rejected for the target asset; the out-of-region matches
likely belong to a different loaded asset, but their presence is a Phase 4
lead worth pursuing separately.

- Step 49 status remains "closed-negative-current-live-state" (unchanged).
- docs/live-memory-step49-status.json: no changes.
- No schema change required.
- Parser/export promotion remains blocked for THIS asset.
- Companion handoff (decision matrix): docs/handoffs/2026-06-14-phase3-fail-step49-stays-closed.md (filled).
- Phase 4 lead handoff (separate commit, see below): docs/handoffs/2026-06-14-phase3-fail-mode-b-surrogate-lead.md (filled).

Refs: docs/handoffs/2026-06-13-phase3-bounded-triplet-invocation.md.
```

**Commit 2 (Phase 4 lead, separate commit per parser-UX handoff §Schedule's conflict-avoidance rationale):**

```text
docs: phase3 FAIL Mode B — file Phase 4 surrogate-lead handoff

Phase 3 produced <M> out-of-region hit(s) that are not co-resident with the
target asset. The matches are a Phase 4 lead for: (a) re-running the probe
in a different load state, (b) characterizing the surrogate (instanced /
transformed / GPU staging / LOD), or (c) re-pinning --scan-region-base to
the surrogate's region.

- Companion handoff (Phase 4 plan): docs/handoffs/2026-06-14-phase3-fail-mode-b-surrogate-lead.md (filled).
- Step 49 status unchanged; this commit does NOT flip any status field.
- Live-read tooling remains dormant until Phase 4 planning is complete.

Refs: docs/handoffs/2026-06-14-phase3-fail-step49-stays-closed.md (parent FAIL record).
```

## JSON status-update payloads (one per Mode)

All three apply on top of the current `docs/live-memory-step49-status.json`. Use `python -c "import json; ..."` to apply (see operator-fill block below).

### Mode C/D (PASS) — required changes

```python
# Load current
import json
from pathlib import Path
p = Path("docs/live-memory-step49-status.json")
d = json.loads(p.read_text(encoding="utf-8"))

# Apply PASS-mode updates
d["Step49ClosureMode"] = "open-positive-live-<partial|confirmed>"  # operator picks
d["Step49ClosureDecision"] = (
    "Phase 3 bounded float3 triplet probe (4 × RiftReader --scan-float-triplet "
    "invocations for v0..v3) produced <N> in-region hit(s) within ±4 MiB of the "
    "Phase 2 co-resident anchor A=0x<HEX>. Raw contiguous static float3 representation "
    "hypothesis is confirmed for the current live state."
)
d["BoundedExpectedStaticBatchHitCount"] = <N>  # operator fills
d["NextAction"] = (
    "Step 49 closed as open-positive-live-<partial|confirmed>. Run proof-guard-suite "
    "and parser/export promotion-readiness check; do not auto-promote."
)

# Validate against schema BEFORE writing
import jsonschema
schema = json.loads(Path("docs/schemas/live-memory-step49-status-v1.schema.json").read_text(encoding="utf-8"))
jsonschema.validate(d, schema)  # NB: this will FAIL until the schema const is widened (see Schema update below)

# Write
p.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
print("PASS-mode status update written")
```

### Mode A/B (FAIL) — no changes to the status JSON

The existing `Step49ClosureMode: "closed-negative-current-live-state"` already covers both FAIL outcomes. The operator commits the §8.4 FAIL handoff (with the per-vertex tables filled) and does not touch the status JSON.

## Schema update (Mode C/D PASS only)

The current `docs/schemas/live-memory-step49-status-v1.schema.json` has:

```json
"Step49ClosureMode": { "const": "closed-negative-current-live-state" }
```

This MUST be widened for the PASS-mode status update to validate. The widening is a one-line change, applied as part of the same §8.4 commit:

```diff
--- a/docs/schemas/live-memory-step49-status-v1.schema.json
+++ b/docs/schemas/live-memory-step49-status-v1.schema.json
@@
-    "Step49ClosureMode": { "const": "closed-negative-current-live-state" },
+    "Step49ClosureMode": { "enum": ["closed-negative-current-live-state", "open-positive-live-partial", "open-positive-live-confirmed"] },
```

**Mode A and Mode B do NOT require the schema change** — the FAIL closure is already covered by the existing const.

**Schema-validation tests** (`scripts/test_fifty_step_plan_status.py` lines 70 and 92) assert the current `closed-negative-current-live-state` value. The PASS commit must update these tests to accept the new enum members, or they will fail. Update them in the same commit:

```python
# Before (in scripts/test_fifty_step_plan_status.py):
check("step 49 closure mode", step49_status["Step49ClosureMode"], "closed-negative-current-live-state")

# After (in scripts/test_fifty_step_plan_status.py):
ALLOWED = {"closed-negative-current-live-state", "open-positive-live-partial", "open-positive-live-confirmed"}
assert step49_status["Step49ClosureMode"] in ALLOWED, f"unexpected Step49ClosureMode: {step49_status['Step49ClosureMode']}"
```

Run `python scripts/test_fifty_step_plan_status.py` to confirm the test passes with the new value.

## Proof-guard-suite invocation (pre-commit gate for all 3 Modes)

Run this immediately before `git commit`. Expect 0 regressions.

```text
python scripts/rift_workflow.py proof-guard-suite --full
```

**Expected output**: all 8 proof guards PASS (attribute_extra_proof_guard, attribute_extra_sibling_proof_guard, usage_access_correlation_guard, position_source_sibling_lead_guard, residual_lead_guard, ghidra_function_site_target_guard, ghidra_pairing_non_export_guard, ghidra_attribute_candidate_guard). If any guard regresses, do NOT commit; investigate the regression and either (a) document the accepted change in the §8.4 handoff's "Proof-guard-suite output" section, or (b) revert the §8.4 decision.

**Mode B** additionally requires `python scripts/test_post50_validation_suite_status.py` (or equivalent) to confirm the validation suite still passes after the FAIL record + Phase 4 lead are both committed.

## Filename-deviation patch (if applicable)

If the operator's Phase 3 `--output` paths deviated from the §5.1 `phase3-bounded-triplet-<UTC>-vN.json` recipe, apply this one-line patch to `docs/handoffs/2026-06-14-phase3-fail-mode-b-surrogate-lead.md` line 16 (the only direct filename-pattern reference in the §8.4 chain):

```diff
-- [ ] Per-vertex out-of-region hit addresses captured from the four `phase3-bounded-triplet-<UTC>-vN.json` files
+- [ ] Per-vertex out-of-region hit addresses captured from the four `<NEW_PATTERN>` files
```

The per-vertex tables in the PASS/FAIL templates are immune to filename deviation (TBD placeholders anchored on v0–v3 row labels); no other patches are required. Patch and §8.4 commit land atomically.

## Pre-flight checklist (operator fills before commit)

- [ ] Phase 1/2/3 results captured in operator's working notes (addresses, hit counts, distances)
- [ ] §8.4 Mode classified (A / B / C / D) per the per-vertex hit-count matrix in this handoff
- [ ] §8.4 template filled: PASS (`2026-06-14-phase3-pass-step49-status-update.md`), FAIL (`2026-06-14-phase3-fail-step49-stays-closed.md`), and Mode B's lead (`2026-06-14-phase3-fail-mode-b-surrogate-lead.md` if applicable)
- [ ] Filename-deviation patch applied (if applicable)
- [ ] Status JSON updated (PASS only)
- [ ] Schema widened (PASS only)
- [ ] Test assertions updated (PASS only)
- [ ] Proof-guard-suite run; 0 regressions
- [ ] Commit message selected from the template above
- [ ] `git status` checked; no live reports or unrelated diffs staged

## Per-vertex in-region hit-count matrix (operator fills)

| Vertex | Triplet | In-region hits | Out-of-region hits | First hit address (any region) | Distance from A |
|---|---|---:|---:|---|---:|
| v0 | `(8.458028, 55.920349, 11.567474)` | TBD | TBD | TBD | TBD |
| v1 | `(5.999848, 54.718262, 13.064880)` | TBD | TBD | TBD | TBD |
| v2 | `(7.556799, 52.199829, 11.407593)` | TBD | TBD | TBD | TBD |
| v3 | `(5.999830, 52.299988, 12.751602)` | TBD | TBD | TBD | TBD |

`A` is the Phase 2 co-resident anchor. "Distance from A" is `|hit_address - A|` in bytes; "in-region" requires `distance <= 0x400000` (4 MiB).

## Mode classification (auto-derived from the table above)

| Mode | In-region | Out-of-region | §8.4 path | Commit(s) |
|---|:---:|:---:|---|---|
| **A. Representation rejected, no surrogate** | 0 | 0 | FAIL | 1 commit (FAIL record) |
| **B. Representation rejected, surrogate present** | 0 | ≥1 | FAIL + Phase 4 lead | 2 commits (FAIL record + Phase 4 lead) |
| **C. Representation region-confirmed, cross-vertex partial** | ≥1 | 0–N | PASS (partial) | 1 commit (PASS + schema widening + status update) |
| **D. Representation region-confirmed, all-vertex full** | ≥1 per vertex | 0–N | PASS (confirmed) | 1 commit (PASS + schema widening + status update) |

## Related follow-ups

- **§8.4 PASS template** (pre-staged): `docs/handoffs/2026-06-14-phase3-pass-step49-status-update.md` — fill on Mode C/D.
- **§8.4 FAIL template** (pre-staged): `docs/handoffs/2026-06-14-phase3-fail-step49-stays-closed.md` — fill on Mode A/B.
- **§8.4 FAIL Mode B lead** (pre-staged): `docs/handoffs/2026-06-14-phase3-fail-mode-b-surrogate-lead.md` — fill on Mode B (separate commit).
- **Parser UX follow-up** (blocked): `docs/handoffs/2026-06-14-parser-ux-region-pin-hint.md` — the §8.4 decision commit unblocks this 1-line parser change.
- **m3 follow-up batch cross-ref**: `docs/handoffs/2026-06-13-m3-safe-followup-batch.md` §"Deferred items" — the parser UX follow-up is cross-referenced from the deferred side.
- **Proof-guard suite**: `scripts/rift_workflow.py proof-guard-suite --full` (8 guards, all PASS on current state).
- **Step 49 status test assertions**: `scripts/test_fifty_step_plan_status.py` lines 70 and 92 (must be updated for PASS).
- **Step 49 status schema**: `docs/schemas/live-memory-step49-status-v1.schema.json` (must be widened for PASS).
- **Step 49 status JSON**: `docs/live-memory-step49-status.json` (current value: `closed-negative-current-live-state`).

## Decision log

- 2026-06-14: Pre-staged as a DRAFT, unfilled, uncommitted handoff. Consolidates the §8.4 commit message templates, status-update payloads, schema-widening diff, proof-guard-suite invocation, filename-deviation patch, and pre-flight checklist in one place. Trigger: Phase 3 hit counts posted by operator. The handoff is the single artifact the operator reaches for when the §8.4 decision lands.
