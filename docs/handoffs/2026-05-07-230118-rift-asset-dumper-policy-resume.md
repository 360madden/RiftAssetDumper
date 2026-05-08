# RIFT Asset Dumper Handoff — Policy and next discovery resume 🛡️

Date: 2026-05-07
Workspace: `C:\RIFT MODDING\Assets`
Repo: `RiftAssetDumper`
Branch: `main`

## TL;DR 🧭

The repo is clean and pushed at the reasoning/task-routing policy milestone. The latest current truth is:

| Area | Current state |
|---|---|
| Current pushed head | `99d52d3` — `Document safe reasoning task routing policy` |
| Previous proof milestone | `8794ebe` — `Guard NIF attribute extra topology proof` |
| Worktree at handoff creation | Clean: `main...origin/main` |
| Export status | Still blocked; no OBJ/model export is ready or enabled |
| Generated asset folders | `Source/`, `Extracted/`, and `Exports/` remain local/generated and must not be staged by accident |
| Reasoning policy | Lower-intelligence/lower-reasoning work is allowed only for reversible mechanical tasks after the safety checklist passes and main high-reasoning review follows |

## Latest pushed commits ✅

```text
99d52d3 Document safe reasoning task routing policy
8794ebe Guard NIF attribute extra topology proof
a9510e4 Inventory NIF attribute extra streams
bc02cee Score NIF attribute-set topology leads
4586a56 Inventory NIF mesh attribute sets
```

## Durable policy surfaces now in repo 📌

| File | Purpose |
|---|---|
| `AGENTS.md` | Repo-level instructions now require following the task-routing safety policy. |
| `README.md` | Operating mode points to the safety policy and summarizes the high/extra-high default. |
| `docs/current-status.md` | Current workflow truth includes reasoning safety as part of the approved operating mode. |
| `docs/task-routing-safety-policy.md` | Strong policy for when lower-intelligence/lower-reasoning work is allowed or forbidden. |

## Strong policy summary 🧠

Default to high/extra-high reasoning for:

- asset truth classification;
- API truth classification;
- runtime memory or offset discovery;
- truth taxonomy and durable-vs-session wording;
- asset-guided reacquisition strategy;
- schemas and shared packet contracts;
- proof guard design or weakening;
- cross-repo boundaries across Assets, RiftScan, and RiftReader;
- live game interaction;
- exporter gates;
- commit/push review.

Lower-intelligence/lower-reasoning execution is allowed only when all of this is true:

1. task is reversible;
2. task is mechanical, not interpretive;
3. inputs and expected outputs are explicit;
4. no live game interaction;
5. no memory/process scanning;
6. no exact address, offset, candidate, or proof anchor promotion;
7. no truth taxonomy, schema, guard, or promotion rule changes;
8. no cross-repo edits;
9. no `Source/`, `Extracted/`, or `Exports/` generated/copied asset output can be staged;
10. main high-reasoning lane reviews before commit, push, or any truth claim.

If unsure, keep the stronger reasoning path.

## Current asset-discovery truth 🧷

The latest proof milestone remains the `@264/#15` attribute-extra topology lane:

```text
@264/#15 explicit-index stream => raw-zero-based + degenerate-bridge/stitch topology hypothesis
```

Current guard-backed facts:

| Proof area | Current state |
|---|---|
| Aggregate `@264` proof | `5/5` raw-zero-based wins, `0` subtract-one wins, `0` ties across four groups |
| Focused siblings | `6fc01704d4a509d5` and `caa9a88e94ec8db0` pass exact `v=128` `@264` invariants |
| Negative side stream | `@272/#25` remains `u32-sentinel-mask-body` |
| Repeated side streams | repeated `@296` bodies remain low-variation guardrails |
| Export | Still blocked pending stronger proof and review |

## Known useful commands 🔁

Check current repo state:

```powershell
cd "C:\RIFT MODDING\Assets"
git status --short --branch
git log --oneline -5
```

Run current proof guards before touching topology/export logic:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProofGuard -SkipBuild
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraSiblingProofGuard -SkipBuild
```

Representative negative side-stream probe:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProbe -Id 75d5a06d7c0de1dd -MeshBlock 7 -ExtraOffset 272 -SkipBuild -PrivacyScan
```

Diff/privacy checks before staging:

```powershell
git diff --check
git status --short
```

## Recommended next safe implementation slice 🎯

The best next repo-native slice is:

```text
AttributeExtraNegativeProofGuard + combined ProofGuards mode
```

Why:

- `@264` positive proof is now guarded both in aggregate and focused sibling form.
- `@272/#25` and repeated `@296` are currently negative/guardrail evidence, but they do not yet have a first-class regression guard.
- A combined guard mode would make it harder to forget one side of the truth split before future topology changes.

Expected behavior:

| Mode | Required behavior |
|---|---|
| `AttributeExtraNegativeProofGuard` | Rerun representative/top negative probes and fail if `@272/#25` stops being `u32-sentinel-mask-body` or repeated `@296` stops being `u32-repeated-pattern-body`. |
| `ProofGuards` | Run `AttributeExtraProofGuard`, `AttributeExtraSiblingProofGuard`, and `AttributeExtraNegativeProofGuard` in one workflow mode. |

## Future strategic docs to add 📚

After guards, the next high-reasoning docs should be:

| Doc | Purpose |
|---|---|
| `docs/truth-taxonomy.md` | Separate API truth, asset truth, runtime-session proof, restart-stable structure, exact runtime address, and historical/cached artifacts. |
| `docs/asset-guided-runtime-reacquisition-strategy.md` | Explain how local asset discovery can guide RiftScan/RiftReader reacquisition without treating exact addresses as durable. |
| `docs/schemas/asset-semantic-index-v1.schema.json` | Define future asset semantic index packets for map/zone/waypoint/objective/model ID discovery. |

## Hard boundaries 🚫

- Do not add or enable OBJ/model export yet.
- Do not stage or commit copied game files or generated output from `Source/`, `Extracted/`, or `Exports/`.
- Do not use lower-intelligence/lower-reasoning execution for truth, guards, schemas, runtime, live-game, cross-repo, exporter, or commit/push decisions.
- Do not treat exact runtime addresses from any old capture or handoff as durable truth.
- Do not cross into RiftScan or RiftReader implementation unless explicitly requested and the cross-repo boundary is documented.

## Ready-to-paste resume prompt 🚀

```text
Resume in C:\RIFT MODDING\Assets. Read AGENTS.md, docs/task-routing-safety-policy.md, docs/current-status.md, and the newest handoff only. Confirm git status/log. Keep high/extra-high reasoning for truth/proof/schema/runtime/guard decisions. Next safe slice: implement AttributeExtraNegativeProofGuard and combined ProofGuards mode in scripts/Invoke-RiftAssetWorkflow.ps1 / RiftAssetDumper as needed, update docs, validate with build + all guards + privacy/diff checks. Do not stage Source/, Extracted/, or Exports/. Do not add exporter work.
```
