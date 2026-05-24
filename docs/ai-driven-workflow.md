# AI-driven workflow

This repo uses a Codex-first autonomous milestone loop for safe asset-discovery work.

## Default loop

1. Read `AGENTS.md`, `knowledge.md`, `docs/current-status.md`, and the newest handoff before changing direction.
2. Choose one bounded milestone with a concrete success condition.
3. Prefer durable repo workflow commands over one-off scripts.
4. Make the smallest coherent code/doc change needed for the milestone.
5. Run validation and generated-output safety checks.
6. Commit and push the coherent milestone after gates pass.
7. Write or update a handoff only when the milestone changes durable repo truth or resume context.

## Commit and push gate

Before staging, verify:

```powershell
git status --short
git diff --name-only
git diff --check
python scripts/rift_workflow.py generated-output-guard
```

For Python workflow changes, also run:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/rift_workflow_utils.py scripts/ghidra_runner.py scripts/test_rift_workflow_utils.py
python scripts/test_rift_workflow_utils.py
ruff check scripts/
mypy scripts/ --no-error-summary
```

For tool-registry or Ghidra workflow changes, also run:

```powershell
python scripts/rift_workflow.py tools-status
python scripts/rift_workflow.py ghidra-dry-run
```

Stage only the intended tracked files. Do not use broad staging such as `git add .` in this repo.

## Safety boundaries

Never stage or commit:

- `Source/`
- `Extracted/`
- `Exports/`
- `bin/`, `obj/`, `__pycache__/`, `*.pyc`
- `.env`
- `.aider.input.history`
- `.aider.chat.history.md`
- `.aider.llm.history`
- `.aider*.log`

Keep local Windows user-profile paths and account-like usernames out of tracked docs and chat summaries unless explicitly requested.

Use high/extra-high reasoning for asset truth, parser truth, proof guards, schemas, runtime/live-game work, Ghidra interpretation, exporter gates, commit review, and push decisions.

## Tool roles

### Codex

Codex is the primary driver for multi-step work:

- use `/goal` for multi-step milestones;
- keep each goal bounded and testable;
- continue autonomously through safe follow-up milestones when the lane is open;
- validate before every commit/push.

### Repo workflow commands

`scripts/rift_workflow.py` is the durable Python workflow surface. Add new recurring capabilities there before creating one-off helpers, unless the new helper needs a genuinely separate runtime surface.

### Ghidra

Ghidra is an explicit offline static-analysis support tool, not part of the default discovery suite.

Use it first for target-bound questions such as TWAD, NIF, or `NiDataStream` parser anchors. Keep generated projects under ignored `Exports/ghidra-projects/`. Treat findings as hypotheses until parser output and proof guards validate them.

### Aider

Aider is optional secondary tooling and must stay in its own lane until stabilized. Use diagnostics with `--no-gitignore`, `--no-check-update`, `--no-analytics`, and `--no-auto-commits` so it does not mutate repo policy or create commit noise.

Recommended no-call startup check:

```powershell
aider --exit --no-git --no-gitignore --no-check-update --no-analytics --no-auto-commits --model gemini/gemini-2.5-pro --weak-model gemini/gemini-2.5-flash --no-show-model-warnings
```

Do not commit Aider history, logs, environment files, or provider config.

## Current recommended next milestone

After the Ghidra workflow checks are committed, the next technical milestone is a no-broad-analysis Ghidra plan for `rift_x64.exe` that identifies static TWAD/NIF/`NiDataStream` parser anchors before any deeper decompilation or parser changes.
