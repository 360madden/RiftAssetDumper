# Compact handoff — Assets navigation-discovery truth slice

Date: 2026-05-17
Repo: `C:\RIFT MODDING\Assets`
Branch: `main`

## TL;DR

Assets-only discovery advanced in two safe ways:

1. Added a fail-closed `UsageAccessCorrelationGuard` workflow mode for NiDataStream usage/access correlation.
2. Added a bounded NIF semantic-hints matrix profile for static navigation context leads.

This remains **discovery-first**. Usage/access and semantic hints are ranking/search evidence only; no export, OBJ, or durable geometry/runtime truth was promoted.

## Git state at start of this slice

```text
main...origin/main [ahead 2]
HEAD: 1275848 Summarize full usage-access mesh binding evidence
Previous local commit: 7df59c1 Add usage-access mesh binding summaries
```

This handoff slice is intended to be committed with:

- `scripts/Invoke-RiftAssetWorkflow.ps1`
- `scripts/discovery-matrices/nif-semantic-hints.json`
- this handoff file

Do not stage `Source/`, `Extracted/`, `Exports/`, build output, `__pycache__`, or `.pyc`.

## What changed

| File | Change |
|---|---|
| `scripts/Invoke-RiftAssetWorkflow.ps1` | Added `UsageAccessCorrelationGuard` mode that reruns full mesh-binding inventory, validates expected usage/access role aggregates, and rejects top pairing exceptions. |
| `scripts/Invoke-RiftAssetWorkflow.ps1` | MeshBindings summary now prints position-stream lead cross-tabs by mesh size, payload size, and sample stream references. |
| `scripts/discovery-matrices/nif-semantic-hints.json` | Added bounded external matrix jobs for NIF `hint:actor-object`, `hint:map-zone`, and `hint:waypoint-poi` leads. |

## Latest full mesh-binding evidence

Report path:

```text
C:\RIFT MODDING\Assets\Exports\nif-mesh-binding-inventory.json
```

Key counts:

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

Usage/access guard expectations that passed:

| Family | Role | Usage/access | Count | Min guard |
|---|---|---|---:|---:|
| Vertex UV rotated-float lead | `uv-float2-ror1-lead` | `1/19` | 4,633 | 3,000 |
| Vertex normal rotated-float lead | `normal-float3-ror1-lead` | `1/19` | 4,167 | 3,000 |
| Index strip lead | `index-u16be-strip-lead` | `0/19` | 2,101 | 1,500 |
| Position rotated-float lead | `position-float3-ror1-lead` | `1/19` | 210 | 100 |
| Index list lead | `index-u16be-list-lead` | `0/19` | 112 | 50 |

Top-pairing guard:

```text
100 top index-to-vertex pairings checked
0 exceptions
Expected pattern: index usage=0 access=19 -> vertex usage=1 access=19
```

Position-stream cross-tab now shown by the workflow:

| Rank | Mesh size | Count |
|---:|---:|---:|
| 1 | 329 | 72 |
| 2 | 305 | 41 |
| 3 | 321 | 24 |
| 4 | 297 | 19 |
| 5 | 370 | 18 |
| 6 | 333 | 10 |
| 7 | 346 | 9 |
| 8 | 326 | 5 |
| 9 | 330 | 2 |
| 10 | 365 | 2 |

Top position payload sizes: `192=20`, `456=7`, `48=6`, `264=6`, `276=6`, `624=6`, `88=5`, `128=5`, `168=5`, `408=4`.

## NIF semantic-hints profile result

Profile:

```text
C:\RIFT MODDING\Assets\scripts\discovery-matrices\nif-semantic-hints.json
```

Validation run:

```powershell
python "C:\RIFT MODDING\Assets\scripts\rift_asset_discovery_matrix.py" --skip-build --matrix "C:\RIFT MODDING\Assets\scripts\discovery-matrices\nif-semantic-hints.json" --out "C:\RIFT MODDING\Assets\Exports\discovery-matrix\nif-semantic-hints" --privacy-scan
```

Results from first 500 NIF payloads per job:

| Job | Exit | Inspected | Entries | Meaning |
|---|---:|---:|---:|---|
| `semantic-nif-actor-object` | 0 | 500 | 11 | Static actor/object NIF leads found. |
| `semantic-nif-map-zone` | 0 | 500 | 19 | Static map/zone NIF leads found. |
| `semantic-nif-waypoint-poi` | 0 | 500 | 0 | No waypoint/POI NIF leads in this bounded sample. |

These are static hints only. Route any future cross-repo use through proof-tiered packets; do not treat them as runtime truth.

## Geometry proof status

`@264/#15` remains the strongest topology-bearing lane:

| Group | Status |
|---|---|
| `meshSize=297 extra@264 index-u16be-strip-lead` | Guarded aggregate evidence still passes. |
| `v=128` | count 2, raw wins 2, subtract-one wins 0, strip `degenerate-bridge-stitch-candidate`. |
| `v=95` | count 1, raw wins 1, subtract-one wins 0. |
| `v=80` | count 1, raw wins 1, subtract-one wins 0. |
| `v=64` | count 1, raw wins 1, subtract-one wins 0. |

Focused sibling probes still pass for:

- `6fc01704d4a509d5`
- `caa9a88e94ec8db0`

Both preserve raw-zero-based fitness over subtract-one, no sentinel restarts, and the same degenerate-bridge/stitch structure.

## Validation completed

| Check | Result |
|---|---|
| `dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo` | Passed; existing `SharpCompress` NU1902 warning only. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode UsageAccessCorrelationGuard -SkipBuild -PrivacyScan` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode AttributeExtraProofGuard -SkipBuild -PrivacyScan` | Passed. |
| `Invoke-RiftAssetWorkflow.ps1 -Mode AttributeExtraSiblingProofGuard -SkipBuild -PrivacyScan` | Passed. |
| `rift_asset_discovery_matrix.py --matrix nif-semantic-hints.json --privacy-scan` | Passed. |
| `git diff --check` | Passed; line-ending warning only. |
| Privacy scans | Passed; no tracked raw username or non-placeholder `C:\Users` paths. |

Python source was not changed, so `python -m py_compile` was not required for this slice.

## Safety boundaries

- Do **not** do OBJ/export work yet.
- Do **not** stage or commit `Source/`, `Extracted/`, `Exports/`, build output, `__pycache__`, or `.pyc`.
- Keep `.NET RiftAssetDumper` as parser/source of truth.
- Use Python/PowerShell only for orchestration, summaries, schemas, validation, and privacy scans.
- Usage/access and semantic hints are **leads only** until repeated family evidence + proof guards support promotion.
- Do not weaken existing proof guards.

## Resume prompt

```text
Resume in C:\RIFT MODDING\Assets. Work Assets-only. Confirm git status/log first. Continue discovery-first NIF/static asset truth work; no export/OBJ and no live movement. Treat usage/access and semantic hints as leads only. New helper mode should exist: Invoke-RiftAssetWorkflow.ps1 -Mode UsageAccessCorrelationGuard. New matrix profile should exist: scripts/discovery-matrices/nif-semantic-hints.json. Start by using the guarded usage/access split and position cross-tab to rank the next proof slice: either tighten @264/#15 topology fitness or search meshSize=325/321 for missing position-source candidates after known streams are removed. Validate with build, relevant guard/smoke, git diff --check, and privacy scan before commit/push.
```

## Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Commit this validated Assets-only helper/profile slice. |
| 2 | Add topology-fitness fields directly to `TopPairings` groups for faster ranking. |
| 3 | Build a meshSize `325/321` residual-stream report after known index/normal/UV/position/sentinel roles are removed. |
| 4 | Add a focused `meshSize=325` probe set using current top pairings as seed samples. |
| 5 | Add a focused `meshSize=321` probe set using current top pairings as seed samples. |
| 6 | Extend the usage/access guard with a non-failing exception summary for low-count mixed roles. |
| 7 | Generate a Markdown summary from MeshBindings JSON to avoid manual transcription. |
| 8 | Convert NIF semantic-hints output into an `asset-semantic-context` packet schema, still hint-only. |
| 9 | Cross-tab NIF semantic hints by archive/entry family and referenced texture/model strings. |
| 10 | Push only after confirming no generated/copy asset outputs are staged. |
