# 50-Step Autonomous Discovery Plan

**Created:** 2026-05-20
**Status:** 🟡 Revived tracker — Stage 5 active, Step 49 in progress
**Game state:** RIFT client at character selection screen (live process available)
**Conflict rule:** All outputs under ignored `Exports/discovery-plan/` — never touch shared state

> Current position note (2026-05-26): this original 50-step plan was later superseded by
> `docs/current-status.md` and staged handoffs for offline geometry/export work. Steps 1-45
> are now treated as complete/superseded by that later evidence. Step 46 is complete via
> `docs/live-memory-readonly-safety-boundary.md`; Step 47 is complete via `scan-live-memory`; Step 48 live read completed through RiftReader and remains candidate-only. Step 49 has an initial RiftReader single-float probe, but no confirmed float3 cluster yet.

---

## 🛡️ Defensive Coding Principles (all stages)

| # | Principle | Enforcement |
|---:|-----------|-------------|
| P1 | No live game writes ever | Read-only memory access only in Stage 5 |
| P2 | Unique output namespaces | All outputs under `Exports/discovery-plan/<stage>/` |
| P3 | No conflict with other discoverers | Never write to `Source/`, `Extracted/`, or shared `Exports/` root |
| P4 | Validate before commit | `dotnet build` + `python tests` + `generated_output_guard` every stage |
| P5 | Guard regression protection | Run proof guards before/after every code change |
| P6 | Privacy-redacted by default | Use `--privacy-scan` on all exports |
| P7 | Commit stable milestones only | Each stage produces one commit |
| P8 | Explicit experimental gates | Export features behind `--experimental` flag |
| P9 | Sidecar evidence reports | Every export includes JSON proof sidecar |
| P10 | Never promote candidates silently | Confidence language: observed → lead → candidate → validated → proven |

---

## 📋 Stage 0: Foundation & Baseline Validation (Steps 1-5)

**Goal:** Confirm project is healthy and current proof state is known before any changes.

### Step 1 — Build & test baseline

- [x] `dotnet build RiftAssetDumper.slnx --nologo`
- [x] `python scripts/test_rift_workflow_utils.py`
- [ ] Verify all Python imports
- [x] `git status --short`
- **Exit:** 0 build errors, 46/46 tests pass, imports OK

### Step 2 — Refresh proof guard suite

- [ ] Run `inventory-nif-mesh-bindings --limit 0` (full copied set)
- [ ] Run `AttributeExtraProofGuard` via legacy PS
- [ ] Run `AttributeExtraSiblingProofGuard` via legacy PS
- [ ] Run `UsageAccessCorrelationGuard` if available
- **Exit:** All guards pass, `raw-zero-based` 5/5 signal intact, no regressions

### Step 3 — Baseline export: capture current proof JSONs

- [ ] Copy key proof JSONs to `Exports/discovery-plan/stage0-baseline/`
- [ ] inventory: `nif-mesh-binding-inventory.json`
- [ ] probes: `probe-nif-attribute-extra-6fc01704d4a509d5-mesh6-extra264.json`
- [ ] probes: `probe-nif-attribute-extra-caa9a88e94ec8db0-mesh6-extra264.json`
- **Exit:** Baseline snapshots archived for regression comparison

### Step 4 — Inventory current C# command capabilities

- [ ] Catalog all CLI commands in Program.cs
- [ ] Document what each command outputs
- [ ] Identify dead/untested code paths
- **Exit:** Command inventory in plan appendix

### Step 5 — Stage 0 handoff

- [x] Write `docs/handoffs/2026-05-20-stage0-baseline.md`
- [ ] Commit: "Stage 0 baseline: build, tests, proof guards, command inventory"
- **Exit:** Clean commit with baseline snapshots

---

## 📋 Stage 1: Safe Geometry Decode (Steps 6-15)

**Goal:** Add OBJ face export and cross-validate UInt16-packed positions — no live game.

**Depends on:** Stage 0 complete.

### Step 6 — Read decode-nif-geometry current implementation

- [ ] Read the full `DecodeNifGeometry()` method in Program.cs
- [ ] Understand OBJ point-cloud path
- [ ] Understand UInt16 experimental path
- [ ] Identify where face/index injection point is
- **Exit:** Detailed notes on current implementation

### Step 7 — Add degenerate-bridge triangle decode to OBJ export

- [ ] Read the `@264/#15` strip structure from mesh-binding data
- [ ] Implement degenerate-bridge restart parser (77 segments, 318 windows)
- [ ] Generate triangle list from strip with degenerate removal
- [ ] Behind `--write-obj` + `--experimental` gate
- **Exit:** OBJ output contains `f v1 v2 v3` face lines

### Step 8 — Add proof sidecar to OBJ export

- [ ] Each `.obj` gets a `.obj.proof.json` sidecar
- [ ] Records: asset ID, mesh block, vertex count, triangle count, topology method, confidence
- [ ] Includes raw/raw-zero-based mapping used
- **Exit:** Sidecar files generated alongside OBJ

### Step 9 — Smoke test OBJ face export on @264/#15 sample

- [ ] `decode-nif-geometry --id 6fc01704d4a509d5 --mesh-block 6 --write-obj --experimental`
- [ ] Verify `.obj` has correct vertex count (128) and face count (~151 triangles)
- [ ] Verify no NaNs, no out-of-bounds indices
- [ ] Verify sidecar proof JSON matches expectations
- **Exit:** Known-good OBJ with faces from strongest lead

### Step 10 — Cross-validate UInt16-packed positions vs float32 ground truth

- [ ] Find meshes with BOTH float32 attribute positions AND UInt16 experimental positions
- [ ] Run `decode-nif-geometry --experimental` on attribute-set meshes (v=16 family)
- [ ] Compare UInt16 decode vertices against float32 ground truth
- [ ] Compute per-vertex delta, RMS error, max error
- **Exit:** Quantified accuracy of magic-43606 position encoding

### Step 11 — Add UInt16 position validation report command

- [ ] New CLI: `validate-uint16-positions --id <assetId> --mesh-block <n>`
- [ ] Outputs: per-vertex comparison JSON
- [ ] Reports: vertex count agreement, RMS error, outliers
- **Exit:** Automated position-encoding validation tool

### Step 12 — Run full UInt16 validation across all attribute-set meshes

- [ ] Run `validate-uint16-positions` on all 52 attribute-compatible meshes
- [ ] Aggregate results: pass/fail count, RMS distribution, outlier report
- [ ] Write `Exports/discovery-plan/stage1/uint16-validation-full.json`
- **Exit:** Full-set UInt16 encoding truth table

### Step 13 — Build and test

- [ ] `dotnet build` — 0 errors
- [ ] `python scripts/test_rift_workflow_utils.py` — 46/46
- [ ] Run smoke tests on new commands
- **Exit:** Clean build, passing tests

### Step 14 — Code review

- [ ] Spawn code-reviewer-deepseek on all Stage 1 changes
- [ ] Address all critical/high findings
- **Exit:** Review passed

### Step 15 — Stage 1 handoff

- [x] Write `docs/handoffs/2026-05-21-stage1-geometry-decode.md` (actual)
- [ ] Commit: "Stage 1: OBJ face export + UInt16 position cross-validation"
- **Exit:** Clean commit

---

## 📋 Stage 2: Position Source Discovery (Steps 16-25)

**Goal:** Find missing position streams for the indexed `meshSize=325` and `321` families.

**Depends on:** Stage 1 complete.

### Step 16 — Map the position gap

- [ ] Run full mesh-bindings inventory
- [ ] Extract all indexed families that have normals+UVs but NO position stream
- [ ] Group by mesh size, vertex count, index stream size
- [ ] Document the gap: which families, how many meshes affected
- **Exit:** Position gap report JSON

### Step 17 — Scan NiMesh payload windows for inline positions

- [ ] For each position-missing mesh, scan the NiMesh block payload
- [ ] Look for float3 windows matching expected vertex count
- [ ] Check bounding box sanity
- [ ] Add to mesh-binding inventory: `MeshPayloadPositionCandidate`
- **Exit:** Mesh-payload position candidates ranked by confidence

### Step 18 — Scan unlinked NiDataStream blocks for orphan positions

- [ ] For each NIF, find data streams NOT currently linked to the target mesh
- [ ] Test each orphan for position-float3-ror1-lead compatibility
- [ ] Check if vertex count matches the mesh's known vertex count
- **Exit:** Orphan-stream position candidates

### Step 19 — Add position-source probe command

- [ ] New CLI: `probe-nif-position-source --id <assetId> --mesh-block <n>`
- [ ] Reports: mesh payload candidates, orphan stream candidates, neighbor block candidates
- [ ] Ranks by: vertex count match, bounding box sanity, stride consistency
- **Exit:** Focused position-source diagnostic tool

### Step 20 — Run position-source probe on top indexed families

- [ ] `probe-nif-position-source` on `meshSize=325` family (c841eb9a0ed1c95e mesh #6)
- [ ] `probe-nif-position-source` on `meshSize=321` family
- [ ] `probe-nif-position-source` on `meshSize=301` family
- **Exit:** Ranked position candidates per family

### Step 21 — Attempt neighbor-block position decode

- [ ] For meshes where neighbor blocks have float3 data, attempt decode
- [ ] Compare decoded positions against expected vertex count
- [ ] Check normalized positions for sanity (finite, reasonable range)
- **Exit:** Decoded position candidates

### Step 22 — Add position discovery to decode-nif-geometry

- [ ] Modify `decode-nif-geometry` to use discovered position sources
- [ ] Behind `--experimental-position-source` flag
- [ ] Falls back to UInt16-packed if no float3 position found
- **Exit:** decode-nif-geometry can now produce OBJ with positions from any source

### Step 23 — Build and test

- [ ] `dotnet build` — 0 errors
- [ ] Unit tests pass
- [ ] Smoke test on `meshSize=325` with discovered positions
- **Exit:** Clean build, command works

### Step 24 — Code review

- [ ] Code-reviewer-deepseek on Stage 2 changes
- [ ] Address findings
- **Exit:** Review passed

### Step 25 — Stage 2 handoff

- [x] Write `docs/handoffs/2026-06-02-stage2-position-source-enhanced-findings.md` (actual)
- [ ] Commit: "Stage 2: Position source discovery for indexed NIF mesh families"
- **Exit:** Clean commit

---

## 📋 Stage 3: Proof Guard Migration (Steps 26-35)

**Goal:** Port remaining PowerShell proof guards to Python — enables guard CI and removes PS dependency.

**Depends on:** Stage 2 complete (guards protect the new position work).

### Step 26 — Inventory remaining guards

- [ ] Catalog all unported guard functions in `Invoke-RiftAssetWorkflow.ps1`
- [ ] Prioritize by: regression risk, complexity, dependency on other ports
- **Exit:** Guard migration priority list

### Step 27 — Port AttributeExtraProofGuard to Python

- [ ] Read PS implementation
- [ ] Port to `scripts/rift_workflow_guards.py` (new file)
- [ ] Wire into `scripts/rift_workflow.py` COMMAND_MAP
- [ ] Write unit tests for guard logic
- **Exit:** Guard runs from Python, tests pass

### Step 28 — Port AttributeExtraSiblingProofGuard to Python

- [ ] Port focused sibling guard
- [ ] Same validate-and-fail-on-regression pattern
- [ ] Unit tests
- **Exit:** Guard runs from Python, tests pass

### Step 29 — Port UsageAccessCorrelationGuard to Python

- [ ] Port usage/access correlation guard
- [ ] Unit tests
- **Exit:** Guard runs from Python, tests pass

### Step 30 — Port ResidualPositionClusterProbeReport to Python

- [ ] Port residual position cluster probe (~400 lines)
- [ ] Unit tests
- **Exit:** Report runs from Python, tests pass

### Step 31 — Port remaining low-priority guards

- [ ] `position-source-gap-report`
- [ ] `position-source-sibling-lead-guard`
- [ ] `position-source-sibling-family-report`
- [ ] `position-source-sibling-probe-report`
- [ ] `position-source-sibling-representative-probe-report`
- [ ] `position-source-sibling-secondary-probe-report`
- [ ] `position-source-sibling-extra-position-report`
- **Exit:** All 13 deferred guards ported

### Step 32 — Add guard smoke test suite

- [ ] Create `scripts/test_rift_workflow_guards.py`
- [ ] Test each guard with known-good and known-bad inputs
- [ ] Test guard failure messages are clear
- **Exit:** Comprehensive guard test suite

### Step 33 — Wire guards into discovery pipeline

- [ ] `python scripts/rift_workflow.py` auto-runs guards after relevant commands
- [ ] `--skip-guards` flag to bypass for speed
- [ ] Guard summary at end of each workflow run
- **Exit:** Guards are automated

### Step 34 — Build and test everything

- [ ] `dotnet build` — 0 errors
- [ ] Full Python test suite — all pass
- [ ] Run all guards with known-good data — all pass
- [ ] Deliberately break a guard — verify it fails
- **Exit:** Full test coverage, all green

### Step 35 — Stage 3 handoff

- [x] Write `docs/handoffs/2026-05-20-stage2-ps-py-guards-migration.md` (actual)
- [ ] Commit: "Stage 3: Complete PS→Python guard migration"
- **Exit:** Clean commit

---

## 📋 Stage 4: Discovery Automation Suite (Steps 36-45)

**Goal:** One-command discovery suite that runs the full pipeline and writes a summary.

**Depends on:** Stage 3 complete.

### Step 36 — Design discovery suite architecture

- [ ] Define suite stages: build → inventory → probes → guards → report
- [ ] Design summary report format
- [ ] Design failure mode: partial results saved, failing stage identified
- **Exit:** Architecture document

### Step 37 — Add `run-discovery-suite` C# command

- [ ] New CLI command that orchestrates the full pipeline
- [ ] Stages: mesh-bindings → position-source → decode-geometry → guard-checks
- [ ] Each stage writes intermediate JSON
- [ ] Final summary JSON aggregates all results
- **Exit:** One `dotnet run` invocation runs full discovery

### Step 38 — Add summary report generator

- [ ] Python script: `scripts/discovery_summary.py`
- [ ] Reads suite output JSON
- [ ] Generates Markdown summary with tables
- [ ] Highlights regressions, new findings, confidence changes
- **Exit:** Human-readable summary from each suite run

### Step 39 — Add `--quick` mode for fast smoke cycles

- [ ] `--max-total 100` on all inventory commands
- [ ] Single mesh probe instead of full set
- [ ] Guard checks on smoke data
- **Exit:** Fast feedback loop (< 2 min) for development

### Step 40 — Add regression alerting

- [ ] Compare current suite output against baseline
- [ ] Flag: new guard failures, role count drops, pairing count drops, topology signal flips
- [ ] Color-coded summary: 🟢 stable / 🟡 changed / 🔴 regressed
- **Exit:** Automated regression detection

### Step 41 — Add discovery suite to Python workflow

- [ ] Wire into `scripts/rift_workflow.py` as `discovery-suite` mode
- [ ] `--full` for complete scan, default `--quick` for smoke
- [ ] Runs generated_output_guard before and after
- **Exit:** Python workflow supports discovery suite

### Step 42 — Create CI-ready runner script

- [ ] `scripts/ci_discovery_check.py`
- [ ] Exits non-zero on regression
- [ ] Writes JUnit XML for CI integration
- [ ] Timestamps and versions in output
- **Exit:** CI-ready discovery check

### Step 43 — Build and test full suite

- [ ] `dotnet build` — 0 errors
- [ ] Run full discovery suite — all stages complete
- [ ] Run quick mode — completes in < 2 min
- [ ] Run CI script — exits 0
- [ ] Deliberately regress proof — verify exit 1
- **Exit:** Suite fully validated

### Step 44 — Code review

- [ ] Code-reviewer-deepseek on Stage 4 changes
- [ ] Address findings
- **Exit:** Review passed

### Step 45 — Stage 4 handoff

- [x] Write `docs/handoffs/2026-05-22-035126-stage14-discovery-resume.md` (actual; discovery-suite + Stage 14+)
- [ ] Commit: "Stage 4: Automated discovery suite with regression detection"
- **Exit:** Clean commit

---

## 📋 Stage 5: Live-Game Safe Read-Only Validation (Steps 46-50)

**Goal:** Cross-validate static discoveries against live RIFT process memory — read-only, no writes, no injection.

**Depends on:** Stage 4 complete.
**⚠️ HIGH RISK per task-routing-safety-policy.md — extra-high reasoning required.**

### Step 46 — Design live memory scan safety boundary

- [x] Document: what we will read, what we will NOT touch
- [x] Define pattern scan targets: known NIF asset IDs, index buffer prefixes, float3 vertex clusters
- [x] Define safety: no writes, no hooks, no DLL injection, no handle duplication
- [x] Define output: under ignored `Exports/discovery-plan/stage5-live/`
- [x] Define non-conflict: use unique scan signatures, don't interfere with other discoverers
- **Exit:** Approved safety boundary document: `docs/live-memory-readonly-safety-boundary.md`

### Step 47 — Implement read-only process memory scanner

- [x] New workflow command: `scan-live-memory --live-pattern <label=hex> [--pid <n>]`
- [x] Automatic process selection fails closed; actual reads require explicit `--pid`
- [x] `ReadProcessMemory` only — no writes
- [x] Scans for byte patterns: known asset IDs, index buffer prefixes, position clusters
- [x] Behind `--experimental-live` plus `--confirm-live-read` and `--execute-live-read` gates
- **Exit:** Read-only memory scanner scaffold: `scripts/live_memory_scanner.py`

### Step 48 — Scan for @264/#15 index buffer pattern in live memory

- [x] Pattern target manifest: `00010002000200010003000400050006...` (big-endian strip prefix)
- [x] Cross-reference found addresses against known mesh vertex counts
- [x] Report: found/not-found, addresses, match confidence
- **Exit:** Live confirmation or contradiction of static index buffer hypothesis: `docs/live-memory-step48-status.json`

### Step 49 — Scan for position float3 clusters matching mesh bounds

- [x] Run initial RiftReader single-float probe for the `meshSize=297 v=128` sample
- [x] Expose bounded RiftReader `--scan-float-triplet <x,y,z>` command for candidate float3 probes
- [x] Run first bounded triplet positive-control/expected-static-v0 probe; positive control found 2 hits, expected static `v0` found 0 in that region
- [x] Run bounded expected-static batch for `v0-v3` across four single-float hit regions; 16 scans completed with 0 expected-static hits
- [x] Run full-process expected-static batch for `v0-v3`; 4 scans completed with 0 expected-static hits
- [x] Close Step 49 as `closed-negative-current-live-state`; cluster not confirmed and parser/export promotion remains blocked
- [ ] Convert the noisy single-float hit set into a confirmed multi-float/float3-cluster check (not achieved; superseded by negative closure for the current live state)
- [ ] For `meshSize=297 v=128`, scan for 128×float3 clusters
- [ ] For `meshSize=325 v=24`, scan for 24×float3 clusters
- [ ] Use known bounding boxes from static decode to filter matches
- **Exit:** Candidate-only live validation closure; current status: `docs/live-memory-step49-status.json`. The current session did **not** confirm a live position stream.

### Step 50 — Final comprehensive session handoff

- [x] Write `docs/handoffs/2026-05-26-final-50-step-session.md`
- [x] Aggregate all stage results
- [x] Update `docs/current-status.md`
- [x] Commit: `83306f1` — `docs: complete fifty step live validation handoff`
- **Exit:** Final clean commit, full documentation; parser/export promotion remains blocked by Step 49 negative evidence.

---

## 📊 Dependency Graph

```
Stage 0 (steps 1-5)
    |
    v
Stage 1 (steps 6-15) ─── OBJ faces + position cross-val
    |
    v
Stage 2 (steps 16-25) ─── Position source discovery
    |
    v
Stage 3 (steps 26-35) ─── Guard migration PS→Python
    |
    v
Stage 4 (steps 36-45) ─── Automation suite
    |
    v
Stage 5 (steps 46-50) ─── Live-game validation (read-only)
```

---

## 🔄 Conflict Avoidance Rules

| Rule | Implementation |
|------|----------------|
| Output namespace | All plan outputs under `Exports/discovery-plan/` |
| Unique file names | Include stage prefix: `stage0-`, `stage1-`, etc. |
| No shared state writes | Never write to `Source/`, `Extracted/`, or root `Exports/` |
| Non-destructive reads | C# and Python code only reads from `Source/` and `Exports/` |
| Other discoverer safety | Use unique output paths; don't modify shared manifests or indices |
| Live process safety | ReadProcessMemory only; unique scan patterns; no hooks/injection |

---

## 📋 Progress Tracking

| Stage | Steps | Status | Commit |
|-------|-------|--------|--------|
| 0 — Foundation | 1-5 | ✅ Complete/superseded | `docs/handoffs/2026-05-20-stage0-baseline.md` |
| 1 — Geometry Decode | 6-15 | ✅ Complete/superseded | `docs/handoffs/2026-05-21-stage1-geometry-decode.md` |
| 2 — Position Discovery | 16-25 | ✅ Complete/superseded | `docs/handoffs/2026-06-02-stage2-position-source-enhanced-findings.md` |
| 3 — Guard Migration | 26-35 | ✅ Complete/superseded | Python guards/workflow tests |
| 4 — Automation Suite | 36-45 | ✅ Complete/superseded | `discovery-suite` and Stage 14+ handoffs |
| 5 — Live Validation | 46-50 | ✅ Complete: Step 49 closed negative, Step 50 handoff written | `docs/live-memory-step48-status.json`; `docs/live-memory-step49-status.json`; `docs/handoffs/2026-05-26-final-50-step-session.md` |
