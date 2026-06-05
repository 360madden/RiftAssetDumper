# Stage 2 Handoff — PS→Py Proof Guard Migration

Date: 2026-05-20

## Summary

Ported `AttributeExtraProofGuard` and `AttributeExtraSiblingProofGuard` from PowerShell (`Invoke-RiftAssetWorkflow.ps1` lines 3062–3380) to Python, wired them into `rift_workflow.py`, and hardened JSON type accessors against silent boolean/string coercion.

## Changes

### New file: `scripts/rift_workflow_guards.py`

- `attribute_extra_proof_guard(report_path)` — asserts @264 raw-zero-based preferred across 4 vertex-count groups (128, 95, 80, 64), checking edge/normal/area deltas, strip structure, sentinels, parity breaks, and cross-group totals
- `attribute_extra_sibling_proof_guard(report_path, asset_id)` — deep per-asset guard asserting exact stream/block shape, index prefix, mapping candidates, stitch structure, first-segment triangle proof (24 samples), raw-vs-subtract-one fitness gaps, and proof review parity
- Helpers: `_get_named_json_object()`, `_test_json_array_equals()`

### Modified: `scripts/rift_workflow.py`

- Added import of `attribute_extra_proof_guard`, `attribute_extra_sibling_proof_guard`
- Removed both from `complex_modes` set (was 13 deferred, now 11)
- Added routing:
  - `attribute-extra-proof-guard` → runs `inventory-nif-mesh-bindings` (C#) then calls `attribute_extra_proof_guard()`
  - `attribute-extra-sibling-proof-guard` → runs `probe-nif-attribute-extra` (C#, hardcoded `--mesh-block 6 --extra-offset 264`) then calls `attribute_extra_sibling_proof_guard()`

### Modified: `scripts/rift_workflow_utils.py`

- `required_json_number` now rejects booleans (`isinstance(value, bool)` check before `float()`)
- Added `required_json_boolean(obj, key, context)` — rejects non-bool values (strings like `"true"`, ints like `1`, None)
- Updated `assert_proof_guard` docstring noting callers should pre-validate with `required_json_boolean`

### Modified: `scripts/rift_workflow_guards.py` (type hardening)

- Import and use `required_json_boolean` instead of `bool(required_json_value(...))` for 4 boolean JSON fields: `MaxIndexWithinVertexCount`, `UsesZeroIndex`, `ValidForVertexCount` (×2)

### Modified: `scripts/test_rift_workflow_utils.py`

- 8 new test cases: `required_json_boolean` acceptance/rejection, `required_json_number` bool rejection, `required_json_integer` bool rejection inheritance

### Modified: `docs/current-status.md`

- Added `scripts/rift_workflow_guards.py` row as ✅ complete
- Reduced deferred guard count from 13 → 11
- Added Python/PS command examples for both new guards
- Removed `AttributeExtraProofGuard`/`AttributeExtraSiblingProofGuard` from legacy PS-only section

## Validation

| Check | Result |
|---|---|
| Python imports | ✅ All OK, both commands in COMMAND_MAP |
| Unit tests | ✅ 56/56 pass (48 existing + 8 new) |
| Hardened type checks | ✅ `required_json_number` rejects booleans, `required_json_boolean` rejects strings/ints/None |
| C# build | ✅ 0 errors (2 pre-existing SharpCompress warnings) |
| Code review | ✅ Hardening correct, no regressions |

## PS→Py Migration Progress

| Status | Count |
|---|---|
| ✅ Ported & wired | 2 (`attribute-extra-proof-guard`, `attribute-extra-sibling-proof-guard`) |
| ⏳ Still deferred | 11 (`usage-access-correlation-guard`, `residual-lead-guard`, `residual-position-classifier-report`, `residual-position-cluster-probe-report`, `position-source-gap-report`, `position-source-sibling-lead-guard`, `position-source-sibling-family-report`, `position-source-sibling-probe-report`, `position-source-sibling-representative-probe-report`, `position-source-sibling-secondary-probe-report`, `position-source-sibling-extra-position-report`) |

## Usage

```powershell
# Thin PS wrapper
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Invoke-RiftWorkflow.ps1 attribute-extra-proof-guard --full --skip-build
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Invoke-RiftWorkflow.ps1 attribute-extra-sibling-proof-guard --id 6fc01704d4a509d5 --skip-build

# Direct Python
python scripts/rift_workflow.py attribute-extra-proof-guard --full --skip-build
python scripts/rift_workflow.py attribute-extra-sibling-proof-guard --id 6fc01704d4a509d5 --skip-build
```

## Next steps (suggested)

- Port `usage-access-correlation-guard` next (same pattern: inventory + Python guard)
- Port `residual-lead-guard` and `residual-position-classifier-report` (extends the same JSON report consumption pattern)
- Run both new guards against live full inventory to validate assertions still hold
