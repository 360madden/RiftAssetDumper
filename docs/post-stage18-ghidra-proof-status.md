# Post-Stage-18 Ghidra/NiDataStream proof status

Status date: 2026-06-06

## Canonical stage position

> **Note**: The historical geometry/export pipeline is Phase 49 complete (350 OBJs, 0 unknowns). All 7 promotion gates are now CLEARED. This document is a historical status snapshot from 2026-05-25.

Do not relabel this lane as a new Stage 4. Earlier `Stage 4` references in this repo belong to older geometry/export planning and batch-export work.

## Current lane goal

Convert candidate-only Ghidra `NiDataStream` evidence into executable proof gates before any parser/export promotion.

## Current executable status

```powershell
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-parser-field-proof-guard
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
```

Current gate truth:

- FunctionSite target registry safety: guarded.
- FunctionSite local evidence availability: 7/7 evidence-ready after the 2026-05-25 local summary refresh.
- Descriptor field-order proof: candidate-only, schema-backed by `nidatastream-descriptor-proof-status --list-json`, not promoted.
- Sample-byte agreement: ✅ **PROOF PASSING** — 184/184 Ghidra-style-valid blocks show `SampleByteAgreement: true` with per-block `SampleByteAgreementDetail` fields (all show "First N bytes agree (1-byte shift)"). Schema-backed in `nidatastream-layout-report-v1.schema.json`, reported by `python scripts/rift_workflow.py nidatastream-layout`. Not yet promoted to parser/export behavior — gated behind `--ghidra-body-offset` flag (Step 3).
- Pairing impact proof: local ignored attribute-candidate report has 0 complete Ghidra-only position+normal+UV groups across 14 groups; guarded and still candidate-only, not promoted.
- Export isolation: guarded by `ghidra-workflow-guard-suite` / `nidatastream-parser-field-proof-guard` / `ghidra-pairing-non-export-guard`.
- Narrow parser patch: not started.

## Current decision

Parser/export behavior remains unchanged. Ghidra evidence is useful for client-code intent and target selection, but it must remain sidecar/report-only until descriptor/sample/pairing proof gates become executable and pass.

## Do next

1. ✅ Keep `nidatastream-parser-field-proof-guard` passing as a no-premature-promotion guard.
2. ✅ **DONE (2026-06-06)** — Added concrete sample-byte proof fields to `nidatastream-layout` (`SampleByteAgreement`, `SampleByteAgreementDetail`, `SampleByteAgreementBlocks`). Proof passes: 184/184 blocks agree.
3. Implement the narrow parser patch — add `--ghidra-body-offset` flag to `AppOptions`, wire it through `decode-nif-geometry` / `probe-nif-mesh` / inventory commands to use `PayloadPrefixBytes` (28) as the primary body offset instead of `LegacyPayloadOffset` (29).
