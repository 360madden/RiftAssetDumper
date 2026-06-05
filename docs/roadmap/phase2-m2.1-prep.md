# Phase 2 M2.1 Prep Note — NiDataStream Descriptor Field-Order & Semantic Mapping

**Date**: 2026-06
**Type**: Milestone Prep — Phase 2 M2.1
**Status**: **ACTIVE**
**Parent(s)**: `docs/roadmap/project-roadmap.md` (Phase 2 M2.1), `docs/roadmap/current-phase.md` (Phase 2 ACTIVE)
**Entry**: Phase 1 COMPLETE (329: 12/12 matrix + 10/10 classification + 12/12 guards; 305: structural comparison; comprehensive exit handoff)

**Roadmap Reference**: This prep supports **M2.1** — the first milestone of **Phase 2: NiDataStream Descriptor & Binding Proof System**. Per the roadmap: "Complete field-order + semantic mapping for high-priority NiDataStream descriptors using Ghidra + sample bytes."

**Anti-drift**: All Ghidra work must tie back to specific mesh/stream families from Phase 1 (329: matrix IDsCovered; 305: representative anchors). No new Ghidra targets without explicit linkage to geometry proof. **Candidate-only** throughout; no parser/export promotion. Use existing `scripts/rift_workflow.py` Ghidra commands + Java scripts; only add narrow new modes if justified. Do NOT commit `Exports/` content. High-reasoning lane per `docs/task-routing-safety-policy.md`.

## Objective

Per `docs/roadmap/project-roadmap.md` Phase 2:

> **M2.1**: Complete field-order + semantic mapping for high-priority NiDataStream descriptors using Ghidra + sample bytes.

This milestone uses Phase 1's classified stream roles as **ground truth anchors** to guide Ghidra descriptor field mapping. Phase 1 provides precise, machine-readable evidence on what each stream IS (role, payload size, vector count, body classification, endianness) — M2.1 connects that to Ghidra's static descriptor table to answer: **which descriptor fields encode position vs normal vs UV vs index semantics?**

## Entry Criteria (Phase 1 Complete)

| Criterion | Status |
|---|---|
| Phase 1 exit complete | ✅ 329: 12/12 matrix + deep analysis + guards; 305: structural comparison; comprehensive exit handoff |
| Strong position source families classified | ✅ 329 family with known stream offsets, roles, payloads, and body classification |
| Existing Ghidra/NiDataStream work exists | ✅ 4 Java scripts, 8 schemas, retained-project evidence, 4 function-site targets |
| Ghidra + JDK 21 installed and wired | ✅ `.tools.json` confirms both installed; dry-run verified |
| Promotion checklists reviewed | ✅ `nidatastream-promotion-readiness-checklist.md`; `ghidra-nidatastream-parser-field-comparison.md` |

## Target Scope

### Phase 1 anchor streams (ground truth for descriptor mapping)

| Stream | Offset | Role (c) | Family | Body Class | Key Characteristics |
|---|---|---|---|---|---|
| **Position** | @212 | position-float3-ror1-lead (75) | 329 #7/#34 | Ror1 float3, plausible | Shared between siblings; same BodyFirst16 |
| **Normal** | @220 | normal-float3-ror1-lead (85) | 329 #7 | Ror1 float3, 100% unit vectors | Present on #7 only (attrSets=1) |
| **UV** | @304 | uv-float2-ror1-lead (80) | 329 #7 | Float2, UV range | Present on #7 only; absent on #34 |
| **Anomalous pos-like** | @304 | position-float3-ror1-lead (75) | 329 #34 | Low plaus (10/10), ~0.4× size, mixed endian, distinct bodies | Candidate-only; semantic role unresolved |
| **u32 repeated** | @296 | u32-repeated-pattern-body (25) | 329 #34 | u32 pattern | Present on #34; function unknown |
| **Index (strip)** | varies | index-u16be-strip-lead | Various | u16 big-endian | Present in some meshes |

### Existing Ghidra targets (from `docs/ghidra-function-site-targets.json`)

| Target | Purpose | Status |
|---|---|---|
| `nidatastream-loadbinary` | Load routine anchor — reads stream binary fields | Surveyed; evidence-ready |
| `nidatastream-descriptor-helper` | Descriptor helper — gates negative signed values | Surveyed; evidence-ready |
| `nidatastream-descriptor-builder-1770` | Builder 1 — descriptor field construction | Surveyed; evidence-ready |
| `nidatastream-descriptor-builder-17c0` | Builder 2 — descriptor field construction | Surveyed; evidence-ready |
| `nidatastream-semantic-adapter` | Semantic adapter — stream-element ordering | Surveyed; evidence-ready |

### Current NiDataStream evidence state (baseline)

From `docs/ghidra-nidatastream-parser-field-comparison.md`:

| Evidence | State |
|---|---|
| Declared payload byte count | Reported; used for bounds checks |
| Payload prefix/trailer | Ghidra-aligned layout validated (184/184 blocks) |
| Descriptor static lookup table | Stride-12 hypothesis; **0/768 nonzero rows** in all-index sample |
| Descriptor reference classification | 20 DATA/address-like refs across 6 functions |
| Descriptor byte-0 (index) | Candidate-mapped as static-table index |
| Descriptor bytes 1-2 | Unmapped for parser/export semantics |
| Descriptor byte-3 | Uniform-zero padding/reserved candidate |
| Pairing impact | 0 complete Ghidra-only position+normal+UV groups |

**Key problem**: The current stride-12 descriptor table hypothesis produced 768 readable rows but ALL ZERO. This means either the stride is wrong, or the base address is wrong, or the descriptor table is populated dynamically at runtime. The reference classification found 20 DATA refs across 6 functions — these could point to a different base or a dynamically-built table.

## Focused Approach for M2.1

### Strategy: Use Phase 1 evidence to constrain the descriptor model

Phase 1 tells us exactly what the streams ARE. We can work backward: given a stream known to be `position-float3-ror1-lead` with 48 float3 vectors at 576 bytes, what would its NiDataStream descriptor need to encode? This constrains the search space for descriptor field semantics.

### Step 1: Extract Phase 1 stream metadata for anchor IDs

For each matrix ID (prioritize 3 pilots: 0364ea142bc00ce7, 04de901531a091ab, 066fa520a8ce62e3):

- Known stream roles, payload sizes, vector counts
- BodyFirst16 / header bytes for each stream
- Block assignments (block index, offset within mesh)
- Attribute set status

### Step 2: Cross-reference with Ghidra descriptor evidence

For each anchor stream:

- Map the Phase 1 stream to a NiDataStream block index
- Extract the descriptor record bytes from the NIF binary at that block
- Compare descriptor byte patterns against Ghidra's static table hypothesis
- Use Phase 1's known role to **label** descriptor bytes

### Step 3: Re-sampling with Phase 1 constraints

Instead of blind stride-12 sampling across all 256 byte indices:

- Use Phase 1 stream payload sizes to constrain stride candidates
- Use Phase 1 body classification (ror1-float3 vs u16 vs mixed) to constrain format/component fields
- Target the specific descriptor bytes for Phase 1 anchor streams
- Cross-reference with reference classification findings (20 DATA refs across 6 functions)

### Step 4: Field-order documentation

Produce a candidate field-order table mapping:

- Descriptor byte offset → candidate semantic (count, format, component, stride, usage, access)
- Evidence source: Ghidra decompile + Phase 1 stream classification + sample bytes
- Confidence level per field

### Step 5: Semantic feasibility check

For each candidate field assignment:

- Does the assigned semantic produce consistent values across all anchor streams?
- Does the Phase 1 stream role match the Ghidra-derived descriptor field?
- Are there contradictions (e.g., a stream classified as position but whose descriptor says UV)?

## Commands

```bash
# 1. Verify tool wiring (Ghidra + JDK)
python scripts/rift_workflow.py tools-status
python scripts/rift_workflow.py ghidra-dry-run --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project

# 2. Check current Ghidra evidence status
python scripts/rift_workflow.py ghidra-function-site-status --list-json
python scripts/rift_workflow.py nidatastream-evidence-status --list-json
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json

# 3. Refresh descriptor sample compare (Phase 1 evidence fed in)
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare

# 4. Re-run descriptor reference classifier (with Phase 1 anchor context)
python scripts/rift_workflow.py nidatastream-descriptor-reference-classify

# 5. Re-run descriptor base-model review (updated stride hypothesis)
python scripts/rift_workflow.py nidatastream-descriptor-base-model-review

# 6. Run descriptor table sample with Phase 1-informed stride/base
python scripts/rift_workflow.py nidatastream-descriptor-table-sample

# 7. Refresh NIF layout report
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full

# 8. Promotion brakes (expect still blocked)
python scripts/rift_workflow.py nidatastream-promotion-preflight
python scripts/rift_workflow.py nidatastream-promotion-status --list-json

# CI (Python only — no C# changes)
ruff check scripts/
mypy scripts/ --no-error-summary
python -m pytest scripts/ -v --tb=short
```

## Deliverables

- [ ] `docs/roadmap/phase2-m2.1-prep.md` (this file)
- [ ] `docs/handoffs/draft-2026-06-m2.1-nidatastream-descriptor-mapping.md` (M2.1 handoff)
- [ ] Refreshed `Exports/ghidra-reports/nidatastream_descriptor_reference_classify.*` (with Phase 1 anchor context)
- [ ] Refreshed `Exports/ghidra-reports/nidatastream_descriptor_base_model_review.*`
- [ ] Candidate field-order table (descriptor byte → Phase 1 role mapping)
- [ ] Updated `docs/roadmap/current-phase.md` (M2.1 IN PROGRESS)

## Validation Gates

- [ ] Phase 1 anchor streams (3 pilot IDs: 0364, 04de, 066fa) used as ground truth inputs
- [ ] Each Ghidra target run ties back to specific Phase 1 stream offsets/roles
- [ ] Field-order table entries cite evidence source (Ghidra decompile line + Phase 1 stream data)
- [ ] Candidate-only language throughout; no promotion claims
- [ ] Drift check: strictly M2.1 scope (descriptor field mapping) — no parser changes, no new families
- [ ] All refs to Phase 2 M2.1 + roadmap + Phase 1 exit handoff + matrix
- [ ] Python + Java only; no new .ps1/.cmd
- [ ] CI green: ruff 0, mypy 0, Python tests passing
- [ ] No `Exports/` committed
- [ ] `FieldOrderPromoted` remains `false`; `ParserExportPromotionAllowed` remains `false`

## Blockers (inherited from NiDataStream lane)

| Blocker | Status | M2.1 Impact |
|---|---|---|
| `FieldOrderPromoted=false` | **Holds** — descriptor field order not proven | M2.1 goal: advance toward promotion without crossing gate |
| `DescriptorTableAllZero` | **Holds** — 0/768 nonzero rows in stride-12 sample | M2.1 must revise stride/base hypothesis |
| `DescriptorBytes1-2Unmapped` | **Holds** — variable bytes 1-2 not mapped to semantics | M2.1 target: use Phase 1 roles to constrain byte mapping |
| `ParserExportPromotionAllowed=false` | **Holds** | M2.1 does not attempt promotion; docs + evidence only |
| `ZeroGhidraOnlyPositionNormalUVGroups` | **Holds** — 0 complete groups | M2.1 may identify first candidate groups |

## Phase 1 → Phase 2 Bridge (Key Input)

From `docs/handoffs/2026-06-m1.5-phase1-exit-consolidation.md`:

1. **Durable target families**: 329 (23 groups, 12 matrix IDs) and 305 (15 groups) with known stream offsets, roles, and sibling relationships
2. **Machine-readable matrix**: `mesh329-family-attribute-role-matrix.json` — can drive automated descriptor extraction
3. **Quantified stream classification**: @304 (low plaus, ~0.4×, mixed endian), @212 (primary position), @296 (u32 pattern) — precise descriptors to match in Ghidra
4. **Guard infrastructure**: Sibling-binding + variant attr layout guards (12/12 PASS) — can be extended for descriptor validation
5. **Cross-family validation**: attrSets=1/0 pattern confirmed across families — strong structural insight for descriptor field mapping

---

See `docs/roadmap/project-roadmap.md` (Phase 2), `docs/handoffs/2026-06-m1.5-phase1-exit-consolidation.md`, `docs/roadmap/current-phase.md`, `docs/ghidra-nidatastream-offline-quickstart.md`, `docs/ghidra-nidatastream-parser-field-comparison.md`.

**End of M2.1 prep.**
