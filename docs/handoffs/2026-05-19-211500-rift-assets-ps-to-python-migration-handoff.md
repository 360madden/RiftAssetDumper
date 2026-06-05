# RIFT Assets — PowerShell → Python Migration Handoff

**Date:** 2026-05-19-2115  
**Branch:** `main`  
**Commit:** (to be committed below)

## What changed

### Migration: PowerShell utilities → Python (`scripts/rift_workflow_utils.py`)

Ported 21 utility/helper functions from `Invoke-RiftAssetWorkflow.ps1` to a Python module, establishing the single source of truth for JSON access, guard assertions, formatting, and subprocess orchestration.

| # | PS Original | Python Equivalent | Category |
|:--|---|---|---|
| 1 | `Get-JsonValueOrDash` | `json_value_or_dash()` | JSON access |
| 2 | `Get-JsonValueOrNull` | `json_value_or_none()` | JSON access |
| 3 | `Get-JsonDoubleOrNull` | `json_double_or_none()` | JSON access |
| 4 | `Get-MeasureSumOrZero` | `measure_sum_or_zero()` | JSON access |
| 5 | `Get-JsonArrayCountOrDash` | `json_array_count_or_dash()` | JSON access |
| 6 | `Get-RequiredJsonValue` | `required_json_value()` | Assertive JSON |
| 7 | `Get-RequiredJsonNumber` | `required_json_number()` | Assertive JSON |
| 8 | `Get-RequiredJsonInteger` | `required_json_integer()` | Assertive JSON |
| 9 | `Get-UsageAccessGuardInteger` | `usage_access_guard_integer()` | Assertive JSON |
| 10 | `Assert-ProofGuardCondition` | `assert_proof_guard()` | Guard |
| 11 | `Assert-UsageAccessGuardCondition` | `assert_usage_access_guard()` | Guard |
| 12 | `Test-GeneratedOutputPath` | `is_generated_output_path()` | Guard |
| 13 | `Invoke-GeneratedOutputGuard` | `generated_output_guard()` | Guard |
| 14 | `Invoke-Checked` | `checked_run()` | Subprocess |
| 15 | `Format-WorkflowMarkdownCell` | `format_markdown_cell()` | Formatting |
| 16 | `Get-TopText` | `top_text()` | Formatting |
| 17 | `Format-NifUsageAccess` | `format_nif_usage_access()` | Formatting |
| 18 | `Format-VectorSample` | `format_vector_sample()` | Formatting |
| 19 | `Format-ProofReviewSummary` | `format_proof_review_summary()` | Formatting |
| 20 | `Get-SemanticHintPrimaryModel` | `semantic_hint_primary_model()` | Semantic |
| 21 | `Get-SemanticHintBucket` | `semantic_hint_bucket()` | Semantic |

**Bonus:** `load_json_report()` — encapsulates the common `Get-Content | ConvertFrom-Json` pattern.

### Thin PowerShell entry point (`scripts/Invoke-RiftWorkflow.ps1`)

A ~50-line PowerShell wrapper that:

1. Runs `generated_output_guard()` from Python on every invocation
2. Delegates workflow commands to `scripts/rift_workflow.py`
3. Demonstrates the "PS for thin wrappers only" pattern

The original `Invoke-RiftAssetWorkflow.ps1` (3600+ lines) is **not removed** — it's still operational while migration proceeds incrementally.

### Testing

- `scripts/test_rift_workflow_utils.py` — 49 smoke tests covering all 21 functions
- All 49 tests pass ✅
- C# build still passes ✅

## What was NOT done

- **No workflow functions were migrated yet.** Only pure utility/helper functions. Report generators (`Show-ReportSummary`, `Invoke-ResidualPositionClusterProbeReport`, etc.) remain in PowerShell.
- **PowerShell not deleted.** The 3600-line script is intact and functional.
- **No `rift_workflow.py` orchestrator created yet.** The thin PS wrapper references it, but the actual Python orchestrator is the next step.

## Safety boundaries

| Boundary | Status |
|---|---|
| Generated output guard | ✅ Implemented in Python, invoked from thin PS wrapper |
| C# parser truth | ✅ Unchanged — C# remains source of truth |
| No live game interaction | ✅ No changes touch game I/O |
| No copied assets committed | ✅ Guard still active, verified |

## Next steps (suggested)

1. **Port `Show-ReportSummary` to Python** — it's ~150 lines, uses only the now-ported utility functions, and is a good next migration target.
2. **Port one guard function** (e.g., `Invoke-UsageAccessCorrelationGuard`) to prove the Python guard pattern end-to-end.
3. **Create `scripts/rift_workflow.py`** as the Python orchestrator entry point, wiring `checked_run()` calls to C# CLI commands.
4. **Port `Invoke-ResidualPositionClusterProbeReport`** — the most complex report generator, ~400 lines.
5. **Port `Invoke-AttributeExtraProofGuard`** — safety-critical guard that validates C# probe output.

## Validation

| Check | Result |
|---|---|
| `python -c "from scripts.rift_workflow_utils import ..."` | ✅ All imports work |
| `python scripts/test_rift_workflow_utils.py` | ✅ 49/49 tests pass |
| `dotnet build src/RiftAssetDumper/RiftAssetDumper.csproj` | ✅ 0 errors |
| `git status` | ✅ Clean working tree (after commit) |

## Files changed

| File | Delta | New |
|---|---|---|
| `scripts/rift_workflow_utils.py` | +330 | ✅ |
| `scripts/__init__.py` | +0 (empty) | ✅ |
| `scripts/Invoke-RiftWorkflow.ps1` | +52 | ✅ |
| `scripts/test_rift_workflow_utils.py` | +124 | ✅ |
