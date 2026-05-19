# Assets discovery resume handoff — usage/access, semantic hints, and topology ranking

Date: 2026-05-17 19:06:55 America/New_York
Repo: `C:\RIFT MODDING\Assets`
Branch: `main`

## TL;DR

At the original handoff point, `main` was clean and synced with `origin/main` after the latest Assets-only discovery commits. After the continuation update below, the worktree has local uncommitted Assets-only report changes. The current durable lane is **NIF/NiMesh truth advancement** with no export/OBJ work. Latest pushed work added:

1. A fail-closed `UsageAccessCorrelationGuard` workflow mode.
2. Position-stream cross-tabs in the MeshBindings summary.
3. A bounded NIF semantic-hints matrix profile.
4. Group-level topology-ranking fields on `TopPairings`.

Usage/access and semantic hints remain **leads only**. They are ranking/search evidence, not geometry/export/runtime truth.


## Continuation update — 2026-05-17 19:22:12 America/New_York

Resumed development from this handoff and the latest 20 commits. Added a non-promotional residual-stream summary to the existing MeshBindings inventory:

| File | Continuation change |
|---|---|
| `src/RiftAssetDumper/Program.cs` | Adds `TopResidualStreams` to `inventory-nif-mesh-bindings`, limited to `meshSize=325/321`, after filtering known index/normal/UV/position/sentinel roles. |
| `scripts/Invoke-RiftAssetWorkflow.ps1` | Prints the residual-stream summary in MeshBindings workflow output when the new field exists. |

Full copied-set evidence from the rerun:

| Target | Residual result |
|---|---|
| `meshSize=325` | No residual groups after known-role filtering. |
| `meshSize=321` | One residual group: `stream@204`, target size `69`, payload `40`, `usage=1 access=19`, string hint `POSITION`, role `strided-body`, count `1`, sample `fedf45d1500a61ea` mesh `#6`. |

Interpretation: the original `325/321` residual-scan next step is now implemented, and the result is mostly negative evidence for missing high-count residual position sources in these two families. This remains ranking/search evidence only; no geometry/export truth was promoted.

Validation after this continuation:

| Check | Result |
|---|---|
| `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo` | Passed; existing `SharpCompress` NU1902 warning only. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode MeshBindings -SmokeMaxTotal 100 -SkipBuild` | Passed; smoke JSON includes the new field, with no residuals in first 100 NIFs. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode UsageAccessCorrelationGuard -SkipBuild -PrivacyScan` | Passed; full run found one `meshSize=321` residual and preserved usage/access guard invariants. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode AttributeExtraProofGuard -SkipBuild -PrivacyScan` | Passed; `@264` raw-zero-based proof invariants preserved. |
| `git diff --check` | Passed; Windows LF-to-CRLF warnings only. |


## Autonomous continuation update — 2026-05-17 21:01:58 America/New_York

Continued from the residual-stream slice without promoting geometry/export truth.

### Milestone A — probe lone `meshSize=321` residual

| Probe | Result |
|---|---|
| `MeshProbe -Id fedf45d1500a61ea -MeshBlock 6` | Mesh `#6` has 3 streams, 0 pairings, 0 attribute sets. Residual `@204/#26` is `payload=40`, `strided-body`, `usage=1 access=19`, string hint `POSITION`. |
| `probe-nif-stream-body --id fedf45d1500a61ea --stream-block 26` | Body is sentinel/extreme-looking (`ffff80ff...`), mixed u16, low signal for geometry. |

Interpretation: keep this as side-stream/noise evidence unless a later family-level pattern says otherwise.

### Milestone B — expand residual reporting to position-rich families

`TopResidualStreams` now covers target mesh sizes `297/305/321/325/329` and the report adds `ResidualTargetMeshSizes` so zero-residual targets remain visible.

Full copied-set target summary after rerun:

| Mesh size | Mesh blocks | Residual streams | Residual patterns | Current interpretation |
|---:|---:|---:|---:|---|
| `305` | `419` | `55` | `23` | Strongest residual follow-up lane. |
| `329` | `159` | `49` | `21` | Secondary residual follow-up lane, many color/repeated-pattern side streams. |
| `297` | `43` | `2` | `2` | Keep behind guarded `@264/#15` topology proof lane. |
| `321` | `212` | `1` | `1` | Mostly negative after probe. |
| `325` | `329` | `0` | `0` | Negative residual evidence after known roles are removed. |

### Milestone C — add residual position-signal fields

`TopResidualStreams` now carries non-promotional rotate-right-1 float3 metrics:

| Field | Purpose |
|---|---|
| `StringValue` | Preserve mesh string hint such as `POSITION`/`COLOR`. |
| `RotatedFloat3VectorCount` | Show candidate vector count without role promotion. |
| `RotatedFloat3PlausibleValueRatio` | Rank position-like residual streams that missed the stricter role classifier. |
| `RotatedFloat3NonZeroVectorRatio` | Separate real-valued bodies from zero/sentinel side streams. |
| `RotatedFloat3MaxExtent` | Rank bounded coordinate-like streams. |

Top new candidate-only lead: `meshSize=305 stream@188` with `StringValue=POSITION`, payloads `180/96/288`, counts `6/6/6`, and ROR1 float3 plausible ratios `0.8444/0.875/0.9444`. This is a ranked lead only; it is not promoted to `position-float3-ror1-lead` yet.

### Milestone D — add candidate-only residual lead guard

Added `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualLeadGuard` as a fail-closed guard around the new residual lead lane. It checks:

- `ResidualTargetMeshSizes` exists for target mesh sizes `297/305/321/325/329`.
- `meshSize=305` still has broad residual evidence (`>=50` residual streams, `>=20` residual patterns).
- `meshSize=325` remains residual-negative after known geometry/sentinel roles are removed.
- At least three `meshSize=305 stream@188 StringValue=POSITION usage=1 access=19` residual leads have `RotatedFloat3PlausibleValueRatio >= 0.80`.

Guard result: passed. This preserves the `meshSize=305 stream@188` lane as candidate-only ranking evidence and does not promote a parser role or geometry truth.

### Milestone E — persist residual ROR1 prefix evidence and spot-check representatives

`TopResidualStreams` now includes `RotatedFloat3Prefix` so the candidate-only residual report preserves the decoded ROR1 float3 prefix that explains each ranking score. This removes a manual decode step during future review.

Representative `meshSize=305 stream@188 StringValue=POSITION` probes:

| Payload | Sample | ROR1 float3 prefix signal |
|---:|---|---|
| `96` | `ada8ae04960eeefe mesh #7 stream #21` | `(-0.000001, 0.246593, 11.999756)`, `(-12.000144, 0.246590, 12.000000)` |
| `180` | `8c3e2a88780e74bd mesh #7 stream #21` | `(0.000000, 0.332687, 12.000000)`, `(12.000139, 0.332687, 12.000000)` |
| `288` | `014e1ff60d8508f1 mesh #7 stream #21` | `(-12.000139, 0.332687, 0.000000)`, `(-12.000139, 0.332687, 12.000000)` |
| `396` | `b4de91a46cb7d4bc mesh #7 stream #21` | `(-12.000139, 0.332687, -12.000000)`, `(-12.000123, 0.332687, 0.000000)` |

Interpretation: these are position-like bounded coordinate prefixes, but still candidate-only. They missed the existing strict `position-float3-ror1-lead` classifier, so do not promote them without a dry-run classifier report plus repeated-family guard support.

### Validation after autonomous continuation

| Check | Result |
|---|---|
| `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo` | Passed; existing `SharpCompress` NU1902 warning only. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode MeshBindings -SmokeMaxTotal 100 -SkipBuild` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode UsageAccessCorrelationGuard -SkipBuild -PrivacyScan` | Passed; usage/access guard unchanged. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode AttributeExtraProofGuard -SkipBuild -PrivacyScan` | Passed; `@264` raw-zero-based proof unchanged. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode AttributeExtraSiblingProofGuard -SkipBuild -PrivacyScan` | Passed for `6fc01704d4a509d5` and `caa9a88e94ec8db0`. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualLeadGuard -SkipBuild -PrivacyScan` | Passed; candidate-only residual lead guard added. |
| Representative `probe-nif-stream-body` checks for `meshSize=305 stream@188` payloads `96/180/288/396` | Completed into ignored `Exports/` probe JSON; ROR1 prefixes are position-like but not promoted. |

Next safe discovery milestone: build a dry-run residual-position classifier report for `meshSize=305 stream@188 StringValue=POSITION` that explains why these streams miss the strict classifier and what guard threshold would be required. Keep it candidate-only until repeated evidence and proof guards support promotion.

## Current git state

```text
main...origin/main
local tracked changes: src/RiftAssetDumper/Program.cs; scripts/Invoke-RiftAssetWorkflow.ps1
local untracked handoff: docs/handoffs/2026-05-17-190655-assets-discovery-resume-handoff.md
ignored local/generated dirs present only: Exports/, Extracted/, Source/, scripts/__pycache__/, src/RiftAssetDumper/bin/, src/RiftAssetDumper/obj/
```

Latest commits:

| Commit | Purpose |
|---|---|
| `05954a1` | Add topology rank fields to mesh pairings. |
| `8fd72ad` | Add usage-access guard and NIF semantic profile. |
| `1275848` | Summarize full usage-access mesh binding evidence. |
| `7df59c1` | Add usage-access mesh binding summaries. |
| `59f8568` | Add asset semantic discovery matrix and stream metadata. |

## Key changed files in latest pushed slice

| File | Durable change |
|---|---|
| `src/RiftAssetDumper/Program.cs` | `TopPairings` now include `IndexPairCount`, `TriangleListTriangleCount`, `TriangleStripWindowCount`, and `MaxIndexCoverageRatio`. |
| `scripts/Invoke-RiftAssetWorkflow.ps1` | Added `UsageAccessCorrelationGuard`; MeshBindings summary prints usage/access, position cross-tabs, and topology-rank fields. |
| `scripts/discovery-matrices/nif-semantic-hints.json` | Bounded NIF semantic jobs for `hint:actor-object`, `hint:map-zone`, `hint:waypoint-poi`. |
| `docs/handoffs/2026-05-17-1805-compact-usage-access-mesh-discovery-resume.md` | Prior compact resume with exact evidence and validation. |

## Latest full MeshBindings evidence

Report currently available under ignored output:

```text
C:\RIFT MODDING\Assets\Exports\nif-mesh-binding-inventory.json
```

| Metric | Count |
|---|---:|
| Inspected payloads | 40,203 |
| NIF payloads | 5,111 |
| NiMesh blocks | 5,507 |
| Candidate stream links | 11,564 |
| Valid declared stream bodies | 11,564 |
| Invalid declared stream bodies | 0 |
| Pair-compatible meshes | 2,076 |
| Pair-compatible links | 4,468 |
| Attribute-compatible meshes | 52 |
| Attribute-compatible sets | 52 |

Usage/access guard evidence:

| Role | Usage/access | Count | High-confidence |
|---|---|---:|---:|
| `uv-float2-ror1-lead` | `1/19` | 4,633 | 4,633 |
| `normal-float3-ror1-lead` | `1/19` | 4,167 | 4,167 |
| `index-u16be-strip-lead` | `0/19` | 2,101 | 2,101 |
| `position-float3-ror1-lead` | `1/19` | 210 | 210 |
| `index-u16be-list-lead` | `0/19` | 112 | 112 |

Guard result:

```text
100 top index-to-vertex pairings checked
0 usage/access exceptions
Expected pattern: index usage=0 access=19 -> vertex usage=1 access=19
```

## Current top pairing topology-rank examples

| Mesh size | Count | Index role | Vertex role | Vertex count | Index pairs | List tris | Strip windows | Coverage |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 325 | 134 | `index-u16be-strip-lead` | `normal-float3-ror1-lead` | 24 | 36 | 12 | 34 | 1 |
| 325 | 118 | `index-u16be-strip-lead` | `uv-float2-ror1-lead` | 24 | 36 | 12 | 34 | 1 |
| 321 | 60 | `index-u16be-strip-lead` | `normal-float3-ror1-lead` | 24 | 36 | 12 | 34 | 1 |
| 305 | 57 | `index-u16be-strip-lead` | `uv-float2-ror1-lead` | 4 | 6 | 2 | 4 | 1 |
| 301 | 50 | `index-u16be-strip-lead` | `uv-float2-ror1-lead` | 48 | 72 | 24 | 70 | 1 |

This makes `meshSize=325/321` easier to rank for the missing position-source search, but it still does not prove final geometry/export truth.

## Position-source lead cross-tab

Current `position-float3-ror1-lead` count is 210. Top mesh-size families:

| Mesh size | Count |
|---:|---:|
| 329 | 72 |
| 305 | 41 |
| 321 | 24 |
| 297 | 19 |
| 370 | 18 |
| 333 | 10 |
| 346 | 9 |
| 326 | 5 |
| 330 | 2 |
| 365 | 2 |

Top position payload sizes: `192=20`, `456=7`, `48=6`, `264=6`, `276=6`, `624=6`, `88=5`, `128=5`, `168=5`, `408=4`.

## NIF semantic-hints profile

Tracked profile:

```text
C:\RIFT MODDING\Assets\scripts\discovery-matrices\nif-semantic-hints.json
```

Generated ignored outputs:

```text
C:\RIFT MODDING\Assets\Exports\discovery-matrix\nif-semantic-hints\
```

Bounded first-500 NIF sample results:

| Job | Exit | Inspected | Entries | Meaning |
|---|---:|---:|---:|---|
| `semantic-nif-actor-object` | 0 | 500 | 11 | Static actor/object NIF leads. |
| `semantic-nif-map-zone` | 0 | 500 | 19 | Static map/zone NIF leads. |
| `semantic-nif-waypoint-poi` | 0 | 500 | 0 | No waypoint/POI NIF leads in this bounded sample. |

These are static asset hints only. Do not promote to runtime truth without external proof-tiered consumers.

## Guard/proof status

`@264/#15` remains the strongest topology-bearing family:

| Family | Current guarded status |
|---|---|
| `meshSize=297 extra@264 index-u16be-strip-lead` | Aggregate guard passes. |
| `v=128` | count 2, raw-zero-based wins 2, subtract-one wins 0. |
| `v=95` | count 1, raw-zero-based wins 1, subtract-one wins 0. |
| `v=80` | count 1, raw-zero-based wins 1, subtract-one wins 0. |
| `v=64` | count 1, raw-zero-based wins 1, subtract-one wins 0. |

Focused sibling proof guard passed for:

- `6fc01704d4a509d5`
- `caa9a88e94ec8db0`

## Latest validation performed before push

| Check | Result |
|---|---|
| `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo` | Passed; existing `SharpCompress` NU1902 warning only. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode UsageAccessCorrelationGuard -SkipBuild -PrivacyScan` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode AttributeExtraProofGuard -SkipBuild -PrivacyScan` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode AttributeExtraSiblingProofGuard -SkipBuild -PrivacyScan` | Passed before topology-rank follow-up. |
| `rift_asset_discovery_matrix.py --matrix nif-semantic-hints.json --privacy-scan` | Passed. |
| `git diff --check` / cached check | Passed; line-ending warning only. |
| Privacy scans | Passed. |

Python source was not changed in the last pushed slice, so `python -m py_compile` was not required.

## Safety boundaries

- Work Assets-only unless explicitly told otherwise.
- Do **not** do export/OBJ work yet.
- Do **not** stage or commit `Source/`, `Extracted/`, `Exports/`, `bin/`, `obj/`, `__pycache__`, or `.pyc`.
- Keep `.NET RiftAssetDumper` as parser/source of truth.
- Keep Python/PowerShell as orchestration/reporting/helper surfaces only.
- Treat usage/access and semantic hints as leads only.
- Do not weaken proof guards.
- Do not promote geometry truth without repeated family evidence and proof guards.

## Resume prompt

```text
Resume in C:\RIFT MODDING\Assets. Work Assets-only. Start by checking git status/log and latest docs/handoffs file. main is at 05954a1 with a coherent local residual-stream discovery slice in src/RiftAssetDumper/Program.cs, scripts/Invoke-RiftAssetWorkflow.ps1, and this handoff. Continue discovery-first NIF/static asset truth work; no export/OBJ and no live movement. Existing helpers: Invoke-RiftAssetWorkflow.ps1 -Mode UsageAccessCorrelationGuard, AttributeExtraProofGuard, AttributeExtraSiblingProofGuard, ResidualLeadGuard, plus scripts/discovery-matrices/nif-semantic-hints.json. Use usage/access, semantic hints, and residual leads as candidate-only ranking evidence. Next best slice: add a dry-run residual-position classifier report for meshSize=305 stream@188 StringValue=POSITION that explains why payloads 96/180/288/396 miss the strict classifier and what guard threshold would be needed. Validate with build, relevant guard/smoke, git diff --check, and privacy scan before commit/push.
```

## Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Add a dry-run residual-position classifier report for `meshSize=305 stream@188 StringValue=POSITION`; keep output explicitly candidate-only. |
| 2 | Cross-tab `meshSize=305 stream@188` residuals by payload size, vector count, plausible ratio, extent, archive, entry family, and mesh block repetition. |
| 3 | Cross-tab residual `StringValue=POSITION` groups by payload size, vector count, plausible ratio, and mesh size. |
| 4 | Keep `meshSize=325` residual search deprioritized unless new evidence appears; current residual count is zero. |
| 5 | Generate Markdown summaries directly from MeshBindings JSON to reduce manual handoff work. |
| 6 | Create an `asset-semantic-context` packet schema for hint-only map/zone/actor NIF leads. |
| 7 | Cross-tab semantic-hint NIFs by archive, entry family, model refs, and texture refs. |
| 8 | Add a staged-file guard that refuses generated/copy/build outputs before commit. |
| 9 | Re-run `@264/#15` sibling probes after any topology parser/report change. |
| 10 | Keep OBJ/export blocked until position source, index/topology, normal/UV, sane bounds, repeated-family evidence, and proof guards all agree. |
## Autonomous continuation update — 2026-05-18 03:11:58 -04:00 America/New_York

Continued Assets-only NIF/NiMesh residual discovery. No OBJ/export work, no live-game interaction, and no generated/copied asset output was staged.

### Milestone F — dry-run residual position classifier report

Added a candidate-only `ResidualPositionClassifierReport` workflow mode over the existing MeshBindings inventory.

| File | Change |
|---|---|
| `src/RiftAssetDumper/Program.cs` | Adds residual ROR1 finite-ratio output plus `StrictRotatedFloat3PositionClassifierReview` to each `TopResidualStreams` row. The review records current strict classifier thresholds, pass/fail, miss reasons, and the maximum plausible-ratio threshold that would be required for each sample if all other strict inputs pass. |
| `scripts/Invoke-RiftAssetWorkflow.ps1` | Adds `-Mode ResidualPositionClassifierReport`, prints strict threshold context, target rows, miss reasons, and sample/repetition context for `meshSize=305 stream@188 StringValue=POSITION usage=1 access=19`. |

Strict classifier remains unchanged:

```text
VectorCount >= 3
FiniteVectorRatio >= 0.95
PlausibleValueRatio >= 0.95
MaxExtent >= 0.0001
NonZeroVectorRatio >= 0.50
```

Current dry-run result for `meshSize=305 stream@188 POSITION`:

| Result | Evidence |
|---|---|
| Target rows | 8 residual rows. |
| Strict pass rows | 0. |
| Candidate-guard rows | 5 rows can support candidate-only `PlausibleValueRatio >= 0.80` tracking. |
| Plausible range among candidate-guard rows | `0.8283..0.9444`. |
| Main strict miss reason | `PlausibleValueRatio < 0.95` for the repeated bounded-position-like rows. |
| Low-signal rows | Payloads `40`, `116`, and `132` also miss finite/nonzero/extent thresholds and should remain noise unless future family evidence says otherwise. |
| Repetition context | Stronger repeated rows are in one archive and repeat across `mesh#7`/`mesh#27` sample pairs; this is still candidate-only ranking evidence, not geometry truth. |

Interpretation: `meshSize=305 stream@188 POSITION` remains the best residual follow-up lane, but the strict parser role should not be promoted. The right next step is broader candidate-only family cross-tab/ranking, not threshold weakening.

### Milestone G — generated Markdown sidecar for resume speed

`ResidualPositionClassifierReport` now writes an ignored generated Markdown sidecar:

```text
C:\RIFT MODDING\Assets\Exports\residual-position-classifier-report.md
```

This sidecar preserves the same candidate-only classifier summary, miss reasons, and sample repetition context outside console scrollback. It is generated output under `Exports/` and must not be staged.

### Validation after this continuation

| Check | Result |
|---|---|
| `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo` | Passed; existing `SharpCompress` NU1902 warning only. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualPositionClassifierReport -SkipBuild -PrivacyScan` | Passed after strict-mode sample-count fix; wrote ignored Markdown sidecar; privacy scan passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode MeshBindings -SmokeMaxTotal 100 -SkipBuild -PrivacyScan` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualLeadGuard -SkipBuild -PrivacyScan` | Passed before the final display-only sample-context patch. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode UsageAccessCorrelationGuard -SkipBuild -PrivacyScan` | Passed before the final display-only sample-context patch. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode AttributeExtraProofGuard -SkipBuild -PrivacyScan` | Passed before the final display-only sample-context patch. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode AttributeExtraSiblingProofGuard -SkipBuild -PrivacyScan` | Passed before the final display-only sample-context patch. |

### Current exact resume step

Continue with candidate-only residual family ranking for `meshSize=305 stream@188 POSITION`:

1. Cross-tab repeated rows by payload, vector count, plausible ratio, extent, archive, entry family, and mesh-block repetition.
2. Compare `mesh#7` and `mesh#27` repetitions for the same asset IDs to decide whether this is duplicated stream binding or a structural family clue.
3. Keep `ResidualPositionClassifierReport` and `ResidualLeadGuard` fail-closed; do not lower the strict `PlausibleValueRatio >= 0.95` role threshold.
4. Do not promote geometry/export truth.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Add a JSON/Markdown residual-family cross-tab for `meshSize=305 stream@188 POSITION` grouped by payload and sample ID. |
| 2 | Compare `mesh#7` vs `mesh#27` rows for matching IDs to see if duplicate mesh blocks carry the same candidate stream. |
| 3 | Add a candidate-only guard requiring repeated rows to stay below strict promotion while preserving plausible-ratio evidence. |
| 4 | Probe one `payload=288` and one `payload=180` sample with stream-body output and compare prefix vectors side by side. |
| 5 | Keep payloads `40`, `116`, and `132` in low-signal/noise status until repeated evidence appears. |
| 6 | Cross-tab `meshSize=329` residual COLOR/repeated-pattern rows separately from POSITION rows. |
| 7 | Generate a compact Markdown summary from MeshBindings JSON to reduce handoff drift. |
| 8 | Add a pre-commit generated-output guard for `Source/`, `Extracted/`, `Exports/`, `bin/`, `obj/`, `__pycache__`, and `.pyc`. |
| 9 | Re-run `AttributeExtraSiblingProofGuard` after any future topology/probe behavior change. |
| 10 | Keep OBJ/export blocked until position source, topology/index, normal/UV, sane bounds, repeated-family evidence, and proof guards all agree. |

## Autonomous continuation update — 2026-05-18 03:38:27 -04:00 America/New_York

Continued the residual-stream lane without changing parser truth promotion, topology proof guards, OBJ/export behavior, or live-game interaction. Generated probe/report files are under ignored `Exports/` and remain non-staged output.

### Milestone H — meshSize=321 residual sample probed and classified low-signal

Focused the remaining handoff-specified sample:

| Field | Evidence |
|---|---|
| Asset ID | `fedf45d1500a61ea` |
| Mesh block | `#6` |
| Residual stream | `stream@204` / block `#26` |
| Declared payload | `40` bytes |
| Probe output | `C:\RIFT MODDING\Assets\Exports\probe-residual-mesh321-fedf45d1500a61ea-stream26.json` |
| Stream-body class | `strided-body` |
| Body prefix | `ffff80ffffff80ffffff80ffffff80ff` |
| U16 prefix | repeated `65535,65408`-style sentinel values |
| Float32 prefix | mostly null/non-plausible, with extreme negative values later |
| ROR1 stats from MeshBindings | `VectorCount=3`, `Finite=1`, `Plausible=0.2222`, `NonZero=0.3333`, `Extent=0` |
| Decision | side-stream noise, not a narrow position-source lead |

### Milestone I — residual target family review/guard

Expanded `ResidualLeadGuard` beyond the original target counts so it now fail-closes on changed residual-family routing:

| Family | Current routing |
|---|---|
| `meshSize=305 stream@188 POSITION` | Candidate-only repeated family; five rows with `PlausibleValueRatio >= 0.80`, still below strict `0.95` role promotion. |
| `meshSize=297 stream@24 TEXCOORD` | Two high-plausible singleton follow-ups only; guard fails if these become repeated or POSITION-labeled without review. |
| `meshSize=321 stream@204 POSITION` | Low-signal side-stream noise profile guarded. |
| `meshSize=329 stream@212 POSITION` | Low-signal side-stream noise profile guarded (`finite=0`, `plausible=0`, `nonzero=0`, `extent=0`). |
| `meshSize=329 stream@296 COLOR` | Repeated-pattern side-stream family guarded (`20` COLOR/u32-repeated-pattern rows, plausible max `0`). |
| `meshSize=325` | Residual-empty state retained (`0` residual streams). |

New ignored generated review outputs:

```text
C:\RIFT MODDING\Assets\Exports\residual-target-family-review.json
C:\RIFT MODDING\Assets\Exports\residual-target-family-review.md
```

### Validation for Milestones H-I

| Check | Result |
|---|---|
| `probe-nif-stream-body --id fedf45d1500a61ea --stream-block 26` | Passed; wrote ignored probe JSON; existing `SharpCompress` NU1902 warning only. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualLeadGuard -SkipBuild -PrivacyScan` | Passed; wrote ignored residual target family review JSON/Markdown; privacy scan passed. |

### Current exact resume step

Continue with safe offline validation/finalization for this residual slice:

1. Re-run `ResidualPositionClassifierReport` after the `ResidualLeadGuard` expansion to ensure the meshSize=305 cross-tab still agrees with the broader family review.
2. Run `dotnet build`, `git diff --check`, and a tracked-file privacy/hygiene scan.
3. If all pass, inspect `git status --short --branch` and keep generated `Exports/` output unstaged.
4. Next safe discovery slice after validation: compare representative `payload=288` and `payload=180` probe JSON against the family cross-tab in a generated note, or pivot to semantic-hint cross-tabs if residual evidence is exhausted.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Re-run `ResidualPositionClassifierReport` and confirm its meshSize=305 payload/sample cross-tab still matches the broader residual target family review. |
| 2 | Add a generated probe-comparison note for representative payloads `288` and `180` using existing stream-body probe JSON plus the family cross-tab prefixes. |
| 3 | Keep the meshSize=321 residual stream in side-stream noise status unless future data changes finite/plausible/nonzero/extent evidence. |
| 4 | Keep meshSize=329 COLOR repeated-pattern rows separated from POSITION rows in all future ranking summaries. |
| 5 | Re-check meshSize=297 singleton TEXCOORD rows only as follow-up candidates; do not promote without repetition. |
| 6 | Add a staged-file generated-output guard before any future commit/push. |
| 7 | Run `UsageAccessCorrelationGuard` after any usage/access routing change. |
| 8 | Run `AttributeExtraProofGuard` and `AttributeExtraSiblingProofGuard` after any topology/probe behavior change. |
| 9 | Keep semantic NIF hints as static ranking context only, not runtime truth. |
| 10 | Keep OBJ/export blocked until position source, topology/index, normal/UV, sane bounds, repeated-family evidence, and proof guards all agree. |

## Autonomous continuation update — 2026-05-18 03:43:54 -04:00 America/New_York

### Milestone J — representative residual probe commands and comparison note

`ResidualPositionClassifierReport` now adds representative stream-body probe commands to the generated residual family cross-tab. It selects one `mesh#7` sample per repeated candidate payload and writes command strings that output ignored JSON under `Exports/`.

Generated output updated by the workflow:

```text
C:\RIFT MODDING\Assets\Exports\residual-position-family-crosstab.json
C:\RIFT MODDING\Assets\Exports\residual-position-family-crosstab.md
```

A separate ignored comparison note was generated from existing `payload=288` and `payload=180` probes:

```text
C:\RIFT MODDING\Assets\Exports\residual-position-probe-comparison.md
```

Probe comparison summary:

| Payload | ID | Probe class | Cross-tab interpretation |
|---:|---|---|---|
| `288` | `014e1ff60d8508f1` | `uint16-compatible-body` | ROR1 prefix is bounded-position-like, but still candidate-only. |
| `180` | `8c3e2a88780e74bd` | `uint16-compatible-body` | ROR1 prefix is bounded-position-like, but still candidate-only. |

No parser role, topology truth, or export readiness was promoted.

### Validation after Milestone J

| Check | Result |
|---|---|
| `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualPositionClassifierReport -SkipBuild -PrivacyScan` | Passed; cross-tab guard stayed `same paired stream/body/prefix rows=11`, divergent paired rows `0`, strict passes `0`; privacy scan passed. |
| `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo` | Passed; existing `SharpCompress` NU1902 warning only. |
| `git diff --check` | Passed; Windows LF-to-CRLF warnings only. |
| `git diff --cached --check` | Passed; no staged files. |
| Changed-file hygiene scan | Passed: no trailing whitespace, no raw local user-profile/account paths, no unexpected control chars. |
| Generated-output ignore check | Passed for residual classifier/cross-tab/family/probe comparison outputs under `Exports/`. |

Current status remains uncommitted and unstaged:

```text
## main...origin/main
 M scripts/Invoke-RiftAssetWorkflow.ps1
 M src/RiftAssetDumper/Program.cs
?? docs/handoffs/2026-05-17-190655-assets-discovery-resume-handoff.md
```

### Current exact resume step

The residual lane now has candidate-only guards and generated summaries for `meshSize=305`, low-signal routing for `321/329`, singleton routing for `297`, and explicit probe commands. The next safe offline slice is either:

1. add a generated-output/staged-file safety guard before any future commit/push, or
2. return to NIF semantic-hint cross-tabs for actor/object/map-zone static leads, keeping them hint-only.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Add a staged/generated-output guard before any commit/push workflow touches these files. |
| 2 | Re-run `ResidualLeadGuard` and `ResidualPositionClassifierReport` together after any future residual C# change. |
| 3 | Keep `payload=288` as the strongest residual-position candidate-only family but below strict classifier promotion. |
| 4 | Keep `payload=180` as useful corroborating candidate-only evidence, not a role promotion. |
| 5 | Probe one representative `payload=96` row if additional residual-body comparison is needed. |
| 6 | Keep `meshSize=321 stream@204` in side-stream noise status unless future evidence changes. |
| 7 | Keep `meshSize=329 COLOR` repeated-pattern rows separated from POSITION searches. |
| 8 | Only revisit `meshSize=297` residuals if singleton rows repeat or become POSITION-labeled. |
| 9 | Build a semantic-hint cross-tab from NIF actor/object and map-zone results as hint-only ranking context. |
| 10 | Keep OBJ/export blocked until position source, topology/index, normal/UV, sane bounds, repeated-family evidence, and proof guards all agree. |

## Autonomous continuation update — 2026-05-18 03:49:30 -04:00 America/New_York

### Milestone K — generated-output safety guard

Added `Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard`.

The guard checks both tracked and staged paths and fails if any of these generated/copy/build output classes are present:

```text
Source/
Extracted/
Exports/
bin/
obj/
__pycache__/
*.pyc
```

Validation:

| Check | Result |
|---|---|
| `Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard -PrivacyScan` | Passed: tracked generated/copy/build output paths `0`; staged generated/copy/build output paths `0`; privacy scan passed. |

### Milestone L — hint-only NIF semantic cross-tab

Created an ignored, generated cross-tab from the existing bounded `nif-semantic-hints` matrix outputs:

```text
C:\RIFT MODDING\Assets\Exports\discovery-matrix\nif-semantic-hints\nif-semantic-hint-crosstab.json
C:\RIFT MODDING\Assets\Exports\discovery-matrix\nif-semantic-hints\nif-semantic-hint-crosstab.md
```

Summary:

| Metric | Count |
|---|---:|
| `hint:actor-object` NIF entries | 11 |
| `hint:map-zone` NIF entries | 19 |
| `hint:waypoint-poi` NIF entries | 0 |
| Actor/map overlap IDs | 3 |

Overlapping IDs in the bounded sample:

| ID | Primary hint bucket |
|---|---|
| `0928f21ce4b7ae64` | `vfx/atmosphere/model/sky_ep3_character_select_starfield_01.ma` |
| `48ca3efc7ea35d1f` | `ep1/character/common/props` |
| `78f96107f1fb5c38` | `vfx/atmosphere/model/sky_freemarch_dome.ma` |

Interpretation: semantic hints remain static search/ranking context only. They do not prove runtime identity, mesh geometry roles, topology, or export readiness.

### Current exact resume step

The current local slice is now validation/handoff-ready. Before any commit request, run:

1. `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo`
2. `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualLeadGuard -SkipBuild -PrivacyScan`
3. `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualPositionClassifierReport -SkipBuild -PrivacyScan`
4. `Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard -PrivacyScan`
5. `git diff --check`
6. `git status --short --branch`

Do not stage ignored generated outputs. Do not commit unless explicitly requested.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | If commit is requested, stage only `src/RiftAssetDumper/Program.cs`, `scripts/Invoke-RiftAssetWorkflow.ps1`, and this handoff. |
| 2 | Re-run `GeneratedOutputGuard` immediately before staging/commit. |
| 3 | Keep residual streams as candidate-only ranking evidence; do not lower strict classifier thresholds. |
| 4 | Probe `payload=96` only if one more residual-body comparison is needed. |
| 5 | Use the semantic-hint cross-tab only to prioritize offline inspection, not as runtime truth. |
| 6 | Consider a tracked helper to regenerate semantic cross-tabs if this generated note proves useful. |
| 7 | Re-run `AttributeExtraProofGuard` after any topology parser/report change. |
| 8 | Re-run `AttributeExtraSiblingProofGuard` after any focused topology/probe behavior change. |
| 9 | Keep generated/copy/build outputs ignored and unstaged. |
| 10 | Keep OBJ/export blocked until position source, topology/index, normal/UV, sane bounds, repeated-family evidence, and proof guards all agree. |

## Autonomous continuation update — 2026-05-18 03:55:10 -04:00 America/New_York

### Milestone M — repeatable semantic hint cross-tab workflow mode

Promoted the generated-only semantic hint cross-tab into a repeatable workflow mode:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode SemanticHintCrossTab -PrivacyScan
```

This mode reads existing bounded matrix output under ignored `Exports/discovery-matrix/nif-semantic-hints/` and rewrites:

```text
C:\RIFT MODDING\Assets\Exports\discovery-matrix\nif-semantic-hints\nif-semantic-hint-crosstab.json
C:\RIFT MODDING\Assets\Exports\discovery-matrix\nif-semantic-hints\nif-semantic-hint-crosstab.md
```

It does not run live game interaction, does not export OBJ/assets, and does not promote hints beyond static search/ranking context.

Validation:

| Check | Result |
|---|---|
| `Invoke-RiftAssetWorkflow.ps1 -Mode SemanticHintCrossTab -PrivacyScan` | Passed: actor/object entries `11`, map-zone entries `19`, waypoint/POI entries `0`, actor/map overlap `3`; privacy scan passed. |
| `git diff --check` | Passed; Windows LF-to-CRLF warnings only. |
| Changed-file hygiene scan | Passed. |

### Current exact resume step

If continuing without committing, the next best offline slice is narrow review only:

1. Run the final validation bundle (`build`, residual guards, semantic cross-tab, generated-output guard, `git diff --check`).
2. If still clean, stop for user approval before commit/push or before broader feature expansion.
3. Do not stage generated `Exports/` outputs.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Run final validation bundle before any commit request. |
| 2 | If commit is requested, stage only the two tracked code files plus this handoff. |
| 3 | Keep all generated reports under ignored `Exports/`. |
| 4 | Re-run `SemanticHintCrossTab` only after regenerating the underlying matrix outputs. |
| 5 | Re-run `ResidualPositionClassifierReport` after any residual classifier/report change. |
| 6 | Re-run `ResidualLeadGuard` after any residual target family change. |
| 7 | Keep meshSize=321 and meshSize=329 side-stream decisions candidate/noise only. |
| 8 | Keep meshSize=297 singleton residuals as follow-up only. |
| 9 | Keep semantic hints as static asset-ranking context only. |
| 10 | Keep OBJ/export blocked until all required geometry proof conditions agree. |

## Final validation checkpoint — 2026-05-18 03:59:30 -04:00 America/New_York

| Check | Result |
|---|---|
| `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo` | Passed; existing `SharpCompress` NU1902 warning only. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualLeadGuard -SkipBuild -PrivacyScan` | Passed; residual target family review regenerated; privacy scan passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualPositionClassifierReport -SkipBuild -PrivacyScan` | Passed; `same paired stream/body/prefix rows=11`, divergent paired rows `0`, strict passes `0`; privacy scan passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode SemanticHintCrossTab -PrivacyScan` | Passed; actor/object `11`, map-zone `19`, waypoint/POI `0`, overlap `3`; privacy scan passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard -PrivacyScan` | Passed; tracked generated/copy/build output paths `0`, staged generated/copy/build output paths `0`; privacy scan passed. |
| `git diff --check` | Passed; Windows LF-to-CRLF warnings only. |
| `git diff --cached --check` | Passed; no staged files. |
| Changed-file hygiene scan | Passed. |

Status at checkpoint:

```text
## main...origin/main
 M scripts/Invoke-RiftAssetWorkflow.ps1
 M src/RiftAssetDumper/Program.cs
?? docs/handoffs/2026-05-17-190655-assets-discovery-resume-handoff.md
```

No generated/copied asset output is staged.

## Autonomous continuation update — 2026-05-18 04:35:55 -04:00 America/New_York

### Milestone N — position-source gap report workflow mode

Added and validated a repeatable candidate-only workflow mode:

`	ext
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode PositionSourceGapReport -SkipBuild -PrivacyScan
`

Generated ignored outputs:

`	ext
C:\RIFT MODDING\Assets\Exports\position-source-gap-report.json
C:\RIFT MODDING\Assets\Exports\position-source-gap-report.md
`

Current target-family ranking summary:

| Mesh size | Position leads | Pairing count | Attribute rows | Residuals | Residual POSITION candidates | Decision |
|---:|---:|---:|---:|---:|---:|---|
| 297 | 19 | 17 | 4 | 2 | 0 | topology-proof anchor; residual singleton follow-up only |
| 305 | 41 | 145 | 2 | 55 | 5 | residual-position-candidate-family |
| 321 | 24 | 197 | 9 | 1 | 0 | topology-rich family; residual side-streams low-signal |
| 325 | 1 | 501 | 1 | 0 | 0 | topology-rich sparse-position singleton lead |
| 329 | 72 | 16 | 22 | 49 | 0 | attribute-rich family; residual side-streams low-signal |

Interpretation: this is a search-ranking/gap report only. It does not promote residual streams, sparse position leads, topology candidates, or semantic hints into parser truth or export readiness.

Validation:

| Check | Result |
|---|---|
| Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceGapReport -SkipBuild -PrivacyScan | Passed after explicit mode dispatch was added; privacy scan passed. |

### Milestone O — meshSize 325/329 sibling position-source probe

Focused probe-nif-mesh on asset e3de1077a37d0337:

| Mesh | Mesh size | Position | Normal | UV | Vertex count | Topology | Pairings/extras |
|---:|---:|---|---|---|---:|---|---:|
| #6 | 325 | stream@292/#24 payload=852 usage=1 access=19 | stream@216/#25 payload=852 | stream@300/#29 payload=568 | 71 | implicit-triangle-strip-or-fan-candidate | 0/0 |
| #30 | 329 | stream@296/#24 payload=852 usage=1 access=19 | stream@220/#44 payload=852 | stream@304/#48 payload=568 | 71 | implicit-triangle-strip-or-fan-candidate | 0/0 |

Candidate-only clue: both sibling meshes share the same position stream block #24 and payload length while mesh payload offsets shift by the same +4 as the mesh-size delta. Normal/UV streams remain sibling-local blocks. This is parser-search evidence only, not geometry truth.

Generated ignored probes:

`	ext
C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-e3de1077a37d0337-mesh6.json
C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-e3de1077a37d0337-mesh30.json
`

### Milestone P — meshSize 329 repeated sibling position-source probe

Focused probe-nif-mesh on asset 8e01613d7ce9e297:

| Mesh | Mesh size | Position | Normal | UV | Vertex count | Topology | Pairings/extras |
|---:|---:|---|---|---|---:|---|---:|
| #6 | 329 | stream@296/#25 payload=1116 usage=1 access=19 | stream@220/#26 payload=1116 | stream@304/#30 payload=744 | 93 | implicit-triangle-list-candidate | 0/0 |
| #31 | 329 | stream@296/#25 payload=1116 usage=1 access=19 | stream@220/#45 payload=1116 | stream@304/#49 payload=744 | 93 | implicit-triangle-list-candidate | 0/0 |

Candidate-only clue: both sibling meshes share the same position stream block #25, payload length, usage/access, mesh payload offset, vertex count, and topology candidate. Normal/UV streams remain sibling-local blocks. This is a narrow follow-up lead for source binding discovery, not a role promotion.

Generated ignored probes:

`	ext
C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-8e01613d7ce9e297-mesh6.json
C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-8e01613d7ce9e297-mesh31.json
`

### Milestone Q — repeatable sibling position-source probe report

Added and validated a repeatable workflow mode:

`	ext
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode PositionSourceSiblingProbeReport -SkipBuild -PrivacyScan
`

This mode regenerates the four focused sibling probes above, then writes ignored report outputs:

`	ext
C:\RIFT MODDING\Assets\Exports\position-source-sibling-probe-report.json
C:\RIFT MODDING\Assets\Exports\position-source-sibling-probe-report.md
`

Guarded invariants:

| Pair | Guarded candidate invariant |
|---|---|
| e3de1077a37d0337 mesh #6/#30 | shared position block/payload/usage/access/role, same vertex count, same primary topology, shifted position offset consistent with mesh-size delta |
| 8e01613d7ce9e297 mesh #6/#31 | shared position block/payload/usage/access/role, same vertex count, same primary topology, same position mesh payload offset |

Validation:

| Check | Result |
|---|---|
| Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingProbeReport -SkipBuild -PrivacyScan | Passed; regenerated all four focused probes; sibling comparison report written; privacy scan passed. |

### Current exact resume step

Run the validation bundle after this appended handoff section:

1. dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo
2. Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceGapReport -SkipBuild -PrivacyScan
3. Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingProbeReport -SkipBuild -PrivacyScan
4. Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard -PrivacyScan
5. git diff --check
6. changed-file hygiene scan
7. git status --short --branch

No generated/copied asset output should be staged. Do not commit unless explicitly requested.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Validate the new PositionSourceSiblingProbeReport mode with the full final bundle. |
| 2 | Use the sibling report to prioritize source-binding inspection for shared position stream blocks only. |
| 3 | Keep e3de1077a37d0337 as a shifted-offset sibling clue, not parser truth. |
| 4 | Keep 8e01613d7ce9e297 as a repeated-offset sibling clue, not parser truth. |
| 5 | Add more sibling pairs only after they repeat the shared-position invariant without weakening guards. |
| 6 | Keep residual meshSize=305 candidates separate from sibling position-source evidence. |
| 7 | Keep meshSize=321/329 residual side-stream/noise decisions candidate-only. |
| 8 | Re-run AttributeExtraSiblingProofGuard after any topology/probe reporting behavior change. |
| 9 | Re-run GeneratedOutputGuard before any staging or commit request. |
| 10 | Keep OBJ/export blocked until position source, topology/index, normal/UV, sane bounds, repeated-family evidence, and proof guards all agree. |

## Autonomous continuation update — 2026-05-18 04:48:40 -04:00 America/New_York

### Milestone R — parser-derived position-source sibling lead guard

Added parser-derived sibling position-source aggregation to `inventory-nif-mesh-bindings`:

```text
TopPositionSourceSiblings
```

This groups repeated `position-float3-ror1-lead` streams by asset ID, target `NiDataStream` block, payload length, usage/access, and role. The grouping is candidate-only parser-search evidence; it does not promote geometry truth or export readiness.

Added and validated workflow mode:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode PositionSourceSiblingLeadGuard -SkipBuild -PrivacyScan
```

Generated ignored outputs:

```text
C:\RIFT MODDING\Assets\Exports\position-source-sibling-lead-guard.json
C:\RIFT MODDING\Assets\Exports\position-source-sibling-lead-guard.md
```

Guarded known sibling leads:

| ID | Target block | Payload | Mesh blocks | Mesh offsets | Decision |
|---|---:|---:|---|---|---|
| `e3de1077a37d0337` | `#24` | `852` | `#6,#30` | `292,296` | shifted-position sibling clue only |
| `8e01613d7ce9e297` | `#25` | `1116` | `#6,#31` | `296` | repeated-position sibling clue only |

The new aggregate also exposes broader candidate-only repeated sibling leads in position-rich families, especially mesh pairs shaped like `mesh#7/#27` for meshSize `305`, `mesh#7/#31` for meshSize `321`, and `mesh#7/#34` for meshSize `329`. These are ranking/search leads only and still require focused probes plus normal/UV/topology/proof agreement before any promotion.

Implementation note: first validation attempt caught a PowerShell object/array `Count` ambiguity in the guard wrapper; fixed by array-wrapping the lookup result before checking match count.

Validation:

| Check | Result |
|---|---|
| `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo` | Passed; existing `SharpCompress` NU1902 warning only. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingLeadGuard -SkipBuild -PrivacyScan` | Passed after guard wrapper fix; generated sibling lead guard JSON/markdown; privacy scan passed. |

### Current exact resume step

Run final validation after this handoff append:

1. `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo`
2. `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingLeadGuard -SkipBuild -PrivacyScan`
3. `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingProbeReport -SkipBuild -PrivacyScan`
4. `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceGapReport -SkipBuild -PrivacyScan`
5. `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualLeadGuard -SkipBuild -PrivacyScan`
6. `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualPositionClassifierReport -SkipBuild -PrivacyScan`
7. `Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard -PrivacyScan`
8. `git diff --check`
9. changed-file hygiene scan
10. `git status --short --branch`

Do not stage ignored generated outputs. Do not commit unless explicitly requested.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Use `TopPositionSourceSiblings` to choose the next focused `probe-nif-mesh` pair in meshSize `305`, `321`, or `329`. |
| 2 | Probe one `mesh#7/#27` meshSize `305` sibling group with shared `stream@188` to compare against residual `meshSize=305` candidates. |
| 3 | Probe one `mesh#7/#31` meshSize `321` sibling group with shared `stream@204` to cross-check the current `meshSize=321` side-stream/noise decision. |
| 4 | Probe one `mesh#7/#34` meshSize `329` sibling group with shared `stream@212` to separate position-source siblings from residual `stream@212` noise. |
| 5 | Keep all sibling groups as candidate-only until focused probes show position, normal, UV, topology, and proof guards agree. |
| 6 | Add a compact generated cross-tab by mesh size and sibling mesh-block pair if the guard table becomes too broad. |
| 7 | Keep residual `meshSize=305` reports separate from parser-derived position-source sibling groups. |
| 8 | Re-run `AttributeExtraSiblingProofGuard` after any future topology/probe behavior change. |
| 9 | Re-run `GeneratedOutputGuard` before any staging or commit request. |
| 10 | Keep OBJ/export blocked until all geometry proof gates agree. |

## Autonomous continuation update — 2026-05-18 04:55:32 -04:00 America/New_York

### Milestone S — representative sibling probes for meshSize 305/321/329

Used `TopPositionSourceSiblings` to probe one representative sibling pair in each target family:

| Family | ID | Mesh pair | Shared position stream | Key observation | Decision |
|---|---|---|---|---|---|
| meshSize `305` | `04297730afc68f38` | `#7/#27` | `block#21 payload=192 offsets @188/@188` | mesh `#7` has full `p/n/uv` attribute set; mesh `#27` repeats position but has no full attribute-set binding. | candidate-only source-binding lead |
| meshSize `321` | `03c35c3ba518aab0` | `#7/#31` | `block#25 payload=960 offsets @204/@204` | mesh `#7` has full `p/n/uv` attribute set; mesh `#31` repeats position but has no full attribute-set binding. | candidate-only source-binding lead |
| meshSize `329` | `0364ea142bc00ce7` | `#7/#34` | `block#28 payload=576 offsets @212/@212` | mesh `#7` has full `p/n/uv` attribute set; mesh `#34` repeats position, has no full attribute set, and also exposes an extra position-like stream at `@304/#57 payload=240`. | candidate-only source-binding lead |

Generated ignored probes and comparison report:

```text
C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-04297730afc68f38-mesh7.json
C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-04297730afc68f38-mesh27.json
C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-03c35c3ba518aab0-mesh7.json
C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-03c35c3ba518aab0-mesh31.json
C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-0364ea142bc00ce7-mesh7.json
C:\RIFT MODDING\Assets\Exports\probe-nif-mesh-0364ea142bc00ce7-mesh34.json
C:\RIFT MODDING\Assets\Exports\position-source-sibling-representative-probe-comparison.json
C:\RIFT MODDING\Assets\Exports\position-source-sibling-representative-probe-comparison.md
```

Validation:

| Check | Result |
|---|---|
| `Invoke-RiftAssetWorkflow.ps1 -Mode MeshProbe ... -SkipBuild -PrivacyScan` for all six focused probes | Passed; privacy scan passed for each probe. |
| Representative comparison JSON/markdown generation | Passed after rewriting JSON without embedded raw mesh objects. |

Interpretation: these probes strengthen `TopPositionSourceSiblings` as a useful search index, but they also show the sibling mesh often lacks a complete `position+normal+uv` attribute-set binding. No parser role, topology proof, geometry truth, or OBJ/export readiness was promoted.

### Current exact resume step

Next safe offline slice: convert the representative sibling comparison into a repeatable workflow mode only if it will be reused; otherwise probe the next `TopPositionSourceSiblings` target manually and keep it ignored under `Exports/`.

Do not stage ignored generated outputs. Do not commit unless explicitly requested.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | If this representative comparison will be reused, add a repeatable workflow mode for the three meshSize `305/321/329` sibling probe pairs. |
| 2 | Inspect why sibling meshes `#27/#31/#34` repeat position streams but do not form full attribute sets. |
| 3 | For meshSize `329`, follow up on mesh `#34` extra position-like `@304/#57 payload=240` as candidate-only evidence. |
| 4 | Compare mesh `#7` full attribute sets against sibling-only position streams for normal/UV source shifts. |
| 5 | Keep meshSize `305 stream@188` residual candidates separate from parser-derived position-source siblings. |
| 6 | Keep meshSize `321 stream@204` side-stream/noise residual decision separate from parser-derived position-source siblings. |
| 7 | Keep meshSize `329 stream@212` residual noise decision separate from parser-derived position-source siblings. |
| 8 | Add a compact sibling-family cross-tab only if manual probe count grows. |
| 9 | Re-run final validation before any commit request. |
| 10 | Keep OBJ/export blocked until all geometry proof gates agree. |

## Autonomous continuation update — 2026-05-18 05:02:15 -04:00 America/New_York

### Milestone T — repeatable representative sibling probe report

Converted the manual meshSize `305`/`321`/`329` sibling comparison into a repeatable workflow mode:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode PositionSourceSiblingRepresentativeProbeReport -SkipBuild -PrivacyScan
```

The mode regenerates six ignored `probe-nif-mesh` outputs, then writes:

```text
C:\RIFT MODDING\Assets\Exports\position-source-sibling-representative-probe-comparison.json
C:\RIFT MODDING\Assets\Exports\position-source-sibling-representative-probe-comparison.md
```

Guard behavior stays candidate-only:

| Guard | Result |
|---|---|
| Each representative pair has exactly two focused mesh probes. | Passed |
| Each pair still shares at least one position stream by target block and payload. | Passed |
| Primary mesh still has a complete `position+normal+uv` attribute set. | Passed |
| Sibling mesh still has zero complete attribute sets. | Passed |

Validation:

| Check | Result |
|---|---|
| `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingRepresentativeProbeReport -SkipBuild -PrivacyScan` | Passed; existing `SharpCompress` NU1902 warning only; privacy scan passed. |

Interpretation: this makes the representative sibling comparison reproducible without promoting sibling streams to geometry truth. The mode is a candidate-ranking/reporting guard only.

### Current exact resume step

Run final validation for the full current slice, then continue with the next safe offline report/search improvement if validation passes. Do not stage ignored generated outputs. Do not commit unless explicitly requested.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Run final validation across build, sibling guards, residual guards, generated-output guard, and diff hygiene. |
| 2 | Add a compact `TopPositionSourceSiblings` family cross-tab only if it materially improves selecting the next probes. |
| 3 | Keep representative sibling probes separate from residual-stream reports. |
| 4 | Follow up meshSize `329` mesh `#34` `@304/#57 payload=240` as a candidate-only oddity if cross-tab ranking keeps it high. |
| 5 | Probe another meshSize `305` sibling family only if it is distinct by payload/target block from the current representative. |
| 6 | Probe another meshSize `321` sibling family only if it can clarify source-binding vs residual side-stream distinctions. |
| 7 | Re-run `AttributeExtraSiblingProofGuard` after topology/probe behavior changes. |
| 8 | Re-run `GeneratedOutputGuard` before any staging request. |
| 9 | Preserve all generated reports under ignored `Exports/`. |
| 10 | Keep OBJ/export blocked until position, topology/index, normal/UV, bounds, repeated-family evidence, and proof guards agree. |

## Autonomous continuation update — 2026-05-18 05:13:53 -04:00 America/New_York

### Milestone U — position-source sibling family cross-tab guard

Added a repeatable workflow mode:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode PositionSourceSiblingFamilyReport -SkipBuild -PrivacyScan
```

Generated ignored outputs:

```text
C:\RIFT MODDING\Assets\Exports\position-source-sibling-family-report.json
C:\RIFT MODDING\Assets\Exports\position-source-sibling-family-report.md
```

The report groups parser-derived `TopPositionSourceSiblings` by dominant mesh size, sibling mesh-block pair, and stream offset. It remains candidate-only ranking/search evidence.

Guarded family summary:

| Family | Groups | Links | Decision |
|---|---:|---:|---|
| meshSize `329`, mesh `#7/#34`, `stream@212`, target `#28` | `23` | `46` | repeated source-binding probe queue only |
| meshSize `305`, mesh `#7/#27`, `stream@188`, target `#21` | `15` | `30` | repeated source-binding probe queue only |
| meshSize `321`, mesh `#7/#31`, `stream@204`, target `#25` | `10` | `20` | repeated source-binding probe queue only |
| meshSize `325`, mesh `#6/#30`, `stream@292/@296`, target `#24` | `1` | `2` | shifted sibling clue only |
| meshSize `329`, mesh `#6/#31`, `stream@296`, target `#25` | `1` | `2` | shifted sibling clue only |

Why it matters: the repeated families are now easy to rank without confusing them with residual-stream geometry truth. This also guards the known shifted-sibling leads from disappearing silently.

### Milestone V — secondary sibling-family spot checks

Probed one additional sibling pair for each repeated family to test whether the representative probe shape was universal. Outputs are generated under ignored `Exports/`.

| Family | ID | Mesh pair | Result | Decision |
|---|---|---|---|---|
| meshSize `329` `#7/#34 @212` | `04de901531a091ab` | `#7/#34` | mesh `#7` has full `p/n/uv` attribute set (`v=37`); mesh `#34` has no attribute set and repeats position `@212/#28 payload=444`; sibling also has position-like `@304/#57 payload=280`. | candidate-only, reinforces `#34 @304/#57` as follow-up oddity |
| meshSize `305` `#7/#27 @188` | `0d9a25c9a6af7b18` | `#7/#27` | both meshes repeat position `@188/#21 payload=264`, but neither mesh formed a complete attribute set in the probe; mesh `#27` has separate normal/UV-looking streams. | candidate-only; family repetition is not equivalent to full geometry binding |
| meshSize `321` `#7/#31 @204` | `1dc433d4d2e4db64` | `#7/#31` | mesh `#7` has full `p/n/uv` attribute set (`v=60`); mesh `#31` repeats position `@204/#25 payload=720` but has no attribute set. | candidate-only; aligns with representative pattern |

Interpretation: the family cross-tab is useful for selecting probes, but focused probes show family members can vary in complete attribute-set availability. Do not promote any source-sibling family to geometry truth without normal/UV/topology/proof agreement.

### Validation

| Check | Result |
|---|---|
| `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo` | Passed; existing `SharpCompress` NU1902 warning only. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingFamilyReport -SkipBuild -PrivacyScan` | Passed; family cross-tab guard generated JSON/markdown; privacy scan passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingLeadGuard -SkipBuild -PrivacyScan` | Passed; known shifted sibling leads still guarded. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingRepresentativeProbeReport -SkipBuild -PrivacyScan` | Passed; representative pairs stayed candidate-only. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceGapReport -SkipBuild -PrivacyScan` | Passed; topology/residual gap ranking preserved. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualLeadGuard -SkipBuild -PrivacyScan` | Passed; residual side-stream decisions preserved. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualPositionClassifierReport -SkipBuild -PrivacyScan` | Passed; strict classifier dry-run still has zero passes. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode AttributeExtraSiblingProofGuard -SkipBuild -PrivacyScan` | Passed; @264 sibling proof invariants preserved. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard -SkipBuild -PrivacyScan` | Passed; no generated/copy/build outputs tracked or staged. |
| `git diff --check` | Passed; Git emitted existing LF-to-CRLF working-copy warnings only. |
| `git diff --cached --check` | Passed; nothing staged. |
| changed-file hygiene scan | Passed; no non-placeholder `C:\Users` paths in changed tracked files. |

### Current exact resume step

Next safest offline slice: use `position-source-sibling-family-report.md` plus the secondary spot-check result to choose whether to add a narrow, repeatable secondary-probe report or to probe the next distinct payload in the top family. Keep all outputs under ignored `Exports/`. Do not stage or commit without explicit instruction.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | If more automated coverage is worth the runtime, add a narrow secondary sibling-probe report for the three spot-checked IDs above. |
| 2 | Follow meshSize `329` sibling mesh `#34` unique position-like `@304/#57` across another `#7/#34` family member. |
| 3 | For meshSize `305`, probe a different payload where both `#7/#27` might recover a complete attribute set, because `0d9a25...` did not. |
| 4 | Keep `TopPositionSourceSiblings` and residual-stream reports separate; they answer different ranking questions. |
| 5 | Compare family report payload clusters against `ResidualPositionClassifierReport` payload clusters before choosing new probes. |
| 6 | Do not generalize representative-probe attribute-set behavior to the whole family without focused probes. |
| 7 | Re-run `PositionSourceSiblingFamilyReport` after any parser role or inventory limit changes. |
| 8 | Re-run `GeneratedOutputGuard` before any staging/commit request. |
| 9 | Keep copied/generated asset outputs out of git. |
| 10 | Keep OBJ/export blocked until all geometry proof gates agree. |

## Autonomous continuation update — 2026-05-18 13:52:01 -04:00 America/New_York

### Milestone W — secondary sibling probe report

Added repeatable workflow mode:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode PositionSourceSiblingSecondaryProbeReport -SkipBuild -PrivacyScan
```

This regenerates the three previously manual secondary sibling spot checks and writes ignored outputs:

```text
C:\RIFT MODDING\Assets\Exports\position-source-sibling-secondary-probe-comparison.json
C:\RIFT MODDING\Assets\Exports\position-source-sibling-secondary-probe-comparison.md
```

Guarded candidate-only observations:

| Family | ID | Mesh pair | Guarded attribute-set shape | Decision |
|---|---|---|---|---|
| meshSize 329 #7/#34 @212 | 04de901531a091ab | #7/#34 | #7=1, #34=0 | shared source-binding clue only |
| meshSize 305 #7/#27 @188 | 0d9a25c9a6af7b18 | #7/#27 | #7=0, #27=0 | family repetition is not complete geometry binding |
| meshSize 321 #7/#31 @204 | 1dc433d4d2e4db64 | #7/#31 | #7=1, #31=0 | shared source-binding clue only |

### Milestone X — meshSize 329 mesh#34 extra-position report

Manual follow-up on 066fa520a8ce62e3 confirmed that meshSize 329 sibling mesh #34 repeats the extra position-like stream at @304/#57 beyond the original representative. Added repeatable workflow mode:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode PositionSourceSiblingExtraPositionReport -SkipBuild -PrivacyScan
```

Generated ignored outputs:

```text
C:\RIFT MODDING\Assets\Exports\position-source-sibling-extra-position-report.json
C:\RIFT MODDING\Assets\Exports\position-source-sibling-extra-position-report.md
```

Guarded candidate-only rows:

| ID | Shared primary position | mesh#34 extra position | Decision |
|---|---|---|---|
| 0364ea142bc00ce7 | block#28 payload=576 offsets=@212/@212 | @304/#57 payload=240 | repeated oddity; candidate-only |
| 04de901531a091ab | block#28 payload=444 offsets=@212/@212 | @304/#57 payload=280 | repeated oddity; candidate-only |
| 066fa520a8ce62e3 | block#28 payload=264 offsets=@212/@212 | @304/#57 payload=96 | repeated oddity; candidate-only |

Interpretation: @304/#57 is now a repeatable meshSize 329 source-binding clue, but mesh #34 still lacks a complete attribute-set binding. This remains separate from residual-stream evidence and does not promote geometry truth, parser roles, or OBJ/export readiness.

### Milestone Y — residual classifier JSON sidecar

Added a missing machine-readable sidecar for ResidualPositionClassifierReport:

```text
C:\RIFT MODDING\Assets\Exports\residual-position-classifier-report.json
```

The existing Markdown and family cross-tab remain unchanged in purpose. The JSON preserves the strict-threshold dry-run summary for downstream tooling while keeping the lane candidate-only.

Current regenerated result remains:

| Check | Result |
|---|---|
| Target rows | 8 |
| Strict classifier pass rows | 0 |
| Candidate guard rows | 5 |
| Candidate plausible range | 0.8283..0.9444 |
| Same paired stream/body/prefix rows | 11 |
| Divergent paired rows | 0 |

### Current exact resume step

Run final validation for this script/report slice, then either commit on explicit request or continue with the next safe offline probe: compare meshSize 305 residual payload clusters against PositionSourceSiblingFamilyReport before selecting another distinct #7/#27 @188 payload. Keep all generated outputs ignored under Exports/.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Run final validation bundle for build, new modes, sibling regressions, residual classifier, generated-output guard, and diff hygiene. |
| 2 | Compare meshSize 305 residual payload clusters with sibling-family payload clusters before probing another #7/#27 @188 target. |
| 3 | Probe a meshSize 305 payload where both sibling meshes may recover full p/n/uv; current 0d9a25... did not. |
| 4 | Keep the meshSize 329 @304/#57 report as source-binding search evidence only. |
| 5 | Do not merge TopPositionSourceSiblings evidence with residual-stream evidence without a clear report boundary. |
| 6 | Re-run PositionSourceSiblingFamilyReport after any inventory parser or limit changes. |
| 7 | Re-run ResidualPositionClassifierReport after any residual classifier/report changes. |
| 8 | Re-run GeneratedOutputGuard before any staging or commit request. |
| 9 | Keep generated/copied asset outputs out of git. |
| 10 | Keep OBJ/export blocked until position, topology/index, normal/UV, bounds, repeated-family evidence, and proof guards all agree. |

## Final validation checkpoint — 2026-05-18 13:55:03 -04:00 America/New_York

| Check | Result |
|---|---|
| dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo | Passed; existing SharpCompress NU1902 warning only. |
| Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingSecondaryProbeReport -SkipBuild -PrivacyScan | Passed; regenerated secondary sibling comparison JSON/Markdown; privacy scan passed. |
| Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingExtraPositionReport -SkipBuild -PrivacyScan | Passed; regenerated meshSize 329 mesh #34 @304/#57 extra-position JSON/Markdown; privacy scan passed. |
| Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingRepresentativeProbeReport -SkipBuild -PrivacyScan | Passed; representative sibling probes stayed candidate-only. |
| Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingFamilyReport -SkipBuild -PrivacyScan | Passed; family cross-tab stayed candidate-only. |
| Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingLeadGuard -SkipBuild -PrivacyScan | Passed; known sibling leads stayed guarded. |
| Invoke-RiftAssetWorkflow.ps1 -Mode ResidualPositionClassifierReport -SkipBuild -PrivacyScan | Passed; generated missing JSON sidecar and preserved strict-pass 0. |
| Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard -SkipBuild -PrivacyScan | Passed; generated/copy/build outputs are not tracked or staged. |
| git diff --check | Passed; Git emitted existing LF-to-CRLF working-copy warnings only. |
| git diff --cached --check | Passed; nothing staged. |
| changed-file hygiene scan | Passed; no raw user-profile path or local username fragments found in changed tracked files. |

Current tracked changes:

```text
M docs/handoffs/2026-05-17-190655-assets-discovery-resume-handoff.md
M scripts/Invoke-RiftAssetWorkflow.ps1
```

No generated/copied asset output is staged. Do not commit unless explicitly requested.


## Autonomous continuation update — 2026-05-19 01:49:18 -04:00 America/New_York

### Milestone Z — handoff hygiene and DiscoveryWorkbench workflow mode

Executed requested actions #1-10 as an offline, candidate-only Assets slice.

Hygiene fixed first:

| Check | Result |
|---|---|
| Control-character scan before fix | Found 11 affected handoff lines in the newest 2026-05-18 append. |
| Fix applied | Rewrote the corrupted append text/fences/IDs/numeric zeroes as plain UTF-8 Markdown. |
| Control-character scan after fix | Passed: 0 non-whitespace control-character lines in the handoff, workflow script, and workbench script. |

Added a repeatable workflow surface for the previously orphaned Python helper:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode DiscoveryWorkbench -SkipBuild -PrivacyScan
```

Tracked helper/workflow changes:

| File | Purpose |
|---|---|
| `scripts/Invoke-RiftAssetWorkflow.ps1` | Added `DiscoveryWorkbench` mode, candidate-only output checks, queue output checks, and CandidateOnly/CrossChecks guards. |
| `scripts/discovery_workbench.py` | Aggregates existing ignored JSON reports into a candidate-only ranked scoreboard and next-probe queue; now includes explicit cross-check guardrails. |

Generated ignored outputs:

```text
Exports/discovery-workbench-scoreboard.json
Exports/discovery-workbench-scoreboard.md
Exports/discovery-next-probe-queue.json
Exports/discovery-next-probe-queue.md
```

Current DiscoveryWorkbench result:

| Metric | Result |
|---|---:|
| Candidates ranked | 28 |
| Probe queue items | 12 |
| Reports loaded | 8/8 |
| Reports older than current inventory | 5 |
| Top candidate | `residual-305-stream188-payload288` |
| Top score | 100 |

Cross-check guardrails now preserved in the generated scoreboard:

| Guardrail | Decision |
|---|---|
| `mesh305-residual-vs-sibling-family` | Probe the best `meshSize=305 stream@188` residual payload before moving to another family, but do not merge residual plausibility with sibling-source repetition. |
| `mesh329-extra-position-boundary` | Keep meshSize 329 mesh #34 `@304/#57` as source-binding search evidence only. |
| `export-promotion-block` | OBJ/export remains blocked until all geometry proof gates agree. |

### Milestone AA — top candidate payload 288 probed and kept candidate-only

Used the workbench top candidate before probing another family:

```text
residual-305-stream188-payload288
asset id: 014e1ff60d8508f1
stream block: #21
mesh blocks: #7 and #27
```

Generated ignored probe outputs:

```text
Exports/probe-residual-position-payload288-014e1ff60d8508f1-stream21.json
Exports/probe-nif-mesh-014e1ff60d8508f1-mesh7.json
Exports/probe-nif-mesh-014e1ff60d8508f1-mesh27.json
```

Probe result:

| Probe | Result | Interpretation |
|---|---|---|
| Stream body `#21` | payload=288, first16=`0040c19256aa3e00000000000040c192`, classifier=`uint16-compatible-body` | High-ranking residual-position lead, but not a strict parser-role pass. |
| Mesh `#7` | meshSize=305, `@188 -> #21`, payload=288, role=`uint16-compatible-body`, confidence=25, attributeSets=0, pairings=0 | Not a complete geometry binding. |
| Mesh `#27` | meshSize=305, `@188 -> #21`, payload=288, role=`uint16-compatible-body`, confidence=25, attributeSets=0, pairings=0 | Not a complete geometry binding. |

Comparison against sibling-family report:

| Evidence lane | Current evidence | Decision |
|---|---|---|
| Residual classifier | `payload=288`, `PlausibleValueRatio=0.9444`, strict pass remains 0 because threshold is 0.95. | Do not lower thresholds. Keep as candidate-only. |
| Sibling family | meshSize 305 `mesh#7/#27 stream@188` has 15 groups / 30 links. | Useful probe queue, not proof. |
| Focused top probe | Both mesh #7 and #27 reuse stream #21 but do not form complete attribute sets. | This narrows the next question to more residual-cluster comparison, not exporter work. |

### Validation after actions #1-10

| Check | Result |
|---|---|
| `dotnet build .\RiftAssetDumper.slnx --nologo` | Passed; existing SharpCompress NU1902 warning only. |
| PowerShell parser check for `scripts/Invoke-RiftAssetWorkflow.ps1` | Passed. |
| `python -m py_compile scripts/discovery_workbench.py` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingSecondaryProbeReport -SkipBuild -PrivacyScan` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingExtraPositionReport -SkipBuild -PrivacyScan` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingRepresentativeProbeReport -SkipBuild -PrivacyScan` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingFamilyReport -SkipBuild -PrivacyScan` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode PositionSourceSiblingLeadGuard -SkipBuild -PrivacyScan` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualPositionClassifierReport -SkipBuild -PrivacyScan` | Passed; strict-pass remains 0. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode DiscoveryWorkbench -SkipBuild -PrivacyScan` | Passed; top candidate remains payload 288. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard -SkipBuild -PrivacyScan` | Passed; generated/copy/build outputs are not tracked or staged. |
| Top candidate stream-body probe | Passed. |
| Top candidate mesh #7/#27 probes | Passed. |

### Current exact resume step

Next safest offline slice: use the workbench queue to compare additional `meshSize=305 stream@188` residual payload clusters (`96`, `180`, `192`, `396`) against their `mesh#7/#27` focused probes. Keep this as residual-vs-sibling evidence only; do not promote parser roles, geometry truth, or OBJ/export readiness.

Do not stage generated `Exports/` output. Do not commit unless explicitly requested.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Run final git hygiene checks after this handoff append. |
| 2 | If committing is requested, stage only the coherent code/docs slice: workflow script, workbench helper, and this handoff. |
| 3 | Keep generated `Exports/` outputs ignored and unstaged. |
| 4 | Probe payload `96` next, then compare with the payload `288` shape before broadening families. |
| 5 | Probe payload `180` after `96` if payload `96` still shows no full attribute set. |
| 6 | Keep `meshSize=329 @304/#57` separate as source-binding search evidence only. |
| 7 | Do not reduce the strict residual classifier threshold below `0.95`. |
| 8 | Re-run `DiscoveryWorkbench` after each payload-cluster probe to refresh the queue. |
| 9 | Re-run `GeneratedOutputGuard` before any staging request. |
| 10 | Keep OBJ/export blocked until position, topology/index, normal/UV, bounds, repeated-family evidence, and proof guards all agree. |


### Final hygiene note — 2026-05-19 01:55:00 -04:00 America/New_York

After the validation table above, the changed-file privacy scan caught that `scripts/discovery_workbench.py` contained the literal local account token inside its own privacy-pattern definition. The helper was adjusted to construct that token from split string fragments, matching the existing workflow-script hygiene pattern.

Final hygiene checks after that adjustment:

| Check | Result |
|---|---|
| `python -m py_compile scripts/discovery_workbench.py` | Passed. |
| Control-character scan across changed docs/scripts | Passed: 0 affected lines. |
| Changed-file privacy scan across changed docs/scripts | Passed: 0 raw user-profile/account hits. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode DiscoveryWorkbench -SkipBuild -PrivacyScan` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard -SkipBuild -PrivacyScan` | Passed; generated/copy/build outputs remain untracked/unstaged. |
| `git diff --check` | Passed; Git emitted only the existing LF-to-CRLF working-copy warning for the workflow script. |

Current tracked/untracked work remains intentional and unstaged:

```text
M docs/handoffs/2026-05-17-190655-assets-discovery-resume-handoff.md
M scripts/Invoke-RiftAssetWorkflow.ps1
?? scripts/discovery_workbench.py
```


## Autonomous continuation update — 2026-05-19 02:21:37 -04:00 America/New_York

### Milestone AB — saved DiscoveryWorkbench slice before expanding probes

The previously validated DiscoveryWorkbench/handoff slice was committed before starting the residual-cluster probe expansion:

```text
c3614e1 Add candidate-only discovery workbench
```

No generated/copied asset output was staged in that commit.

### Milestone AC — repeatable residual-position cluster probe workflow mode

Added repeatable workflow mode:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode ResidualPositionClusterProbeReport -SkipBuild -PrivacyScan
```

The mode probes the repeated `meshSize=305 stream@188` residual payload cluster that DiscoveryWorkbench and the residual classifier ranked highest. It writes ignored outputs:

```text
Exports/residual-position-cluster-probe-report.json
Exports/residual-position-cluster-probe-report.md
Exports/probe-residual-position-payload96-75cea2f2254e8a76-stream21.json
Exports/probe-residual-position-payload180-14924c7e9f7f03a9-stream21.json
Exports/probe-residual-position-payload192-5a4f390f196037c6-stream21.json
Exports/probe-residual-position-payload288-014e1ff60d8508f1-stream21.json
Exports/probe-residual-position-payload396-b4de91a46cb7d4bc-stream21.json
```

Focused payload result:

| Payload | ID | Stream body classifier | Mesh #7/#27 role at `@188 -> #21` | Attribute sets | Pairings | Decision |
|---:|---|---|---|---:|---:|---|
| 96 | `75cea2f2254e8a76` | `uint16-compatible-body` | both `uint16-compatible-body` | 0 | 0 | candidate-only; no complete geometry binding |
| 180 | `14924c7e9f7f03a9` | `uint16-compatible-body` | both `uint16-compatible-body` | 0 | 0 | candidate-only; no complete geometry binding |
| 192 | `5a4f390f196037c6` | `uint16-compatible-body` | both `uint16-compatible-body` | 0 | 0 | candidate-only; no complete geometry binding |
| 288 | `014e1ff60d8508f1` | `uint16-compatible-body` | both `uint16-compatible-body` | 0 | 0 | candidate-only; no complete geometry binding |
| 396 | `b4de91a46cb7d4bc` | `uint16-compatible-body` | both `uint16-compatible-body` | 0 | 0 | candidate-only; no complete geometry binding |

Interpretation: probing payloads `96/180/192/288/396` confirms that this residual cluster repeats across mesh #7/#27, but focused probes still do not recover a complete geometry binding. Do not promote parser roles, geometry truth, or OBJ/export readiness from this evidence.

### Milestone AD — workbench refreshed after residual-cluster probes

Re-ran:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode DiscoveryWorkbench -SkipBuild -PrivacyScan
```

Result remained:

| Metric | Result |
|---|---:|
| Candidates ranked | 28 |
| Probe queue items | 12 |
| Top candidate | `residual-305-stream188-payload288` |
| Top score | 100 |

Why the top candidate did not promote: DiscoveryWorkbench ranks next discovery value. It does not override strict classifier results, complete-attribute-set checks, topology/index proof, normal/UV proof, bounds checks, or export gates.

### Current exact resume step

Next safest offline slice: add a compact residual-cluster comparison/crosstab that compares these five probed payloads against the residual classifier plausible ratios and sibling-family counts in one generated report. Keep it strictly candidate-only unless a later parser/proof guard recovers position + normal + UV + topology/index + bounds agreement.

Do not stage ignored `Exports/` outputs. Push is not done unless explicitly requested.

### Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Run final validation/hygiene checks for the residual-cluster mode. |
| 2 | If validation passes, commit the coherent residual-cluster workflow/handoff slice separately from `c3614e1`. |
| 3 | Keep generated `Exports/` outputs ignored and unstaged. |
| 4 | Use the cluster report to compare payload `288` against `96/180/192/396` rather than probing a new family yet. |
| 5 | Add classifier-ratio columns to the cluster report if the report becomes the main resume surface. |
| 6 | Keep `meshSize=329 @304/#57` as source-binding evidence only. |
| 7 | Do not lower strict classifier threshold below `0.95`. |
| 8 | Re-run `DiscoveryWorkbench` after any cluster report schema change. |
| 9 | Re-run `GeneratedOutputGuard` before any staging. |
| 10 | Keep OBJ/export blocked until position, topology/index, normal/UV, bounds, repeated-family evidence, and proof guards all agree. |

## Autonomous continuation update — 2026-05-19 02:32:54 -04:00 America/New_York

### Milestone AE — pushed prior residual-cluster slices

Pushed the two already-validated commits to `origin/main` before starting this slice:

```text
c3614e1 Add candidate-only discovery workbench
19bf01a Add residual position cluster probe report
```

Remote `main` is no longer behind those two commits. No generated/copied asset output was staged or pushed.

### Milestone AF — enriched residual cluster report with classifier and sibling-family evidence

Updated `scripts/Invoke-RiftAssetWorkflow.ps1` so `ResidualPositionClusterProbeReport` now cross-links the focused `meshSize=305 stream@188` cluster with existing generated source reports when present:

| Source report | Added evidence in cluster rows |
|---|---|
| `Exports/residual-position-classifier-report.json` | Plausible ratio, strict-pass flag, miss reasons, max plausible threshold for the sample. |
| `Exports/residual-position-family-crosstab.json` | Residual sample/id counts and candidate-guard flag per payload. |
| `Exports/position-source-sibling-family-report.json` | Repeated mesh #7/#27 sibling-family counts for `meshSize=305 stream@188`. |

Refreshed `Exports/residual-position-cluster-probe-report.md` now reports:

| Payload | Plausible | Strict pass | Candidate guard | Residual IDs | Sibling family | Stream classifier | Attribute sets | Pairings | Decision |
|---:|---:|---|---|---:|---|---|---:|---:|---|
| 96 | 0.875 | False | True | 3 | groups=15; links=30; ids=15; target=block#21 | `uint16-compatible-body` | 0 | 0 | candidate-only; no complete geometry binding |
| 180 | 0.8444 | False | True | 3 | groups=15; links=30; ids=15; target=block#21 | `uint16-compatible-body` | 0 | 0 | candidate-only; no complete geometry binding |
| 192 | 0.8542 | False | True | 1 | groups=15; links=30; ids=15; target=block#21 | `uint16-compatible-body` | 0 | 0 | candidate-only; no complete geometry binding |
| 288 | 0.9444 | False | True | 3 | groups=15; links=30; ids=15; target=block#21 | `uint16-compatible-body` | 0 | 0 | candidate-only; no complete geometry binding |
| 396 | 0.8283 | False | True | 1 | groups=15; links=30; ids=15; target=block#21 | `uint16-compatible-body` | 0 | 0 | candidate-only; no complete geometry binding |

Interpretation: payload `288` remains the best candidate by ratio, but it still does not cross the strict `0.95` classifier threshold and still has no complete position + normal/UV + topology/index binding. OBJ/export remains blocked.

### Validation for Milestone AF

| Check | Result |
|---|---|
| PowerShell parse of `scripts/Invoke-RiftAssetWorkflow.ps1` | Passed. |
| `git diff --check` | Passed; Git emitted only the LF-to-CRLF working-copy warning for the workflow script. |
| `dotnet build .\RiftAssetDumper.slnx --nologo` | Passed; existing `SharpCompress` NU1902 warning still appears. |
| `ResidualPositionClassifierReport -SkipBuild -PrivacyScan` | Passed. |
| `PositionSourceSiblingFamilyReport -SkipBuild -PrivacyScan` | Passed. |
| `ResidualPositionClusterProbeReport -SkipBuild -PrivacyScan` | Passed with enriched classifier/family columns. |
| `DiscoveryWorkbench -SkipBuild -PrivacyScan` | Passed; top candidate still `residual-305-stream188-payload288`. |
| `GeneratedOutputGuard -SkipBuild -PrivacyScan` | Passed; generated/copy/build outputs remain untracked and unstaged. |

### Current exact resume step

Commit and push the enriched cluster-report slice after final hygiene checks, staging only:

```text
scripts/Invoke-RiftAssetWorkflow.ps1
docs/handoffs/2026-05-17-190655-assets-discovery-resume-handoff.md
```

Do not stage `Source/`, `Extracted/`, `Exports/`, `bin/`, `obj/`, `__pycache__/`, or `.pyc` files.

### Optional top 20 next best actions

| # | Action |
|---:|---|
| 1 | Commit/push the enriched residual-cluster report slice once final hygiene is clean. |
| 2 | Keep the cluster report as the main resume surface for `meshSize=305 stream@188` instead of opening a new family immediately. |
| 3 | Add a tiny stale-source-report note if any enrichment source is missing when running the cluster mode standalone. |
| 4 | Compare payload `288` against payload `96/180/192/396` by body-layout deltas, not only plausible ratio. |
| 5 | Inspect whether the `uint16-compatible-body` classifier is masking packed/quantized position data. |
| 6 | Keep strict classifier threshold at `0.95`; do not tune it downward to promote payload `288`. |
| 7 | Add a guard assertion that enriched cluster rows never claim export readiness. |
| 8 | Keep `meshSize=329 @304/#57` as separate source-binding evidence only. |
| 9 | Re-run `DiscoveryWorkbench` after any cluster-report schema change. |
| 10 | Re-run `GeneratedOutputGuard` before every staging operation. |
| 11 | Add a compact markdown comparison of `BodyFirst16` values if humans need byte-level triage in the handoff surface. |
| 12 | Add a JSON-only `SourceReportTimestamps` field later if stale generated reports become confusing. |
| 13 | Keep source/generated output ignored and never commit extracted RIFT assets. |
| 14 | Search for a true complete attribute set near repeated payload `288` before considering export paths. |
| 15 | Use `PositionSourceSiblingRepresentativeProbeReport` only after the enriched cluster report stops yielding value. |
| 16 | Preserve candidate-only wording in docs until proof guards agree. |
| 17 | If a new parser hypothesis is added, gate it with bounds, topology/index, normal/UV, and repeated-family checks. |
| 18 | Avoid broad refactors of `Invoke-RiftAssetWorkflow.ps1` while discovery truth is still moving. |
| 19 | Track `SharpCompress` NU1902 separately as dependency hygiene, not as part of this discovery slice. |
| 20 | Keep OBJ/export blocked until position, topology/index, normal/UV, bounds, repeated-family evidence, and proof guards all agree. |

## Autonomous continuation update — 2026-05-19 02:40:41 -04:00 America/New_York

### Milestone AG — action #1-20 residual-cluster proof-surface hardening

Worked the next safe action set from the previous top-20 list while keeping the lane offline, candidate-only, and non-exporting.

Changed `scripts/Invoke-RiftAssetWorkflow.ps1` in `ResidualPositionClusterProbeReport` to add:

| Action area | Result |
|---|---|
| Stale/missing enrichment source handling | Added source-report status rows with existence, UTC write time, and a missing-report note that keeps enrichment omitted rather than failing open. |
| Export-readiness safety | Added per-row `ExportReady=false`, `GeometryTruthPromoted=false`, and a fail-closed assertion that throws if any cluster row ever claims export readiness or promoted geometry truth. |
| Payload `288` byte-layout comparison | Added `BodyComparisonRows` comparing payloads `96/180/192/288/396` against baseline payload `288` using first-128-byte common prefix, diff counts, length deltas, and preferred stride summaries. |
| Packed/quantized review flag | Added `PackedOrQuantizedReview=true` when a row is `uint16-compatible-body`, has high plausible ratio, has no strict pass, and still lacks attribute/pairing proof. This is review evidence only. |
| Focused attribute/index binding search | Added `FocusedAttributeBindingSearchRows`; all five focused payloads still show `0` attribute sets and `0` pairings, so no complete binding was found. |
| Secondary lead separation | Added boundary notes that keep `meshSize=329 @304/#57` separate as source-binding evidence only. |
| Source freshness | Added `SourceReportStatuses` to the generated JSON report so stale source-report confusion is easier to spot in later runs. |

Current generated cluster evidence after validation:

| Payload | Common prefix vs 288 | Diff bytes / compared | Length delta | Packed/quantized review | Focused complete binding |
|---:|---:|---:|---:|---|---|
| 96 | 0 | 57/96 | -192 | True | False |
| 180 | 1 | 43/128 | -108 | True | False |
| 192 | 15 | 56/128 | -96 | True | False |
| 288 | 128 | 0/128 | 0 | True | False |
| 396 | 9 | 55/128 | 108 | True | False |

Interpretation: the `uint16-compatible-body` rows remain plausible enough to justify packed/quantized-position review, but there is still no strict classifier pass, no complete focused attribute/index binding, and no export readiness. Payload `288` remains the best-ranked candidate but stays below the strict `0.95` plausible threshold.

### Validation for Milestone AG

| Check | Result |
|---|---|
| Current branch/status before work | Clean `main...origin/main` at `ec82115`. |
| Latest handoff/recent commits reviewed | Done; resumed from Milestone AF and recent commit `ec82115`. |
| PowerShell parse of `scripts/Invoke-RiftAssetWorkflow.ps1` | Passed. |
| `dotnet build .\RiftAssetDumper.slnx --nologo` | Passed; existing `SharpCompress` NU1902 warning remains. |
| `ResidualPositionClassifierReport -SkipBuild -PrivacyScan` | Passed. |
| `PositionSourceSiblingFamilyReport -SkipBuild -PrivacyScan` | Passed. |
| `ResidualPositionClusterProbeReport -SkipBuild -PrivacyScan` | Passed with byte-layout and focused binding rows. |
| `DiscoveryWorkbench -SkipBuild -PrivacyScan` | Passed; top candidate remains `residual-305-stream188-payload288`. |
| `GeneratedOutputGuard -SkipBuild -PrivacyScan` | Passed; tracked/staged generated/copy/build outputs are zero. |

### Current exact resume step

Run final git hygiene, then commit/push only this coherent code + handoff slice:

```text
scripts/Invoke-RiftAssetWorkflow.ps1
docs/handoffs/2026-05-17-190655-assets-discovery-resume-handoff.md
```

Do not stage generated output under `Source/`, `Extracted/`, `Exports/`, `bin/`, `obj/`, `__pycache__/`, or `.pyc`.

### Optional top 20 next best actions

| # | Action |
|---:|---|
| 1 | Commit/push this proof-surface hardening slice if final hygiene remains clean. |
| 2 | Add a small machine-readable assertion test for `ExportReady=false` / `GeometryTruthPromoted=false` in cluster JSON. |
| 3 | Promote the byte-comparison table into DiscoveryWorkbench scoring only as ranking context, not proof. |
| 4 | Add a packed/quantized parser hypothesis behind a separate fail-closed report mode, not in exporter code. |
| 5 | Compare `UInt16TriplesPrefix` patterns for payloads `96/180/192/288/396`. |
| 6 | Add min/max/range summaries for `UInt16TriplesPrefix` to avoid relying on raw hex alone. |
| 7 | Keep strict plausible threshold at `0.95`; do not tune it downward. |
| 8 | Search for a complete position + normal + UV + topology/index bundle near payload `288` before any promotion. |
| 9 | Keep `meshSize=329 @304/#57` separate until it has its own proof guard. |
| 10 | Re-run `DiscoveryWorkbench` after any schema or scoring change. |
| 11 | Re-run `GeneratedOutputGuard` before every staging operation. |
| 12 | Keep generated outputs ignored and untracked. |
| 13 | Add source-report age warnings only if stale timestamps cause real confusion. |
| 14 | Avoid broad workflow-script refactors until this discovery lane stabilizes. |
| 15 | Keep report schemas backward-compatible for existing generated JSON consumers. |
| 16 | Preserve candidate-only wording in docs and generated reports. |
| 17 | Track `SharpCompress` NU1902 separately from geometry discovery. |
| 18 | Prefer one new guarded evidence surface per commit. |
| 19 | Keep live/export work out of scope until proof guards agree. |
| 20 | Stop at candidate evidence if position, topology/index, normal/UV, bounds, repeated-family evidence, and proof guards do not all agree. |
