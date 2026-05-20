# RIFT Assets handoff — UInt16TriplesPrefix comparison and ExportSafetyAssertion

Date: 2026-05-19 07:18:16 UTC
Repo: `C:\RIFT MODDING\Assets`
Branch: `main`
HEAD: `23a7abe` ("Harden residual cluster proof surface")

## TL;DR

This handoff captures uncommitted safety/evidence hardening in `scripts/Invoke-RiftAssetWorkflow.ps1` (+38/-7). The slice adds:

1. **UInt16TriplesPrefix component min/max comparison** to the residual-position cluster probe report's byte-layout table.
2. **Machine-readable ExportSafetyAssertion** in the cluster JSON so downstream tooling can verify `ExportReady=false` / `GeometryTruthPromoted=false` invariants without reading script logic.
3. **Markdown table column alignment fixes** for sibling-probe and semantic-hint reports.

No C# parser changes. No parser role, geometry truth, or OBJ/export readiness was promoted.

## Current git state

```text
## main...origin/main
 M scripts/Invoke-RiftAssetWorkflow.ps1
```

No staged files. Untracked: this handoff file only. No generated/copied asset output is staged.

Latest commits before this slice:

| Commit | Purpose |
|---|---|
| `23a7abe` | Harden residual cluster proof surface |
| `ec82115` | Enrich residual cluster probe report |
| `19bf01a` | Add residual position cluster probe report |
| `c3614e1` | Add candidate-only discovery workbench |

## Changed file

| File | Change | Lines |
|---|---|---|
| `scripts/Invoke-RiftAssetWorkflow.ps1` | UInt16TriplesPrefix parsing, export safety assertions, markdown column fixes | +38/-7 |

## Change details

### Change 1 — UInt16TriplesPrefix per-component min/max

`Get-ClusterStreamRow` now parses `UInt16TriplesPrefix` from stream-body probe JSON. It computes the min/max value per component (A, B, C) and produces:

| Field | Purpose |
|---|---|
| `UInt16TriplesCount` | How many triple prefix entries exist |
| `UInt16TriplesSummary` | `A=min..max B=min..max C=min..max` |

Data flow: `Get-ClusterStreamRow` → `$streamRows` → `$payloadRows` → `Get-HexByteComparison` → markdown byte-layout comparison table.

The `Get-HexByteComparison` function and the markdown format string each have a single `UInt16TriplesSummary` reference (no duplicates).

### Change 2 — ExportSafetyAssertion in cluster JSON

Added per-row assertion fields to `$payloadRows`:

```powershell
ExportReadyAssertionPassed = $true
GeometryTruthAssertionPassed = $true
```

Added top-level assertion object to the JSON report:

```powershell
ExportSafetyAssertion = [ordered]@{
    AllRowsExportReadyFalse = ($unsafePromotionRows.Count -eq 0)
    AllRowsGeometryTruthPromotedFalse = ($unsafePromotionRows.Count -eq 0)
    UnsafePromotionRowCount = $unsafePromotionRows.Count
    Guard = 'cluster rows must never claim export readiness or promoted geometry truth'
}
```

The existing fail-closed guard at line ~1782 throws before the report writes if any row violates, so these assertion fields are always `true`/`0` when the JSON file exists. The dynamic references to `$unsafePromotionRows.Count` keep the assertion truthful if the guard logic changes.

### Change 3 — Markdown table column alignment

| Function | Fix |
|---|---|
| `Invoke-SemanticHintCrossTab` | Format string 8→9 columns |
| `Invoke-PositionSourceSiblingProbeReport` | Format string 8→9 columns |
| `Invoke-PositionSourceSiblingRepresentativeProbeReport` | Format string 8→9 columns |
| `Invoke-PositionSourceSiblingLeadGuard` | Header separator aligned for 10-column layout |

## Generated output evidence (current run)

Byte-layout comparison from `Exports/residual-position-cluster-probe-report.md`:

| Payload | Common prefix vs 288 | Diff bytes / compared | Length delta | UInt16 triples (min..max) | Packed/quantized review |
|---|---:|---:|---:|---:|---|---|
| 96 | 0 | 57/96 | -192 | A=62..65469 B=13926..48309 C=65..51297 | True |
| 180 | 1 | 43/128 | -108 | A=0..16384 B=0..47923 C=0..43606 | True |
| 192 | 15 | 56/128 | -96 | A=0..41953 B=0..57585 C=0..56129 | True |
| 288 | 128 | 0/128 | 0 | A=0..49152 B=0..37570 C=0..43606 | True |
| 396 | 9 | 55/128 | 108 | A=0..62270 B=0..37569 C=0..44544 | True |

Interpretation: the UInt16 triples ranges vary by payload — payload 96 has a reserved-looking minimum at component A (62) while payloads 180+ start at 0. This remains candidate-only evidence; no parser role was promoted.

## DiscoveryWorkbench state

Current top-5 candidates are unchanged:

| Rank | Score | Candidate | Evidence |
|---:|---:|---|---|
| 1 | 100 | `residual-305-stream188-payload288` | plausible=0.9444 |
| 2 | 98 | `residual-305-stream188-payload96` | plausible=0.875 |
| 3 | 97 | `residual-305-stream188-payload180` | plausible=0.8444 |
| 4 | 93 | `residual-305-stream188-payload192` | plausible=0.8542 |
| 5 | 93 | `residual-305-stream188-payload396` | plausible=0.8283 |

Cross-checks unchanged: OBJ/export blocked, residual-vs-sibling-family lanes separate, meshSize=329 @304/#57 kept as source-binding only.

## Workflow modes available

| Mode | Purpose |
|---|---|
| `MeshBindings` | Full mesh-binding inventory (smoke or full) |
| `MeshProbe` | Focused single-mesh probe |
| `MeshStreams` | Mesh-stream candidate inventory |
| `IndexCandidates` | Index-candidate inventory |
| `StreamEndianness` | Stream endianness inventory |
| `StreamBodies` | Stream-body inventory |
| `AttributeExtraProbe` | Attribute extra-stream probe |
| `AttributeExtraProofGuard` | Aggregate @264 topology proof regression |
| `AttributeExtraSiblingProofGuard` | Focused sibling @264 proof regression |
| `UsageAccessCorrelationGuard` | Usage/access correlation regression |
| `ResidualLeadGuard` | Residual target family routing guard |
| `ResidualPositionClassifierReport` | Dry-run residual classifier report |
| `ResidualPositionClusterProbeReport` | Focused meshSize=305 stream@188 probe |
| `PositionSourceGapReport` | Position-source gap ranking |
| `PositionSourceSiblingProbeReport` | Focused sibling probe report |
| `PositionSourceSiblingLeadGuard` | Parser-derived sibling lead guard |
| `PositionSourceSiblingFamilyReport` | Sibling family cross-tab |
| `PositionSourceSiblingRepresentativeProbeReport` | Representative sibling probes |
| `PositionSourceSiblingSecondaryProbeReport` | Secondary sibling spot-checks |
| `PositionSourceSiblingExtraPositionReport` | meshSize=329 @304/#57 extra-position report |
| `SemanticHintCrossTab` | NIF semantic-hint cross-tab |
| `DiscoveryWorkbench` | Candidate-only scoreboard and probe queue |
| `GeneratedOutputGuard` | Staged/tracked generated-output safety |
| `AssetSignatures` | Asset signature inventory |
| `AssetSemanticIndex` | Asset semantic index build |

## Validation performed (from prior session)

| Check | Result |
|---|---|
| `dotnet build src/RiftAssetDumper/RiftAssetDumper.csproj --nologo -v q` | Passed; existing `SharpCompress` NU1902 warning only |
| `Invoke-RiftAssetWorkflow.ps1 -Mode ResidualPositionClusterProbeReport -SkipBuild` | Passed; UInt16 triples column rendered; markdown/JSON written |
| `Invoke-RiftAssetWorkflow.ps1 -Mode GeneratedOutputGuard` | Passed; 0 tracked/staged generated outputs |
| PowerShell parse of `scripts/Invoke-RiftAssetWorkflow.ps1` | Passed |
| `git diff --check` | Passed; LF-to-CRLF warnings only |
| Changed-file hygiene scan | Passed; no raw user-profile paths |
| No duplicate UInt16TriplesSummary references | Verified (single copy in Get-HexByteComparison, single copy in markdown format args) |
| `$stream` variable scope in payloadRows | Verified; `$stream` assigned from `$streamRows` before UInt16Triples references |
| Markdown separator column count matches header | Verified (8 columns, all aligned) |

## Safety boundaries

- Work Assets-only. No live game interaction.
- No parser role, geometry truth, or OBJ/export readiness promoted.
- All UInt16 triples evidence is candidate-only.
- `ExportSafetyAssertion` is machine-readable verification of existing guard behavior.
- Generated `Exports/` output remains ignored and unstaged.
- Strict residual classifier threshold remains at `0.95`; not lowered.
- `meshSize=329 @304/#57` kept separate as source-binding evidence only.

## Resume prompt

```text
Resume in C:\RIFT MODDING\Assets. Work Assets-only. Start by checking git status/log and latest docs/handoffs file.
main is at 23a7abe with uncommitted UInt16TriplesPrefix + ExportSafetyAssertion changes in scripts/Invoke-RiftAssetWorkflow.ps1 (+38/-7).
Continue discovery-first NIF/static asset truth work; no export/OBJ and no live movement.
Existing helpers: Invoke-RiftAssetWorkflow.ps1 with all modes listed above.
Use usage/access, semantic hints, and residual leads as candidate-only ranking evidence.
Next best slice: compare UInt16TriplesPrefix patterns across payload clusters,
or add packed/quantized parser hypothesis behind a separate fail-closed report mode.
Validate with build, relevant guards, git diff --check, and privacy scan before commit/push.
```

## Optional top 10 next best actions

| # | Action |
|---:|---|
| 1 | Commit/push this UInt16Triples + ExportSafetyAssertion slice after final hygiene checks. |
| 2 | Compare UInt16TriplesPrefix A/B/C ranges across payloads 96/180/192/288/396 to see if any component encodes vertex count or stride. |
| 3 | Add a packed/quantized parser hypothesis behind a separate fail-closed report mode (not in exporter code). |
| 4 | Cross-tab residual `StringValue=POSITION` groups by UInt16TriplesPrefix min/max ranges. |
| 5 | Keep strict classifier threshold at `0.95`; do not lower it to promote payload `288`. |
| 6 | Search for a complete position + normal + UV + topology/index bundle near payload `288` before any promotion. |
| 7 | Re-run `DiscoveryWorkbench` after any schema or scoring change. |
| 8 | Re-run `GeneratedOutputGuard` before every staging operation. |
| 9 | Keep `meshSize=329 @304/#57` separate until it has its own proof guard. |
| 10 | Keep OBJ/export blocked until position, topology/index, normal/UV, bounds, repeated-family evidence, and proof guards all agree. |
