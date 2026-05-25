# 2026-05-25 CI runtime notes handoff

## Goal

Capture current non-failing GitHub Actions runtime warnings without mixing a CI migration into the Ghidra/NiDataStream proof lane.

## What changed

- Added `docs/ci-runtime-notes.md`.
- Documented the observed Node.js 20 JavaScript-action warning and `windows-latest` migration notice from current passing CI runs.
- Added a practical policy: do not update action majors from memory; verify official releases before a future isolated CI-only patch.

## Why it matters

The repo now records CI hygiene risks without derailing the active discovery workflow or making speculative action-version changes.

## Evidence / validation

Commands run for this docs-only slice:

```powershell
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

## Known blockers / limits

- This does not update `.github/workflows/ci.yml`.
- A future workflow change should verify current official GitHub Actions releases first.

## Generated-output handling

No generated outputs were created or staged.

## Next recommended actions

1. Leave current CI unchanged while green.
2. If warnings become failures or deadlines approach, perform a small CI-only action-version/runs-on update after checking official releases.
3. Keep Ghidra/NiDataStream workflow patches separate from CI migration patches.
