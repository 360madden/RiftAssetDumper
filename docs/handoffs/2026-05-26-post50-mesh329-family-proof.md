# 2026-05-26 Post-50 mesh329 family proof handoff

## Goal

Create a schema-backed, candidate-only proof packet for the current top-ranked
post-50 source-binding lane: meshSize `329`, mesh#`7/#34`, stream `@212`,
target block `#28`.

## What changed

- Added workflow command `post50-mesh329-family-proof`.
- The command reads ignored `Exports/nif-mesh-binding-inventory.json`, filters
  inventory-level `TopPositionSourceSiblings`, and writes ignored:
  - `Exports/post50-mesh329-family-proof.json`
  - `Exports/post50-mesh329-family-proof.md`
- Added schema `docs/schemas/post50-mesh329-family-proof-v1.schema.json`.
- Integrated the proof packet into `post50-position-source-status`.
- Added wrapper/wiring coverage for `Post50Mesh329FamilyProof`.
- Added targeted report/schema tests.

## Current evidence

The current ignored local proof packet confirms the top family claim from
inventory rows:

| Field | Value |
|---|---:|
| Evidence groups | 23 |
| Total stream links | 46 |
| Distinct IDs | 23 |
| Mesh blocks | 7 and 34 |
| Mesh payload offset | 212 |
| Target block | 28 |
| Role | `position-float3-ror1-lead` |
| Family report consistency | all checked fields match |

Payload bytes currently covered:

`168, 192, 264, 276, 360, 372, 408, 420, 432, 444, 456, 468, 540, 552, 576, 588, 624, 672, 768, 924`

## Validation

- `python -m py_compile scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_post50_mesh329_family_proof.py scripts/test_post50_position_source_status.py scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_post50_mesh329_family_proof.py`
- `python scripts/test_post50_position_source_status.py`
- `python scripts/test_rift_workflow_command_wiring.py`
- `python scripts/rift_workflow.py post50-mesh329-family-proof`
- Actual ignored family proof report validated against
  `docs/schemas/post50-mesh329-family-proof-v1.schema.json`.
- `python scripts/rift_workflow.py post50-position-source-status --list-json`
- `python scripts/test_schema_registry.py`
- `ruff check scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_post50_mesh329_family_proof.py scripts/test_post50_position_source_status.py scripts/test_rift_workflow_command_wiring.py`
- `mypy scripts/rift_workflow.py scripts/rift_workflow_reports.py scripts/test_post50_mesh329_family_proof.py scripts/test_post50_position_source_status.py scripts/test_rift_workflow_command_wiring.py --no-error-summary`
- `git diff --check`
- `python scripts/rift_workflow.py generated-output-guard`

## Known blockers

- `source-binding-family-candidate-only`
- `mesh34-complete-geometry-binding-not-proven`
- `parser-export-promotion-not-allowed`

## Generated-output status

The generated family proof JSON/Markdown are ignored local outputs under
`Exports/`. They were validated but must not be staged.

## Next recommended actions

1. Schema-lock the remaining post-50 input reports that still drive blockers:
   `position-source-gap-report`, `residual-position-classifier-report`, and
   `residual-position-cluster-probe-report`.
2. Add a compact promotion checklist that consumes the mesh329 family proof and
   extra-position compare packets as inputs while keeping parser/export locked.
3. Only after complete geometry binding evidence exists, draft a separate
   guarded parser/export promotion proposal.
