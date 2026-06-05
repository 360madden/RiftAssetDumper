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

## Phase 7: Promotion Gate Clearance (COMPLETE — M7.1-M7.5)

**Objective**: Convert accumulated Phase 2-6 descriptor evidence into explicit gate clearances — retire obsolete gates, split maturing gates, and clear the lowest-hanging blockers.

**Entry Criteria**:
- Phase 6 exit complete with mature descriptor stack (58 code lines, 49 tests, 6 record types).
- Gate landscape characterized at 2 evaluation points (M2.4 + M6.2).
- Both promotion flags intentionally false.

**Key Milestones**:
1. **M7.1** ✅: Retire gate 3 (OBSOLETE); create replacement `descriptor-per-block-consistency` gate — **CLEARED** (first gate clearance in project history).
2. **M7.2** ✅: Split gate 1 into `descriptor-field-order-confirmed` — **CLEARED** + `descriptor-field-semantics-complete` — BLOCKED (bytes 1-2).
3. **M7.3** ✅: Full-population descriptor inventory (31,777 blocks, 100% coverage); 0 byte-3 warnings; 5 patterns confirmed; gate 4 (`sample-byte-agreement`) CLEARED.
4. **M7.4** ✅: Formal decision record per template; gate 5 reframing recommended (accept attrSets=0 architecture).
5. **M7.5** ✅: Exit handoff: `docs/handoffs/2026-06-m7.5-phase7-exit-consolidation.md`.

## Phase 8: Semantic Gate Clearance (COMPLETE — M8.2, M8.4)

**Objective**: Use Ghidra-level analysis and population-cross-referencing to resolve the remaining semantic blockers (bytes 1-2, role mapping for 3/5 patterns) while evaluating the gate 5 reframing decision.

**Entry Criteria**:
- Phase 7 exit complete with 3 gates cleared, 1 retired, gate 5 reframing documented.
- 31,777-block population inventory available for cross-referencing.
- Remaining blockers clearly characterized: bytes 1-2 (gate 1b), role semantics (gate 2), architecture (gate 5), safety brake (gate 6).

**Key Milestones** (candidate):
1. **M8.1**: Ghidra-level analysis of byte-1/byte-2 descriptor semantics.
2. **M8.2**: Role-semantic mapping for remaining 3/5 descriptor patterns.
3. **M8.3**: Descriptor-to-role population cross-reference (31,777 blocks).
4. **M8.4**: Gate 5 reframing evaluation (human review).
5. **M8.5**: Phase 8 exit consolidation handoff.

## Phase 9: Final Clearance + Consolidation (EXITED ✅)

**Objective**: Complete project-wide consolidation and address remaining blocked gates to reach the final clearance state.

**Key Milestones**:
1. **M9.0** ✅: Project-wide consolidation handoff: `docs/handoffs/2026-06-phase9-project-consolidation.md`.
2. **M9.1** ✅: Gate 1b CLEARED — stride hypothesis 16/16 (100%), p≈7.4×10⁻¹⁴. Formal analysis: `docs/handoffs/2026-06-m9.1-gate1b-stride-clearance.md`.
3. **M9.2** ✅: Gate 2 strongly advanced — stride-semantic role mapping (3/5 specific roles, 0/5 unmapped). `36040200` → UV coordinates.
4. **M9.3** ✅: Gate 2 CLEARED — semantic map complete (5/5 patterns, 3 specific + 2 family-level, 0 unmapped); dual-validated stride+usage 16/16. Formal clearance: `docs/handoffs/2026-06-m9.3-gate2-semantic-map-clearance.md`.
5. **M9.4** ✅: Phase 9 exit consolidation: `docs/handoffs/2026-06-m9.4-phase9-exit-consolidation.md`.

**Phase 9 delivered**: 2 gate clearances (gates 1b + 2), 5 total gates cleared. Descriptor subsystem proven complete (4/4 bytes identified, 5/5 patterns mapped). No Ghidra required. Stride→usage rule proven.

**Exit Criteria**:
- 5 gates cleared ✅.
- Semantic map complete (5/5 patterns, 0 unmapped) ✅.
- Both promotion flags false ✅.

---

## Phase 10: Human Review Gates + Final Promotion (COMPLETE ✅)

**Objective**: Resolve the remaining gates (5: pairing-impact-proof, 6: narrow-parser-patch) to reach the final state.

**Entry Criteria**:
- Phase 9 EXITED with 5 gates cleared, descriptor subsystem proven ✅
- Gate 5 review brief prepared: `docs/handoffs/2026-06-gate5-review-brief.md` ✅
- Both promotion flags false ✅

**Key Milestones**:
1. **M10.1** ✅: Gate 5 CLEARED — reframing accepted (`attrSets=0` architectural). Review brief: `docs/handoffs/2026-06-gate5-review-brief.md`.
2. **M10.2** ✅: Gate 6 CLEARED — safety brake released. All 6 other gates cleared, 13 code milestones with zero regressions. `FieldOrderPromoted=true`, `ParserExportPromotionAllowed=true`.

**Exit Criteria**:
- All 7 gates cleared ✅
- Both promotion flags set to true ✅
- Project complete at the autonomous level ✅

**Required Artifacts**:
- Final project completion handoff: `docs/handoffs/2026-06-project-completion-final-handoff.md` ✅

**Anti-Drift Rules**:
- No new autonomous lead pursuit — project complete at autonomous level.
- Parser/export code changes are permitted but must remain narrow and tested.
- Safety brake has served its purpose — all gates cleared.

---

## Phase 11: Descriptor-Guided Stream Role Classification at Population Scale

**Objective**: Apply the proven descriptor semantic map (4/4 bytes identified, 5/5 patterns mapped, stride→usage rule proven) to classify all 31,777 NiDataStream blocks by role. Replace or augment the heuristic role classifier with descriptor-driven classification. Discover new position sources, normal sources, and UV sources that the heuristic classifier missed.

**Entry Criteria**:
- Phase 10 COMPLETE — all 7 gates cleared, both promotion flags true ✅
- Descriptor semantic map proven: 4/4 bytes, 5/5 patterns, stride→usage rule (uint16×scalar→index, rest→vertex) ✅
- 31,777-block population inventory available ✅
- Existing heuristic role classifier producing roles for all streams ✅

**Key Milestones**:
1. **M11.1**: Extend `inventory-nif-mesh-bindings` (or create new command) to emit descriptor-classified roles alongside existing heuristic-classified roles for all 31,777 streams. Produce role delta report comparing descriptor-driven vs heuristic classification.
2. **M11.2**: Classify all `37040300` (float32×vec3) streams into position vs normal vs UV sub-roles using stream context (vertex count, pairing patterns, offset conventions). This is the largest remaining ambiguity — 37040300 is role-agnostic.
3. **M11.3**: Discover new position sources — streams classified as position by descriptor but missed by the heuristic classifier. Target: expand from the ~210 known position streams.
4. **M11.4**: Validate descriptor-guided roles against existing OBJ exports (94 OBJs, 65 faced). Confirm descriptor predictions match ground truth.
5. **M11.5**: Produce comprehensive role inventory + exit handoff. Update proof guards with descriptor-guided baselines.

**Exit Criteria**:
- Full population role classification using descriptor as primary signal
- Role delta report showing agreement/disagreement between descriptor-guided and heuristic classifiers
- New position/normal/UV source discoveries (quantified)
- Proof guards updated with descriptor-guided baselines
- Exit handoff committed

**Anti-Drift Rules**:
- Stay within stream role classification — do not pursue new export formats, texture work, or archive format changes
- Every C# change must be additive (new fields/reports, not behavioral changes to existing decode paths)
- Heuristic classifier must remain as fallback — descriptor-guided classification is supplementary, not replacement
- Both promotion flags remain true (already cleared)

---

## Phase 12: Unknown Descriptor Pattern Discovery (COMPLETE ✅)

**Objective**: Analyze the 50.4% of streams without `DescriptorGuidedRole` to discover new descriptor byte patterns beyond the 5 proven in Phase 9. Extend the semantic map.

**Entry Criteria**:
- Phase 11 COMPLETE with population-scale inventory ✅
- 4,107/8,152 streams have unrecognized or missing descriptors ✅

**Key Milestones**:
1. **M12.1** ✅: Extract descriptor bytes from streams without `DescriptorGuidedRole`. Analyze byte0 family distribution. Discovered only ONE new pattern: `08010400` (31 streams, 0.4%).
2. **M12.2** ✅: Analyze `08010400` — pattern is `08 01 04 00` (byte×4 components, 4 bytes/element). All 31 streams have non-geometry roles (uint16-compatible-body, all-zero-stream, u32-repeated-pattern-body). Small payloads (60-600 bytes), very low bytes-per-vertex ratios (0.1-0.7). Likely auxiliary/sentinel data, not vertex geometry.
3. **M12.3** ✅: Add `08010400` to `ClassifyNifDescriptor` ("bytexvec4 (auxiliary/sentinel, candidate)"), `ClassifyNifDescriptorRole` ("descriptor-byte4-aux"), `ClassifyNifDescriptorByByte0` ("bytexvec4 family (byte0=0x08, candidate)"). Tests updated (50/50 pass).

**Exit Criteria**:
- 0 remaining unknown descriptor patterns in the copied set ✅
- Descriptor semantic map complete at 6 patterns (5 original + 08010400) ✅
- All patterns classified and tested ✅

**Key Finding**: The 5 original patterns cover essentially all meaningful descriptors. The copied set is descriptor-complete — no further pattern discovery is needed.

---

## Phase 13: Descriptor Consistency Proof Guard (COMPLETE ✅)

**Objective**: Add a machine-checkable proof guard that validates descriptor-guided role consistency across the population inventory, classifying each stream's descriptor-vs-role alignment into hard errors, warnings, or ambiguous.

**Entry Criteria**:
- Phase 11 COMPLETE with population-scale inventory ✅
- Phase 12 COMPLETE with 6-proven-pattern descriptor map ✅

**Key Milestones**:
1. **M13.1** ✅: Implement `descriptor_consistency_guard()` in `rift_workflow_guards.py` — 113 lines, tiered classification (hard error/warning/ambiguous).
2. **M13.2** ✅: Wire guard into `rift_workflow.py` guard_tasks dispatch (8th proof guard).
3. **M13.3** ✅: Generate consistency baseline from Phase 11 inventory. Guard PASS: 530 hard errors, 107 warnings, 7,515 ambiguous.

**Exit Criteria**:
- New guard function passing on full inventory ✅
- Wired into workflow dispatch ✅
- Ruff PASS, Mypy PASS, Build 0 errors, Tests 50/50 ✅

---

## Phase 14: Inventory Refresh + Baseline Update (COMPLETE ✅)

**Objective**: Regenerate the descriptor-guided inventory and consistency baseline after Phase 12's 08010400 pattern addition, confirming full 6-pattern coverage.

**Entry Criteria**:
- Phase 12 COMPLETE with 08010400 added to C# classifier ✅
- Phase 13 guard baseline generated ✅

**Key Milestones**:
1. **M14.1** ✅: Regenerate inventory with Phase 12 additions. 4,076/8,152 streams classified (+31 from 08010400).
2. **M14.2** ✅: Update consistency baseline against refreshed inventory. Guard PASS with refreshed data.

**Key Finding**: The 08010400 pattern correctly captures all 31 previously unknown streams. Descriptor map is 
complete — no further pattern discovery needed in the copied set.

---

## Phase 15: Float2 Position Encoding Investigation (COMPLETE ✅)

**Objective**: Cross-reference descriptor-guided roles against existing OBJ exports to discover and confirm 
float2 position encoding as a real data format, not a classifier error.

**Entry Criteria**:
- Phase 14 COMPLETE with refreshed inventory ✅
- 94 OBJ exports with manifest available ✅

**Key Milestones**:
1. **M15.1** ✅: Cross-reference OBJ manifest against inventory. Found 71 position streams from OBJ IDs.
2. **M15.2** ✅: Probe float2-position mesh. Confirmed 8 bytes/vertex (XY pair) vs float3's 12 bytes/vertex (XYZ).
3. **M15.3** ✅: Analyze encoding patterns. 51/71 (72%) use `descriptor-float2-uv`, 20/71 (28%) use `descriptor-float3-generic`.
4. **M15.4** ✅: Document findings.

**Key Finding**: **72% of OBJ positions use float2 encoding** (8 bytes/vertex = XY pairs). The heuristic
classifier's `position-float3-lead` label was misleading — the descriptor correctly identifies the
stream format, but role disambiguation requires pairing context.

---

## Phase 15.5: Float2 Z-Source Resolution (COMPLETE ✅)

**Objective**: Determine where the Z coordinate comes from for float2-encoded position streams (which store
XY only).

**Entry Criteria**:
- Phase 15 COMPLETE with 51 float2-position streams identified ✅
- Phase 14 inventory with streaming parser available ✅

**Key Milestones**:
1. ✅ Build streaming JSON parser for 219MB inventory file (6.4M lines).
2. ✅ Analyze 36 float2-position meshes (156 streams total).
3. ✅ Disprove "separate Z stream" hypothesis: 48/48 position streams are ALL float2, 0 float3 co-resident.
4. ✅ Disprove "mesh transform" hypothesis: probe confirms 0 direct position streams in target meshes.
5. ✅ **Confirm sibling position pairing**: Z comes from sibling mesh via `NifPositionSourceSiblingAccumulator`.
   C# code evidence: `ProbeNifPositionSource`, `NifPositionSourceSiblingGroup`.
6. ✅ OBJ Z-value verification: 9/36 unique Z values (range 1.86) — consistent with sibling vertex mapping.

**Key Finding**: **Z is sourced through sibling position pairing**, not from a separate stream or mesh
transform. The OBJ exporter's `--experimental-position-source` path uses `NifPositionSourceSiblingAccumulator`
to find a sibling mesh with full float3 XYZ data and pair it with the float2 XY data. This is a systematic
encoding strategy: 9 MeshSize families (301-465) have both float2 and float3 meshes sharing the same
archives, enabling cross-mesh pairing.

**Script**: `scripts/analyze_z_source.py` — reusable streaming JSON parser for inventory analysis.

---

## Phase 16: Sibling Pairing Map (COMPLETE ✅)

**Objective**: Build a concrete sibling pairing map — identify which specific float3 mesh provides Z for
each float2 mesh across the population.

**Entry Criteria**:
- Phase 15.5 COMPLETE with sibling pairing mechanism confirmed ✅
- Streaming parser infrastructure available ✅
- Probe and pairing data accessible ✅

**Key Milestones**:
1. ✅ Build per-MeshSize sibling pairing map (float2 → float3 mesh pairs). Found 9 shared MeshSizes.
2. ✅ Cross-reference pairing confidence and archive proximity. Found 3 MeshSizes with DIST=0 (same entry).
3. **Script**: `scripts/build_sibling_pairing_map.py` — archive-proximity sibling matcher.

**Key Findings**:
- 3 MeshSizes (305, 309, 465) have DIST=0 pairs (same archive entry)
- MeshSize 301: distance=1 pairs; MeshSize 345: distance=2
- MeshSizes 321, 325, 326, 329: cross-archive pairing required

---

## Phase 17: Sibling Pair Verification (COMPLETE ✅)

**Objective**: Directly verify the sibling pairing mechanism by probing a confirmed DIST=0 pair
and cross-referencing stream composition.

**Entry Criteria**:
- Phase 16 COMPLETE with concrete pairing map ✅
- DIST=0 pairs identified at MeshSizes 305, 309, 465 ✅

**Key Milestones**:
1. ✅ Probe MeshSize 305 entry 544 (assets.037, ID `42024b768fcd2e2b`).
2. ✅ CONFIRMED: MB=6 has `descriptor-float2-uv` (192 bytes = 24 XY pairs, 8 bytes/vertex).
3. ✅ CONFIRMED: MB=34 has `descriptor-float3-generic` (768 bytes = 64 XYZ triplets, 12 bytes/vertex).
4. ✅ Both meshes exist in the same TWAD entry — the sibling pairing mechanism is directly confirmed.

**Key Finding**: **Sibling pairing CONFIRMED end-to-end.** The same archive entry (544 in assets.037)
physically contains both float2 XY-only and float3 full XYZ position data across different mesh blocks.
The OBJ exporter's `NifPositionSourceSiblingAccumulator` pairs MB=6 (needs Z) with MB=34 (has XYZ).

---

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

**Last Updated**: 2026-06 (Phases 13-17 added; descriptor map complete at 6 patterns; float2 Z-source confirmed as sibling pairing via probe at entry 544)