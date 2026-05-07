# RIFT Asset Dumper Resume Handoff 🚀

Date: 2026-05-07
Workspace: `C:\RIFT MODDING\Assets`
Repo: `RiftAssetDumper`
Branch: `main`

## TL;DR 🧭

We paused during the next autonomous geometry milestone after successfully pushing the attribute-topology milestone.

| Area | Current state |
|---|---|
| Last pushed commit | `bc02cee` — `Score NIF attribute-set topology leads` |
| Current worktree | Has uncommitted changes in `src/RiftAssetDumper/Program.cs`, `scripts/Invoke-RiftAssetWorkflow.ps1`, and `docs/current-status.md` |
| New uncommitted lead | Extra same-mesh stream fit scoring beside complete position/normal/UV attribute sets |
| Best new evidence | For the top `v=16` attribute family, extra stream `@272`, payload `64`, role `strided-body`, count `6`, fit=`per-vertex:4,per-quad:16` |
| Export status | Still blocked; no OBJ/model export should be claimed or enabled yet |
| Safety | `Source/`, `Extracted/`, and `Exports/` remain ignored/local generated data |

## What was pushed already ✅

Pushed to `origin/main`:

```text
bc02cee Score NIF attribute-set topology leads
```

That commit added structural topology scoring for complete position/normal/UV attribute sets:

| Evidence | Result |
|---|---|
| Complete attribute sets | `52` across copied set |
| Top attribute topology | `implicit-strip-or-quad-candidate` |
| Top vertex count | `16` |
| Top topology count | `7` |
| Topology detail | strip/fan=`14` triangles, quad=`4`, triangle-list rejected |

Validated before that push:

```powershell
dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshBindings -SmokeMaxTotal 50 -SkipBuild -PrivacyScan
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshBindings -NoSmoke -Full -SkipBuild
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshProbe -Id 75d5a06d7c0de1dd -MeshBlock 7 -SkipBuild
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshProbe -Id c841eb9a0ed1c95e -MeshBlock 6 -SkipBuild
```

## Current uncommitted work 🧪

Changed files:

```text
src/RiftAssetDumper/Program.cs
scripts/Invoke-RiftAssetWorkflow.ps1
docs/current-status.md
```

### `src/RiftAssetDumper/Program.cs`

Added extra-stream fit analysis for complete attribute sets:

- `FindNifAttributeSetExtraStreams(...)`
- `NifAttributeExtraStreamSample`
- `NifAttributeExtraStreamAccumulator`
- `NifAttributeExtraStreamGroup`
- `TopAttributeExtraStreams` on `NifMeshBindingInventoryReport`
- Probe console output now shows attribute-set extra streams under the attribute set.

Fit ratios currently calculated:

| Fit | Meaning |
|---|---|
| `per-vertex` | extra payload divides evenly by attribute vertex count |
| `per-triangle-list-triangle` | extra payload divides evenly by triangle-list triangle count |
| `per-strip-or-fan-triangle` | extra payload divides evenly by strip/fan triangle count |
| `per-quad` | extra payload divides evenly by quad count |

This is structural scoring only. It does **not** prove topology by itself.

### `scripts/Invoke-RiftAssetWorkflow.ps1`

Workflow summaries now include:

- `Top attribute extras` in `MeshBindings` summary.
- Per-attribute-set extra streams in `MeshProbe` summary.
- `Get-JsonValueOrDash` helper so missing/null JSON properties print as `-` instead of throwing under strict mode.

### `docs/current-status.md`

Partially updated with the new extra-stream evidence table and the sample extra stream for asset `75d5a06d7c0de1dd`, mesh `#7`.

## Validation already run for uncommitted work ✅

### Build

```powershell
dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo
```

Result: success, `0` warnings, `0` errors.

### Smoke workflow + privacy scan

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshBindings -SmokeMaxTotal 50 -SkipBuild -PrivacyScan
```

Result: success.

Smoke result still has no attribute sets in first 50 NIF payloads, which is expected:

```text
NIF payloads: 50
Pair-compatible meshes: 20
Pair-compatible links: 40
Attribute-compatible meshes: 0
Attribute-compatible sets: 0
Privacy scan passed.
```

### Full mesh-binding inventory

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshBindings -NoSmoke -Full -SkipBuild
```

Result: success.

Key output:

```text
Inspected payloads: 40,203
NIF payloads: 5,111
NiMesh blocks: 5,507
Candidate stream links: 11,564
Pair-compatible meshes: 2,076
Pair-compatible links: 4,468
Attribute-compatible meshes: 52
Attribute-compatible sets: 52
```

Top extra-stream findings:

| Topology | Vertex count | Extra stream | Payload | Role | Count | Fit |
|---|---:|---:|---:|---|---:|---|
| `implicit-strip-or-quad-candidate` | `16` | `@272` | `64` | `strided-body` | `6` | `per-vertex:4,per-quad:16` |
| `implicit-triangle-strip-or-fan-candidate` | `23` | `@296` | `92` | `uv-float2-lead` | `2` | `per-vertex:4` |
| `implicit-triangle-list-or-quad-candidate` | `36` | `@296` | `144` | `position-float3-lead` | `2` | `per-vertex:4,per-triangle-list-triangle:12,per-quad:16` |
| `implicit-triangle-strip-or-fan-candidate` | `38` | `@296` | `152` | `uv-float2-lead` | `2` | `per-vertex:4` |
| `implicit-triangle-list-candidate` | `51` | `@288` | `204` | `strided-body` | `2` | `per-vertex:4,per-triangle-list-triangle:12` |

### Focused attribute-set probe

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshProbe -Id 75d5a06d7c0de1dd -MeshBlock 7 -SkipBuild
```

Result: success.

Key output:

```text
Mesh #7 size=305
@188 -> #21 payload=192 role=position-float3-ror1-lead
@196 -> #22 payload=192 role=normal-float3-ror1-lead
@272 -> #25 payload=64 role=strided-body
@280 -> #26 payload=128 role=uv-float2-ror1-lead
Attribute set: vertexCount=16 topology=implicit-strip-or-quad-candidate
Extra: @272/#25 payload=64 strided-body fit=per-vertex:4,per-quad:16
```

### Focused indexed-family regression probe

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshProbe -Id c841eb9a0ed1c95e -MeshBlock 6 -SkipBuild
```

Result: success; indexed lane unchanged:

```text
Mesh #6 size=325
Pairings: 2
@292/#23 index-u16be-strip-lead max=23 -> @216/#25 normal vertexCount=24 coverage=1
@292/#23 index-u16be-strip-lead max=23 -> @300/#29 uv vertexCount=24 coverage=1
Position source still not proven.
```

## Important interpretation 🧠

The extra stream `@272/#25` in the top `v=16` attribute family is now the highest-value immediate target:

| Observation | Interpretation |
|---|---|
| Payload `64` with `v=16` | Exactly `4` bytes per vertex |
| Same payload with quad candidate `4` | Exactly `16` bytes per quad |
| Role currently `strided-body`, confidence `25` | It needs deeper decoding; current role is intentionally low-confidence |
| Appears in top family `6` times | Repeated enough to justify a targeted probe |

Most useful next command/feature: a probe that dumps/decodes this extra stream body across several sample assets and compares byte/float/u16/u32 interpretations.

## Resume procedure 🔁

Start here:

```powershell
cd "C:\RIFT MODDING\Assets"
git status --short --branch
git log --oneline -5
git diff --stat
```

Then inspect current uncommitted changes:

```powershell
git diff -- src/RiftAssetDumper/Program.cs scripts/Invoke-RiftAssetWorkflow.ps1 docs/current-status.md
```

Recommended validation before committing the uncommitted milestone:

```powershell
dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshBindings -SmokeMaxTotal 50 -SkipBuild -PrivacyScan
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshBindings -NoSmoke -Full -SkipBuild
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode MeshProbe -Id 75d5a06d7c0de1dd -MeshBlock 7 -SkipBuild
git diff --check
git grep -n -I "C:\\Users\\" -- .
```

The `git grep` command should return no tracked raw Windows user-profile paths. The repo intentionally uses `C:\RIFT MODDING\Assets` workspace paths in docs and examples because they do not expose the Windows account username.

## Suggested next implementation slice 🎯

Add a focused extra-stream probe for the attribute-set lane:

```text
probe-nif-attribute-extra --id 75d5a06d7c0de1dd --mesh-block 7 --extra-offset 272
```

Minimal acceptable behavior:

- Find the mesh block.
- Find the attribute set and extra stream at mesh payload offset `@272`.
- Isolate the extra stream declared body after the proven `29`-byte `NiDataStream` header.
- Report:
  - first 64 bytes hex,
  - byte histogram/small integer view,
  - little/big endian `uint16`, `uint32`, `float32`,
  - grouped views: `16 x 4 bytes`, `4 x 16 bytes`, and optionally `14 strip/fan triangle slots` if divisible or near-divisible,
  - repeated values/patterns across top samples.

Do **not** export geometry from this yet.

## Optional top 10 next best recommended actions 🧭

1. Commit the current extra-stream fit milestone after one final validation pass.
2. Add `probe-nif-attribute-extra` for `@272/#25` on the `v=16` attribute family.
3. Aggregate first16/first64 signatures for all top attribute extra streams.
4. Decode `@272` as `16 x 4 bytes` and `4 x 16 bytes`; compare which grouping has stable semantic-looking values.
5. Sample the other `v=16` assets from `TopAttributeExtraStreams` to check whether `@272` repeats structurally.
6. Add targeted role scoring for 4-byte-per-vertex streams instead of leaving them as generic `strided-body`.
7. Continue indexed-lane position-source search for `meshSize=325` after the attribute extra stream is understood.
8. Add index-family topology scoring to pair reports, but keep OBJ export disabled.
9. Keep generated reports under `Exports/` and copied assets under `Source/`; never stage them.
10. Run privacy scans before every push; keep username/profile redaction enabled.

## Ready-to-paste resume prompt 💬

```text
Resume C:\RIFT MODDING\Assets from docs\handoffs\<this-file>. Read the handoff first, inspect current git status and uncommitted changes, then continue autonomously. First finish validating and committing the current attribute extra-stream fit milestone if still present. Then implement the next focused probe for the top v=16 attribute extra stream @272/#25. Keep Source/, Extracted/, and Exports/ uncommitted; run build, workflow smoke/full, probe, privacy scan, commit/push, then reassess strategy.
```
