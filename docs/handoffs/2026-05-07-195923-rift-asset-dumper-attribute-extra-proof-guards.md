# RIFT Asset Dumper Handoff — Attribute-extra topology proof guards 🧷

Date: 2026-05-07
Workspace: `C:\RIFT MODDING\Assets`
Repo: `RiftAssetDumper`
Branch: `main`

## TL;DR 🧭

This handoff captures the `@264/#15` attribute-extra topology proof milestone. The repo now has both broad aggregate and focused sibling regression guards around the current best topology hypothesis:

```text
@264/#15 explicit-index stream => raw-zero-based + degenerate-bridge/stitch topology hypothesis
```

No exporter was added. `Source/`, `Extracted/`, and `Exports/` remain local/generated data and should not be committed.

| Area | Current truth |
|---|---|
| Strongest positive topology lead | `meshSize=297`, extra `@264/#15`, role `index-u16be-strip-lead` |
| Current preferred mapping | `raw-zero-based` |
| Aggregate proof | `5/5` raw wins, `0` subtract-one wins, `0` ties across four `@264` groups |
| Focused sibling proof | `6fc01704d4a509d5` and `caa9a88e94ec8db0` both pass exact `@264` proof invariants |
| Negative side-stream proof | `@272/#25` remains `u32-sentinel-mask-body`; repeated `@296` bodies remain low-variation guardrails |
| Export status | Still blocked; current work is JSON/proof only |

## Files changed in this milestone 📁

```text
README.md
docs/current-status.md
scripts/Invoke-RiftAssetWorkflow.ps1
src/RiftAssetDumper/Program.cs
docs/handoffs/<this file>
```

Generated reports under `Exports\` were regenerated during validation but are intentionally ignored/local.

## Main implementation changes 🛠️

### `src/RiftAssetDumper\Program.cs`

Added/extended non-exporting NIF attribute-extra proof surfaces:

- Focused `probe-nif-attribute-extra` output for extra streams beside complete position/normal/UV attribute sets.
- Low-variation classifiers:
  - `u32-sentinel-mask-body`
  - `u32-repeated-pattern-body`
- Index compatibility diagnostics for index-like attribute extras.
- Raw-zero-based vs subtract-one mapping candidates.
- Decoded position, normal, UV, and triangle-area fitness scoring.
- Degenerate-bridge/stitch strip-structure diagnostics.
- Segment-aware fitness fields.
- Bounded first-segment triangle proof packets with:
  - triangle indices
  - edge metrics
  - normal/UV deltas
  - triangle area
  - dominant signed plane
  - strip winding parity
  - compact proof-review flags
- Full-inventory aggregate `TopAttributeExtraMappingFitness` groups.

### `scripts\Invoke-RiftAssetWorkflow.ps1`

Added durable workflow modes:

| Mode | Purpose |
|---|---|
| `AttributeExtraProbe` | Focused one-asset/one-mesh/one-extra proof packet |
| `AttributeExtraProofGuard` | Full-inventory aggregate guard for the current `@264` topology hypothesis |
| `AttributeExtraSiblingProofGuard` | Focused guard for the two known-positive `v=128` sibling probes |

The guard modes throw on proof regression and print compact pass tables.

### `docs/current-status.md` and `README.md`

Updated current truth, usage commands, interpretation, and safety notes. Export remains explicitly blocked pending further proof review.

## Current best proof details ✅

### Positive `@264/#15` aggregate inventory

`AttributeExtraProofGuard` reruns full mesh-binding inventory and requires these groups to stay stable:

| Mesh size | Vertex count | Extra | Count | Raw wins | Subtract-one wins | Edge gap | Normal gap | Area gap | Strip structure |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| `297` | `128` | `@264` | `2` | `2` | `0` | `4.986899` | `0.351314` | `11.158707` | `degenerate-bridge-stitch-candidate` |
| `297` | `95` | `@264` | `1` | `1` | `0` | `3.208409` | `1.126855` | `12.981545` | `degenerate-bridge-stitch-candidate` |
| `297` | `80` | `@264` | `1` | `1` | `0` | `2.056958` | `0.015236` | `2.511989` | `degenerate-bridge-stitch-candidate` |
| `297` | `64` | `@264` | `1` | `1` | `0` | `0.386752` | `1.263661` | `16.973598` | `degenerate-bridge-stitch-candidate` |

Guard invariants include:

- raw preferred total at least `5`
- subtract-one total exactly `0`
- tie total exactly `0`
- positive segmented edge/normal/area gaps
- no sentinel restarts
- no dropped non-degenerate cross-segment windows
- no first-segment parity breaks

### Focused positive sibling probes

`AttributeExtraSiblingProofGuard` reruns:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraSiblingProofGuard -SkipBuild
```

It validates:

| Asset ID | Mesh | Extra | Raw edge median | Subtract-one edge median | Raw normal median | Subtract-one normal median | Raw area median | Subtract-one area median |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `6fc01704d4a509d5` | `#6` | `@264/#15` | `6.241469` | `11.228368` | `1.001207` | `1.352521` | `7.306626` | `18.465333` |
| `caa9a88e94ec8db0` | `#6` | `@264/#15` | `6.241469` | `11.228368` | `1.001207` | `1.352521` | `7.306626` | `18.465333` |

Focused guard invariants include:

- mesh size `297`
- extra block `#15`
- payload/header `906/29`
- role `index-u16be-strip-lead`
- position/normal/UV rotate-right-1 leads present
- index min/max/distinct `1/127/127`
- raw zero absent
- raw missing vertex `0`
- subtract-one missing vertex `127`
- strip structure `degenerate-bridge-stitch-candidate`
- `77` segment-like runs and `51` mirrored bridges
- `24` first-segment triangle proof samples
- parity breaks stay `0`

### Negative/guardrail side-stream proof

The representative `@272/#25` probe still reports:

```text
role=u32-sentinel-mask-body
byte histogram: 0xff×63, 0x01×1
```

Interpretation: `@272/#25` is still a negative/guardrail stream, not topology proof.

## Validation already run ✅

```powershell
dotnet build "C:\RIFT MODDING\Assets\RiftAssetDumper.slnx" --nologo
```

Result: passed, `0` warnings, `0` errors.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraSiblingProofGuard -SkipBuild
```

Result: passed for both focused `@264` sibling probes.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProofGuard -SkipBuild
```

Result: passed for four aggregate `@264` groups.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProbe -Id 75d5a06d7c0de1dd -MeshBlock 7 -ExtraOffset 272 -SkipBuild -PrivacyScan
```

Result: passed; privacy scan passed.

```powershell
git diff --check
```

Result: passed; only normal LF-to-CRLF warnings from Git.

## Resume procedure 🔁

Start here after pulling latest `main`:

```powershell
cd "C:\RIFT MODDING\Assets"
git status --short --branch
git log --oneline -5
```

Re-run proof guards before touching topology/export logic:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraProofGuard -SkipBuild
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\Assets\scripts\Invoke-RiftAssetWorkflow.ps1" -Mode AttributeExtraSiblingProofGuard -SkipBuild
```

## Recommended next safe slice 🎯

Add negative regression guard coverage for the side streams:

- `@272/#25` should remain `u32-sentinel-mask-body` across the top `v=16` samples.
- Repeated `@296` payloads should remain `u32-repeated-pattern-body`.

This would protect the current split-truth framing: `@264` is the positive topology-bearing lead, while `@272`/`@296` are guardrails/negative evidence.

## Do not do yet 🚫

- Do not add or enable OBJ/model export from this lane yet.
- Do not commit copied game assets from `Source\`, `Extracted\`, or generated proof reports under `Exports\`.
- Do not treat helper-generated proof packets as visual/render validation.
- Do not collapse raw-zero-based vs subtract-one ambiguity without keeping guards updated.
