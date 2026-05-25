# Post-Stage-18 Ghidra/NiDataStream proof status

Status date: 2026-05-25

## Canonical stage position

The historical geometry/export pipeline is **Stage 18 complete**. Active work is now the **post-Stage-18 Ghidra/NiDataStream proof-guard lane**.

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
- Sample-byte agreement: local ignored `nidatastream-layout-report.json` currently shows 184/184 Ghidra-style-valid `NiDataStream` blocks; schema-backed but still report-only, not promoted.
- Pairing impact proof: blocked; grouped Ghidra attribute guard still expects zero complete Ghidra-only position+normal+UV groups.
- Export isolation: guarded by `ghidra-workflow-guard-suite` / `nidatastream-parser-field-proof-guard` / `ghidra-pairing-non-export-guard`.
- Narrow parser patch: not started.

## Current decision

Parser/export behavior remains unchanged. Ghidra evidence is useful for client-code intent and target selection, but it must remain sidecar/report-only until descriptor/sample/pairing proof gates become executable and pass.

## Do next

1. Keep `nidatastream-parser-field-proof-guard` passing as a no-premature-promotion guard.
2. Add concrete sample-byte proof fields to `nidatastream-layout`.
3. Only after those proofs pass, consider the smallest parser-field patch.
