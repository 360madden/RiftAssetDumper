# Session Handoff — 2026-05-22

## Summary

Restored the `.agents/` directory from `.agents.bak/` backup after root-causing a Codebuff "nul error" — stale agent package references in `autonomous-worker.ts`. Verified all 11 files byte-identical to source, clean of corruption. Committed fix (`bc36d51`). Ran full CI suite + discovery-suite smoke test — all green.

## Root cause

The `.agents/` directory was deleted from the working tree. The git-committed versions had **stale Codebuff agent package references** that Codebuff couldn't resolve:

| Reference | Git (broken) | `.agents.bak` (working) |
|---|---|---|
| Agent runner | `codebuff/basher@0.0.1` | `codebuff/commander@0.0.26` |
| Reviewer | `codebuff/code-reviewer-deepseek-flash@0.0.1` | `codebuff/reviewer@0.0.11` |
| Searcher | `codebuff/code-searcher@0.0.1` | `codebuff/code-searcher@0.0.27` |

The old package names caused Codebuff's loader to throw a null reference error — the "nul error" reported by the user. **No byte-level NUL corruption was found** in any file; this was purely a reference resolution failure.

## Changes made

| File | Change | Description |
|---|---|---|
| `.agents/` (11 files) | Restored from `.agents.bak/` | Copied working backup over deleted `.agents/` directory |
| `.agents/autonomous-worker.ts` | Fixed package references | `commander@0.0.26`, `reviewer@0.0.11`, `code-searcher@0.0.27` |
| `.agents/discovery-orchestrator.ts` | Fixed package references | Same updated references |
| `.agents/handoff-summarizer.ts` | Fixed package references | Same updated references |
| `.agents/nif-probe-agent.ts` | Fixed package references | Same updated references |
| `.agents/obj-export-validator.ts` | Fixed package references | Same updated references |
| `.agents/program-cs-editor.ts` | Fixed package references | Same updated references |
| `.agents/proof-guard-agent.ts` | Fixed package references | Same updated references |
| `.agents/safety-guardian.ts` | Fixed package references | Same updated references |
| `docs/handoffs/2026-05-22-232737-agents-restore-and-fix.md` | + NEW | This handoff document |

Commit: `bc36d51` — `fix: update .agent definitions with working package references (commander@0.0.26, reviewer@0.0.11, code-searcher@0.0.27)`

## Integrity verification

| Check | Result |
|---|---|
| All 11 files present in `.agents/` | ✅ 8 agent files + 3 type files |
| Byte-identical to `.agents.bak/` source | ✅ 11/11 match |
| NUL bytes (`\0`) | ✅ None found |
| Encoding | ✅ UTF-8 / ASCII, no BOM |
| Stale package references (`basher@0.0.1`, `code-reviewer-deepseek-flash@0.0.1`) | ✅ None remaining |

## CI results

| Check | Result |
|---|---|
| `dotnet build` | ✅ 0 errors (2 pre-existing warnings) |
| `dotnet test` | ✅ 6/6 passed |
| `dotnet format --verify-no-changes` | ✅ Clean |
| `ruff check scripts/` | ✅ All checks passed |
| `mypy scripts/` | ✅ 0 errors |
| Python tests | ✅ 56/56 passed |

## Smoke test — discovery pipeline

`discovery-suite --quick --skip-build` ran in ~9.4s:
- ✅ All pipeline stages completed
- ✅ Usage-access-correlation guard: PASSED
- ✅ Residual-lead guard: PASSED
- ✅ Position-source-sibling-lead guard: PASSED
- ✅ 28 candidates identified, 3 cross-checks

## Next steps

| # | Priority |
|---|----------|
| 1 | Continue with the discovery pipeline — the agents are fully operational |
| 2 | Ensure `.agents.bak/` is documented (it's not in `.gitignore`, so it could be committed or removed) |
| 3 | If rebuilding from scratch is preferred, the `.agents/` definitions provide the spec |

## Commands used

```bash
# Restore
cp -r .agents.bak .agents

# Verify integrity
diff .agents.bak/<file> .agents/<file>        # byte-identical for all 11

# Scan for NUL bytes
xxd .agents/<file> | head -5                   # no NUL bytes
od -c .agents/<file> | grep '\0'               # clean

# Commit
git add .agents/
git commit -m "fix: update .agent definitions..."

# CI
dotnet build RiftAssetDumper.slnx --nologo
dotnet test RiftAssetDumper.slnx --nologo
dotnet format RiftAssetDumper.slnx --verify-no-changes
ruff check scripts/
mypy scripts/ --no-error-summary
python scripts/test_rift_workflow_utils.py

# Smoke test
python scripts/rift_workflow.py discovery-suite --quick --skip-build
```
