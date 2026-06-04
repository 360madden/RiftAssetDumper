# RiftAssetDumper Project Roadmap

**Purpose of this document**: Provide a single source of truth for the long-term plan. It breaks the work into discrete, focused phases with clear entry/exit criteria, milestones, and anti-drift rules. This keeps the primary agent and any subagents locked on the current task.

**Repo Purpose (never lose sight of this)**:
- Research workspace for safe, evidence-driven reverse engineering of RIFT game assets.
- Primary focus: Prove and implement reliable decoding of NIF geometry (NiMesh → NiDataStream bindings, stream role assignment, position sources, topology).
- Core output: Verifiable parser components, schemas, proof guards, and documented truth — not speculative exports.
- Operating mode: **Aggressive Evidence Workflow** (small focused probe → smoke → full inventory → ranked evidence → documented truth → small commit → next lead).
- Non-negotiable: Strict safety gates (no committing Source/Extracted/Exports data, no parser/export promotion without passing all gates, high-reasoning for all truth/proof work).

**Current Baseline (as of June 2026)**:
- Original 50-step discovery plan completed as a cycle (ended negative on live position validation in current game state).
- Python workflow + all proof guards fully migrated and tested.
- Strong offline evidence on repeated source-binding families (meshSize=329 is strongest: 23 groups / 46 links on stream@212 between mesh#7/#34 variants).
- Recent deep autonomous analysis on 329 family revealed consistent role/attribute patterns (mesh#7 often has complete attribute sets; mesh#34 shares primary position but shows 0 attribute sets + extra position-like streams).
- NiDataStream/Ghidra analysis advanced but promotion remains locked (candidate-only).
- Rich set of schemas, checklists, handoffs, and automation exists.
- Parser/export promotion: Blocked.

**Definition of Project Completion**:
A state where:
- Core NIF geometry structures (bindings, stream roles, position sources) are mapped with high-confidence, machine-readable evidence.
- Working, guarded parser components exist for base mesh decoding and position source resolution.
- All critical promotion gates are passed and documented.
- Sustainable, low-drift discovery process is in place (automation, proof systems, clear handoff patterns).
- The repo serves as a trustworthy foundation for further RIFT asset work.

---

## Phase Structure

Each phase follows this template for focus:
- **Objective**
- **Entry Criteria**
- **Key Milestones / Discrete Steps** (with anti-drift rules)
- **Exit Criteria & Success Metrics**
- **Required Artifacts**
- **Focus & Anti-Drift Rules**

---

## Phase 0: Foundation & Roadmap Establishment (Current — In Progress)

**Objective**: Establish this roadmap as the single source of truth, consolidate current state, and lock in operating conventions so all future work has minimal drift.

**Entry Criteria**:
- Existing 50-step cycle complete.
- Python migration complete.
- Recent 329-family role analysis completed.

**Key Milestones / Steps**:
1. Create and commit this `docs/roadmap/project-roadmap.md`.
2. Create `docs/roadmap/current-phase.md` (symlink or pointer to active phase).
3. Update AGENTS.md and README.md to reference the roadmap.
4. Baseline current evidence state (run key status commands).
5. Define "Current Phase" and seed the first 1-2 milestones with concrete todos.

**Exit Criteria**:
- Roadmap document exists and is referenced in AGENTS.md.
- `current-phase.md` points to Phase 1.
- At least one full status baseline run completed and documented.

**Required Artifacts**:
- This roadmap.
- Updated AGENTS.md / README.md.
- `docs/roadmap/current-state-baseline.md` (or handoff).

**Focus Rules**:
- Do not start new discovery probes until Phase 0 exit criteria are met.
- All new work must reference this roadmap.

---

## Phase 1: Position Source Family Proof & Role Classification (Current Strongest Lead)

**Objective**: Turn the strongest offline signal (meshSize=329 family and related) into high-confidence, classified evidence on bindings and stream roles. Directly attack the "extra position-like stream" and "attribute set completion" blockers.

**Entry Criteria**:
- Phase 0 complete.
- 329 family data + recent role analysis handoffs exist.

**Key Milestones** (discrete, one at a time):
1. **M1.1**: Expand sample of 329-family mesh pairs (target 10+ groups). Systematically run `mesh-probe` on mesh#7 and #34 variants. Produce machine-readable attribute/role matrix.
2. **M1.2**: Deep classification of the @304 extra stream on mesh#34 variants (payload analysis, vector comparison, magic patterns, role scoring refinement).
3. **M1.3**: Develop or extend proof guard(s) for "sibling source-binding + variant attribute layout".
4. **M1.4**: Apply similar (lighter) treatment to the #2 family (meshSize=305) for comparison.
5. **M1.5**: Produce comprehensive family proof handoff + update promotion-readiness checklists.

**Exit Criteria**:
- At least 10 high-confidence 329-family examples with classified roles and attribute status.
- New or updated guard(s) passing on the family.
- Clear "candidate-only" vs "promotion-blocking" distinctions documented.
- One major focused handoff committed.

**Required Artifacts**:
- Updated schemas or reports for family evidence.
- New/updated proof guard code + tests.
- Dedicated handoff in `docs/handoffs/`.

**Focus & Anti-Drift Rules**:
- Stay strictly within meshSize=329 (and light 305 comparison). Do not open new unrelated leads.
- Every probe must produce JSON + markdown + handoff contribution.
- Use existing `rift_workflow.py` commands; only add narrow new modes if justified by a milestone.

---

## Phase 2: NiDataStream Descriptor & Binding Proof System

**Objective**: Mature the NiDataStream side (Ghidra + offline) into a reliable, machine-readable binding and descriptor system that can feed the parser.

**Entry Criteria**:
- Phase 1 exit complete (strong position source families classified).
- Existing Ghidra/NiDataStream work and promotion checklists reviewed.

**Key Milestones**:
1. M2.1: Complete field-order + semantic mapping for high-priority NiDataStream descriptors using Ghidra + sample bytes.
2. M2.2: Build/validate "NiMesh offset → NiDataStream block" binding proofs at scale.
3. M2.3: Integrate role assignment (position/normal/UV/index) with descriptor data.
4. M2.4: Pass key NiDataStream promotion gates (or document exactly why they remain blocked).

**Exit Criteria**:
- Machine-readable descriptor field map with high coverage on relevant streams.
- Binding proofs for top position source families.
- Promotion dashboard shows measurable progress (or locked reasons clearly documented).

**Anti-Drift Rules**:
- All Ghidra work must tie back to specific mesh/stream families from Phase 1.
- No new Ghidra targets without explicit linkage to geometry proof.

---

## Phase 3: NiDataStream Descriptor Propagation (COMPLETE)

**Objective**: Propagate DescriptorBytes + DescriptorClassification fields across all 6 NiDataStream record types so every probe and inventory command emits descriptor data. No behavioral changes — classification is purely informational with both promotion flags held false.

**Entry Criteria**:
- Phase 2 exit complete with per-block-embedded descriptors, 5 patterns, binding reuse proven.
- Both promotion flags intentionally false.

**Key Milestones**:
1. **M3.1**: Decision record + core implementation — NifDataStreamLayout.DescriptorBytes, ClassifyNifDescriptor(), NifMeshBoundStreamSummary fields; 5 xUnit tests; live-verified on mesh#7/#34.
2. **M3.2**: NifStreamHeaderSample + inventory-nif-stream-headers descriptor propagation; 5-pattern distribution verified across 16 samples.
3. **M3.3**: NifMeshBindingStreamSample auto-inherits descriptor fields from M3.1 (COVERED).
4. **M3.4**: NifStreamBodySample + inventory-nif-stream-bodies descriptor propagation.
5. **M3.5**: NifStreamBodyProbe + probe-nif-stream-body descriptor propagation.

**Exit Criteria**:
- All 6 NiDataStream record types carry DescriptorBytes + DescriptorClassification.
- CI green: build 0 errors, 17/17 tests pass, format PASS.
- Both promotion flags still false.
- Exit handoff: docs/handoffs/2026-06-m3.5-phase3-exit-consolidation.md.

**Anti-Drift Rules**:
- No behavioral changes — classification is informational only.
- No promotion flag changes.
- Every record type change must match existing field patterns.

## Phase 4: Descriptor-Aware Parser (COMPLETE — M4.1-M4.6)

**Objective**: Consume Phase 3 descriptor data for parser behavioral changes — integrity checks, classification coverage, console visibility, and role cross-checks — while maintaining the candidate-only safety boundary and promotion gate discipline.

**Entry Criteria**:
- Phase 3 exit complete with all 6 record types carrying descriptor fields.
- Descriptor facts established: per-block embedded, 4-byte structure, byte-3=0x00, 5 patterns.

**Key Milestones**:
1. **M4.1**: Byte-3 != 0x00 integrity check in AnalyzeNifDataStreamLayout — warns on anomaly; verified at scale (0/375 warnings).
2. **M4.2**: Byte-0 fallback classification (ClassifyNifDescriptorByByte0) — 5 family labels; verified 16/16 classified, 0 nulls.
3. **M4.3**: DescriptorClassificationGroups distribution in inventory JSON report.
4. **M4.4**: Console descriptor classification summary in inventory-nif-stream-headers output.
5. **M4.5**: Descriptor-role cross-check in probe-nif-mesh — warns on float/u16 mismatches.
6. **M4.6**: Descriptor classification in probe-nif-stream-body console output.

**Exit Criteria**:
- At least 6 narrow, tested, descriptor-consuming behavioral changes delivered.
- CI green throughout: build 0 errors, 29/29 tests pass, format PASS.
- Both promotion flags still false.
- All changes are guarded, informational, or warning-only — no decode/export path changes.

**Anti-Drift**:
- Every behavioral change must be narrow, tested, and guarded by proof-gate checks.
- No parser/export promotion without completed decision record.
- Both FieldOrderPromoted and ParserExportPromotionAllowed remain false.

## Phase 5: Descriptor-Guided Parser (COMPLETE — M5.1-M5.4, M5.5 handoff)

**Objective**: Extend Phase 4 observational consumption into guided routing — pairing confidence adjustment, position candidate pre-filtering, and Usage/Access-enriched validation — without changing decode/export behavior.

**Key Milestones**:
1. **M5.1**: Descriptor classification on NifMeshProbePairing and NifMeshBindingPairingSample records.
2. **M5.2**: Descriptor-guided pairing confidence adjustment (AdjustConfidenceByDescriptor).
3. **M5.3**: Descriptor-based position stream pre-filter in decode-nif-geometry (behind --experimental-position-source).
4. **M5.4**: Usage/Access enrichment in descriptor-role cross-check warnings.
5. **M5.5**: Exit handoff: docs/handoffs/2026-06-m5.5-phase5-exit-consolidation.md.

**Shared Infrastructure**: IsFloatRole(), IsFloatDescriptor(), IsU16Descriptor() helpers.

**Exit Criteria**:
- 4 narrow, tested, descriptor-consuming behavioral changes delivered.
- CI green: build 0 errors, 41/41 tests pass, format PASS.
- Both promotion flags still false.
- All changes behind gates or candidate-only.

## Phase 6: Descriptor-Validated Export (COMPLETE — M6.1-M6.4)

**Objective**: Use Phase 3-5 descriptor evidence to validate and enrich OBJ export — metadata comments, formal promotion gate re-evaluation, and pre-export validation checks — without changing decode/export behavior.

**Key Milestones**:
1. **M6.1**: Descriptor metadata in OBJ export: `# Position descriptor:` comment + console warning; both export paths covered.
2. **M6.2**: Promotion gate re-evaluation against Phase 3-6 evidence (10 milestones): 4 strengthened, 1 retired (OBSOLETE), 0 cleared.
3. **M6.3**: `ValidateDescriptorExportPrechecks()`: structural + descriptor alignment warnings in OBJ comments and console.
4. **M6.4**: Exit handoff: `docs/handoffs/2026-06-m6.4-phase6-exit-consolidation.md`.

**Exit Criteria**:
- 3 narrow, tested, descriptor-consuming export enrichments delivered.
- CI green: build 0 errors, 49/49 tests pass, format PASS.
- Both promotion flags still false; 0 gates cleared.
- All changes are metadata, validation, or documentation — zero decode/export path changes.

## Phase 7: Promotion Gate Clearance (ACTIVE — M7.1-M7.2 COMPLETE)

**Objective**: Convert accumulated Phase 2-6 descriptor evidence into explicit gate clearances — retire obsolete gates, split maturing gates, and clear the lowest-hanging blockers.

**Entry Criteria**:
- Phase 6 exit complete with mature descriptor stack (58 code lines, 49 tests, 6 record types).
- Gate landscape characterized at 2 evaluation points (M2.4 + M6.2).
- Both promotion flags intentionally false.

**Key Milestones**:
1. **M7.1** ✅: Retire gate 3 (OBSOLETE); create replacement `descriptor-per-block-consistency` gate — **CLEARED** (first gate clearance in project history).
2. **M7.2** ✅: Split gate 1 into `descriptor-field-order-confirmed` — **CLEARED** + `descriptor-field-semantics-complete` — BLOCKED (bytes 1-2).
3. **M7.3** 🔜: Full-population descriptor inventory (31,777 blocks) to advance gate 4.
4. **M7.4** 🔜: Formal decision record per `docs/nidatastream-parser-export-promotion-decision-template.md`.

**Exit Criteria**:
- At least 1 gate formally cleared or retired (✅ 2 cleared, 1 retired in M7.1-M7.2).
- Promotion readiness checklists updated with Phase 7 evidence.
- Both promotion flags evaluated against updated gate states.

**Anti-Drift Rules**:
- Every gate clearance must have a traceable evidence chain to specific Phase 2-6 milestones.
- No clearance without formal documentation per decision template.
- Safety brake (gate 6) remains held until all other gates pass.

---

## Anti-Drift & Focus Mechanisms (Apply to All Phases)

1. **Always reference the current phase** in every handoff and major commit.
2. **One lead at a time** (per Aggressive Evidence Workflow). New leads only after current phase milestone exit.
3. **Mandatory artifacts per milestone**: JSON report + markdown summary + handoff contribution (even small).
4. **High-reasoning lane** for any truth, role assignment, or promotion decision (per task-routing-safety-policy.md).
5. **Living `docs/roadmap/current-phase.md`** — updated at the start of every session or major milestone.
6. **Weekly (or per session) "drift check"**: Explicitly confirm work is still inside the active phase/milestone.

**Living Documents**:
- `docs/roadmap/current-phase.md` (points to active phase + current milestone)
- `docs/current-status.md` (high-level summary, updated at phase boundaries)
- This roadmap (revised only at phase transitions with justification)

---

*This roadmap is the single source of truth for scope and sequencing. All autonomous or subagent work must be traceable to a specific phase + milestone.*

**Last Updated**: 2026-06 (initial creation during autonomous planning session)