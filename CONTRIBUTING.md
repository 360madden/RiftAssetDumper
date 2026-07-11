# Contributing to RiftAssetDumper

Welcome. This is a **read-only** RIFT asset archive research workspace. Contributions are
welcome, but the project is intentionally conservative about state mutation, security, and
parser/diff behavior changes. Please review the rules below before opening a PR or pushing.

Project roadmap, durable plans, and ongoing lane state live under `docs/roadmap/`. Recent
session-by-session context lives under `docs/handoffs/`. The durable architecture summary
is in `knowledge.md`.

---

## Contribution path

1. Open a PR against `main` (or push to `main` if you have direct write access).
2. Wait for **all 5 leaf CI jobs** plus the **Summary** job to go green (6 GH checks total):

   | GH check job | What it runs |
   |---|---|
   | `.NET Build & Test` | `dotnet build`, `dotnet format --verify-no-changes`, `dotnet test` |
   | `Python Lint & Test` | `ruff check`, `mypy` (whole `scripts/`), every `scripts/test_*.py` |
   | `Docs Lint` | `markdownlint-cli2` over `docs/**/*.md` and `*.md` |
   | `Orphan Guard Regression` | `pytest` of orphan-process / no-spawn guards |
   | `Pre-commit Checks` | `pre-commit run --all-files` with `SKIP=gitleaks` (gitleaks needs repo-external Windows binary) |
   | `Summary` | Aggregated status; fails if any leaf is not `success` |

3. Merge with `gh pr merge --squash --delete-branch` once the PR is approved. Direct pushes
   to `main` are a documented fallback for solo work and AI agent runs.

If a CI job fails, the artifacts and logs under the failed job tell you which command
exited non-zero. Reproduce it locally with the matching command from the **CI jobs** section
below before pushing again.

---

## Development setup

Requires **Python 3.14**, **.NET SDK 9.0.x**, and a `pwsh`-compatible shell (Windows
PowerShell or PowerShell Core on Linux/macOS). The repo is Windows-first.

```
python -m venv .venv
.venv\Scripts\activate
python -m pip install ruff mypy pytest ijson jsonschema Pillow pefile
```

(Each name matches a `pip install` line already declared in `.github/workflows/ci.yml`.
The repo has no `[tool.setuptools]` packages config, so `pip install -e ".[dev]"` is
intentionally not used — install packages explicitly.)

Optional .NET build for the C# dumper:

```
dotnet build RiftAssetDumper.slnx --nologo
```

---

## Pre-commit hooks (local gate)

Install the hooks once after clone:

```
..\Tools\pre-commit\pre-commit.cmd install
```

Run all hooks manually against every file:

```
..\Tools\pre-commit\pre-commit.cmd run --all-files
```

The hooks that will run on each commit:

| Hook | What it does |
|---|---|
| `ruff` | Lints `scripts/` and `tests/` (`args: [--fix]`) |
| `ruff-format` | Formats `scripts/` and `tests/` |
| `mypy (scripts/)` | Runs `python -m mypy --no-error-summary scripts/` as a `system` hook |
| `gitleaks` | Scans staged files for path leaks and secrets (skipped in CI; needs repo-external Windows binary) |
| `markdownlint-cli2` | Lints all `.md` files via `.markdownlint.json` |
| `dotnet format` | Runs `dotnet format RiftAssetDumper.slnx --verify-no-changes` if `.cs` files staged |
| `generated-output-guard` | Blocks `Source/`, `Exports/`, `Extracted/`, `RecoveredNames/` from being committed |

> **Note:** The `mypy` hook uses `language: system` so it can see your activated `.venv`'s
> `mypy` and the `pyproject.toml` `pythonpath`. Run every commit from an activated venv, or
> the hook will fail to find `mypy` and the project's dependencies.

If a hook fails because it modified files (`ruff --fix`, `ruff-format`), re-stage and
re-commit; the default local flow is `pre-commit run --all-files` → review diff →
`git add -u` → `git commit`.

If a hook fails because it found a real problem, fix the underlying issue. Do not silence
hooks with `SKIP=` unless you have a specific documented exception.

---

## CI jobs (the GH Actions backstop)

### `.NET Build & Test` — `windows-latest`

- `dotnet build RiftAssetDumper.slnx --nologo`
- `dotnet format RiftAssetDumper.slnx --verify-no-changes`
- `dotnet test RiftAssetDumper.slnx --nologo` (xUnit, 56 tests)

Run `dotnet format` locally before pushing C# changes to avoid a one-revision lag.

### `Python Lint & Test` — `windows-latest`

- `ruff check scripts/`
- `mypy scripts/ --no-error-summary` (whole-package; honors `[tool.mypy.overrides]]` for `scripts.*`)
- For each `scripts/test_*.py`, run it as `python <file>`; non-zero exit aborts the step.

Reproduce locally:

```
ruff check scripts/
mypy scripts/ --no-error-summary
pytest tests/ -q    # optional, tests/ suite is ~1042
```

### `Docs Lint` — `ubuntu-latest`

- `markdownlint-cli2 docs/**/*.md *.md` against `.markdownlint.json`

Many rules are intentionally relaxed in the shared config (line length, heading increment,
table pipe style) to match the existing docs. Don't tighten them without checking that the
existing `docs/handoffs/INDEX.md` and recent handoffs still pass.

### `Orphan Guard Regression` — `windows-latest`

- `pytest tests/test_rift_workflow_orphan_guard.py tests/test_rift_workflow_orphan_guard_bypass.py tests/test_bulk_export_orphan_guard.py tests/test_rift_read_only_no_spawn.py -v`

Run when changing CLI entry points in `scripts/rift_workflow.py` or
`scripts/rift_read_only.py` to make sure no new command accidentally spawns a long-running
process outside the orphan guard.

### `Pre-commit Checks` — `windows-latest`

- Setup Python 3.14, .NET 9.0 SDK, cache pre-commit environments at
  `~/AppData/Local/pre-commit`
- Install `pre-commit` + dev dependencies
- Run `pre-commit run --all-files` with `SKIP: gitleaks`

If a hook modifies files in CI (e.g. `ruff-format` after you forgot to run it locally), the
step exits non-zero. Run `pre-commit run --all-files` locally, `git add -u`, and re-push.

---

## Repository conventions

- **C# coding style**: Allman braces, semi-colons required, `record`-based DTOs (never
  `class` for data containers). ID values are 16-char lowercase hex (`^[0-9a-f]{16}$`).
- **Python coding style**: `ruff` (lint + format) and `mypy` are the source of truth; see
  `.pre-commit-config.yaml` and `pyproject.toml`. Don't bypass them with `noqa`/`type: ignore`
  without a comment explaining why.
- **Tests**: `tests/pytest`-style tests live in `tests/`. Smoke-style unit tests live in
  `scripts/test_*.py` and run individually during CI; pytest also picks them up.
- **Commit prefixes**:

  | Prefix | Used for |
  |---|---|
  | `ft{N}.{M}: <title>` | Flythrough Bridge plan steps (e.g. `ft2.5:`) |
  | `docs: <title>` | Handoffs, README, schema, and other doc-only changes |
  | `fix: <title>` | Bug fixes (CI, parser, lint) |
  | `chore: <title>` | Tooling housekeeping (pre-commit, gitignore, ruff config) |
  | `feat: <title>` | New feature or schema |

- **Idempotence**: All scripts that touch disk must be safely re-runnable. Use `.state.json`
  files or atomic writes where re-runs are common.
- **Privacy**: Paths that include a Windows user-profile segment are redacted to
  `%USERPROFILE%\\...` or `C:\\Users\\%USERNAME%\\...` by the CLI by default. Don't paste
  unredacted local paths into issues or commits.

---

## Read-only mandate

The repo is read-only with respect to the live RIFT install at
`C:\Program Files (x86)\Glyph\Games\RIFT\Live`. Never modify, write to, or copy from the
live install write paths. The `extract-archives` family of commands accepts `--live-root`
for **read-only** fallback when an asset ID is missing from the copied `Source/` set; this
is the only sanctioned live-install interaction.

Never commit any of:

- `Source/` — local copied game files (gitignored)
- `Exports/` — generated inventories and reports (gitignored)
- `Extracted/` — extracted payload dumps (gitignored)
- `RecoveredNames/` — generated name matches (gitignored)
- `*.nif`, `*.dds`, `*.ogg`, screenshots, `rift_x64.exe`, `temp_analyze.py`, `*.bmp`
  (gitignored)

The `generated-output-guard` pre-commit hook will refuse to let you commit anything under
`Source/`, `Exports/`, `Extracted/`, or `RecoveredNames/`.

---

## What to read before changing the parser or a guard

- `docs/aggressive-discovery-workflow.md` — durable workflow
- `docs/task-routing-safety-policy.md` — when high reasoning is required
- `docs/handoffs/INDEX.md` — most recent handoffs per cycle/phase
- `docs/roadmap/current-phase.md` — what's open right now
- `knowledge.md` — durable architecture summary, conventions, and gotchas

If your change touches a proof guard, follow the existing pattern in
`scripts/rift_workflow_guards.py` and add a regression test in the matching `tests/`
file. If it touches a schema in `docs/schemas/`, the schema's `SchemaVersion` constant is
load-bearing — bump it on additive changes only.

---

## Asking for help

Open an issue with:

1. The exact command(s) you ran and the trimmed output (use `--privacy-scan` / redaction).
2. The relevant handoff or roadmap pointer if this is a continuation of prior work.
3. The CI run URL if the failure is in CI rather than locally.

For agent-driven work in this repo, see `AGENTS.md` and the `.agents/` directory for
custom agent type definitions and the model-routing strategy.

---

*End of contributing guide.*
